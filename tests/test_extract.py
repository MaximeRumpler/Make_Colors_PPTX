import shutil
import json

import pytest
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
    assert any("guide.pdf" in n for n in res["notes"])
    assert ex.main([str(tmp_path / "logo.svg"), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["colours"]
    assert ex.main([str(tmp_path / "guide.pdf")]) == 2


def test_brand_hues_skip_greys_and_shades(tmp_path):
    (tmp_path / "site.css").write_text("""
:root { --navy: #17255A; --navy-light: #5A6FB8; --orange: #E07A1F; --teal: #2A9D8F; --grey: #6B6B6B; }
h1 { color: var(--navy); } .btn { background: var(--orange); } .tag { color: var(--teal); }
""")
    res = ex.extract([tmp_path / "site.css"])
    assert sorted(res["brand_hues"]) == ["#17255A", "#2A9D8F", "#E07A1F"]
    assert "Distinct brand hues" in ex.as_text(res)


def test_brand_hues_of_a_one_hue_theme(tmp_path, harbour_roles):
    rep = build_theme.build({**harbour_roles, "ramp": "single", "secondary": None}, tmp_path)
    res = ex.extract([rep["variants"]["light"]["files"][0]])
    assert len(res["brand_hues"]) == 1  # six shades of one blue are one brand hue


def _text_pdf(path, lines):
    """A one-page PDF with plain Helvetica text, built by hand (no PDF library needed)."""
    body = "BT /F1 12 Tf 40 780 Td 16 TL " + " ".join("(%s) Tj T*" % ln for ln in lines) + " ET"
    objs = ["<< /Type /Catalog /Pages 2 0 R >>", "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R "
            "/Resources << /Font << /F1 5 0 R >> >> >>",
            "<< /Length %d >>\nstream\n%s\nendstream" % (len(body), body),
            "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    out, offsets = b"%PDF-1.4\n", []
    for i, o in enumerate(objs, 1):
        offsets.append(len(out))
        out += ("%d 0 obj\n%s\nendobj\n" % (i, o)).encode()
    xref = len(out)
    out += ("xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)).encode()
    out += b"".join(("%010d 00000 n \n" % o).encode() for o in offsets)
    out += ("trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)).encode()
    path.write_bytes(out)


@pytest.mark.skipif(shutil.which("pdftotext") is None, reason="poppler is not installed")
def test_pdf_brand_guide_values(tmp_path):
    pdf = tmp_path / "guide.pdf"
    _text_pdf(pdf, ["Primary blue HEX #1D4E89", "Accent orange RGB 224 122 31",
                    "Support green CMYK 80 0 40 20", "Pantone 7692 C for print"])
    res = ex.extract([pdf])
    got = {c["hex"]: " ".join(c["sources"]) for c in res["colours"]}
    assert "#1D4E89" in got and "Primary blue" in got["#1D4E89"]
    assert "#E07A1F" in got and "Accent orange" in got["#E07A1F"]
    green = next(h for h, src in got.items() if "CMYK" in src)
    assert "approximate" in got[green]
    assert any("Pantone" in n for n in res["notes"]) and any("approximate" in n for n in res["notes"])


def test_pdf_without_poppler_says_so(tmp_path, monkeypatch):
    pdf = tmp_path / "guide.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")
    monkeypatch.setattr(shutil, "which", lambda name: None)
    res = ex.extract([pdf])
    assert res["read"] == [] and any("pdftotext" in n for n in res["notes"])
