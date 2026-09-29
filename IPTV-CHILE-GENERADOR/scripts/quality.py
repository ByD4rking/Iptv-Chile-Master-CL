import json
import re
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from concurrent.futures import ThreadPoolExecutor, as_completed


BASE = Path(__file__).resolve().parent.parent

CHANNELS_FILE = BASE / "data" / "channels.json"
QUALITY_FILE = BASE / "data" / "quality.json"

TIMEOUT = 8
WORKERS = 15


def resolution_score(width, height):

    if not width or not height:
        return 0

    return int(height)


def detect_resolution(text):

    if not text:
        return None

    patterns = [
        r'RESOLUTION=(\d+)x(\d+)',
        r'(\d{3,4})x(\d{3,4})',
        r'(\d{3,4})p'
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if not match:
            continue

        if pattern.endswith("p"):

            height = int(
                match.group(1)
            )

            return {
                "width": None,
                "height": height,
                "resolution": f"{height}p"
            }

        width = int(
            match.group(1)
        )

        height = int(
            match.group(2)
        )

        return {
            "width": width,
            "height": height,
            "resolution":
                f"{width}x{height}"
        }

    return None


def detect_bandwidth(text):

    if not text:
        return None

    patterns = [
        r'BANDWIDTH=(\d+)',
        r'AVERAGE-BANDWIDTH=(\d+)'
    ]

    values = []

    for pattern in patterns:

        for match in re.finditer(
            pattern,
            text,
            re.IGNORECASE
        ):

            try:
                values.append(
                    int(match.group(1))
                )
            except ValueError:
                pass

    if not values:
        return None

    return max(values)


def inspect_url(item):

    channel = item["channel"]
    source = item["source"]

    url = source.get(
        "url",
        ""
    ).strip()

    result = {
        "channel_id":
            channel.get("id", ""),

        "channel_name":
            channel.get("name", ""),

        "url": url,

        "source":
            source.get("source", ""),

        "width": None,
        "height": None,
        "resolution": None,
        "bitrate": None,
        "quality_score": 0,
        "detected": False,
        "error": None
    }

    if not url:
        result["error"] = "URL vacía"
        return result

    try:

        request = Request(
            url,
            headers={
                "User-Agent":
                    "IPTV-CHILE-GENERADOR/QUALITY-1.0",
                "Accept":
                    "*/*"
            }
        )

        with urlopen(
            request,
            timeout=TIMEOUT
        ) as response:

            content = response.read(
                128 * 1024
            )

            text = content.decode(
                "utf-8",
                errors="ignore"
            )

            resolution = detect_resolution(
                text
            )

            bitrate = detect_bandwidth(
                text
            )

            if resolution:

                result["width"] = (
                    resolution["width"]
                )

                result["height"] = (
                    resolution["height"]
                )

                result["resolution"] = (
                    resolution["resolution"]
                )

                result["quality_score"] = (
                    resolution_score(
                        resolution["width"],
                        resolution["height"]
                    )
                )

                result["detected"] = True

            if bitrate:

                result["bitrate"] = bitrate

                # El bitrate sirve como desempate
                # sin permitir que un bitrate alto
                # haga parecer superior una resolución menor.
                result["quality_score"] = (
                    result["quality_score"] * 10000000
                    + bitrate
                )

    except HTTPError as error:

        result["error"] = (
            f"HTTP {error.code}"
        )

    except URLError as error:

        result["error"] = str(
            error.reason
        )

    except Exception as error:

        result["error"] = str(
            error
        )

    return result


def main():

    if not CHANNELS_FILE.exists():

        print(
            "No existe channels.json"
        )

        return

    with CHANNELS_FILE.open(
        "r",
        encoding="utf-8"
    ) as f:

        channels = json.load(f)

    tasks = []

    for channel in channels:

        for source in channel.get(
            "sources",
            []
        ):

            tasks.append({
                "channel": channel,
                "source": source
            })

    total = len(tasks)

    print("")
    print("=" * 60)
    print("IPTV-CHILE-GENERADOR - QUALITY SCANNER")
    print("=" * 60)
    print(
        f"Canales: {len(channels)}"
    )
    print(
        f"URLs:    {total}"
    )
    print(
        f"Workers: {WORKERS}"
    )
    print("")

    results = []

    with ThreadPoolExecutor(
        max_workers=WORKERS
    ) as executor:

        futures = [
            executor.submit(
                inspect_url,
                item
            )
            for item in tasks
        ]

        completed = 0

        for future in as_completed(
            futures
        ):

            result = future.result()

            results.append(
                result
            )

            completed += 1

            if (
                completed == 1
                or completed % 100 == 0
                or completed == total
            ):

                detected = sum(
                    1
                    for r in results
                    if r["detected"]
                )

                print(
                    f"[{completed}/{total}] "
                    f"Resoluciones detectadas: {detected}"
                )

    # --------------------------------------------------
    # AGRUPAR POR CANAL
    # --------------------------------------------------

    channels_quality = {}

    for result in results:

        channel_id = result[
            "channel_id"
        ]

        channels_quality.setdefault(
            channel_id,
            {
                "channel_name":
                    result["channel_name"],

                "sources": []
            }
        )

        channels_quality[
            channel_id
        ]["sources"].append(
            result
        )

    # --------------------------------------------------
    # SELECCIONAR MEJOR FUENTE
    # --------------------------------------------------

    for channel in channels_quality.values():

        available = [
            source
            for source in channel["sources"]
            if source["detected"]
        ]

        if available:

            available.sort(
                key=lambda x: (
                    x["height"] or 0,
                    x["bitrate"] or 0
                ),
                reverse=True
            )

            channel["best"] = (
                available[0]
            )

        else:

            channel["best"] = None

    output = {
        "total_channels":
            len(channels),

        "total_urls":
            total,

        "detected":
            sum(
                1
                for result in results
                if result["detected"]
            ),

        "results":
            results,

        "channels":
            channels_quality
    }

    with QUALITY_FILE.open(
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            output,
            f,
            ensure_ascii=False,
            indent=2
        )

    print("")
    print("=" * 60)
    print("QUALITY SCANNER TERMINADO")
    print("=" * 60)
    print(
        f"URLs analizadas:       {total}"
    )
    print(
        f"Resoluciones detectadas: "
        f"{output['detected']}"
    )
    print(
        f"Archivo: {QUALITY_FILE}"
    )
    print("")
    print(
        "La M3U NO fue modificada."
    )
    print("")


if __name__ == "__main__":
    main()
