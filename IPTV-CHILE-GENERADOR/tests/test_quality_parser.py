from pathlib import Path
import sys

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE / "scripts"))

from quality import parse_master_playlist


def main():
    malformed = """#EXTM3U
#EXT-X-STREAM-INF:BANDWIDTH=100000,RESOLUTION=640x360
# comentario sin URI
#EXT-X-STREAM-INF:BANDWIDTH=500000,RESOLUTION=1280x720
video-720.m3u8
"""
    variants = parse_master_playlist(malformed, "https://example.test/master.m3u8")
    assert len(variants) == 1, "El parser asoció una URI posterior a una variante sin URI."
    assert variants[0]["url"] == "https://example.test/video-720.m3u8"
    assert variants[0]["height"] == 720

    valid = """#EXTM3U
#EXT-X-STREAM-INF:BANDWIDTH=100000,RESOLUTION=640x360
video-360.m3u8
#EXT-X-STREAM-INF:BANDWIDTH=500000,RESOLUTION=1280x720
video-720.m3u8
"""
    variants = parse_master_playlist(valid, "https://example.test/master.m3u8")
    assert len(variants) == 2
    assert variants[0]["height"] == 720
    assert variants[1]["height"] == 360
    print("QUALITY PARSER TESTS OK")


if __name__ == "__main__":
    main()
