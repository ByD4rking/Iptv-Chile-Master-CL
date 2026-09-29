import json
import time
from pathlib import Path
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


BASE = Path(__file__).resolve().parent.parent

CHANNELS_FILE = BASE / "data" / "channels.json"
STATUS_FILE = BASE / "data" / "status.json"
HISTORY_FILE = BASE / "data" / "history.json"

TIMEOUT = 8
WORKERS = 25


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


def save_json(path, data):

    with path.open(
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=2
        )


def check_url(item):

    channel = item["channel"]
    source = item["source"]

    url = source.get(
        "url",
        ""
    ).strip()

    result = {
        "channel_id": channel.get(
            "id",
            ""
        ),
        "channel_name": channel.get(
            "name",
            ""
        ),
        "url": url,
        "source": source.get(
            "source",
            ""
        ),
        "online": False,
        "status_code": None,
        "response_time_ms": None,
        "error": None
    }

    if not (
        url.startswith("http://")
        or url.startswith("https://")
    ):

        result["error"] = (
            "URL no compatible"
        )

        return result

    start = time.perf_counter()

    try:

        request = Request(
            url,
            headers={
                "User-Agent":
                "IPTV-CHILE-GENERADOR/2.0",
                "Accept":
                "*/*"
            }
        )

        with urlopen(
            request,
            timeout=TIMEOUT
        ) as response:

            result["status_code"] = (
                response.status
            )

            response.read(1024)

            elapsed = (
                time.perf_counter()
                - start
            ) * 1000

            result["response_time_ms"] = round(
                elapsed,
                2
            )

            if 200 <= response.status < 400:

                result["online"] = True

    except HTTPError as error:

        result["status_code"] = error.code
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

    channels = load_json(
        CHANNELS_FILE,
        []
    )

    history = load_json(
        HISTORY_FILE,
        {}
    )

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
    print("IPTV-CHILE-GENERADOR - CHECK V2")
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
                check_url,
                item
            )
            for item in tasks
        ]

        completed = 0

        for future in as_completed(
            futures
        ):

            try:

                result = future.result()

            except Exception as error:

                result = {
                    "channel_id": "",
                    "channel_name": "",
                    "url": "",
                    "source": "",
                    "online": False,
                    "status_code": None,
                    "response_time_ms": None,
                    "error": str(error)
                }

            results.append(
                result
            )

            completed += 1

            if (
                completed == 1
                or completed % 100 == 0
                or completed == total
            ):

                online = sum(
                    1
                    for r in results
                    if r["online"]
                )

                print(
                    f"[{completed}/{total}] "
                    f"Online acumulados: {online}"
                )

    # --------------------------------------------------
    # RESUMEN
    # --------------------------------------------------

    online_count = sum(
        1
        for result in results
        if result["online"]
    )

    offline_count = (
        len(results)
        - online_count
    )

    # --------------------------------------------------
    # HISTORIAL
    # --------------------------------------------------

    checked_at = datetime.now(
        timezone.utc
    ).isoformat()

    for result in results:

        url = result.get(
            "url",
            ""
        )

        if not url:
            continue

        item = history.setdefault(
            url,
            {
                "channel_id":
                    result["channel_id"],

                "channel_name":
                    result["channel_name"],

                "source":
                    result["source"],

                "checks": 0,
                "online": 0,
                "offline": 0,
                "last_status": None,
                "last_response_ms": None,
                "last_checked": None
            }
        )

        item["checks"] += 1

        if result["online"]:
            item["online"] += 1
        else:
            item["offline"] += 1

        item["last_status"] = (
            result["status_code"]
        )

        item["last_response_ms"] = (
            result["response_time_ms"]
        )

        item["last_checked"] = checked_at

        item["availability"] = round(
            (
                item["online"]
                / item["checks"]
            ) * 100,
            2
        )

    status = {
        "checked_at": checked_at,
        "total": len(results),
        "online": online_count,
        "offline": offline_count,
        "results": results
    }

    save_json(
        STATUS_FILE,
        status
    )

    save_json(
        HISTORY_FILE,
        history
    )

    print("")
    print("=" * 60)
    print("CHECK V2 TERMINADO")
    print("=" * 60)
    print(
        f"URLs comprobadas: {len(results)}"
    )
    print(
        f"Online:           {online_count}"
    )
    print(
        f"Offline:          {offline_count}"
    )
    print(
        f"Historial:        {HISTORY_FILE}"
    )
    print(
        f"Reporte:          {STATUS_FILE}"
    )
    print("")
    print(
        "La M3U NO fue modificada por este CHECK."
    )
    print("")


if __name__ == "__main__":
    main()
