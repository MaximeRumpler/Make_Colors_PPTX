import json

from PIL import Image, ImageDraw

import logo_light


def run(capsys, *args):
    code = logo_light.main([str(a) for a in args])
    return code, json.loads(capsys.readouterr().out)


def one_colour_png(path, colour=(30, 60, 140)):
    im = Image.new("RGBA", (200, 80), (0, 0, 0, 0))
    ImageDraw.Draw(im).ellipse([10, 10, 70, 70], fill=colour + (255,))
    ImageDraw.Draw(im).rectangle([90, 30, 190, 50], fill=colour + (255,))
    im.save(path)
    return path


def test_one_colour_png_becomes_light_and_keeps_its_transparency(tmp_path, capsys):
    src = one_colour_png(tmp_path / "logo.png")
    code, rep = run(capsys, src)
    assert code == 0 and rep["use"]["logo_dark"].endswith("logo-light.png")
    out = Image.open(tmp_path / "logo-light.png").convert("RGBA")
    assert out.size == (200, 80)
    assert out.getpixel((40, 40)) == (245, 245, 245, 255)
    assert out.getpixel((0, 0))[3] == 0
    assert Image.open(src).convert("RGBA").getpixel((40, 40)) == (30, 60, 140, 255)  # original untouched


def test_custom_colour_and_out(tmp_path, capsys):
    src = one_colour_png(tmp_path / "logo.png")
    code, rep = run(capsys, src, "--colour", "#EEE", "--out", tmp_path / "b" / "l.png")
    assert code == 0 and Image.open(tmp_path / "b" / "l.png").convert("RGBA").getpixel((40, 40))[:3] == (238, 238, 238)


def test_two_colour_and_opaque_logos_are_refused(tmp_path, capsys):
    im = one_colour_png(tmp_path / "two.png")
    two = Image.open(im).convert("RGBA")
    ImageDraw.Draw(two).rectangle([90, 30, 190, 50], fill=(230, 120, 40, 255))
    two.save(tmp_path / "two.png")
    code, rep = run(capsys, tmp_path / "two.png")
    assert code == 1 and "several colours" in rep["reason"] and not (tmp_path / "two-light.png").exists()
    Image.new("RGB", (50, 50), (30, 60, 140)).save(tmp_path / "flat.png")
    code, rep = run(capsys, tmp_path / "flat.png")
    assert code == 1 and "transparent" in rep["reason"]


def test_svg_one_colour_and_several(tmp_path, capsys):
    (tmp_path / "one.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"><circle fill="#1e3c8c" r="5"/>'
                                      '<path style="fill:#1e3c8c;stroke:none" d="M0 0"/></svg>')
    code, rep = run(capsys, tmp_path / "one.svg")
    assert code == 0
    text = (tmp_path / "one-light.svg").read_text()
    assert "#F5F5F5" in text and "1e3c8c" not in text and "stroke:none" in text
    (tmp_path / "two.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"><circle fill="#1e3c8c"/>'
                                      '<rect fill="#e67828"/></svg>')
    code, rep = run(capsys, tmp_path / "two.svg")
    assert code == 1 and "several colours" in rep["reason"]
    (tmp_path / "g.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"><linearGradient id="g"/>'
                                    '<circle fill="url(#g)"/></svg>')
    assert run(capsys, tmp_path / "g.svg")[0] == 1


def test_bad_inputs(tmp_path, capsys):
    assert run(capsys, tmp_path / "missing.png")[0] == 2
    (tmp_path / "x.gif").write_bytes(b"GIF89a")
    assert run(capsys, tmp_path / "x.gif")[0] == 2
    assert run(capsys, one_colour_png(tmp_path / "l.png"), "--colour", "nope")[0] == 2
