#!/usr/bin/env python3
"""Make a light version of a one-colour logo, for dark covers and dark themes (deck.json "logo_dark").

    logo_light.py brand/logo.png [--colour F5F5F5] [--out brand/logo-light.png]
    logo_light.py brand/logo.svg

PNG: the logo needs a transparent background; every visible pixel takes the light colour and keeps its
transparency (so soft edges stay soft). SVG: every fill and stroke colour becomes the light colour.
A logo with several colours (a symbol and a word in different colours, a gradient, a photo) is left alone:
recolouring it would change the brand, so the script says so and asks for the brand's own light version.
Prints a JSON report; exit code 0 written, 1 not a one-colour logo, 2 file problem.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _colour import ThemeError, delta_e, hex_to_rgb, parse_hex, rgb_to_hex  # noqa: E402

LIGHT = "F5F5F5"
ONE_COLOUR_SHARE = 0.9   # share of the visible pixels in the main colour (the rest is anti-aliasing)
SAME_COLOUR = 8.0        # CIE76 distance under which two colours count as one
NONE = {"none", "transparent", "inherit", "currentcolor"}


def logo_png(path: Path, colour: str, out: Path) -> dict:
    from PIL import Image
    with Image.open(path) as im:
        im.load()
        rgba = im.convert("RGBA")
    raw = rgba.tobytes()
    px = [tuple(raw[i:i + 4]) for i in range(0, len(raw), 4)]
    visible = [p for p in px if p[3] >= 128]
    if len(visible) < 0.02 * len(px) or len(visible) == len(px):
        return {"ok": False, "reason": "the logo has no transparent background: ask for a PNG with a transparent "
                                       "background, or for the brand's own light version"}
    counts = Counter((p[0] // 16, p[1] // 16, p[2] // 16) for p in visible)
    main = counts.most_common(1)[0][0]
    near = sum(n for k, n in counts.items()
               if delta_e(tuple((v * 16 + 8) / 255 for v in k), tuple((v * 16 + 8) / 255 for v in main)) < SAME_COLOUR * 2)
    share = near / len(visible)
    if share < ONE_COLOUR_SHARE:
        return {"ok": False, "reason": "the logo has several colours (%.0f%% in the main one): recolouring it would "
                                       "change the brand, ask for the brand's own light version" % (share * 100)}
    r, g, b = hex_to_rgb(colour)
    rgb = bytes((round(r * 255), round(g * 255), round(b * 255)))
    light = Image.frombytes("RGBA", rgba.size, b"".join(rgb + bytes((p[3],)) for p in px))
    out.parent.mkdir(parents=True, exist_ok=True)
    light.save(out)
    return {"ok": True, "colours": 1}


def logo_svg(path: Path, colour: str, out: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    found = set()

    def paint(value: str):
        v = value.strip().lower()
        if v in NONE or v.startswith("url("):
            return None
        return v

    pat = re.compile(r'(\b(?:fill|stroke)\s*[:=]\s*["\']?)(#[0-9a-fA-F]{3,8}|[a-zA-Z]+)(?=["\';\s/>])')
    for m in pat.finditer(text):
        if paint(m.group(2)):
            found.add(m.group(2).lower())
    if "gradient" in text.lower():
        return {"ok": False, "reason": "the logo uses a gradient: ask for the brand's own light version"}
    if len(found) > 1:
        hexes = [parse_hex(c) for c in found if c.startswith("#")]
        if len(hexes) != len(found) or any(delta_e(hex_to_rgb(a), hex_to_rgb(hexes[0])) > SAME_COLOUR for a in hexes):
            return {"ok": False, "reason": "the logo has several colours (%s): recolouring it would change the brand, "
                                           "ask for the brand's own light version" % ", ".join(sorted(found))}
    new = pat.sub(lambda m: m.group(1) + ("#" + colour if paint(m.group(2)) else m.group(2)), text)
    if not found:  # shapes with no colour are black by default
        new = re.sub(r"<svg\b", '<svg fill="#%s"' % colour, new, count=1)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(new, encoding="utf-8")
    return {"ok": True, "colours": max(1, len(found))}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("logo")
    ap.add_argument("--colour", default=LIGHT, help="the light colour (default F5F5F5)")
    ap.add_argument("--out", help="output file (default: <logo>-light next to it)")
    a = ap.parse_args(argv)
    path = Path(a.logo)
    try:
        colour = parse_hex(a.colour)
        if not path.is_file():
            raise ThemeError("not found: %s" % path)
        ext = path.suffix.lower()
        if ext not in (".png", ".svg"):
            raise ThemeError("%s: use a PNG with a transparent background or an SVG" % path.name)
        out = Path(a.out) if a.out else path.with_name(path.stem + "-light" + ext)
        res = (logo_png if ext == ".png" else logo_svg)(path, colour, out)
    except (ThemeError, ValueError, OSError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 2
    if not res["ok"]:
        print(json.dumps({"written": None, "reason": res["reason"]}, ensure_ascii=False, indent=1))
        return 1
    print(json.dumps({"written": str(out), "colour": "#" + colour, "use": {"logo_dark": str(out)}},
                     ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
