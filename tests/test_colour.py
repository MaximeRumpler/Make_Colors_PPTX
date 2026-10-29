import pytest

from _colour import at_luminance, describe, hex_to_rgb, luminance, parse_hex, ratio, simulate


def test_wcag_basics():
    assert ratio((0, 0, 0), (1, 1, 1)) == pytest.approx(21.0)
    assert ratio(hex_to_rgb("777777"), (1, 1, 1)) == pytest.approx(4.48, abs=0.01)
    assert luminance((1, 1, 1)) == pytest.approx(1.0)


def test_parse_hex():
    assert parse_hex("#18e") == "1188EE"
    assert parse_hex(" 1d4e89 ") == "1D4E89"
    with pytest.raises(ValueError):
        parse_hex("navy")


@pytest.mark.parametrize("target", [0.01, 0.1, 0.26, 0.5, 0.79])
def test_at_luminance_hits_target(target):
    assert luminance(at_luminance(0.6, 0.7, target)) == pytest.approx(target, abs=0.006)


def test_greyscale_keeps_luminance_and_cvd_changes_hue():
    red = hex_to_rgb("D62828")
    grey = simulate(red, "greyscale")
    assert len(set(round(c, 6) for c in grey)) == 1
    assert luminance(grey) == pytest.approx(luminance(red), abs=0.003)
    green = hex_to_rgb("2A9D3A")
    # red and green get much closer for someone with deuteranopia
    from _colour import delta_e
    assert delta_e(simulate(red, "deuteranopia"), simulate(green, "deuteranopia")) < delta_e(red, green) / 2


def test_describe():
    assert describe(hex_to_rgb("1D4E89")) == "dark blue"
    assert describe(hex_to_rgb("FFFFFF")) == "white"
    assert describe(hex_to_rgb("E07A1F")) == "orange"
