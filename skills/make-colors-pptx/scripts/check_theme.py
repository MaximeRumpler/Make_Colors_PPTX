#!/usr/bin/env python3
"""Check a theme: WCAG contrast of the pairs the Make_Clean layouts use, the accent ramp, fonts,
and how it reads in greyscale and with colour-vision deficiencies.

    check_theme.py brand.potx [--preview brand-check.png] [--json] [--contract PATH]

Accepts a theme (.thmx, theme .xml), a template or deck (.potx, .pptx: its own theme, so this is
also the review of an existing branded deck), or a Word/Excel file. Rules (references/colour-rules.md):
- text pairs need 4.5:1, large text and meaningful graphics 3:1 (WCAG 2.x);
- accent1..accent6 are one ramp from the text colour to the background, neighbours at least 1.1:1
  apart (the theme contract of Make_Clean_PPTX);
- the ramp must survive greyscale and the three colour-vision simulations (Machado et al. 2009):
  neighbouring accents keep at least the same 1.1:1 step there, since only lightness is left.

--preview writes a PNG: the theme drawn as a small slide (text, cards, ramp, chart, text on every
fill) in five views: normal, greyscale, protanopia, deuteranopia, tritanopia. Open it.
Exit code 0 when everything passes, 1 with findings, 2 when the file cannot be read.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _colour import (VIEWS, ThemeError, check_theme, font_note, load_contract, load_theme, ratio,  # noqa: E402
                     simulate, token)

SERIES = ("a1", "a3", "a5", "a2", "a4", "a6")  # Make_Clean's chart order: neighbours far apart on the ramp


def views_check(theme: dict, contract: dict) -> list:
    """Smallest neighbour step of the ramp in each simulated view."""
    step = contract.get("ramp", {}).get("min_step", 1.1)
    out = []
    acc = [token(theme, "a%d" % i, contract) for i in range(1, 7)]
    for v in VIEWS[1:]:
        sim = [simulate(c, v) for c in acc]
        worst = min(range(5), key=lambda i: ratio(sim[i], sim[i + 1]))
        r = ratio(sim[worst], sim[worst + 1])
        out.append({"view": v, "min_step": round(r, 2), "between": "accent%d/accent%d" % (worst + 1, worst + 2),
                    "ok": r >= step})
    return out


def run(path, contract=None) -> dict:
    contract = contract or load_contract()
    theme = load_theme(path)
    res = check_theme(theme, contract)
    res["views"] = views_check(theme, contract)
    for v in res["views"]:
        if not v["ok"]:
            res["findings"].append("in %s, %s are hard to tell apart (%.2f:1)" % (v["view"], v["between"],
                                                                                    v["min_step"]))
    res["fonts"] = theme["fonts"]
    res["font_notes"] = [n for n in {font_note(f) for f in theme["fonts"].values()} if n]
    res["name"] = theme["name"]
    res["colors"] = theme["colors"]
    res["ok"] = not res["findings"]
    return res


# ------------------------------------------------------------------ preview
def _font(size):
    from PIL import ImageFont
    for name in ("DejaVuSans.ttf", "Arial.ttf", "arial.ttf", "LiberationSans-Regular.ttf", "Helvetica.ttc"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size)
    except TypeError:  # Pillow < 10.1
        return ImageFont.load_default()


def _tile(theme, contract, view, w=420, h=330):
    """One view of the theme as a small slide."""
    from PIL import Image, ImageDraw

    def c(name):
        return tuple(int(round(x * 255)) for x in simulate(token(theme, name, contract), view))
    im = Image.new("RGB", (w, h), c("paper"))
    d = ImageDraw.Draw(im)
    big, mid, small = _font(22), _font(13), _font(11)
    d.text((16, 12), view.capitalize(), font=small, fill=c("muted"))
    d.text((16, 30), "Headline in ink", font=big, fill=c("ink"))
    d.text((16, 60), "Body text in ink2, caption in muted", font=mid, fill=c("ink2"))
    # card on surface
    d.rectangle((16, 84, w - 16, 128), fill=c("surface"))
    d.text((26, 90), "Card on surface", font=mid, fill=c("ink"))
    d.text((26, 108), "muted caption on surface", font=small, fill=c("muted"))
    # ramp with the text colour each fill carries
    sw = (w - 32) / 6
    for i in range(6):
        x0 = 16 + i * sw
        d.rectangle((x0, 140, x0 + sw - 4, 190), fill=c("a%d" % (i + 1)))
        on = "paper" if i < 2 else "ink"
        d.text((x0 + 6, 146), "a%d" % (i + 1), font=mid, fill=c(on))
        d.text((x0 + 6, 168), "Text", font=small, fill=c(on))
    # chart: columns in Make_Clean's series order
    base = h - 30
    heights = (100, 82, 70, 58, 46, 34)
    right = w - 160
    bw = (right - 16) / 6
    for i, (s, hh) in enumerate(zip(SERIES, heights)):
        x0 = 16 + i * bw
        d.rectangle((x0 + 3, base - hh, x0 + bw - 3, base), fill=c(s))
    d.line((16, base, right, base), fill=c("ink2"), width=1)
    d.text((16, base + 6), "Chart series a1 a3 a5 a2 a4 a6", font=small, fill=c("muted"))
    # dark panel: light accents as text on accent1 (used on dark slides)
    d.rectangle((right + 14, base - 100, w - 16, base), fill=c("a1"))
    for j, t in enumerate(("a3", "a4", "a5", "a6")):
        d.text((right + 26, base - 92 + j * 22), "%s on a1" % t, font=small, fill=c(t))
    return im


def preview(path, out, contract=None) -> str:
    from PIL import Image, ImageDraw
    contract = contract or load_contract()
    theme = load_theme(path)
    tiles = [_tile(theme, contract, v) for v in VIEWS]
    gap = 12
    w = sum(t.width for t in tiles[:3]) + gap * 4
    h = tiles[0].height * 2 + gap * 3 + 30
    sheet = Image.new("RGB", (w, h), (236, 236, 236))
    ImageDraw.Draw(sheet).text((gap, 8), "%s  (%s)" % (theme["name"] or Path(path).name, ", ".join(
        "%s %s" % (k, theme["fonts"][k]) for k in ("major", "minor"))), font=_font(14), fill=(30, 30, 30))
    for i, t in enumerate(tiles):
        x = gap + (i % 3) * (t.width + gap)
        y = 30 + gap + (i // 3) * (t.height + gap)
        sheet.paste(t, (x, y))
    # swatch legend in the last cell
    x0, y0 = gap + 2 * (tiles[0].width + gap), 30 + gap + tiles[0].height + gap
    d = ImageDraw.Draw(sheet)
    f = _font(12)
    for i, slot in enumerate(("dk1", "lt1", "dk2", "lt2", "accent1", "accent2", "accent3", "accent4", "accent5",
                              "accent6", "hlink", "folHlink")):
        y = y0 + 6 + i * 26
        hx = theme["colors"].get(slot, "000000")
        d.rectangle((x0, y, x0 + 40, y + 20), fill="#" + hx, outline=(150, 150, 150))
        d.text((x0 + 50, y + 3), "%-9s #%s" % (slot, hx), font=f, fill=(30, 30, 30))
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    return str(out)


def as_text(res: dict) -> str:
    lines = ["Theme %s: %s (%s)" % (res["name"] or "?", "passes" if res["ok"] else "%d finding(s)" % len(
        res["findings"]), "dark" if res["dark"] else "light")]
    lines.append("Ramp steps: " + "  ".join("%s>%s %.2f" % (r["from"][-1], r["to"][-1], r["ratio"])
                                            for r in res["ramp"]))
    weak = sorted(res["pairs"], key=lambda p: p["ratio"] / p["needs"])[:5]
    lines.append("Tightest pairs: " + "; ".join("%s%s on %s %.2f:1 (needs %.1f)" % (
        p["text"], "" if p["kind"] == "text" else " " + p["kind"], p["on"], p["ratio"], p["needs"]) for p in weak))
    lines.append("Views (smallest ramp step): " + "  ".join("%s %.2f" % (v["view"], v["min_step"])
                                                            for v in res["views"]))
    lines.append("Fonts: heading %s, body %s" % (res["fonts"]["major"], res["fonts"]["minor"]))
    lines += ["Finding: " + f for f in res["findings"]] + ["Font: " + n for n in res["font_notes"]]
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("theme", help=".potx, .pptx, .thmx, theme .xml, .docx or .xlsx")
    ap.add_argument("--preview", metavar="PNG", help="write the five-view preview image")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--contract", help="a newer theme-contract.json from Make_Clean_PPTX")
    a = ap.parse_args(argv)
    try:
        contract = load_contract(a.contract)
        res = run(a.theme, contract)
        if a.preview:
            res["preview"] = preview(a.theme, a.preview, contract)
    except (ThemeError, OSError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 2
    if a.json:
        print(json.dumps(res, indent=1, ensure_ascii=False))
    else:
        print(as_text(res) + ("\nPreview: %s" % res["preview"] if a.preview else ""))
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
