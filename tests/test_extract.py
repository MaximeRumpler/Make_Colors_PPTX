import json

from PIL import Image, ImageDraw

import build_theme
import extract_candidates as ex


def test_css_colour_forms():
    assert ex.css_colour("#1d4e89") == "1D4E89"
    assert ex.css_colour("#18e") == "1188EE"
    assert ex.css_colour("rgb(29, 78, 137)") == "1D4E89"
    assert ex.css_colour("rgb(29 78 137 / 90%)") == "1D4E89"
    assert ex.css_colour("rgba(0,0,0,0.1)") is None
    assert ex.css_colour("hsl(213deg 65% 33%)") is not None
    assert ex.css_colour("#00000000") is None
    assert ex.css_colour("navy") == "000080"


def test_office_theme_is_the_source(tmp_path, harbour_roles):
    rep = build_theme.build(harbour_roles, tmp_path, thmx=False)
    res = ex.extract([rep["variants"]["light"]["files"][0]])
    hexes = [c["hex"] for c in res["colours"]]
    assert "#1D4E89" in hexes
    first = next(c for c in res["colours"] if c["hex"] == "#1D4E89")
    assert any("accent2" in s for s in first["sources"])
    assert {f["font"] for f in res["fonts"]} == {"Georgia", "Arial"}


def test_saved_web_page(tmp_path):
    (tmp_path / "site.css").write_text("""
:root { --brand-primary: #0F6E5A; --brand-accent: var(--accent-raw); --accent-raw: rgb(240, 160, 30); }
body { color: #222; background: #fff; font-family: "Demo Grotesk", Inter, sans-serif; }
a, .btn { color: var(--brand-primary); }
.btn:hover { background-color: var(--brand-primary); }
/* #ABCDEF in a comment is ignored */
@font-face { font-family: 'Demo Grotesk'; src: url(x.woff2); }
""")
    (tmp_path / "index.html").write_text("""<html><head>
<meta name="theme-color" content="#0F6E5A">
<link rel="stylesheet" href="site.css">
<link rel="stylesheet" href="https://example.invalid/remote.css">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700&display=swap">
<style>h1 { color: hsl(165, 76%, 25%); }</style></head>
<body><p style="color:#0F6E5A">x</p></body></html>""")
    res = ex.extract([tmp_path / "index.html"])
    top = res["colours"][0]
    assert top["hex"] == "#0F6E5A"
    assert any(s.startswith("var --brand-primary") for s in top["sources"])
    assert any(c["hex"] == "#F0A01E" for c in res["colours"])  # resolved through two variables
    assert not any(c["hex"] == "#ABCDEF" for c in res["colours"])
    fonts = {f["font"]: f for f in res["fonts"]}
    assert fonts["Demo Grotesk"]["fallback"] == "Arial"
    assert fonts["Inter"]["fallback"] == "Segoe UI"
    assert fonts["Playfair Display"]["fallback"] == "Georgia"
    assert any("not fetched" in n for n in res["notes"])


def test_logo_image_shares(tmp_path):
    im = Image.new("RGBA", (400, 100), (0, 0, 0, 0))  # right quarter stays transparent
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, 199, 99), fill=(122, 30, 90, 255))   # 2/3 of the visible pixels
    d.rectangle((200, 0, 299, 99), fill=(250, 200, 40, 255))
    im.save(tmp_path / "logo.png")
    res = ex.extract([tmp_path / "logo.png"])
    c = res["colours"]
    assert c[0]["hex"] == "#7A1E5A" and abs(c[0]["share"] - 2 / 3) < 0.02
    assert c[1]["hex"] == "#FAC828"
    assert any("transparent" in n for n in res["notes"])


def test_svg_and_pdf(tmp_path, capsys):
    (tmp_path / "logo.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"><circle fill="#7A1E5A"/>'
                                       '<path style="fill:#FAC828"/></svg>')
    (tmp_path / "guide.pdf").write_bytes(b"%PDF-1.4")
    res = ex.extract([tmp_path / "logo.svg", tmp_path / "guide.pdf"])
    assert {"#7A1E5A", "#FAC828"} <= {c["hex"] for c in res["colours"]}
    assert any("PDF" in n for n in res["notes"])
    assert ex.main([str(tmp_path / "logo.svg"), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["colours"]
    assert ex.main([str(tmp_path / "guide.pdf")]) == 2
