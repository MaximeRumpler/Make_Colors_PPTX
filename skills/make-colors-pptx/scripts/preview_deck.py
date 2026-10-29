#!/usr/bin/env python3
"""Before/after preview: the same Make_Clean deck in neutral grey and with the brand theme.

    preview_deck.py --theme brand/brand.potx [--logo brand/logo.png] [--deck deck.json | --pptx deck.pptx]
                    [--out-dir build/colors-preview] [--make-clean DIR]

Needs the Make_Clean_PPTX skill (it builds and renders the decks). It is found with --make-clean,
the MAKE_CLEAN_PPTX_DIR variable, or next to this skill (skills/make-clean-pptx, ~/.claude/skills,
~/.agents/skills). Without --deck, a bundled six-slide sample deck shows every colour slot.

With --pptx, the deck already exists (made by Make_Clean, restyled by Make_Style_PPTX, or the
user's own): "before" is that file and "after" is a copy with the theme put on by apply_theme.py;
nothing is rebuilt and --logo is not used (a logo is placed when Make_Clean builds the deck).

Steps: build the deck twice (without and with "theme"/"logo"), run Make_Clean's lint on the
branded deck (overflow with the brand font, logo over text) with --contrast (every text against its
fill), render both decks (LibreOffice + poppler) and put the contact sheets one above the other in
before-after.png. Without LibreOffice the decks and the lint are still produced, and the JSON says
the render was skipped.

Prints JSON: decks, before_after (PNG or null), lint findings, theme warnings from the build.
Exit 0 when done (even with findings to fix), 3 when Make_Clean is not found, 2 when a build fails.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _colour import ThemeError  # noqa: E402
from apply_theme import apply  # noqa: E402
SAMPLE = SKILL_DIR / "assets" / "sample-deck.json"


def find_make_clean(explicit=None):
    candidates = [explicit, os.environ.get("MAKE_CLEAN_PPTX_DIR"), SKILL_DIR.parent / "make-clean-pptx",
                  Path.home() / ".claude" / "skills" / "make-clean-pptx",
                  Path.home() / ".agents" / "skills" / "make-clean-pptx"]
    for c in candidates:
        if not c:
            continue
        c = Path(c).expanduser()
        for d in (c, c / "skills" / "make-clean-pptx"):  # the skill folder or a clone of the repo
            if (d / "scripts" / "build_deck.py").is_file():
                return d.resolve()
    return None


def _run(cmd, cwd=None):
    p = subprocess.run([sys.executable] + [str(c) for c in cmd], cwd=cwd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    try:
        out = json.loads(p.stdout) if p.stdout.strip() else {}
    except ValueError:
        out = {"raw": p.stdout[-2000:]}
    return p.returncode, out, p.stderr[-2000:]


def _spec(deck: dict, base_dir: Path, out: Path, theme=None, logo=None, fallback=None) -> dict:
    spec = {k: v for k, v in deck.items() if not k.startswith("_") and k not in ("theme", "logo", "logo_alt",
                                                                                   "theme_fonts_fallback")}
    spec["output"] = str(out)
    if theme:
        spec["theme"] = str(Path(theme).resolve())
        if fallback:
            spec["theme_fonts_fallback"] = fallback
    if logo:
        spec["logo"] = str(Path(logo).resolve())
        spec["logo_alt"] = deck.get("logo_alt") or "Logo"
    # Relative image paths in the user's deck keep pointing next to their deck.json.
    for s in spec.get("slides", []):
        for k, v in list((s.get("fill") or {}).items()):
            is_file = isinstance(v, str) and v.lower().endswith((".png", ".jpg", ".jpeg", ".svg"))
            if is_file and not Path(v).is_absolute() and (base_dir / v).is_file():
                s["fill"][k] = str((base_dir / v).resolve())
    return spec


def side_by_side(before: Path, after: Path, out: Path) -> str:
    """The two contact sheets one above the other, each with its label."""
    from PIL import Image, ImageDraw, ImageFont
    a, b = Image.open(before).convert("RGB"), Image.open(after).convert("RGB")
    gap, label = 24, 40
    sheet = Image.new("RGB", (max(a.width, b.width) + gap * 2, a.height + b.height + label * 2 + gap * 2),
                      (236, 236, 236))
    sheet.paste(a, (gap, label))
    sheet.paste(b, (gap, a.height + label * 2 + gap))
    d = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 22)
    except OSError:
        try:
            font = ImageFont.load_default(22)
        except TypeError:  # Pillow < 10.1
            font = ImageFont.load_default()
    d.text((gap, 8), "Before", font=font, fill=(30, 30, 30))
    d.text((gap, a.height + label + gap + 8), "After (brand theme)", font=font, fill=(30, 30, 30))
    sheet.save(out)
    return str(out)


def preview(theme, logo=None, deck=None, out_dir="build/colors-preview", make_clean=None, fallback=None,
            render=True, pptx=None) -> dict:
    mc = find_make_clean(make_clean)
    if not mc:
        return {"error": "Make_Clean_PPTX not found: install it next to this skill, or pass --make-clean "
                         "<folder> (or set MAKE_CLEAN_PPTX_DIR)", "code": 3}
    out_dir = Path(out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    res = {"make_clean": str(mc), "decks": {}, "before_after": None, "theme_warnings": [], "lint": {}}
    if pptx:
        try:
            applied = apply(pptx, theme, out_dir / "after.pptx", fallback)
        except (ThemeError, OSError, ValueError) as exc:
            return {"error": "the theme could not be put on %s: %s" % (Path(pptx).name, exc), "code": 2}
        res["decks"] = {"before": str(Path(pptx).resolve()), "after": applied["output"]}
        res["theme_warnings"] = applied["findings"] + applied["notes"] + applied["font_notes"]
        res["theme_report"] = {k: applied[k] for k in ("theme", "fonts", "dark", "colour_map", "fixed_colours")}
        if logo:
            res["theme_warnings"].append("--logo is not used with --pptx: the logo is placed when Make_Clean builds")
    return _check_and_render(res, mc, out_dir, render) if pptx else _build(res, mc, out_dir, render, theme, logo,
                                                                          deck, fallback)


def _build(res, mc, out_dir, render, theme, logo, deck, fallback) -> dict:
    deck_path = Path(deck) if deck else SAMPLE
    data = json.loads(deck_path.read_text(encoding="utf-8"))
    for label, th, lg in (("before", None, None), ("after", theme, logo)):
        spec = _spec(data, deck_path.parent.resolve(), out_dir / ("%s.pptx" % label), th, lg, fallback)
        spec_path = out_dir / ("%s.json" % label)
        spec_path.write_text(json.dumps(spec, indent=1, ensure_ascii=False), encoding="utf-8")
        code, out, err = _run([mc / "scripts" / "build_deck.py", "--spec", spec_path], cwd=out_dir)
        if code != 0 or not (out_dir / ("%s.pptx" % label)).is_file():
            return {"error": "the %s deck did not build: %s" % (label, out.get("error") or err.strip()[-400:]),
                    "code": 2}
        res["decks"][label] = str(out_dir / ("%s.pptx" % label))
        if label == "after":
            res["theme_warnings"] = [w for w in out.get("warnings", []) if not w.startswith("spec: unknown key")]
            res["theme_report"] = out.get("theme")
    return _check_and_render(res, mc, out_dir, render)


def _check_and_render(res, mc, out_dir, render) -> dict:
    code, out, _ = _run([mc / "scripts" / "lint_deck.py", res["decks"]["after"], "--json", "--contrast"])
    res["lint"] = out
    if render:
        sheets = {}
        for label in ("before", "after"):
            code, out, err = _run([mc / "scripts" / "render_check.py", res["decks"][label],
                                   "--out-dir", out_dir / ("render-" + label)])
            if code != 0 or not out.get("contact_sheet"):
                res["render"] = "skipped: %s" % (out.get("error") or out.get("hint") or err.strip()[-300:]
                                                 or "LibreOffice or poppler missing")
                break
            sheets[label] = out["contact_sheet"]
        else:
            res["before_after"] = side_by_side(Path(sheets["before"]), Path(sheets["after"]),
                                               out_dir / "before-after.png")
            res["render"] = "done"
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--theme", required=True, help="the theme built by build_theme.py (.potx, .thmx)")
    ap.add_argument("--logo", help="logo file (PNG, JPG or SVG) for the covers and the closing slide")
    src = ap.add_mutually_exclusive_group()
    src.add_argument("--deck", help="a Make_Clean deck.json to preview (default: the bundled sample deck)")
    src.add_argument("--pptx", help="an existing .pptx (Make_Clean, Make_Style or other) to preview as it is")
    ap.add_argument("--out-dir", default="build/colors-preview")
    ap.add_argument("--make-clean", help="folder of the make-clean-pptx skill (or a clone of its repository)")
    ap.add_argument("--fonts-fallback", help='font used when the brand font is missing, e.g. "Arial"')
    ap.add_argument("--no-render", action="store_true", help="build and lint only")
    a = ap.parse_args(argv)
    res = preview(a.theme, a.logo, a.deck, a.out_dir, a.make_clean, a.fonts_fallback, not a.no_render, a.pptx)
    print(json.dumps(res, indent=1, ensure_ascii=False))
    return res.get("code", 0) if "error" in res else 0


if __name__ == "__main__":
    sys.exit(main())
