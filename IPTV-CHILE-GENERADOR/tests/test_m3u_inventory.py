from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from m3u_inventory import clean_url, key_name, parse_m3u


def test_parse_and_dedupe_input_shape():
    text = """#EXTM3U
#EXTINF:-1 tvg-name="Wipeout" group-title="Entertainment",Wipeout (720p)
#EXTVLCOPT:http-referrer=https://teleon.tv/
https://example.test/wipeout.m3u8?token=abc
#EXTINF:-1 group-title="Anime",Dragon Ball
https://example.test/dragon.m3u8
#EXTINF:-1 group-title="Anime",Dragon Ball
https://example.test/dragon.m3u8
"""
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "test.m3u"
        path.write_text(text, encoding="utf-8")
        entries = parse_m3u(path)

    assert len(entries) == 3
    assert entries[0]["name"] == "Wipeout (720p)"
    assert entries[0]["headers"]["http-referrer"] == "https://teleon.tv/"
    assert clean_url(entries[0]["url"]).startswith("https://example.test/")
    assert key_name("Dragon Ball (1080p)") == "dragon ball"


def test_non_http_rejected():
    assert clean_url("#comment") == ""
    assert clean_url("file:///tmp/a.m3u8") == ""


if __name__ == "__main__":
    test_parse_and_dedupe_input_shape()
    test_non_http_rejected()
    print("M3U INVENTORY TESTS OK")
