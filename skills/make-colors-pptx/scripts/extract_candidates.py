#!/usr/bin/env python3
"""List the colour and font CANDIDATES found in brand material. It never decides the roles.

    extract_candidates.py FILE [FILE ...] [--json] [--top 12]

Reads, offline:
- PowerPoint, Word or Excel files and themes (.pptx .potx .thmx .docx .dotx .xlsx): the theme
  part (ppt/theme/theme1.xml and the like), the official source of the brand's colours and fonts;
- a stylesheet or a saved web page (.css .html .htm .svg): CSS custom properties (their names are
  strong hints, e.g. --brand-primary), colours by property and frequency, font families, the
  theme-color meta tag; local stylesheets linked from a saved page are read too, remote ones are
  only listed;
- an image or logo (.png .jpg .jpeg .gif .webp .bmp): the main colours by share of the visible
  pixels (Pillow palette quantisation, transparent pixels ignored);
- a PDF brand guide is not parsed: read it yourself (hex, RGB, CMYK and Pantone values, font names).

Web fonts that PowerPoint does not have get a suggested fallback. "brand_hues" lists up to four
candidates of clearly different hues (greys and shades of a hue already listed left out), in the
order found: the short list to propose a primary, a secondary and one or two others from. The agent proposes roles from
it with the user; nothing here says "first colour = primary".
"""
from __future__ import annotations

import argparse
import colorsys
import json
import math
import re
import sys
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _colour import (COMMON_FONTS, SLOTS, ThemeError, delta_e, describe, hex_to_rgb, luminance,  # noqa: E402
                     ratio, read_theme_xml, rgb_to_hex, theme_parts, to_lab)

OFFICE = {".pptx", ".potx", ".pptm", ".potm", ".thmx", ".docx", ".dotx", ".docm", ".xlsx", ".xltx", ".xlsm"}
WEB = {".css", ".html", ".htm", ".svg", ".scss", ".less"}
IMAGES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tif", ".tiff"}

# Web font -> a font PowerPoint has on Windows and macOS with a close look. Used only as a suggestion.
FONT_FALLBACK = {
    "inter": "Segoe UI", "roboto": "Arial", "open sans": "Segoe UI", "lato": "Calibri", "montserrat": "Century Gothic",
    "poppins": "Century Gothic", "raleway": "Century Gothic", "nunito": "Calibri", "nunito sans": "Calibri",
    "source sans pro": "Calibri", "source sans 3": "Calibri", "work sans": "Segoe UI", "ibm plex sans": "Arial",
    "noto sans": "Arial", "pt sans": "Calibri", "ubuntu": "Segoe UI", "fira sans": "Calibri", "dm sans": "Segoe UI",
    "manrope": "Segoe UI", "outfit": "Century Gothic", "barlow": "Arial Narrow", "oswald": "Arial Narrow",
    "playfair display": "Georgia", "merriweather": "Georgia", "lora": "Georgia", "pt serif": "Georgia",
    "libre baskerville": "Book Antiqua", "eb garamond": "Garamond", "cormorant garamond": "Garamond",
    "roboto slab": "Rockwell", "source serif pro": "Georgia", "noto serif": "Georgia",
    "roboto mono": "Consolas", "fira code": "Consolas", "jetbrains mono": "Consolas", "source code pro": "Consolas",
    "sans-serif": "Arial", "serif": "Georgia", "monospace": "Consolas", "system-ui": "Segoe UI",
    "-apple-system": "Segoe UI", "blinkmacsystemfont": "Segoe UI", "ui-sans-serif": "Arial",
}
GENERIC = {"sans-serif", "serif", "monospace", "system-ui", "-apple-system", "blinkmacsystemfont", "ui-sans-serif",
           "ui-serif", "ui-monospace", "cursive", "fantasy", "emoji", "inherit", "initial", "unset", "var"}
NAMED = {"white": "FFFFFF", "black": "000000", "red": "FF0000", "navy": "000080", "blue": "0000FF",
         "teal": "008080", "green": "008000", "orange": "FFA500", "gold": "FFD700", "purple": "800080",
         "gray": "808080", "grey": "808080", "silver": "C0C0C0", "maroon": "800000", "crimson": "DC143C",
         "tomato": "FF6347", "coral": "FF7F50", "indigo": "4B0082", "olive": "808000"}

COLOR_RE = re.compile(
    r"#(?P<hex>[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3,4})\b"
    r"|(?P<fn>rgba?|hsla?)\(\s*(?P<args>[^)]*)\)", re.I)


# ------------------------------------------------------------------ colour parsing
def css_colour(text: str):
    """Hex of the first CSS colour in `text` (hex, rgb(), hsl(), a few names), or None. Transparent -> None."""
    m = COLOR_RE.search(text)
    if not m:
        name = text.strip().lower()
        return NAMED.get(name)
    if m.group("hex"):
        h = m.group("hex")
        if len(h) in (3, 4):
            if len(h) == 4 and h[3] in "0":
                return None
            h = "".join(c * 2 for c in h[:3])
        elif len(h) == 8:
            if int(h[6:], 16) < 128:
                return None
            h = h[:6]
        return h.upper()
    parts = [p for p in re.split(r"[\s,/]+", m.group("args").strip()) if p]
    if len(parts) < 3:
        return None
    if len(parts) > 3:
        a = parts[3]
        alpha = float(a[:-1]) / 100 if a.endswith("%") else float(a)
        if alpha < 0.5:
            return None
    try:
        if m.group("fn").lower().startswith("rgb"):
            vals = [float(p[:-1]) * 2.55 if p.endswith("%") else float(p) for p in parts[:3]]
            return rgb_to_hex([v / 255 for v in vals])
        hue = float(re.sub(r"deg$", "", parts[0])) / 360
        s, lum = (float(p.rstrip("%")) / 100 for p in parts[1:3])
        return rgb_to_hex(colorsys.hls_to_rgb(hue % 1.0, lum, s))
    except ValueError:
        return None


class Pool:
    """Collects colours with where they came from, merging near-identical ones."""

    def __init__(self):
        self.items = {}  # hex -> {"count", "share", "sources": Counter}

    def add(self, hx, source, weight=1.0, share=None):
        if not hx:
            return
        hx = hx.upper()
        it = self.items.setdefault(hx, {"count": 0.0, "share": 0.0, "sources": Counter()})
        it["count"] += weight
        if share:
            it["share"] += share
        it["sources"][source] += 1

    def candidates(self, top: int, merge: float = 4.0) -> list:
        ranked = sorted(self.items.items(), key=lambda kv: (-kv[1]["share"], -kv[1]["count"], kv[0]))
        kept = []
        for hx, it in ranked:
            rgb = hex_to_rgb(hx)
            twin = next((k for k in kept if delta_e(hex_to_rgb(k["hex"]), rgb) < merge), None)
            if twin:
                twin["count"] += it["count"]
                twin["share"] += it["share"]
                twin["sources"].update(it["sources"])
                continue
            kept.append({"hex": hx, "count": it["count"], "share": it["share"], "sources": Counter(it["sources"])})
        out = []
        for k in kept[:top]:
            rgb = hex_to_rgb(k["hex"])
            sat = colorsys.rgb_to_hls(*rgb)[2]
            out.append({
                "hex": "#" + k["hex"], "name": describe(rgb),
                "neutral": sat < 0.12 or describe(rgb) in ("black", "white", "grey", "dark grey", "light grey",
                                                           "very dark grey"),
                "luminance": round(luminance(rgb), 3),
                "on_white": round(ratio(rgb, (1, 1, 1)), 2), "on_black": round(ratio(rgb, (0, 0, 0)), 2),
                "count": round(k["count"], 1), **({"share": round(k["share"], 3)} if k["share"] else {}),
                "sources": [s for s, _ in k["sources"].most_common(4)],
            })
        return out


# ------------------------------------------------------------------ readers
def read_office(path: Path, pool: Pool, fonts: dict, notes: list):
    try:
        z = zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError) as exc:
        raise ThemeError("%s cannot be opened as an Office file" % path.name) from exc
    with z:
        parts = theme_parts(z)
        if not parts:
            notes.append("%s has no theme part" % path.name)
            return
        for i, part in enumerate(parts):
            th = read_theme_xml(z.read(part))
            label = "theme" if i == 0 else "theme %d" % (i + 1)
            for slot in SLOTS:
                if slot in th["colors"]:
                    pool.add(th["colors"][slot], "%s %s (%s)" % (label, slot, th["name"] or part), 10 if i == 0 else 3)
            for role in ("major", "minor"):
                if th["fonts"].get(role):
                    fonts[th["fonts"][role]].add("%s %s font" % (label, "heading" if role == "major" else "body"))
        if len(parts) > 1:
            notes.append("%s has %d themes; the first is the one its slide master uses" % (path.name, len(parts)))


def _strip_comments(css: str) -> str:
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def read_css(css: str, origin: str, pool: Pool, fonts: dict, variables: dict):
    css = _strip_comments(css)
    for name, value in re.findall(r"(--[\w-]+)\s*:\s*([^;}{]+)", css):
        variables[name] = value.strip()
    for name, value in variables.items():
        hx = css_colour(_resolve(value, variables))
        if hx:
            pool.add(hx, "var %s" % name, 3)
    for prop, value in re.findall(r"(?<![\w-])([a-z-]+)\s*:\s*([^;}{]+)", css):
        if prop.startswith("--"):
            continue
        value = _resolve(value, variables)
        if prop in ("font-family", "font"):
            fam = value if prop == "font-family" else (re.split(r"\d+(?:px|pt|rem|em|%)\s*(?:/\s*\S+\s*)?", value)
                                                      + [""])[-1]
            for family in fam.split(","):
                family = family.strip().strip("'\"")
                if family and family.lower() not in GENERIC and not family.startswith("var("):
                    fonts[family].add("%s font-family" % origin)
            continue
        for m in COLOR_RE.finditer(value):
            pool.add(css_colour(m.group(0)), prop, 1)
        if prop in ("color", "background", "background-color", "fill", "stroke", "border-color"):
            word = value.strip().lower()
            if word in NAMED:
                pool.add(NAMED[word], prop, 1)
    for fam in re.findall(r"@font-face\s*{[^}]*font-family\s*:\s*['\"]?([^;'\"}]+)", css):
        fonts[fam.strip()].add("%s @font-face" % origin)


def _resolve(value: str, variables: dict, depth: int = 0) -> str:
    if depth > 5 or "var(" not in value:
        return value

    def sub(m):
        name, _, default = m.group(1).partition(",")
        return variables.get(name.strip(), default.strip())
    return _resolve(re.sub(r"var\(\s*([^()]*)\)", sub, value), variables, depth + 1)


def read_web(path: Path, pool: Pool, fonts: dict, notes: list):
    text = path.read_text(encoding="utf-8", errors="replace")
    variables = {}
    if path.suffix.lower() in (".html", ".htm"):
        for m in re.finditer(r"<meta[^>]+name=[\"']theme-color[\"'][^>]*>", text, re.I):
            c = re.search(r"content=[\"']([^\"']+)", m.group(0))
            if c:
                pool.add(css_colour(c.group(1)), "meta theme-color", 5)
        for href in re.findall(r"<link[^>]+rel=[\"']?stylesheet[^>]*>", text, re.I):
            h = re.search(r"href=[\"']([^\"']+)", href)
            if not h:
                continue
            target = h.group(1)
            if re.match(r"^(https?:)?//", target):
                gf = re.findall(r"family=([^&:]+)", target) if "fonts.googleapis" in target else []
                for fam in gf:
                    fonts[fam.replace("+", " ")].add("Google Fonts link")
                if not gf:
                    notes.append("remote stylesheet not fetched (offline): %s" % target)
                continue
            local = (path.parent / target.split("?")[0]).resolve()
            if local.is_file():
                read_css(local.read_text(encoding="utf-8", errors="replace"), local.name, pool, fonts, variables)
            else:
                notes.append("linked stylesheet not found next to the page: %s" % target)
        blocks = re.findall(r"<style[^>]*>(.*?)</style>", text, re.S | re.I)
        inline = re.findall(r"style=\"([^\"]*)\"", text, re.I)
        read_css("\n".join(blocks) + "\n" + "\n".join("x{%s}" % s for s in inline), path.name, pool, fonts, variables)
    elif path.suffix.lower() == ".svg":
        for attr, value in re.findall(r"\b(fill|stroke|stop-color)=[\"']([^\"']+)", text):
            pool.add(css_colour(value), "svg " + attr, 1)
        read_css("\n".join(re.findall(r"<style[^>]*>(.*?)</style>", text, re.S)) + "\n" +
                 "\n".join("x{%s}" % s for s in re.findall(r"style=\"([^\"]*)\"", text)), path.name, pool, fonts,
                 variables)
    else:
        read_css(text, path.name, pool, fonts, variables)


def read_image(path: Path, pool: Pool, notes: list, colours: int = 10):
    from PIL import Image
    with Image.open(path) as im:
        im.load()
        rgba = im.convert("RGBA")
    rgba.thumbnail((400, 400))
    raw = rgba.tobytes()
    px = [raw[i:i + 4] for i in range(0, len(raw), 4)]
    visible = [tuple(p[:3]) for p in px if p[3] >= 128]
    if not visible:
        notes.append("%s is fully transparent" % path.name)
        return
    if len(visible) < len(px):
        notes.append("%s: transparent background ignored" % path.name)
    flat = Image.new("RGB", (len(visible), 1))
    flat.putdata(visible)
    q = flat.quantize(colors=colours, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    pal = q.getpalette()
    total = len(visible)
    for count, idx in sorted(q.getcolors(), reverse=True):
        rgb = tuple(pal[idx * 3 + i] / 255 for i in range(3))
        pool.add(rgb_to_hex(rgb), "image %s" % path.name, count, share=count / total)


def _hue_angle(hexval: str) -> float:
    _, a, b = to_lab(hex_to_rgb(hexval))
    return math.degrees(math.atan2(b, a)) % 360


def brand_hues(colours: list, most: int = 4, apart: float = 25.0) -> list:
    """Up to `most` non-neutral candidates whose hues differ by at least `apart` degrees (CIE LCh), in the
    order found: lighter or darker shades of a hue already kept are left out."""
    kept = []
    for c in colours:
        if c["neutral"]:
            continue
        h = _hue_angle(c["hex"])
        if any(min(abs(h - k), 360 - abs(h - k)) < apart for k in map(_hue_angle, kept)):
            continue
        kept.append(c["hex"])
        if len(kept) == most:
            break
    return kept


def fallback_for(font: str) -> str:
    if font.lower() in COMMON_FONTS:
        return ""
    return FONT_FALLBACK.get(font.lower(), "Arial")


def extract(paths, top: int = 12) -> dict:
    pool, fonts, notes, read = Pool(), defaultdict(set), [], []
    for p in map(Path, paths):
        ext = p.suffix.lower()
        if not p.is_file():
            notes.append("not found: %s" % p)
            continue
        if ext in OFFICE:
            read_office(p, pool, fonts, notes)
        elif ext in WEB:
            read_web(p, pool, fonts, notes)
        elif ext in IMAGES:
            read_image(p, pool, notes)
        elif ext == ".pdf":
            notes.append("%s: PDF brand guides are not parsed; read it yourself for hex, RGB, CMYK or Pantone "
                         "values and font names, and ask the user which are primary" % p.name)
            continue
        else:
            notes.append("%s: unsupported file type %s" % (p.name, ext))
            continue
        read.append(str(p))
    font_list = [{"font": f, "sources": sorted(s)[:4], "common": f.lower() in COMMON_FONTS,
                  **({"fallback": fallback_for(f)} if fallback_for(f) else {})}
                 for f, s in sorted(fonts.items(), key=lambda kv: (-len(kv[1]), kv[0].lower()))]
    colours = pool.candidates(top)
    return {"read": read, "colours": colours, "brand_hues": brand_hues(colours), "fonts": font_list,
            "notes": notes}


def as_text(res: dict) -> str:
    lines = ["Colour candidates (not roles: choose them with the user)"]
    for c in res["colours"]:
        share = (" %4.1f%%" % (100 * c["share"])) if c.get("share") else ""
        lines.append("  %s  %-16s%s  on white %5.2f:1  on black %5.2f:1%s  <- %s" % (
            c["hex"], c["name"], share, c["on_white"], c["on_black"], "  (neutral)" if c["neutral"] else "",
            "; ".join(c["sources"])))
    if res.get("brand_hues"):
        names = {c["hex"]: c["name"] for c in res["colours"]}
        lines.append("Distinct brand hues: " + ", ".join("%s %s" % (h, names[h]) for h in res["brand_hues"]))
    if res["fonts"]:
        lines.append("Fonts")
        for f in res["fonts"]:
            fb = "" if f["common"] else "  not in PowerPoint by default, fallback: %s" % f.get("fallback")
            lines.append("  %s%s  <- %s" % (f["font"], fb, "; ".join(f["sources"])))
    for n in res["notes"]:
        lines.append("Note: " + n)
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--top", type=int, default=12, help="how many colours to list (default 12)")
    a = ap.parse_args(argv)
    try:
        res = extract(a.files, a.top)
    except (ThemeError, OSError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(res, indent=1, ensure_ascii=False) if a.json else as_text(res))
    return 0 if res["read"] else 2


if __name__ == "__main__":
    sys.exit(main())
