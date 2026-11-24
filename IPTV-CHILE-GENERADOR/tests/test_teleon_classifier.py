import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from teleon_classifier import classify
from teleon_discovery import recovery_probe_due


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



def test_quarantine_recovery_probe_interval():
    now = datetime.now(timezone.utc)
    assert not recovery_probe_due(
        {"last_probe": (now - timedelta(hours=5, minutes=59)).isoformat()},
        now,
    )
    assert recovery_probe_due(
        {"last_probe": (now - timedelta(hours=6)).isoformat()},
        now,
    )
    assert not recovery_probe_due(
        {"last_failure": (now - timedelta(hours=2)).isoformat()},
        now,
    )
    assert recovery_probe_due({"last_probe": "invalid"}, now)

if __name__ == "__main__":
    test_anime()
    test_competition()
    test_wipeout()
    test_unknown()
    test_quarantine_recovery_probe_interval()
    print("TELEON CLASSIFIER TESTS OK")
