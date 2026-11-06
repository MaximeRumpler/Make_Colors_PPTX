from PIL import Image

import build_theme
import check_theme


def test_check_and_preview(tmp_path, harbour_roles):
    rep = build_theme.build(harbour_roles, tmp_path)
    res = check_theme.run(rep["variants"]["light"]["files"][0])
    assert res["ok"] and not res["dark"]
    assert {v["view"] for v in res["views"]} == {"greyscale", "protanopia", "deuteranopia", "tritanopia"}
    assert all(v["ok"] for v in res["views"])
    png = check_theme.preview(rep["variants"]["dark"]["files"][0], tmp_path / "dark.png")
    with Image.open(png) as im:
        assert im.width > 1000 and im.height > 600


def test_rainbow_fails(tmp_path, capsys):
    rep = build_theme.build({"name": "Demo Rainbow", "primary": "#D62828", "variants": ["light"],
                             "accents": ["#D62828", "#F77F00", "#2A9D8F", "#FCBF49", "#6A4C93", "#1B4332"]},
                            tmp_path)
    path = rep["variants"]["light"]["files"][0]
    assert check_theme.main([path]) == 1
    out = capsys.readouterr().out
    assert "not a ramp" in out and "Finding:" in out


def test_unreadable_file(tmp_path):
    bad = tmp_path / "x.pptx"
    bad.write_text("not a zip")
    assert check_theme.main([str(bad)]) == 2


def test_failing_pair_names_the_roles_key_and_a_passing_value(tmp_path, harbour_roles):
    import _colour as C
    rep = build_theme.build(harbour_roles, tmp_path)
    theme = C.load_theme(rep["variants"]["light"]["files"][0])
    theme["colors"]["lt2"] = "8A8A8A"  # a dark surface under the muted text
    res = C.check_theme(theme)
    hints = [f for f in res["findings"] if "To fix: change neutrals." in f]
    assert hints
    new = hints[0].split("for example to #")[1].rstrip(")")
    assert len(new) == 6
