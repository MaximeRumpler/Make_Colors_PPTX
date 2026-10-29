"""The skill folder must stay a valid, self-contained Agent Skill."""
import json
import re

from conftest import ROOT, SKILL, make_clean_dir


def _frontmatter(text):
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    assert m, "SKILL.md must start with YAML frontmatter"
    out = {}
    for line in m.group(1).splitlines():
        if re.match(r"^[A-Za-z_-]+:", line):
            k, _, v = line.partition(":")
            out[k.strip()] = v.strip()
    return out


def test_skill_md():
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    fm = _frontmatter(text)
    assert fm["name"] == SKILL.name == "make-colors-pptx"
    assert 50 < len(fm["description"]) <= 1024
    assert "charte" in fm["description"]  # French triggers
    assert text.count("\n") < 160


def test_referenced_files_exist():
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    for rel in set(re.findall(r"`((?:references|scripts|assets)/[\w./-]+)`", text)):
        assert (SKILL / rel).exists(), f"SKILL.md mentions {rel} but it does not exist"


STDLIB = {"__future__", "argparse", "collections", "colorsys", "copy", "io", "itertools", "json", "math", "os",
          "pathlib", "re", "shutil", "subprocess", "sys", "zipfile"}
THIRD_PARTY = {"pptx", "PIL", "lxml"}  # python-pptx, Pillow, lxml: nothing else to install


def test_self_contained_and_light():
    for py in (SKILL / "scripts").glob("*.py"):
        src = py.read_text(encoding="utf-8")
        assert "parent.parent.parent" not in src, py.name
        for mod in re.findall(r"^\s*(?:from|import) (\w+)", src, re.M):
            local = (SKILL / "scripts" / (mod + ".py")).is_file()
            assert mod in STDLIB | THIRD_PARTY or local, (py.name, mod)
    reqs = (SKILL / "requirements.txt").read_text().split()
    assert {r.split(">=")[0] for r in reqs} == {"python-pptx", "Pillow", "lxml"}


def test_contract_copy_matches_make_clean():
    ours = json.loads((SKILL / "assets" / "theme-contract.json").read_text(encoding="utf-8"))
    assert ours["version"] == 1 and ours["ramp"]["min_step"] == 1.1
    mc = make_clean_dir()
    if mc and (mc / "assets" / "theme-contract.json").is_file():
        theirs = json.loads((mc / "assets" / "theme-contract.json").read_text(encoding="utf-8"))
        assert ours["version"] == theirs["version"]
        assert ours["tokens"] == theirs["tokens"] and ours["ramp"] == theirs["ramp"]
        # Same rules; the order follows usage counts, which change whenever Make_Clean adds a visual.
        assert sorted((p["text"], p["on"], p["min_ratio"]) for p in ours["pairs"]) == \
               sorted((p["text"], p["on"], p["min_ratio"]) for p in theirs["pairs"])


def test_no_private_links_in_readme():
    """Public pages never link to a private repository (Make_Style_PPTX is private until released)."""
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    links = re.findall(r"\]\((https?://[^)]+)\)", readme)
    assert not [u for u in links if "Make_Style_PPTX" in u]
