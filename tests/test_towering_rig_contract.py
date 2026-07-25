import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_towering_rig_is_registered_as_a_15_second_portrait_reel():
    root = (ROOT / "remotion-shorts/src/Root.tsx").read_text()
    assert 'id="ToweringRig"' in root
    assert "durationInFrames={450}" in root
    assert "width={1080}" in root
    assert "height={1920}" in root
    assert 'from "./ToweringRig"' in root


def test_cc2400_props_lock_the_verified_facts_and_green_brand():
    props = json.loads(
        (ROOT / "remotion-shorts/props/gkmex-cc2400-11200h-sale.json").read_text()
    )
    assert props["headline"] == "TEREX DEMAG CC 2400-1"
    assert props["specLine1"] == "2007 · 400 T · 11,200 HOURS"
    assert props["specLine2"] == "84 M BOOM · 84 M LUFFING JIB"
    assert props["specLine3"] == "12 M FIXED JIB · 30 M SUPERLIFT MAST"
    assert props["price"] == "€1,250,000"
    assert props["sellerName"] == "Gkmex"
    assert props["phone"] == "+90 545 686 72 77"
    assert props["email"] == "gkm@gkmex.com"
    assert props["accent"].lower() == "#16a34a"


def test_public_reel_copy_excludes_forbidden_scope():
    text = (
        (ROOT / "remotion-shorts/src/ToweringRig.tsx").read_text()
        + (ROOT / "remotion-shorts/props/gkmex-cc2400-11200h-sale.json").read_text()
    ).lower()
    for forbidden in ("#e8a430", "turkey", "türkiye", "rental"):
        assert forbidden not in text
