import json
from pathlib import Path
from urllib.request import Request, urlopen


BASE = Path(__file__).resolve().parent.parent

CONFIG = BASE / "config" / "sources.json"
OUTPUT = BASE / "data" / "channels.json"

TIMEOUT = 20


def load_json(path, default):

    if not path.exists():
        return default

    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def save_json(path, data):

    with path.open("w", encoding="utf-8") as f:
        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=2
        )


def read_source(source):

    # Fuente local
    local_path = source.get("path")

    if local_path:

        path = Path(local_path)

        if not path.exists():
            raise FileNotFoundError(
                f"No existe: {path}"
            )

        return path.read_text(
            encoding="utf-8-sig",
            errors="replace"
        )

    # Fuente HTTP/HTTPS
    url = source.get("url", "").strip()

    if url:

        request = Request(
            url,
            headers={
                "User-Agent":
                "IPTV-CHILE-GENERADOR/1.0"
            }
        )

        with urlopen(
            request,
            timeout=TIMEOUT
        ) as response:

            return response.read().decode(
                "utf-8",
                errors="replace"
            )

    raise ValueError(
        "La fuente no tiene 'path' ni 'url'"
    )


def parse_m3u(text, source_name):

    channels = []

    current = None

    for raw_line in text.splitlines():

        line = raw_line.strip()

        if not line:
            continue

        if line.startswith("#EXTINF:"):

            name = line.split(
                ",",
                1
            )[-1].strip()

            current = {
                "name": name,
                "group": "",
                "logo": "",
                "url": "",
                "source": source_name
            }

            if 'group-title="' in line:

                current["group"] = line.split(
                    'group-title="',
                    1
                )[1].split(
                    '"',
                    1
                )[0]

            if 'tvg-logo="' in line:

                current["logo"] = line.split(
                    'tvg-logo="',
                    1
                )[1].split(
                    '"',
                    1
                )[0]

            continue

        if (
            current
            and not line.startswith("#")
            and (
                line.startswith("http://")
                or line.startswith("https://")
            )
        ):

            current["url"] = line

            channels.append(current)

            current = None

    return channels


def main():

    config = load_json(
        CONFIG,
        {"sources": []}
    )

    sources = config.get(
        "sources",
        []
    )

    if not sources:

        print("")
        print("No hay fuentes configuradas.")
        return

    all_entries = []

    print("")
    print("=" * 60)
    print("IPTV-CHILE-GENERADOR - COLLECTOR LOCAL")
    print("=" * 60)

    for source in sources:

        name = source.get(
            "name",
            "FUENTE"
        )

        print("")
        print(
            f"[+] FUENTE: {name}"
        )

        try:

            content = read_source(
                source
            )

            entries = parse_m3u(
                content,
                name
            )

            print(
                f"    Entradas encontradas: {len(entries)}"
            )

            all_entries.extend(
                entries
            )

        except Exception as error:

            print(
                f"    ERROR: {error}"
            )

    # --------------------------------------------------
    # DEDUPLICAR POR NOMBRE
    # --------------------------------------------------

    grouped = {}

    for entry in all_entries:

        name = entry.get(
            "name",
            ""
        ).strip()

        url = entry.get(
            "url",
            ""
        ).strip()

        if not name or not url:
            continue

        key = name.lower()

        if key not in grouped:

            grouped[key] = {
                "id": key,
                "name": name,
                "group": entry.get(
                    "group",
                    ""
                ),
                "logo": entry.get(
                    "logo",
                    ""
                ),
                "sources": []
            }

        existing = {
            item.get("url")
            for item in grouped[key]["sources"]
        }

        if url not in existing:

            grouped[key]["sources"].append({
                "url": url,
                "source": entry.get(
                    "source",
                    ""
                )
            })

    channels = list(
        grouped.values()
    )

    save_json(
        OUTPUT,
        channels
    )

    total_urls = sum(
        len(channel["sources"])
        for channel in channels
    )

    print("")
    print("=" * 60)
    print("COLLECTOR TERMINADO")
    print("=" * 60)
    print(
        f"Entradas originales: {len(all_entries)}"
    )
    print(
        f"Canales únicos:       {len(channels)}"
    )
    print(
        f"URLs conservadas:     {total_urls}"
    )
    print(
        f"Archivo: {OUTPUT}"
    )
    print("")


if __name__ == "__main__":
    main()
