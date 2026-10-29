import colorsys
import json
import sys
import zipfile

import pytest
from lxml import etree

import build_theme
from _colour import check_theme, load_contract, load_theme, rgb_to_hex
from conftest import make_clean_dir

CONTRACT = load_contract()


def hexes():
    """A sweep of brand primaries: 12 hues, from greyish to saturated, dark to light."""
    out = []
    for h in range(0, 360, 30):
        for s, lum in ((0.9, 0.45), (0.6, 0.3), (0.35, 0.6), (1.0, 0.55)):
            out.append("#" + rgb_to_hex(colorsys.hls_to_rgb(h / 360, lum, s)))
    return out


@pytest.mark.parametrize("primary", hexes())
def test_every_primary_gives_two_passing_variants(primary, tmp_path):
    rep = build_theme.build({"name": "Sweep", "primary": primary}, tmp_path)
    assert rep["ok"], rep["variants"]
    for v in ("light", "dark"):
        theme = load_theme(rep["variants"][v]["files"][0])
        res = check_theme(theme, CONTRACT)
        assert res["ok"], (v, res["findings"])
        assert res["dark"] is (v == "dark")


@pytest.mark.parametrize("extra", [
    {"secondary": "#2A9D8F", "ramp_drift": True},
    {"tint_neutrals": True},
    {"neutrals": {"text": "#0E1A2B", "surface": "#EEF2F6"}},
    {"dark": {"background": "#0B1320", "text": "#FFFFFF"}},
])
def test_options_still_pass(extra, tmp_path, harbour_roles):
    rep = build_theme.build({**harbour_roles, **extra}, tmp_path)
    assert rep["ok"], rep["variants"]


def test_primary_kept_exactly_and_files(tmp_path, harbour_roles):
    rep = build_theme.build(harbour_roles, tmp_path, thmx=True)
    light, dark = rep["variants"]["light"], rep["variants"]["dark"]
    assert light["primary_slot"] == "accent2" and light["colors"]["accent2"] == "1D4E89"
    assert dark["primary_slot"] and dark["colors"][dark["primary_slot"]] == "1D4E89"
    assert [p.rsplit("/", 1)[-1] for p in light["files"]] == ["demo-harbour.potx", "demo-harbour.thmx"]
    with zipfile.ZipFile(light["files"][0]) as z:
        assert b"presentationml.template.main+xml" in z.read("[Content_Types].xml")
    with zipfile.ZipFile(dark["files"][0]) as z:
        cm = etree.fromstring(z.read("ppt/slideMasters/slideMaster1.xml")).find(
            "{http://schemas.openxmlformats.org/presentationml/2006/main}clrMap")
        assert cm.get("bg1") == "dk1" and cm.get("tx1") == "lt1"
    thmx = load_theme(light["files"][1])
    assert thmx["colors"] == light["colors"] and thmx["fonts"] == {"major": "Georgia", "minor": "Arial"}
    # secondary orange is too faint for links on white: darkened, and said so
    assert light["colors"]["hlink"] != "E07A1F" and any("secondary" in n for n in light["notes"])
    assert rep["deck_json"] == {"theme": light["files"][0]}


def test_unfit_primary_is_explained(tmp_path):
    rep = build_theme.build({"name": "Demo Lemon", "primary": "#FFE14D", "variants": ["light"]}, tmp_path)
    light = rep["variants"]["light"]
    assert rep["ok"]
    assert light["primary_slot"] in (None, "accent5", "accent6")
    if light["primary_slot"] is None:
        assert "cannot sit on the ramp" in light["notes"][0]


def test_too_light_text_colour_is_reported(tmp_path):
    """Captions are the text colour lightened (muted): a mid-dark text colour makes them too faint."""
    rep = build_theme.build({"name": "Demo", "primary": "#1D4E89", "neutrals": {"text": "#2B2B2B"},
                             "variants": ["light"]}, tmp_path)
    assert not rep["ok"]
    assert any(f.startswith("muted text on paper") for f in rep["variants"]["light"]["findings"])


def test_given_accents_are_checked_not_fixed(tmp_path):
    rainbow = ["#D62828", "#F77F00", "#2A9D8F", "#FCBF49", "#6A4C93", "#1B4332"]
    rep = build_theme.build({"name": "Demo Rainbow", "primary": "#D62828", "accents": rainbow,
                             "variants": ["light"]}, tmp_path)
    assert not rep["ok"]
    assert any("not a ramp" in f for f in rep["variants"]["light"]["findings"])


def test_uncommon_font_gets_fallback_hint(tmp_path):
    rep = build_theme.build({"name": "Demo", "primary": "#1D4E89", "fonts": {"major": "Demo Display Sans"}},
                            tmp_path)
    assert rep["fonts"] == {"major": "Demo Display Sans", "minor": "Demo Display Sans"}
    assert rep["font_notes"] and rep["deck_json"]["theme_fonts_fallback"] == "Arial"


def test_reproducible(tmp_path, harbour_roles):
    a = build_theme.build(harbour_roles, tmp_path / "a")
    b = build_theme.build(harbour_roles, tmp_path / "b")
    for v in ("light", "dark"):
        pa, pb = a["variants"][v]["files"][0], b["variants"][v]["files"][0]
        assert open(pa, "rb").read() == open(pb, "rb").read()


def test_cli_exit_codes(tmp_path, harbour_roles, capsys):
    roles = tmp_path / "roles.json"
    roles.write_text(json.dumps(harbour_roles))
    assert build_theme.main([str(roles), "--out-dir", str(tmp_path / "out")]) == 0
    roles.write_text(json.dumps({"name": "x"}))
    assert build_theme.main([str(roles), "--out-dir", str(tmp_path / "out")]) == 2
    assert "primary" in capsys.readouterr().out


def test_make_clean_accepts_the_theme(tmp_path, harbour_roles):
    """Round trip with Make_Clean's own loader and contract check (skipped when it is not available)."""
    mc = make_clean_dir()
    if not mc:
        pytest.skip("Make_Clean_PPTX not available")
    sys.path.insert(0, str(mc / "scripts"))
    try:
        from _contrast import read_theme, theme_findings
        from _theme import load_theme_source
    except ImportError as exc:
        pytest.skip("Make_Clean_PPTX has no theme loader (%s)" % exc)
    contract = json.loads((mc / "assets" / "theme-contract.json").read_text(encoding="utf-8"))
    rep = build_theme.build(harbour_roles, tmp_path, thmx=True)
    files = rep["variants"]["light"]["files"] + rep["variants"]["dark"]["files"]
    for f in files:
        src = load_theme_source(f)
        theme = read_theme(etree.tostring(src["root"]))
        assert theme_findings(theme, contract, src["clrmap"]) == [], f
    assert load_theme_source(rep["variants"]["dark"]["files"][0])["clrmap"]["bg1"] == "dk1"
