import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from atomic import atomic_write_json, file_sha256

BASE = Path(__file__).resolve().parent.parent
CHANNELS_FILE = BASE / "data" / "channels.json"
STATUS_FILE = BASE / "data" / "status.json"
HISTORY_FILE = BASE / "data" / "history.json"
TIMEOUT = 8
WORKERS = 40
MAX_HISTORY = 5000
RETRIES = 3
RETRY_BACKOFF_SECONDS = (0.8, 1.8, 3.5)
RETRYABLE_HTTP = {408, 425, 429, 500, 502, 503, 504}


def load_json(path, default):
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8-sig") as f:
            return json.load(f)
    except Exception:
        return default


def check_url(item):
    channel = item["channel"]
    source = item["source"]
    url = str(source.get("url") or "").strip()

    result = {
        "channel_id": channel.get("id", ""),
        "channel_name": channel.get("name", ""),
        "url": url,
        "source": source.get("source", ""),
        "online": False,
        "status_code": None,
        "response_time_ms": None,
        "error": None,
    }

    if not url.startswith(("http://", "https://")):
        result["error"] = "URL no compatible"
        return result

    start = time.perf_counter()
    last_error = None
    for attempt in range(RETRIES):
        try:
            request = Request(
                url,
                headers={
                    "User-Agent": "IPTV-CHILE-GENERADOR/CHECK-5.0",
                    "Accept": "*/*",
                },
            )
            with urlopen(request, timeout=TIMEOUT) as response:
                result["status_code"] = response.status
                response.read(2048)
                result["response_time_ms"] = round(
                    (time.perf_counter() - start) * 1000, 2
                )
                result["online"] = 200 <= response.status < 400
                if result["online"] or response.status not in RETRYABLE_HTTP:
                    return result
                last_error = f"HTTP {response.status}"
        except HTTPError as error:
            result["status_code"] = error.code
            last_error = f"HTTP {error.code}"
            if error.code not in RETRYABLE_HTTP:
                break
        except (URLError, TimeoutError) as error:
            last_error = str(getattr(error, "reason", error))
        except Exception as error:
            last_error = str(error)
            break
        if attempt < RETRIES - 1:
            time.sleep(RETRY_BACKOFF_SECONDS[attempt])

    result["response_time_ms"] = round((time.perf_counter() - start) * 1000, 2)
    result["error"] = last_error or "Error desconocido"
    return result

    return result


def main():
    if not CHANNELS_FILE.exists():
        raise SystemExit("No existe channels.json")

    channels_sha256 = file_sha256(CHANNELS_FILE)
    channels = load_json(CHANNELS_FILE, [])
    history = load_json(HISTORY_FILE, {})
    tasks = [
        {"channel": channel, "source": source}
        for channel in channels
        for source in channel.get("sources", [])
    ]
    task_urls = [str(task["source"].get("url") or "").strip() for task in tasks]
    if any(not url.startswith(("http://", "https://")) for url in task_urls):
        raise SystemExit("INCONSISTENCIA: existe un endpoint candidato no HTTP/HTTPS.")
    if len(task_urls) != len(set(task_urls)):
        raise SystemExit("INCONSISTENCIA: channels.json contiene URLs candidatas duplicadas.")
    if any(not str(task["channel"].get("id") or "").strip() for task in tasks):
        raise SystemExit("INCONSISTENCIA: existe un candidato sin channel_id.")

    results = []
    with ThreadPoolExecutor(max_workers=WORKERS) as executor:
        futures = [executor.submit(check_url, item) for item in tasks]
        for future in as_completed(futures):
            results.append(future.result())

    checked_at = datetime.now(timezone.utc).isoformat()

    for result in results:
        url = result.get("url", "")
        if not url:
            continue
        item = history.setdefault(
            url,
            {
                "channel_id": result["channel_id"],
                "channel_name": result["channel_name"],
                "source": result["source"],
                "checks": 0,
                "online": 0,
                "offline": 0,
                "last_status": None,
                "last_response_ms": None,
                "last_checked": None,
            },
        )
        item["checks"] += 1
        item["online"] += int(result["online"])
        item["offline"] += int(not result["online"])
        item["last_status"] = result["status_code"]
        item["last_response_ms"] = result["response_time_ms"]
        item["last_checked"] = checked_at
        item["availability"] = round(item["online"] / item["checks"] * 100, 2)

    if len(history) > MAX_HISTORY:
        history = dict(
            sorted(
                history.items(),
                key=lambda pair: pair[1].get("last_checked") or "",
                reverse=True,
            )[:MAX_HISTORY]
        )

    online = sum(1 for result in results if result["online"])

    status = {
        "schema_version": 2,
        "checked_at": checked_at,
        "channels_sha256": channels_sha256,
        "total": len(results),
        "online": online,
        "offline": len(results) - online,
        "results": results,
    }

    # Both artifacts are committed only after the complete scan succeeds.
    atomic_write_json(STATUS_FILE, status)
    atomic_write_json(HISTORY_FILE, history)

    print(f"URLs comprobadas: {len(results)}")
    print(f"Online: {online}")
    print(f"Offline: {len(results) - online}")
    print(f"Historial limitado a: {MAX_HISTORY}")
    print(f"Snapshot channels.json: {channels_sha256}")


if __name__ == "__main__":
    main()
