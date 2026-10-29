import shutil

import pytest
from PIL import Image, ImageDraw

import build_theme
import preview_deck
from conftest import make_clean_dir


@pytest.fixture
def make_clean():
    mc = make_clean_dir()
    if not mc:
        pytest.skip("Make_Clean_PPTX not available")
    return mc


def _logo(path):
    im = Image.new("RGBA", (480, 150), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse((10, 15, 130, 135), fill=(29, 78, 137, 255))
    d.rectangle((150, 55, 460, 95), fill=(29, 78, 137, 255))
    im.save(path)
    return path


def test_missing_make_clean(tmp_path, monkeypatch):
    monkeypatch.setattr(preview_deck, "find_make_clean", lambda explicit=None: None)
    res = preview_deck.preview(tmp_path / "x.potx", out_dir=tmp_path)
    assert res["code"] == 3 and "Make_Clean_PPTX not found" in res["error"]


def test_build_and_lint_without_render(tmp_path, harbour_roles, make_clean):
    rep = build_theme.build(harbour_roles, tmp_path / "brand")
    res = preview_deck.preview(rep["variants"]["light"]["files"][0], _logo(tmp_path / "logo.png"),
                               out_dir=tmp_path / "prev", make_clean=make_clean, render=False)
    assert "error" not in res, res
    assert set(res["decks"]) == {"before", "after"}
    assert res["lint"].get("errors") == []
    contrast = res["lint"].get("contrast")
    if contrast is not None:  # Make_Clean >= 1.1
        assert contrast["failing_shapes"] == 0 and contrast["theme_findings"] == []


@pytest.mark.skipif(not (shutil.which("soffice") and shutil.which("pdftoppm")), reason="LibreOffice not installed")
def test_before_after_sheet(tmp_path, harbour_roles, make_clean):
    rep = build_theme.build({**harbour_roles, "variants": ["dark"]}, tmp_path / "brand")
    res = preview_deck.preview(rep["variants"]["dark"]["files"][0], out_dir=tmp_path / "prev",
                               make_clean=make_clean)
    assert res["render"] == "done", res
    with Image.open(res["before_after"]) as im:
        assert im.height > im.width / 2
