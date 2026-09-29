import json
from pathlib import Path
from datetime import datetime, timezone


BASE = Path(__file__).resolve().parent.parent

CHANNELS_FILE = BASE / "data" / "channels.json"
STATUS_FILE = BASE / "data" / "status.json"

OUTPUT_FILE = BASE / "IPTV-CHILE-GENERADOR.m3u"


def load_json(path, default):

    if not path.exists():
        return default

    try:

        with path.open(
            "r",
            encoding="utf-8-sig"
        ) as f:

            return json.load(f)

    except Exception:

        return default


def clean(value):

    if value is None:
        return ""

    return str(value).replace(
        "\n",
        " "
    ).replace(
        "\r",
        " "
    ).strip()


def main():

    channels = load_json(
        CHANNELS_FILE,
        []
    )

    status = load_json(
        STATUS_FILE,
        {}
    )

    results = status.get(
        "results",
        []
    )

    online_urls = {
        item.get("url"): item
        for item in results
        if item.get("online")
        and item.get("url")
    }

    lines = []

    lines.append(
        "#EXTM3U"
    )

    generated = 0
    analyzed = 0

    for channel in channels:

        analyzed += 1

        channel_name = clean(
            channel.get(
                "name",
                "Canal"
            )
        )

        group = clean(
            channel.get(
                "group",
                ""
            )
        )

        logo = clean(
            channel.get(
                "logo",
                ""
            )
        )

        sources = channel.get(
            "sources",
            []
        )

        selected = None

        for source in sources:

            url = clean(
                source.get(
                    "url",
                    ""
                )
            )

            if url in online_urls:

                selected = (
                    url,
                    source
                )

                break

        if selected is None:
            continue

        url, source = selected

        attributes = []

        attributes.append(
            f'tvg-name="{channel_name}"'
        )

        if logo:

            attributes.append(
                f'tvg-logo="{logo}"'
            )

        if group:

            attributes.append(
                f'group-title="{group}"'
            )

        extinf = (
            "#EXTINF:-1 "
            + " ".join(attributes)
            + ","
            + channel_name
        )

        lines.append(
            extinf
        )

        lines.append(
            url
        )

        generated += 1

    content = (
        "\n".join(lines)
        + "\n"
    )

    # IMPORTANTE:
    # siempre se escribe sobre EL MISMO archivo.
    OUTPUT_FILE.write_text(
        content,
        encoding="utf-8"
    )

    print("")
    print("=" * 60)
    print("IPTV-CHILE-GENERADOR - GENERATE")
    print("=" * 60)
    print(
        f"Canales analizados: {analyzed}"
    )
    print(
        f"Canales generados:  {generated}"
    )
    print(
        f"Sin fuente online:   "
        f"{analyzed - generated}"
    )
    print(
        f"Archivo: {OUTPUT_FILE}"
    )
    print(
        f"Tamaño:  {OUTPUT_FILE.stat().st_size} bytes"
    )
    print("")
    print(
        "Última actualización:",
        datetime.now(
            timezone.utc
        ).isoformat()
    )
    print("")
    print(
        "LISTA FIJA: no se crean archivos M3U adicionales."
    )


if __name__ == "__main__":
    main()
