from __future__ import annotations

import json
import tempfile
from pathlib import Path

from scripts import health_principal as h


def main() -> None:
    assert h._cooldown(4) == 0
    assert h._cooldown(5) == 60
    assert h._cooldown(13) <= h.MAX_COOLDOWN

    ok = {"ok": True, "latency_ms": 200, "kind": "hls", "resolution": "1920x1080", "bandwidth": 5000000}
    bad = {"ok": False, "latency_ms": None, "kind": "hls"}
    assert 0 <= h._score(ok, {}, 0) <= 100
    assert 0 <= h._score(bad, {}, 5) <= 100

    # A recovery must still respect recent historical stability.
    previous = {"history": [{"ok": False}, {"ok": False}, {"ok": True}]}
    recovery = h._score(ok, previous, 0)
    assert recovery < h._score(ok, {}, 0)

    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "test.m3u"
        p.write_text(
            '#EXTM3U\n#EXTINF:-1 tvg-id="x" tvg-name="Canal X" group-title="Chile",Canal X\nhttps://example.invalid/live.m3u8\n',
            encoding="utf-8",
        )
        entries = h.parse_m3u(p)
        assert len(entries) == 1
        assert entries[0]["url"] == "https://example.invalid/live.m3u8"

    assert h.MAX_HISTORY_SAMPLES == 5
    assert h.ATTEMPTS == 3
    print("SELFTEST OK: Health principal parser, score, cooldown y límites.")


if __name__ == "__main__":
    main()
