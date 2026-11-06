"""Expressive palette: spread the brand colours over the cards of a built deck.

A theme alone recolours text and the shapes that already use an accent. The cards, callouts and
panels of a Make_Clean deck sit on the neutral surface, so a brand with three or four colours
shows only in details. With the expressive option, the fill of sibling cards on one slide takes
different accents of the theme, each chosen so that the text it holds stays readable (4.5:1,
3:1 for large text). Slides, text and positions are untouched; only fills change, and a slide
with a single card keeps it.

Cards are found by their role tag in the shape name (Make_Clean: ``card#1``, ``callout#2``,
``panel#1``, ``keyfigure#1``).
"""
from __future__ import annotations

import colorsys

from lxml import etree

from _colour import DEFAULT_CLRMAP, NS, ratio, hex_to_rgb

A = "{%s}" % NS["a"]
P = "{%s}" % NS["p"]
ROLES = ("card#", "callout#", "keyfigure#", "panel#")
ACCENTS = ["accent%d" % i for i in range(1, 7)]
NEUTRAL_FILLS = {"bg2", "lt2"}


def _box(sp):
    off = sp.find("p:spPr/a:xfrm/a:off", NS)
    ext = sp.find("p:spPr/a:xfrm/a:ext", NS)
    if off is None or ext is None:
        return None
    x, y, w, h = int(off.get("x")), int(off.get("y")), int(ext.get("cx")), int(ext.get("cy"))
    return x, y, x + w, y + h


def _text_colours(sp):
    """[(scheme name, size in pt or None)] of the text runs of a shape."""
    out = []
    for p in sp.findall(".//a:p", NS):
        for r in p.findall("a:r", NS):
            if not (r.findtext("a:t", namespaces=NS) or "").strip():
                continue
            rpr = r.find("a:rPr", NS)
            clr = rpr.find("a:solidFill/a:schemeClr", NS) if rpr is not None else None
            size = int(rpr.get("sz")) / 100 if rpr is not None and rpr.get("sz") else None
            mods = {}
            if clr is not None:
                for m in clr:
                    mods[etree.QName(m).localname] = int(m.get("val", "0"))
            out.append((clr.get("val") if clr is not None else "tx1", size, mods))
    return out


def spread(slide_xml: bytes, theme: dict, clrmap: dict | None) -> tuple[bytes, int]:
    """(new slide xml, number of fills changed)."""
    root = etree.fromstring(slide_xml)
    cmap = {**DEFAULT_CLRMAP, **(clrmap or {})}
    colours = theme["colors"]

    def rgb(scheme, mods=None):
        slot = cmap.get(scheme, scheme)
        if slot not in colours:
            return None
        c = hex_to_rgb(colours[slot])
        if mods and (mods.get("lumMod") or mods.get("lumOff")):  # the muted text colour is a shade of the body colour
            h, lum, s = colorsys.rgb_to_hls(*c)
            lum = lum * mods.get("lumMod", 100000) / 100000 + mods.get("lumOff", 0) / 100000
            c = colorsys.hls_to_rgb(h, max(0.0, min(1.0, lum)), s)
        return c

    tree = root.find(".//p:spTree", NS)
    shapes = [sp for sp in tree.findall("p:sp", NS)]  # top level only: group offsets are relative
    cards = []
    for sp in shapes:
        name = sp.find("p:nvSpPr/p:cNvPr", NS).get("name", "")
        fill = sp.find("p:spPr/a:solidFill/a:schemeClr", NS)
        if name.startswith(ROLES) and fill is not None and not len(fill) and \
                (fill.get("val") in NEUTRAL_FILLS or fill.get("val") in ACCENTS):
            box = _box(sp)
            if box:
                cards.append((sp, box, fill))
    if len(cards) < 2:
        return slide_xml, 0
    changed = 0
    taken = []  # accents already given on this slide, so neighbours differ
    for sp, box, fill in cards:
        cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
        runs = []
        for other in shapes:
            if other is sp:
                continue
            b = _box(other)
            if b and box[0] <= (b[0] + b[2]) / 2 <= box[2] and box[1] <= (b[1] + b[3]) / 2 <= box[3]:
                runs.extend(_text_colours(other))
        if not runs:
            continue

        def ok(acc):
            bg = rgb(acc)
            if bg is None:
                return False
            for scheme, size, mods in runs:
                fg = rgb(scheme, mods)
                if fg is None or ratio(fg, bg) < (3.0 if size and size >= 24 else 4.5):
                    return False
            return True

        passing = [a for a in ACCENTS if ok(a)]
        if not passing:
            continue
        fresh = [a for a in passing if a not in taken] or passing
        choice = fresh[0]
        taken.append(choice)
        if fill.get("val") != choice:
            fill.set("val", choice)
            changed += 1
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True), changed
