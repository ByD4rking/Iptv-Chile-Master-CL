import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from teleon_classifier import classify


def test_anime():
    result = classify("Dragon Ball Super", "Anime", "dragon-ball-super")
    assert result["category"] == "Anime"
    assert "dragon ball" in result["matched_terms"]


def test_competition():
    result = classify("American Ninja Warrior", "Entertainment", "american-ninja-warrior")
    assert result["category"] == "Competencia y entretenimiento"
    assert "ninja warrior" in result["matched_terms"]


def test_wipeout():
    result = classify("Wipeout", "Game Show", "wipeout")
    assert result["profile"] == "competition_entertainment"


def test_unknown():
    result = classify("Canal desconocido", "", "")
    assert result["category"] == "Sin clasificar"
    assert result["confidence"] == 0


if __name__ == "__main__":
    test_anime()
    test_competition()
    test_wipeout()
    test_unknown()
    print("TELEON CLASSIFIER TESTS OK")
