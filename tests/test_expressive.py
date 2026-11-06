from lxml import etree

import _expressive as E

NS = ('xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
      'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"')
THEME = {"colors": {"dk1": "111111", "lt1": "FFFFFF", "dk2": "404040", "lt2": "F2F2F2",
                    "accent1": "2C182E", "accent2": "7A3B2E", "accent3": "8A8A2E",
                    "accent4": "C9B458", "accent5": "E8D8A0", "accent6": "F5EFD8"}}


def card(i, x, text_clr):
    return (f'<p:sp><p:nvSpPr><p:cNvPr id="{i}" name="card#{i}"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>'
            f'<p:spPr><a:xfrm><a:off x="{x}" y="1000000"/><a:ext cx="2000000" cy="2000000"/></a:xfrm>'
            f'<a:solidFill><a:schemeClr val="bg2"/></a:solidFill></p:spPr></p:sp>'
            f'<p:sp><p:nvSpPr><p:cNvPr id="{i + 10}" name="Body {i}"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>'
            f'<p:spPr><a:xfrm><a:off x="{x + 100000}" y="1100000"/><a:ext cx="1800000" cy="900000"/></a:xfrm></p:spPr>'
            f'<p:txBody><a:bodyPr/><a:p><a:r><a:rPr sz="1800"><a:solidFill><a:schemeClr val="{text_clr}"/></a:solidFill>'
            f'</a:rPr><a:t>Hello</a:t></a:r></a:p></p:txBody></p:sp>')


def slide(n):
    body = "".join(card(i + 1, 500000 + i * 2500000, "tx1") for i in range(n))
    return f'<p:sld {NS}><p:cSld><p:spTree>{body}</p:spTree></p:cSld></p:sld>'.encode()


def fills(xml):
    root = etree.fromstring(xml)
    return [e.get("val") for e in root.iterfind(".//p:sp/p:spPr/a:solidFill/a:schemeClr", E.NS)]


def test_sibling_cards_take_different_readable_accents():
    new, n = E.spread(slide(3), THEME, None)
    f = fills(new)
    assert n == 3 and len(set(f)) == 3 and all(a.startswith("accent") for a in f)
    for acc in f:  # dark text stays at 4.5:1 or better on each choice
        assert E.ratio(E.hex_to_rgb(THEME["colors"]["dk1"]), E.hex_to_rgb(THEME["colors"][acc])) >= 4.5


def test_a_single_card_is_left_alone():
    new, n = E.spread(slide(1), THEME, None)
    assert n == 0 and new == slide(1)
