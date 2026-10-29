"""Colour maths, PowerPoint theme reading and the theme contract check, shared by the scripts.

Standard library + lxml (comes with python-pptx). Every colour is an (r, g, b) tuple of floats 0..1
in sRGB, or a "RRGGBB" string when shown to people.

The contract (assets/theme-contract.json) is a copy of the one Make_Clean_PPTX generates from its
libraries; `--contract` on the scripts points to a newer copy if needed.
"""
from __future__ import annotations

import colorsys
import json
import math
import os
import re
import zipfile
from pathlib import Path, PurePosixPath

from lxml import etree

SKILL_DIR = Path(__file__).resolve().parent.parent
CONTRACT = SKILL_DIR / "assets" / "theme-contract.json"

NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
}
A = "{%s}" % NS["a"]
PKG_REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"

SLOTS = ("dk1", "lt1", "dk2", "lt2", "accent1", "accent2", "accent3", "accent4", "accent5", "accent6",
         "hlink", "folHlink")
DEFAULT_CLRMAP = {"bg1": "lt1", "tx1": "dk1", "bg2": "lt2", "tx2": "dk2",
                  **{s: s for s in SLOTS[4:]}}
DARK_CLRMAP = {**DEFAULT_CLRMAP, "bg1": "dk1", "tx1": "lt1", "bg2": "dk2", "tx2": "lt2"}

# Fonts that ship with Windows, macOS and Microsoft Office (same list as Make_Clean_PPTX).
COMMON_FONTS = {
    "arial", "arial black", "arial narrow", "calibri", "calibri light", "cambria", "candara", "consolas",
    "constantia", "corbel", "courier new", "georgia", "tahoma", "times new roman", "trebuchet ms", "verdana",
    "aptos", "aptos display", "aptos narrow", "segoe ui", "helvetica", "helvetica neue", "gill sans mt",
    "century gothic", "franklin gothic medium", "garamond", "palatino linotype", "book antiqua", "impact",
}


class ThemeError(ValueError):
    """A file that cannot be used, explained in plain words."""


# ------------------------------------------------------------------ colour maths
def parse_hex(value: str) -> str:
    """'#1d4e89', '1D4E89' or '#18e' -> '1D4E89'. Raises ValueError otherwise."""
    h = str(value).strip().lstrip("#")
    if re.fullmatch(r"[0-9A-Fa-f]{3}", h):
        h = "".join(c * 2 for c in h)
    if not re.fullmatch(r"[0-9A-Fa-f]{6}", h):
        raise ValueError("not a hex colour: %r (expected something like #1D4E89)" % value)
    return h.upper()


def hex_to_rgb(h: str):
    h = parse_hex(h)
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def rgb_to_hex(rgb) -> str:
    return "".join("%02X" % int(round(max(0.0, min(1.0, c)) * 255)) for c in rgb)


def _lin(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _gamma(c: float) -> float:
    c = max(0.0, min(1.0, c))
    return c * 12.92 if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def luminance(rgb) -> float:
    """WCAG 2.x relative luminance."""
    r, g, b = (_lin(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ratio(fg, bg) -> float:
    """WCAG 2.x contrast ratio, 1..21."""
    l1, l2 = sorted((luminance(fg), luminance(bg)), reverse=True)
    return (l1 + 0.05) / (l2 + 0.05)


def hls(rgb):
    return colorsys.rgb_to_hls(*rgb)


def at_luminance(hue: float, sat: float, target: float):
    """The colour of this HSL hue and saturation whose WCAG luminance is `target`.

    For a fixed hue and saturation every RGB channel grows with HSL lightness, so luminance is
    monotonic and a bisection finds it. The result is rounded to 8 bits, as a theme stores it.
    """
    target = max(0.0, min(1.0, target))
    lo, hi = 0.0, 1.0
    for _ in range(40):
        mid = (lo + hi) / 2
        if luminance(colorsys.hls_to_rgb(hue, mid, sat)) < target:
            lo = mid
        else:
            hi = mid
    return hex_to_rgb(rgb_to_hex(colorsys.hls_to_rgb(hue, (lo + hi) / 2, sat)))


def to_lab(rgb):
    """CIE L*a*b* (D65), for "are these two colours the same to the eye" (delta E)."""
    r, g, b = (_lin(c) for c in rgb)
    x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047
    y = 0.2126 * r + 0.7152 * g + 0.0722 * b
    z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883

    def f(t):
        return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116
    fx, fy, fz = f(x), f(y), f(z)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def delta_e(c1, c2) -> float:
    return math.dist(to_lab(c1), to_lab(c2))


def describe(rgb) -> str:
    """A plain colour name ('dark blue', 'light grey') so people recognise a candidate."""
    h, lum, s = hls(rgb)
    y = luminance(rgb)
    shade = "very dark" if y < 0.03 else "dark" if y < 0.12 else "light" if y > 0.55 else ""
    if s < 0.12 or (lum < 0.08 or lum > 0.96):
        base = "black" if y < 0.01 else "white" if y > 0.92 else "grey"
        if base != "grey":
            return base
    else:
        names = ((15, "red"), (40, "orange"), (65, "yellow"), (160, "green"), (195, "teal"), (255, "blue"),
                 (290, "purple"), (335, "pink"), (360, "red"))
        deg = h * 360
        base = next(n for limit, n in names if deg < limit)
        if base == "orange" and y < 0.15:
            base = "brown"
    return (shade + " " + base).strip()


# Colour-vision simulation: Machado, Oliveira and Fernandes (2009), severity 1.0, applied in linear RGB.
CVD = {
    "protanopia": ((0.152286, 1.052583, -0.204868), (0.114503, 0.786281, 0.099216),
                   (-0.003882, -0.048116, 1.051998)),
    "deuteranopia": ((0.367322, 0.860646, -0.227968), (0.280085, 0.672501, 0.047413),
                     (-0.011820, 0.042940, 0.968881)),
    "tritanopia": ((1.255528, -0.076749, -0.178779), (-0.078411, 0.930809, 0.147602),
                   (0.004733, 0.691367, 0.303900)),
}
VIEWS = ("normal", "greyscale", "protanopia", "deuteranopia", "tritanopia")


def simulate(rgb, view: str):
    """How a colour looks in greyscale or to someone with a colour-vision deficiency."""
    if view == "normal":
        return tuple(rgb)
    if view == "greyscale":
        g = _gamma(luminance(rgb))
        return (g, g, g)
    m = CVD[view]
    lin = [_lin(c) for c in rgb]
    return tuple(_gamma(sum(m[i][j] * lin[j] for j in range(3))) for i in range(3))


# ------------------------------------------------------------------ themes
def read_theme_xml(data: bytes) -> dict:
    """{"name", "colors": {slot: "RRGGBB"}, "fonts": {"major", "minor"}} from an a:theme part."""
    try:
        root = etree.fromstring(data)
    except etree.XMLSyntaxError as exc:
        raise ThemeError("the theme is not valid XML (%s)" % exc) from exc
    if root.tag != A + "theme":
        raise ThemeError("not a PowerPoint theme (root element <%s>)" % etree.QName(root).localname)
    colors = {}
    scheme = root.find(".//a:clrScheme", NS)
    if scheme is not None:
        for slot in SLOTS:
            el = scheme.find("a:" + slot, NS)
            if el is None or not len(el):
                continue
            c = el[0]
            val = c.get("lastClr") if c.tag == A + "sysClr" else c.get("val")
            if c.tag == A + "sysClr" and not val:
                val = "FFFFFF" if c.get("val") == "window" else "000000"
            if val and re.fullmatch(r"[0-9A-Fa-f]{6}", val):
                colors[slot] = val.upper()
    fonts = {}
    for key, tag in (("major", "majorFont"), ("minor", "minorFont")):
        lat = root.find(".//a:fontScheme/a:%s/a:latin" % tag, NS)
        fonts[key] = lat.get("typeface", "") if lat is not None else ""
    return {"name": root.get("name", ""), "colors": colors, "fonts": fonts}


def _rels(z: zipfile.ZipFile, part: str) -> dict:
    p = PurePosixPath(part)
    name = str(p.parent / "_rels" / (p.name + ".rels")) if part else "_rels/.rels"
    if name not in z.namelist():
        return {}
    out = {}
    for rel in etree.fromstring(z.read(name)).iter(PKG_REL + "Relationship"):
        if rel.get("TargetMode") == "External":
            continue
        target = rel.get("Target", "")
        full = target.lstrip("/") if target.startswith("/") else os.path.normpath(str(p.parent / target))
        out.setdefault(rel.get("Type", "").rsplit("/", 1)[-1], full.replace(os.sep, "/"))
    return out


def theme_parts(z: zipfile.ZipFile) -> list:
    """Theme part names of an Office package, the one the first slide master uses first."""
    names = z.namelist()
    found = sorted((n for n in names if re.search(r"(^|/)theme\d*\.xml$", n)),
                   key=lambda n: (len(n), n))
    masters = sorted((n for n in names if re.search(r"(^|/)slideMasters/slideMaster\d+\.xml$", n)),
                     key=lambda n: int(re.search(r"(\d+)\.xml$", n).group(1)))
    first = _rels(z, masters[0]).get("theme") if masters else _rels(z, "").get("officeDocument")
    if first in found:
        found.remove(first)
        found.insert(0, first)
    return found


def load_theme(path) -> dict:
    """Read the theme of a .thmx, .potx, .pptx, .docx, .xlsx or theme .xml file.

    Returns read_theme_xml(...) plus "clrmap" (the first slide master's colour map, or None) and "path".
    """
    path = Path(path)
    if not path.is_file():
        raise ThemeError("file not found: %s" % path)
    if path.suffix.lower() == ".xml":
        out = read_theme_xml(path.read_bytes())
        out.update(clrmap=None, path=str(path))
        return out
    try:
        z = zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError) as exc:
        raise ThemeError("%s cannot be opened as an Office file (damaged, or another format?)" % path.name) from exc
    with z:
        parts = theme_parts(z)
        if not parts:
            raise ThemeError("%s contains no theme" % path.name)
        out = read_theme_xml(z.read(parts[0]))
        clrmap = None
        masters = sorted(n for n in z.namelist() if re.search(r"(^|/)slideMasters/slideMaster1\.xml$", n))
        if masters:
            cm = etree.fromstring(z.read(masters[0])).find("p:clrMap", NS)
            if cm is not None:
                clrmap = dict(cm.attrib)
    out.update(clrmap=clrmap, path=str(path))
    return out


def is_dark(theme: dict) -> bool:
    cmap = {**DEFAULT_CLRMAP, **(theme.get("clrmap") or {})}
    c = theme["colors"]
    return luminance(hex_to_rgb(c[cmap["bg1"]])) < luminance(hex_to_rgb(c[cmap["tx1"]]))


# ------------------------------------------------------------------ contract
def load_contract(path=None) -> dict:
    return json.loads(Path(path or CONTRACT).read_text(encoding="utf-8"))


def token(theme: dict, name: str, contract: dict):
    """Resolve a contract token (ink, paper, muted, a1...) or a bare slot (hlink) to an RGB colour."""
    cmap = {**DEFAULT_CLRMAP, **(theme.get("clrmap") or {})}
    tok = contract["tokens"].get(name)
    scheme = tok["scheme"] if tok else name
    hx = theme["colors"].get(cmap.get(scheme, scheme))
    if not hx:
        return None
    rgb = hex_to_rgb(hx)
    if tok and (tok.get("lumMod") or tok.get("lumOff")):
        h, lum, s = colorsys.rgb_to_hls(*rgb)
        lum = lum * (tok.get("lumMod") or 100000) / 100000 + (tok.get("lumOff") or 0) / 100000
        rgb = colorsys.hls_to_rgb(h, max(0.0, min(1.0, lum)), s)
    return rgb


def check_theme(theme: dict, contract: dict | None = None) -> dict:
    """Check a theme against the contract. Same rules as Make_Clean_PPTX's `lint_deck.py --contrast`.

    Returns {"ok", "dark", "ramp": [...], "pairs": [...], "findings": [plain messages]}.
    """
    contract = contract or load_contract()
    missing = [s for s in SLOTS if s not in theme.get("colors", {})]
    if missing:
        return {"ok": False, "dark": False, "ramp": [], "pairs": [],
                "findings": ["the theme has no value for " + ", ".join(missing)]}
    findings = []
    ink, paper = token(theme, "ink", contract), token(theme, "paper", contract)
    dark = luminance(paper) < luminance(ink)
    acc = [token(theme, "a%d" % i, contract) for i in range(1, 7)]
    lum = [luminance(c) for c in acc]
    ordered = all((b < a) if dark else (b > a) for a, b in zip(lum, lum[1:]))
    step = contract.get("ramp", {}).get("min_step", 1.1)
    ramp = []
    for i in range(5):
        r = ratio(acc[i], acc[i + 1])
        ramp.append({"from": "accent%d" % (i + 1), "to": "accent%d" % (i + 2), "ratio": round(r, 2),
                     "ok": ordered and r >= step})
    if not ordered:
        findings.append("accent1 to accent6 are not a ramp from the text colour to the background (%s): "
                        "charts and levels read them in order, so give them one family of shades, %s first" % (
                            ", ".join(rgb_to_hex(c) for c in acc), "lightest" if dark else "darkest"))
    else:
        for i, r in enumerate(ramp):
            if not r["ok"]:
                findings.append("%s and %s are almost the same lightness (%.2f:1, at least %.2f:1): neighbouring "
                                "series will look identical" % (r["from"], r["to"], r["ratio"], step))
    pairs = []
    for p in contract.get("pairs", []):
        fg, bg = token(theme, p["text"], contract), token(theme, p["on"], contract)
        if fg is None or bg is None:
            continue
        r = ratio(fg, bg)
        ok = r >= p["min_ratio"]
        pairs.append({"text": p["text"], "on": p["on"], "kind": p.get("kind", "text"), "ratio": round(r, 2),
                      "needs": p["min_ratio"], "ok": ok, "runs": p.get("runs", 0)})
        if not ok:
            what = {"graphic": "%s lines and markers on %s", "link": "%s links on %s"}.get(
                p.get("kind"), "%s text on %s") % (p["text"], p["on"])
            where = " (%d text runs in the Make_Clean libraries)" % p["runs"] if p.get("runs") else ""
            findings.append("%s: %.2f:1, %.1f:1 needed%s" % (what, r, p["min_ratio"], where))
    return {"ok": not findings, "dark": dark, "ramp": ramp, "pairs": pairs, "findings": findings}


def views_check(theme: dict, contract: dict) -> list:
    """Smallest neighbour step of the accent ramp in greyscale and the three colour-vision views."""
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


def view_findings(views: list) -> list:
    return ["in %s, %s are hard to tell apart (%.2f:1)" % (v["view"], v["between"], v["min_step"])
            for v in views if not v["ok"]]


def font_note(name: str) -> str:
    """'' when the font is safe to assume on the machine that opens the deck, else a plain warning."""
    if not name or name.lower() in COMMON_FONTS:
        return ""
    return ("%s is not a standard Windows/macOS/Office font: the deck falls back to another font where it is not "
            "installed, and text may overflow; set theme_fonts_fallback in deck.json or pick a common font" % name)
