import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GOD = ROOT / "IPTV-CHILE-MAESTRA_GOD.m3u"

RECONNECT = "#EXTVLCOPT:http-reconnect=true"
CACHING = "#EXTVLCOPT:network-caching=5000"


def is_pluto(url: str) -> bool:
    u = (url or "").lower()
    return (
        "pluto.tv" in u
        or ("stitcher" in u and "pluto" in u)
        or ("pluto" in u and ("/channel/" in u or "/channels/" in u))
    )


def process_block(block: list[str], newline: str) -> tuple[list[str], bool]:
    """Return one EXTINF block, adding reconnect directives only to non-Pluto."""
    if not block or not block[0].lstrip().startswith("#EXTINF:"):
        return block, False

    url = ""
    for line in block[1:]:
        candidate = line.strip()
        if candidate.startswith(("http://", "https://")):
            url = candidate
            break
        if candidate.startswith("#EXTINF:"):
            break

    if not url or is_pluto(url):
        return block, False

    body = [
        line for line in block[1:]
        if line.strip() != RECONNECT
        and not re.fullmatch(
            r"#EXTVLCOPT:network-caching=\d+",
            line.strip(),
            flags=re.IGNORECASE,
        )
    ]
    return [block[0], RECONNECT + newline, CACHING + newline, *body], True


def main() -> None:
    if not GOD.is_file():
        raise SystemExit("GOD: no existe IPTV-CHILE-MAESTRA_GOD.m3u")

    raw = GOD.read_bytes()
    lines = raw.splitlines(keepends=True)
    newline = "\r\n" if b"\r\n" in raw else "\n"

    starts = [i for i, line in enumerate(lines) if line.lstrip().startswith(b"#EXTINF:")]
    if not starts:
        raise SystemExit("GOD: no contiene bloques #EXTINF.")

    output: list[str] = []
    blocks = 0
    changed = 0
    pluto = 0

    prefix = lines[:starts[0]]
    output.extend(prefix)

    for n, start in enumerate(starts):
        end = starts[n + 1] if n + 1 < len(starts) else len(lines)
        block = [line.decode("utf-8", "strict") for line in lines[start:end]]
        processed, did_change = process_block(block, newline)
        output.extend(line.encode("utf-8") for line in processed)
        blocks += 1
        if did_change:
            changed += 1
        else:
            text = "".join(block)
            if "pluto.tv" in text.lower() or ("stitcher" in text.lower() and "pluto" in text.lower()):
                pluto += 1

    GOD.write_bytes(b"".join(output))

    print(f"GOD: {blocks} bloques EXTINF auditados.")
    print(f"GOD: {changed} bloques no-Pluto con reconexión aplicada/verificada.")
    print(f"GOD: {pluto} bloques Pluto omitidos.")
    print("GOD: no se cambian URLs, nombres ni asociación entre canales.")


if __name__ == "__main__":
    main()
