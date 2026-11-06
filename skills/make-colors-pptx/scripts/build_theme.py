#!/usr/bin/env python3
"""Build a PowerPoint theme from the colour roles chosen with the user.

    build_theme.py roles.json [--out-dir brand/] [--thmx] [--contract PATH]

roles.json (see references/roles-reference.md):
    {"name": "Demo Harbour", "primary": "#1D4E89", "secondary": "#E07A1F", "others": ["#2A9D8F"],
     "fonts": {"major": "Georgia", "minor": "Arial"}}

Writes `<slug>.potx` (light) and `<slug>-dark.potx` (dark: dk1 stays dark, the master's colour map
swaps text and background, as Make_Clean_PPTX expects), plus `<slug>.thmx` (light, theme only) with
--thmx. Both files work in PowerPoint (Design > Browse for Themes, or open the template) and in
Make_Clean_PPTX's deck.json: "theme": "brand/<slug>.potx".

The six accents become one ramp from strong to faint, with lightness solved so every pair of the
theme contract passes. Up to four brand colours (primary, secondary, others) each take the ramp slot
nearest their own lightness, exactly when the theme still passes there, else as the nearest readable
shade of the same hue (the other slots move around a kept colour, and body text gets a little stronger when a
mid-tone colour needs it); the slots in between are shades of the nearest brand colour. "ramp": "single"
keeps the primary hue only, "drift" slides from the primary to the secondary hue. Prints a JSON
report: files, slots, where each brand colour went, contract check, colour-blind views, font notes.
Exit code 0 when every variant passes the contract, 1 when a variant still has findings (files are
written anyway), 2 when roles.json cannot be used.
"""
from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent))
import _env  # noqa: E402,F401  (switches to the private environment if needed)

import argparse
import io
import json
import math
import re
import sys
import zipfile
from itertools import permutations
from pathlib import Path

from lxml import etree

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _colour import (A, DARK_CLRMAP, NS, ThemeError, at_luminance, check_theme, font_note,  # noqa: E402
                     hex_to_rgb, hls, load_contract, luminance, parse_hex, ratio, rgb_to_hex, view_findings,
                     views_check)

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
RAMP_MODES = ("brand", "single", "drift")
MAX_BRAND = 4
CHART_FIRST = (0, 2, 4)  # accent1, accent3, accent5: the first three chart series in Make_Clean
SLOT_PENALTY = 0.15  # small: only decides between two slots of nearly the same lightness
WEIGHTS = (2.0, 1.5, 1.0)  # primary, secondary, others: who gets the slot nearest its own lightness
ALTERNATIVES = 8  # assignments tried, best first, when a colour-blind view merges two neighbouring accents
MISS = 0.3  # extra cost of a slot where the exact brand colour would have to become a shade
ACCENT1_REACH = 0.95  # log-distance (about 2.6x in WCAG terms) beyond which a colour may not take accent1


def f(y: float) -> float:
    return y + 0.05


def _clamp(v, lo, hi):
    return max(lo, min(hi, v)) if lo <= hi else (lo + hi) / 2


def _relax(a, pins, bounds, passes=8):
    """Clamp every free slot into the bounds set by its neighbours until nothing moves.

    `a` holds the target luminances, `pins` {slot index: luminance} the slots fixed by an exact brand
    colour; `bounds(a, i)` gives (low, high) for slot i from the current values of the others.
    """
    a = list(a)
    for i, y in pins.items():
        a[i] = y
    for _ in range(passes):
        moved = False
        for i in range(6):
            if i in pins:
                continue
            lo, hi = bounds(a, i)
            v = _clamp(a[i], lo, hi)
            if abs(v - a[i]) > 1e-9:
                a[i], moved = v, True
        if not moved:
            break
    return [max(0.0, min(1.0, v)) for v in a]


def solve_light(paper, ink, ink2, step=1.1, pins=None):
    """Accent luminances for a light theme, given the luminance of paper, ink and ink2 (body text).

    `pins` {slot index: luminance} keeps those slots fixed and lets the others move around them.
    """
    m = MARGIN
    s = step * m

    def bounds(a, i):
        if i == 0:
            return 0.0, min(f(paper) / (4.5 * m), f(a[2]) / (4.5 * m), f(a[1]) / s) - 0.05
        if i == 1:
            return f(a[0]) * s - 0.05, min(f(paper) / (4.5 * m), f(a[2]) / s, f(a[4]) / (4.5 * m)) - 0.05
        if i == 2:
            return (max(4.5 * m * f(ink), f(a[1]) * s, 4.5 * m * f(a[0])) - 0.05,
                    min(f(paper) / (3.0 * m), f(a[3]) / s) - 0.05)
        if i == 3:
            return max(4.5 * m * f(ink2), f(a[2]) * s) - 0.05, f(a[4]) / s - 0.05
        if i == 4:
            return max(4.5 * m * f(a[1]), f(a[3]) * s) - 0.05, f(a[5]) / s - 0.05
        return f(a[4]) * s - 0.05, 1.0
    return _relax(LIGHT_TARGETS, pins or {}, bounds)


def solve_dark(paper, ink, ink2, step=1.1, pins=None):
    """Accent luminances for a dark theme (accent1 lightest): paper is dark, ink and ink2 are light."""
    m = MARGIN
    s = step * m

    def bounds(a, i):
        if i == 0:
            return max(4.5 * m * max(f(paper), f(a[2])), f(a[1]) * s) - 0.05, 1.0
        if i == 1:
            return (max(4.5 * m * f(paper), f(a[2]) * s, 4.5 * m * f(a[4])) - 0.05,
                    f(a[0]) / s - 0.05)
        if i == 2:
            return (max(3.0 * m * f(paper), f(a[3]) * s) - 0.05,
                    min(f(ink) / (4.5 * m), f(a[1]) / s, f(a[0]) / (4.5 * m)) - 0.05)
        if i == 3:
            return f(a[4]) * s - 0.05, min(f(a[2]) / s, f(ink2) / (4.5 * m)) - 0.05
        if i == 4:
            return f(a[5]) * s - 0.05, min(f(a[1]) / (4.5 * m), f(a[3]) / s) - 0.05
        return 0.0, f(a[4]) / s - 0.05
    return _relax(DARK_TARGETS, pins or {}, bounds)


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


def is_neutral(hexval: str) -> bool:
    """Greys, near-black and near-white: they belong to the neutrals (text, background), not the ramp."""
    _, lum, s = hls(hex_to_rgb(hexval))
    return s < 0.12 or lum < 0.06 or lum > 0.97


def brand_colours(roles: dict) -> list:
    """[(role, hex)] of the brand colours in order of importance: primary, secondary, others."""
    out = [("primary", parse_hex(roles["primary"]))]
    if roles.get("secondary"):
        out.append(("secondary", parse_hex(roles["secondary"])))
    others = roles.get("others") or []
    if isinstance(others, str):
        others = [others]
    out += [("other %d" % (i + 1), parse_hex(c)) for i, c in enumerate(others)]
    if len(out) > MAX_BRAND:
        raise ValueError("at most %d brand colours fit on the ramp (primary, secondary and two others): set the "
                         "rest aside for pictures and the logo" % MAX_BRAND)
    return out


def place_brand(colours: list, targets: list, fits) -> list:
    """Assignments {slot index: colour index}, best first: each brand colour on the slot nearest its lightness.

    Brute force over every assignment (at most 6*5*4*3). A slot where the exact colour passes the contract
    (`fits(colour, slot)`) beats one where it would need a shade; the primary weighs most, then the
    secondary; the slots that lead Make_Clean's charts (accent1, accent3, accent5) win near-ties.
    accent1 (dark panels and slides) only takes a brand colour already close to it: a mid-tone colour
    pushed there would turn into a muddy near-black.
    """
    ys = [luminance(hex_to_rgb(c)) for _, c in colours]
    table = {}
    for ci in range(len(colours)):
        for si in range(6):
            d = abs(math.log(f(ys[ci]) / f(targets[si])))
            if si == 0 and d > ACCENT1_REACH:
                table[ci, si] = float("inf")
                continue
            d += (0 if fits(colours[ci][1], si) else MISS) + (0 if si in CHART_FIRST else SLOT_PENALTY)
            table[ci, si] = d * WEIGHTS[min(ci, 2)]

    def cost(ci, si):
        return table[ci, si]
    ranked = sorted(((sum(cost(ci, si) for ci, si in enumerate(slots)), slots)
                     for slots in permutations(range(6), len(colours))))
    return [{si: ci for ci, si in enumerate(slots)} for c, slots in ranked[:ALTERNATIVES] if c < float("inf")]


def _owner(slot: int, placed: dict) -> int:
    """Brand colour whose hue a slot takes: its own; else the primary for accent1, the nearest placed
    slot for the others (ties to the more important colour)."""
    if slot in placed:
        return placed[slot]
    if slot == 0:
        return 0
    return min(placed.items(), key=lambda kv: (abs(kv[0] - slot), kv[1]))[1]


def _passes(theme: dict, contract: dict) -> bool:
    return check_theme(theme, contract)["ok"] and not view_findings(views_check(theme, contract))


BODY_STEPS = {False: ("333333", "262626"), True: ("E8E8E8", "F2F2F2")}  # body text, a little stronger, per theme


def make_variant(roles: dict, dark: bool, contract: dict) -> dict:
    """Colour slots of one variant: {"colors", "clrmap", "notes", "primary_slot", "brand_slots"}.

    Body text (dk2) is a free choice of the theme, so when a mid-tone brand colour cannot keep its exact value
    against the default body text (4.5:1 on its slot), body text is made a little stronger, one step at a time,
    for as long as that keeps more brand colours exact. A body colour given in roles.json is never touched.
    """
    best = _variant(roles, dark, contract)
    given = (roles.get("dark") if dark else roles.get("neutrals")) or {}
    if given.get("body") or roles.get("_body") or roles.get("accents") or roles.get("dark_accents"):
        return best

    def kept(v):
        return sum(1 for x in v["brand_slots"].values() if x)
    for body in BODY_STEPS[dark]:
        if kept(best) == len(best["brand_slots"]):
            break
        trial = _variant({**roles, "_body": body}, dark, contract)
        if kept(trial) > kept(best):
            trial["notes"].append("body text set to #%s (default %s) so that more brand colours stay exact" % (
                body, (DARK_NEUTRALS if dark else LIGHT_NEUTRALS)["body"]))
            best = trial
    return best


def _variant(roles: dict, dark: bool, contract: dict) -> dict:
    notes = []
    primary = parse_hex(roles["primary"])
    secondary = parse_hex(roles["secondary"]) if roles.get("secondary") else None
    mode = roles.get("ramp") or ("drift" if roles.get("ramp_drift") else "brand")
    if mode not in RAMP_MODES:
        raise ValueError("ramp can be %s, not %r" % (", ".join(RAMP_MODES), mode))
    hue = hls(hex_to_rgb(primary))[0]
    given = dict((roles.get("dark") if dark else roles.get("neutrals")) or {})
    if roles.get("_body"):
        given["body"] = roles["_body"]
    neutrals = dict(DARK_NEUTRALS if dark else LIGHT_NEUTRALS)
    if roles.get("tint_neutrals"):
        neutrals = {k: _tint(v, hue, 0.18 if k in ("background", "surface") else 0.25) for k, v in neutrals.items()}
    neutrals.update({k: parse_hex(v) for k, v in given.items() if k in neutrals and v})
    lum = {k: luminance(hex_to_rgb(v)) for k, v in neutrals.items()}
    step = contract.get("ramp", {}).get("min_step", 1.1)

    def theme_of(acc):
        return _theme(neutrals, acc, primary, dark, secondary)

    slots = {}  # brand role -> "accentN" when kept exactly, None when a nearby shade is used
    accents_given = roles.get("dark_accents" if dark else "accents")
    if accents_given:
        accents = [parse_hex(c) for c in accents_given]
        if len(accents) != 6:
            raise ValueError("%s must list exactly six colours" % ("dark_accents" if dark else "accents"))
        return {**theme_of(accents), "notes": notes, "primary_slot": None, "brand_slots": slots}

    brand = brand_colours(roles)
    if mode == "brand":
        for role, c in brand[1:]:
            if is_neutral(c):
                notes.append("%s %s is a neutral, not a ramp colour: use it as a neutral (text, body, background "
                             "or surface) if it matters" % (role, c))
        brand = brand[:1] + [(r, c) for r, c in brand[1:] if not is_neutral(c)]
    else:
        brand = brand[:1]

    targets = (solve_dark if dark else solve_light)(lum["background"], lum["text"], lum["body"], step)
    base = [rgb_to_hex(at_luminance(hue, hls(hex_to_rgb(primary))[2], y)) for y in targets]

    solver = solve_dark if dark else solve_light

    def solved(pins):
        """Luminance targets with the slots in `pins` {slot: hex} fixed and the others moved around them."""
        return solver(lum["background"], lum["text"], lum["body"], step,
                      {i: luminance(hex_to_rgb(c)) for i, c in pins.items()})

    def fits(c, i):
        tg = solved({i: c})
        trial = [c if j == i else rgb_to_hex(at_luminance(hue, hls(hex_to_rgb(primary))[2], tg[j]))
                 for j in range(6)]
        return check_theme(theme_of(trial), contract)["ok"]
    placements = place_brand(brand, targets, fits) if mode != "drift" else [None]

    def ramp(placed):
        """(accents, slots, notes) for one assignment of the brand colours to slots."""
        if mode == "drift":
            hues, sat = _ramp_hues(primary, secondary, True)
            sats = [sat] * 6
            y = luminance(hex_to_rgb(primary))
            tries = [(0, sorted(range(6), key=lambda i: abs(f(y) / f(targets[i]) - 1)))]
        else:
            hs = [hls(hex_to_rgb(c)) for _, c in brand]
            own = [_owner(i, placed) for i in range(6)]
            hues, sats = [hs[o][0] for o in own], [hs[o][2] for o in own]
            # Its own slot first, then the nearest slot no other brand colour is placed on (accent1 only for a colour
            # close to it): a slot belongs to the hue that is placed there.
            tries = []
            for si, ci in sorted(placed.items(), key=lambda kv: kv[1]):
                y = luminance(hex_to_rgb(brand[ci][1]))
                near = [j for j in sorted(range(6), key=lambda j: abs(j - si))
                        if j not in placed and (j or abs(math.log(f(y) / f(targets[0]))) <= ACCENT1_REACH)]
                tries.append((ci, [si] + near))
        def paint(pins):
            """Accents for one set of exact slots: the others re-solved around them, in their own hue."""
            tg = solved(pins)
            return [pins[i] if i in pins else rgb_to_hex(at_luminance(hues[i], sats[i], tg[i])) for i in range(6)]
        pins = {}
        acc = paint(pins)
        got, said = {}, []
        # Each brand colour, most important first, takes its slot exactly when the whole theme still passes,
        # the slots around it moving as far as the contract needs.
        for ci, candidates in tries:
            role, c = brand[ci]
            for i in candidates:
                if i in pins:
                    continue
                trial = paint({**pins, i: c})
                if _passes(theme_of(trial), contract):
                    acc = trial
                    pins[i] = c
                    got[role] = "accent%d" % (i + 1)
                    said.append("%s %s kept exactly, on accent%d" % (role, c, i + 1))
                    break
            else:
                i = next((j for j in candidates if j not in pins), candidates[0])
                got[role] = None
                said.append("%s %s cannot sit on the ramp unchanged (%.1f:1 against the background): accent%d %s "
                            "is the nearest readable shade of the same hue" % (
                                role, c, ratio(hex_to_rgb(c), hex_to_rgb(neutrals["background"])), i + 1, acc[i]))
        return acc, got, said

    # Two hues of the same lightness can merge in a colour-blind view (red and blue in protanopia): then
    # try the next best assignments, and keep the best one if none passes (the report warns).
    first = None
    for placed in placements:
        accents, slots, said = ramp(placed)
        first = first or (accents, slots, said)
        if _passes(theme_of(accents), contract):
            break
    else:
        accents, slots, said = first
    notes += said
    theme = theme_of(accents)
    if secondary and theme["colors"]["hlink"] != secondary:
        notes.append("secondary %s is too faint for links (4.5:1 on background and surface): links use %s" % (
            secondary, theme["colors"]["hlink"]))
    return {**theme, "notes": notes, "primary_slot": slots.get("primary"), "brand_slots": slots}


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


LARGE_TEXT = 3.0  # WCAG large text and graphics: what the emphasis colour needs on the slide background


def deck_options(roles: dict, variant: dict) -> list:
    """Optional Make_Clean deck.json keys that suit this palette. Suggestions with a reason, never applied alone."""
    out = []
    colours = variant["colors"]
    paper = hex_to_rgb(colours["dk1" if variant.get("clrmap") else "lt1"])  # a dark theme swaps the map
    slot = variant.get("primary_slot")
    if slot and slot != "accent1":  # a mid-tone main colour: it sits on a middle accent, not on the dark panels
        r = ratio(hex_to_rgb(colours[slot]), paper)
        if r >= LARGE_TEXT:
            out.append({"key": "emphasis", "value": slot, "why": (
                "the main colour sits on %s, so the dark panels stay on accent1; emphasis puts it on the key "
                "numbers (large text, %.1f:1 on the background)" % (slot, r))})
    n = len(variant["brand_slots"])  # brand colours on the ramp, kept exactly or as a shade
    if n >= 3 and (roles.get("ramp") or "brand") == "brand":
        out.append({"key": "accent_scale", "value": "tints", "why": (
            "%d brand colours share the ramp, so scales (heat grids, funnels, levels) would show %d hues: "
            "tints of accent1 read as levels" % (n, n))})
    return out


def options_value(options: list, key: str, wanted):
    """The value for deck.json: a slot name or "tints" as given, else the suggestion's, else None."""
    if isinstance(wanted, str):
        return wanted
    return next((o["value"] for o in options if o["key"] == key), None)


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
                                 "primary_slot": theme["primary_slot"], "brand_slots": theme["brand_slots"],
                                 "notes": theme["notes"], "contract_ok": check["ok"], "findings": check["findings"],
                                 "view_warnings": view_findings(views_check(theme, contract))}
    first = next(iter(report["variants"].values()))
    fallback = {"theme_fonts_fallback": "Arial"} if report["font_notes"] else {}
    report["deck_json"] = {"theme": first["files"][0], **fallback}
    options = deck_options(roles, report["variants"].get("light") or first)
    report["options"] = options  # suggestions only: nothing here is added to deck_json unless roles.json asks
    for key in ("emphasis", "accent_scale"):
        if roles.get(key):  # explicit in roles.json: the user chose it
            wanted = options_value(options, key, roles[key])
            if wanted:
                report["deck_json"][key] = wanted
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
