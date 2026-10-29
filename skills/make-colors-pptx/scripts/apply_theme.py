#!/usr/bin/env python3
"""Put a brand theme on a deck that already exists, without rebuilding it.

    apply_theme.py deck.pptx --theme brand/brand.potx [--out deck-brand.pptx] [--fonts-fallback Arial]

For any .pptx or .potx: a Make_Clean_PPTX deck, the same deck restyled by Make_Style_PPTX, or the
user's own file. Like Make_Clean's "theme" key: the colour scheme, the font scheme and the theme name
of every slide master's theme are replaced, and the source master's colour map is applied when the
theme file has one (dark variant). Slides, shapes, shape names (Make_Style's role tags), pictures
and notes are copied byte for byte. The input file is never overwritten.

--fonts-fallback replaces a brand font that is not a standard Windows/macOS/Office font.

Prints JSON: output file, fonts, dark or light, the contract check of the result (same rules as
check_theme.py), and how many fixed colours the slides use (the theme cannot change those: a deck
made with Make_Clean has none). Exit 0 when the result passes, 1 with findings, 2 on an error.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from copy import deepcopy
from pathlib import Path

from lxml import etree

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _colour import (COMMON_FONTS, DEFAULT_CLRMAP, NS, ThemeError, _rels, check_theme, font_note,  # noqa: E402
                     load_contract, read_theme_xml, theme_parts, view_findings, views_check)

P = "{%s}" % NS["p"]
CLRMAP_KEYS = tuple(DEFAULT_CLRMAP)
MASTER_RE = re.compile(r"^ppt/slideMasters/slideMaster\d+\.xml$")


def _open(path: Path) -> zipfile.ZipFile:
    try:
        return zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError) as exc:
        raise ThemeError("%s cannot be opened as an Office file (damaged, or another format?)" % path.name) from exc


def read_source(path) -> dict:
    """{"root": a:theme element, "clrmap": dict or None} of a .potx, .pptx, .thmx or theme .xml."""
    path = Path(path)
    if not path.is_file():
        raise ThemeError("theme file not found: %s" % path)
    if path.suffix.lower() == ".xml":
        return {"root": etree.fromstring(path.read_bytes()), "clrmap": None}
    with _open(path) as z:
        parts = theme_parts(z)
        if not parts:
            raise ThemeError("%s contains no theme" % path.name)
        root = etree.fromstring(z.read(parts[0]))
        clrmap = None
        masters = sorted(n for n in z.namelist() if MASTER_RE.match(n))
        if masters:
            cm = etree.fromstring(z.read(masters[0])).find("p:clrMap", NS)
            if cm is not None and set(CLRMAP_KEYS) <= set(cm.attrib):
                clrmap = {k: cm.get(k) for k in CLRMAP_KEYS}
    read_theme_xml(etree.tostring(root))  # raises a plain error when it is not a theme
    return {"root": root, "clrmap": clrmap}


def _xml(el) -> bytes:
    return etree.tostring(el, xml_declaration=True, encoding="UTF-8", standalone=True)


def _new_theme(old: bytes, src, fonts: dict, name: str) -> bytes:
    root = etree.fromstring(old)
    elements = root.find("a:themeElements", NS)
    elements.replace(elements.find("a:clrScheme", NS), deepcopy(src.find("a:themeElements/a:clrScheme", NS)))
    src_fonts = src.find("a:themeElements/a:fontScheme", NS)
    if src_fonts is not None:
        new = deepcopy(src_fonts)
        for role, face in fonts.items():
            lat = new.find("a:%sFont/a:latin" % role, NS)
            if lat is not None and lat.get("typeface") != face:
                lat.set("typeface", face)
                for attr in ("panose", "pitchFamily", "charset"):  # they describe the replaced font
                    lat.attrib.pop(attr, None)
        elements.replace(elements.find("a:fontScheme", NS), new)
    root.set("name", name)
    return _xml(root)


def apply(deck, theme, out=None, fallback=None, contract=None) -> dict:
    deck, theme = Path(deck), Path(theme)
    if not deck.is_file():
        raise ThemeError("deck not found: %s" % deck)
    out = Path(out) if out else deck.with_name("%s-%s%s" % (deck.stem, re.sub(r"[^a-z0-9]+", "-",
                                                                             theme.stem.lower()).strip("-"),
                                                            deck.suffix))
    if out.resolve() == deck.resolve():
        raise ThemeError("the output would overwrite the input deck: choose another --out")
    src = read_source(theme)
    info = read_theme_xml(_xml(src["root"]))
    name = info["name"] or theme.stem
    fonts, notes = {}, []
    for role in ("major", "minor"):
        face = info["fonts"].get(role) or "Arial"
        if fallback and face.lower() not in COMMON_FONTS:
            notes.append("font %s replaced by the fallback %s" % (face, fallback))
            face = fallback
        fonts[role] = face
    with _open(deck) as z:
        names = z.namelist()
        masters = [n for n in names if MASTER_RE.match(n)]
        if not masters:
            raise ThemeError("%s has no slide master: is it a PowerPoint deck?" % deck.name)
        themes = sorted({t for m in masters for t in [_rels(z, m).get("theme")] if t in names})
        changed = {t: _new_theme(z.read(t), src["root"], fonts, name) for t in themes}
        if src["clrmap"]:
            for m in masters:
                root = etree.fromstring(z.read(m))
                cm = root.find("p:clrMap", NS)
                if cm is None:
                    continue
                for k in list(cm.attrib):
                    del cm.attrib[k]
                for k in CLRMAP_KEYS:
                    cm.set(k, src["clrmap"][k])
                changed[m] = _xml(root)
        slides = [n for n in names if re.match(r"^ppt/slides/slide\d+\.xml$", n)]
        fixed = {n: len(re.findall(rb"<a:srgbClr\b", z.read(n))) for n in slides}
        out.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as w:
            for item in z.infolist():
                data = changed.get(item.filename)
                w.writestr(item, data if data is not None else z.read(item.filename))
    # check the result as PowerPoint will read it: first master's theme and colour map
    with _open(out) as z:
        first = sorted(masters, key=lambda n: int(re.search(r"(\d+)\.xml$", n).group(1)))[0]
        result = read_theme_xml(z.read(_rels(z, first)["theme"]))
        cm = etree.fromstring(z.read(first)).find("p:clrMap", NS)
        result["clrmap"] = dict(cm.attrib) if cm is not None else None
    contract = contract or load_contract()
    check = check_theme(result, contract)
    findings = check["findings"] + (view_findings(views_check(result, contract)) if check["ramp"] else [])
    n_fixed = sum(fixed.values())
    if n_fixed:
        notes.append("%d fixed colours on %d of %d slides do not follow the theme: they keep their colour" % (
            n_fixed, sum(1 for v in fixed.values() if v), len(slides)))
    return {"deck": str(deck), "output": str(out), "theme": name, "fonts": fonts,
            "font_notes": [n for n in {font_note(f) for f in fonts.values()} if n],
            "dark": check["dark"], "colour_map": "from the theme" if src["clrmap"] else "kept",
            "masters": len(masters), "fixed_colours": n_fixed, "notes": notes,
            "ok": not findings, "findings": findings}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("deck", help="the .pptx or .potx to brand (never overwritten)")
    ap.add_argument("--theme", required=True, help="the theme built by build_theme.py (.potx, .thmx)")
    ap.add_argument("--out", help="output file (default: <deck>-<theme>.pptx next to the deck)")
    ap.add_argument("--fonts-fallback", help='font used instead of a brand font that is not common, e.g. "Arial"')
    ap.add_argument("--contract", help="a newer theme-contract.json from Make_Clean_PPTX")
    a = ap.parse_args(argv)
    try:
        res = apply(a.deck, a.theme, a.out, a.fonts_fallback, load_contract(a.contract))
    except (ThemeError, OSError, ValueError, KeyError, etree.XMLSyntaxError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(res, indent=1, ensure_ascii=False))
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
