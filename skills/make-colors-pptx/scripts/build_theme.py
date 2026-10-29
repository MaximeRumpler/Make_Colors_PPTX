#!/usr/bin/env python3
"""Build a PowerPoint theme from the colour roles chosen with the user.

    build_theme.py roles.json [--out-dir brand/] [--thmx] [--contract PATH]

roles.json (see references/roles-reference.md):
    {"name": "Demo Harbour", "primary": "#1D4E89", "secondary": "#E07A1F",
     "fonts": {"major": "Georgia", "minor": "Arial"}}

Writes `<slug>.potx` (light) and `<slug>-dark.potx` (dark: dk1 stays dark, the master's colour map
swaps text and background, as Make_Clean_PPTX expects), plus `<slug>.thmx` (light, theme only) with
--thmx. Both files work in PowerPoint (Design > Browse for Themes, or open the template) and in
Make_Clean_PPTX's deck.json: "theme": "brand/<slug>.potx".

The six accents become one ramp of the primary hue, from strong to faint, with lightness solved so
every pair of the theme contract passes; the exact primary takes the ramp slot nearest to it when it
fits there. Prints a JSON report: files, slots, where the primary went, contract check, font notes.
Exit code 0 when every variant passes the contract, 1 when a variant still has findings (files are
written anyway), 2 when roles.json cannot be used.
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
import zipfile
from pathlib import Path

from lxml import etree

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _colour import (A, DARK_CLRMAP, NS, ThemeError, check_theme, font_note, hex_to_rgb, hls,  # noqa: E402
                     load_contract, luminance, parse_hex, ratio, rgb_to_hex, at_luminance)

P = "{%s}" % NS["p"]
CT_PRES = "application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"
CT_TMPL = "application/vnd.openxmlformats-officedocument.presentationml.template.main+xml"
CT_THEME = "application/vnd.openxmlformats-officedocument.theme+xml"

LIGHT_NEUTRALS = {"text": "111111", "background": "FFFFFF", "body": "404040", "surface": "F2F2F2"}
DARK_NEUTRALS = {"text": "F5F5F5", "background": "121212", "body": "D9D9D9", "surface": "262626"}
# Luminance of the neutral accents of Make_Clean_PPTX (light), and a mirrored set for dark themes.
LIGHT_TARGETS = (0.0137, 0.0999, 0.262, 0.451, 0.63, 0.79)
DARK_TARGETS = (0.78, 0.32, 0.135, 0.07, 0.03, 0.015)
MARGIN = 1.03  # aim a little above each threshold so 8-bit rounding never drops a pair below it


def f(y: float) -> float:
    return y + 0.05


def _clamp(v, lo, hi):
    return max(lo, min(hi, v)) if lo <= hi else (lo + hi) / 2


def solve_light(paper, ink, ink2, step=1.1):
    """Accent luminances for a light theme, given the luminance of paper, ink and ink2 (body text)."""
    t, m = LIGHT_TARGETS, MARGIN
    a3 = _clamp(t[2], 4.5 * m * f(ink) - 0.05, f(paper) / (3.0 * m) - 0.05)
    a1 = min(t[0], min(f(paper), f(a3)) / (4.5 * m) - 0.05)
    a2 = _clamp(t[1], f(a1) * step * m - 0.05, min(f(paper) / (4.5 * m), f(a3) / (step * m)) - 0.05)
    a5 = max(t[4], 4.5 * m * f(a2) - 0.05)
    a4 = _clamp(t[3], max(4.5 * m * f(ink2), f(a3) * step * m) - 0.05, f(a5) / (step * m) - 0.05)
    a6 = max(t[5], f(a5) * step * m - 0.05)
    return [max(0.0, a1), a2, a3, a4, a5, min(1.0, a6)]


def solve_dark(paper, ink, ink2, step=1.1):
    """Accent luminances for a dark theme (accent1 lightest): paper is dark, ink and ink2 are light."""
    t, m = DARK_TARGETS, MARGIN
    a3 = _clamp(t[2], 3.0 * m * f(paper) - 0.05, f(ink) / (4.5 * m) - 0.05)
    a1 = max(t[0], 4.5 * m * max(f(paper), f(a3)) - 0.05)
    a2 = _clamp(t[1], max(4.5 * m * f(paper), f(a3) * step * m) - 0.05, f(a1) / (step * m) - 0.05)
    a5 = min(t[4], f(a2) / (4.5 * m) - 0.05)
    a4 = _clamp(t[3], f(a5) * step * m - 0.05, min(f(a3) / (step * m), f(ink2) / (4.5 * m)) - 0.05)
    a6 = min(t[5], f(a5) / (step * m) - 0.05)
    return [min(1.0, a1), a2, a3, a4, a5, max(0.0, a6)]


def _tint(hexval, hue, amount):
    """The same luminance as `hexval`, with a touch of the brand hue (tinted neutrals)."""
    return rgb_to_hex(at_luminance(hue, amount, luminance(hex_to_rgb(hexval))))


def _ramp_hues(primary, secondary, drift):
    h, _, s = hls(hex_to_rgb(primary))
    if not (drift and secondary):
        return [h] * 6, s
    h2 = hls(hex_to_rgb(secondary))[0]
    d = (h2 - h + 0.5) % 1.0 - 0.5  # shortest way round the hue circle
    return [(h + d * i / 5) % 1.0 for i in range(6)], s


def make_variant(roles: dict, dark: bool, contract: dict) -> dict:
    """Colour slots of one variant: {"colors": {slot: hex}, "clrmap": dict or None, "notes": [...]}."""
    notes = []
    primary = parse_hex(roles["primary"])
    secondary = parse_hex(roles["secondary"]) if roles.get("secondary") else None
    hue = hls(hex_to_rgb(primary))[0]
    given = (roles.get("dark") if dark else roles.get("neutrals")) or {}
    neutrals = dict(DARK_NEUTRALS if dark else LIGHT_NEUTRALS)
    if roles.get("tint_neutrals"):
        neutrals = {k: _tint(v, hue, 0.18 if k in ("background", "surface") else 0.25) for k, v in neutrals.items()}
    neutrals.update({k: parse_hex(v) for k, v in given.items() if k in neutrals and v})
    lum = {k: luminance(hex_to_rgb(v)) for k, v in neutrals.items()}
    step = contract.get("ramp", {}).get("min_step", 1.1)

    accents_given = roles.get("dark_accents" if dark else "accents")
    if accents_given:
        accents = [parse_hex(c) for c in accents_given]
        if len(accents) != 6:
            raise ValueError("%s must list exactly six colours" % ("dark_accents" if dark else "accents"))
        placed = None
    else:
        targets = (solve_dark if dark else solve_light)(lum["background"], lum["text"], lum["body"], step)
        hues, s = _ramp_hues(primary, secondary, roles.get("ramp_drift"))
        accents = [rgb_to_hex(at_luminance(hues[i], s, targets[i])) for i in range(6)]
        placed = None
        # The exact primary replaces the nearest ramp slot when the whole theme still passes there.
        y = luminance(hex_to_rgb(primary))
        order = sorted(range(6), key=lambda i: abs(f(y) / f(targets[i]) - 1))
        for i in order:
            trial = accents[:i] + [primary] + accents[i + 1:]
            if check_theme(_theme(neutrals, trial, primary, dark, secondary), contract)["ok"]:
                accents, placed = trial, "accent%d" % (i + 1)
                break
        if placed:
            notes.append("primary %s kept exactly, on %s" % (primary, placed))
        else:
            nearest = order[0]
            notes.append("primary %s cannot sit on the ramp unchanged (%.1f:1 against %s): accent%d %s is the "
                         "nearest readable shade of the same hue" % (
                             primary, ratio(hex_to_rgb(primary), hex_to_rgb(neutrals["background"])),
                             "the background", nearest + 1, accents[nearest]))
    theme = _theme(neutrals, accents, primary, dark, secondary)
    if secondary and theme["colors"]["hlink"] != secondary:
        notes.append("secondary %s is too faint for links (4.5:1 on background and surface): links use %s" % (
            secondary, theme["colors"]["hlink"]))
    return {**theme, "notes": notes, "primary_slot": placed}


def _link_colour(neutrals, accents, secondary, dark):
    paper, surface = (hex_to_rgb(neutrals[k]) for k in ("background", "surface"))
    if secondary:
        c = hex_to_rgb(secondary)
        if min(ratio(c, paper), ratio(c, surface)) >= 4.5:
            return secondary
        h, _, s = hls(c)
        if dark:
            y = 4.5 * MARGIN * max(f(luminance(paper)), f(luminance(surface))) - 0.05
        else:
            y = min(f(luminance(paper)), f(luminance(surface))) / (4.5 * MARGIN) - 0.05
        return rgb_to_hex(at_luminance(h, s, y))
    return accents[1]


def _theme(neutrals, accents, primary, dark, secondary=None) -> dict:
    """Slot values of a variant. Dark: dk1 holds the dark background and the master swaps the map."""
    n = neutrals
    if dark:
        colors = {"dk1": n["background"], "lt1": n["text"], "dk2": n["surface"], "lt2": n["body"]}
    else:
        colors = {"dk1": n["text"], "lt1": n["background"], "dk2": n["body"], "lt2": n["surface"]}
    colors.update({"accent%d" % (i + 1): c for i, c in enumerate(accents)})
    colors["hlink"] = _link_colour(neutrals, accents, secondary, dark)
    colors["folHlink"] = accents[2]
    return {"colors": colors, "clrmap": dict(DARK_CLRMAP) if dark else None}


# ------------------------------------------------------------------ writing files
def _base_package() -> dict:
    """A 16:9 presentation from python-pptx's default template, as {part name: bytes}."""
    from pptx import Presentation
    from pptx.util import Inches
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    buf = io.BytesIO()
    prs.save(buf)
    with zipfile.ZipFile(buf) as z:
        return {n: z.read(n) for n in z.namelist()}


def theme_xml(base: bytes, name: str, colors: dict, fonts: dict) -> bytes:
    root = etree.fromstring(base)
    root.set("name", name)
    scheme = root.find(".//a:clrScheme", NS)
    scheme.set("name", name)
    for slot, hx in colors.items():
        el = scheme.find("a:" + slot, NS)
        for c in list(el):
            el.remove(c)
        etree.SubElement(el, A + "srgbClr", val=hx)
    fs = root.find(".//a:fontScheme", NS)
    fs.set("name", name)
    for key, tag in (("major", "majorFont"), ("minor", "minorFont")):
        fs.find("a:%s/a:latin" % tag, NS).set("typeface", fonts[key])
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


def write_potx(path: Path, name: str, theme: dict, fonts: dict, base: dict):
    parts = dict(base)
    parts["ppt/theme/theme1.xml"] = theme_xml(base["ppt/theme/theme1.xml"], name, theme["colors"], fonts)
    if theme.get("clrmap"):
        master = etree.fromstring(parts["ppt/slideMasters/slideMaster1.xml"])
        cm = master.find("p:clrMap", NS)
        for k, v in theme["clrmap"].items():
            cm.set(k, v)
        parts["ppt/slideMasters/slideMaster1.xml"] = etree.tostring(
            master, xml_declaration=True, encoding="UTF-8", standalone=True)
    parts["[Content_Types].xml"] = parts["[Content_Types].xml"].replace(CT_PRES.encode(), CT_TMPL.encode())
    core = parts.get("docProps/core.xml")
    if core:
        parts["docProps/core.xml"] = re.sub(rb"<dc:title>.*?</dc:title>|<dc:title/>",
                                            b"<dc:title>" + _esc(name) + b"</dc:title>", core)
    _zip(path, parts)


def write_thmx(path: Path, name: str, theme: dict, fonts: dict, base: dict):
    """Theme-only package: what Make_Clean_PPTX and Office read from a .thmx (no colour map, so light only)."""
    ct = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
          '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
          '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
          '<Default Extension="xml" ContentType="application/xml"/>'
          '<Override PartName="/theme/theme/theme1.xml" ContentType="%s"/></Types>' % CT_THEME)
    rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/'
            'theme" Target="theme/theme/theme1.xml"/></Relationships>')
    parts = {"[Content_Types].xml": ct.encode(), "_rels/.rels": rels.encode(),
             "theme/theme/theme1.xml": theme_xml(base["ppt/theme/theme1.xml"], name, theme["colors"], fonts)}
    _zip(path, parts)


def _esc(s: str) -> bytes:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").encode()


def _zip(path: Path, parts: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    order = ["[Content_Types].xml"] + sorted(n for n in parts if n != "[Content_Types].xml")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for n in order:
            info = zipfile.ZipInfo(n, date_time=(2026, 1, 1, 0, 0, 0))  # reproducible bytes
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, parts[n])


def slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s or "brand"


def build(roles: dict, out_dir: Path, thmx: bool = False, contract: dict | None = None) -> dict:
    contract = contract or load_contract()
    if not roles.get("primary"):
        raise ValueError("roles need at least a primary colour")
    name = str(roles.get("name") or "Brand").strip()
    fonts_in = roles.get("fonts") or {}
    fonts = {"major": fonts_in.get("major") or fonts_in.get("minor") or "Arial",
             "minor": fonts_in.get("minor") or fonts_in.get("major") or "Arial"}
    variants = roles.get("variants") or ["light", "dark"]
    base = _base_package()
    report = {"name": name, "fonts": fonts, "font_notes": [n for n in {font_note(v) for v in fonts.values()} if n],
              "variants": {}}
    for v in variants:
        if v not in ("light", "dark"):
            raise ValueError("variants can be 'light' and 'dark', not %r" % v)
        dark = v == "dark"
        theme = make_variant(roles, dark, contract)
        out = out_dir / ("%s%s.potx" % (slug(name), "-dark" if dark else ""))
        write_potx(out, name + (" Dark" if dark else ""), theme, fonts, base)
        files = [str(out)]
        if thmx and not dark:
            t = out_dir / ("%s.thmx" % slug(name))
            write_thmx(t, name, theme, fonts, base)
            files.append(str(t))
        check = check_theme(theme, contract)
        report["variants"][v] = {"files": files, "colors": theme["colors"], "clrmap": theme["clrmap"],
                                 "primary_slot": theme["primary_slot"], "notes": theme["notes"],
                                 "contract_ok": check["ok"], "findings": check["findings"]}
    first = next(iter(report["variants"].values()))
    fallback = {"theme_fonts_fallback": "Arial"} if report["font_notes"] else {}
    report["deck_json"] = {"theme": first["files"][0], **fallback}
    report["ok"] = all(x["contract_ok"] for x in report["variants"].values())
    return report


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("roles", help="roles.json written with the user (references/roles-reference.md)")
    ap.add_argument("--out-dir", default="brand", help="folder for the theme files (default: brand/)")
    ap.add_argument("--thmx", action="store_true", help="also write a theme-only .thmx (light variant)")
    ap.add_argument("--contract", help="a newer theme-contract.json from Make_Clean_PPTX")
    a = ap.parse_args(argv)
    try:
        roles = json.loads(Path(a.roles).read_text(encoding="utf-8"))
        report = build(roles, Path(a.out_dir), a.thmx, load_contract(a.contract))
    except (OSError, ValueError, KeyError, ThemeError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(report, indent=1, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
