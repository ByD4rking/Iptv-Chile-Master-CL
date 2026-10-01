import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GOD = ROOT / "IPTV-CHILE-MAESTRA_GOD.m3u"

RECONNECT = "#EXTVLCOPT:http-reconnect=true"
CACHING = "#EXTVLCOPT:network-caching=1500"


def is_pluto(url: str) -> bool:
    u = (url or "").lower()
    return (
        "pluto.tv" in u
        or ("stitcher" in u and "pluto" in u)
        or ("pluto" in u and ("/channel/" in u or "/channels/" in u))
    )


def main():
    if not GOD.is_file():
        raise SystemExit("GOD: no existe IPTV-CHILE-MAESTRA_GOD.m3u")

    raw = GOD.read_bytes()
    lines = raw.splitlines(keepends=True)
    newline = b"\r\n" if b"\r\n" in raw else b"\n"
    out = []
    blocks = 0
    changed = 0

    for line in lines:
        out.append(line)
        if not line.lstrip().startswith(b"#EXTINF:"):
            continue

        blocks += 1
        # Look ahead for the URL belonging to this EXTINF block.
        idx = len(out)
        url = None
        while idx < len(lines):
            candidate = lines[idx].strip()
            if candidate.startswith((b"http://", b"https://")):
                url = candidate.decode("utf-8", "ignore")
                break
            if candidate.startswith(b"#EXTINF:"):
                break
            idx += 1

        if not url or is_pluto(url):
            continue

        existing = {x.decode("utf-8", "ignore").strip() for x in out[-8:]}
        additions = []
        if RECONNECT not in existing:
            additions.append(RECONNECT.encode() + newline)
        if CACHING not in existing:
            additions.append(CACHING.encode() + newline)

        if additions:
            # Remove the just-appended EXTINF and reinsert directives immediately after it.
            out[-1:] = [out[-1], *additions]
            changed += 1

    GOD.write_bytes(b"".join(out))
    print(f"GOD: {blocks} bloques EXTINF auditados; {changed} bloques actualizados.")
    print("GOD: Pluto omitido; se conserva su mecanismo de recuperación existente.")


if __name__ == "__main__":
    main()
