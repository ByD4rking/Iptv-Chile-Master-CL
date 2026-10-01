import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from teleon_classifier import classify

BASE = Path(__file__).resolve().parent.parent
CONFIG = BASE / "config" / "teleon.json"
OUTPUT = BASE / "data" / "teleon_discovery.json"
HEALTH_FILE = BASE / "data" / "teleon_source_health.json"

TIMEOUT = 20
RETRIES = 3
BACKOFF = (1.0, 2.0, 4.0)
WORKERS = 4
QUARANTINE_AFTER = 6
QUARANTINE_HOURS = 24
RETRYABLE_HTTP = {408, 425, 429, 500, 502, 503, 504}


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.player_urls = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        tag = tag.lower()
        if tag == "a":
            href = attrs.get("href")
            if href:
                href = href.strip()
                self.links.append(href)
                if "/embed/" in href.lower():
                    self.player_urls.append(href)
        elif tag in {"iframe", "frame", "video", "source"}:
            for key in ("src", "data-src", "data-url", "data-stream"):
                value = attrs.get(key)
                if value:
                    self.player_urls.append(value.strip())


def load(path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def same_host(url):
    host = (urlparse(url).hostname or "").lower()
    return host in {"teleon.tv", "www.teleon.tv"}


def classify_http_error(exc):
    if isinstance(exc, HTTPError):
        code = exc.code
        if code == 401:
            return "HTTP_401_UNAUTHORIZED"
        if code == 403:
            return "HTTP_403_FORBIDDEN"
        if code == 404:
            return "HTTP_404_NOT_FOUND"
        if code == 429:
            return "HTTP_429_RATE_LIMIT"
        if 500 <= code <= 599:
            return f"HTTP_{code}_SERVER"
        return f"HTTP_{code}"
    return type(exc).__name__


def fetch(url):
    last_error = None
    for attempt in range(RETRIES):
        try:
            req = Request(
                url,
                headers={
                    "User-Agent": "IPTV-CHILE-GENERADOR/TELEON-DISCOVERY-2.0",
                    "Accept": "text/html,application/xhtml+xml,text/plain,*/*",
                },
            )
            with urlopen(req, timeout=TIMEOUT) as response:
                if response.status >= 400:
                    raise RuntimeError(f"HTTP {response.status}")
                return response.read().decode("utf-8", errors="replace")
        except HTTPError as exc:
            last_error = classify_http_error(exc)
            if exc.code not in RETRYABLE_HTTP:
                raise
        except Exception as exc:
            last_error = str(exc)
        if attempt < RETRIES - 1:
            time.sleep(BACKOFF[attempt])
    raise RuntimeError(last_error or "error de descarga")


def explicit_streams(html, base_url=""):
    """Extract only stream URLs explicitly exposed by public HTML."""
    found = set()
    patterns = [
        r"""https?://[^"'<>\s]+(?:\.m3u8|\.mpd)(?:\?[^"'<>\s]*)?""",
        r"""https?://[^"'<>\s]*(?:m3u8|mpd)[^"'<>\s]*""",
        r"""(?:src|file|url|stream|source|hls|dash)\s*[:=]\s*["']([^"']+(?:m3u8|mpd)[^"']*)["']""",
    ]
    for pattern in patterns:
        for match in re.findall(pattern, html, flags=re.IGNORECASE):
            value = match if isinstance(match, str) else match[0]
            value = value.replace("\\/", "/").strip()
            if value.startswith(("http://", "https://")):
                found.add(value)
            elif base_url and value.startswith("/"):
                found.add(urljoin(base_url, value))
    return sorted(found)


def public_player_documents(html, page_url):
    """Follow one explicitly embedded public player page; no auth/DRM bypass."""
    parser = LinkParser()
    parser.feed(html)
    documents = []
    seen = set()
    for raw in parser.player_urls:
        player_url = urljoin(page_url, raw)
        parsed = urlparse(player_url)
        if parsed.scheme not in {"http", "https"} or player_url in seen:
            continue
        seen.add(player_url)
        try:
            player_html = fetch(player_url)
        except Exception:
            continue
        documents.append({
            "url": player_url,
            "streams": explicit_streams(player_html, player_url),
        })
    return documents


def discover_public_streams(html, page_url):
    streams = set(explicit_streams(html, page_url))
    player_headers = {}
    players = public_player_documents(html, page_url)
    for player in players:
        for stream in player["streams"]:
            streams.add(stream)
            player_headers.setdefault(stream, {"Referer": player["url"]})
    return sorted(streams), player_headers, len(players)


def channel_pages(html, base_url):
    parser = LinkParser()
    parser.feed(html)
    pages = set()
    base_path = urlparse(base_url).path.rstrip("/")
    for href in parser.links:
        absolute = urljoin(base_url, href)
        parsed = urlparse(absolute)
        if parsed.scheme not in {"http", "https"} or not same_host(absolute):
            continue
        path = parsed.path.rstrip("/")
        if not path or path == base_path:
            continue
        if "/channel/" not in path.lower() and "/live-tv/" not in path.lower():
            continue
        if any(path.lower().endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".gif", ".css", ".js", ".xml", ".json")):
            continue
        pages.add(absolute)
    return sorted(pages)


def source_health_state(health, source):
    name = str(source.get("name") or "TELEON").strip()
    state = health.setdefault(name, {
        "url": str(source.get("url") or "").strip(),
        "checks": 0,
        "successes": 0,
        "failures": 0,
        "consecutive_failures": 0,
        "last_success": None,
        "last_failure": None,
        "last_error": None,
        "last_pages": 0,
        "quarantine_until": None,
    })
    state["url"] = str(source.get("url") or "").strip()
    return state


def is_quarantined(state, now):
    until = str(state.get("quarantine_until") or "").strip()
    if not until:
        return False
    try:
        return datetime.fromisoformat(until.replace("Z", "+00:00")) > now
    except ValueError:
        return False


def inspect_source(source, max_pages):
    name = str(source.get("name") or "TELEON").strip()
    source_url = str(source.get("url") or "").strip()
    if not source_url or not same_host(source_url):
        raise ValueError("URL fuera de teleon.tv")
    html = fetch(source_url)
    pages = ([source_url] + channel_pages(html, source_url))[:max_pages]
    return name, source_url, pages, html


def main():
    cfg = load(CONFIG, {})
    sources = cfg.get("sources") or []
    max_sources = max(1, int(cfg.get("max_sources", len(sources))))
    max_pages_per_source = max(1, int(cfg.get("max_pages_per_source", 4)))
    max_channel_pages = max(1, int(cfg.get("max_channel_pages", 100)))
    max_per_profile = max(1, int(cfg.get("max_channels_per_profile", 150)))

    health = load(HEALTH_FILE, {})
    now = datetime.now(timezone.utc)
    all_quarantined = bool(sources) and all(
        is_quarantined(source_health_state(health, source), now)
        for source in sources[:max_sources]
    )

    result = {
        "schema_version": 3,
        "generated_at": now.isoformat(),
        "mode": "discovery_only",
        "published_automatically": False,
        "stream_extraction": "public_html_and_embedded_player_explicit_only",
        "classification": "teleon_classifier_v1",
        "errors": [],
        "profiles": {},
        "sources": [],
    }

    if not sources:
        raise SystemExit("Teleon no tiene fuentes configuradas.")

    pages_seen = set()
    for source in sources[:max_sources]:
        name = str(source.get("name") or "TELEON").strip()
        state = source_health_state(health, source)
        if is_quarantined(state, now) and not all_quarantined:
            state["last_skip"] = now.isoformat()
            state["last_skip_reason"] = "cuarentena_por_fallos_persistentes"
            result["sources"].append({
                "name": name,
                "url": state["url"],
                "status": "quarantined",
                "quarantine_until": state.get("quarantine_until"),
            })
            continue

        state["checks"] = int(state.get("checks") or 0) + 1
        try:
            source_name, source_url, pages, first_html = inspect_source(
                source, min(max_pages_per_source, max_channel_pages)
            )
            profile_names = [
                str(x).strip() for x in source.get("profiles") or [] if str(x).strip()
            ]
            source_items = 0

            # La primera página ya fue descargada; el resto se limita a Teleon
            # y se procesa con concurrencia acotada para no golpear el host.
            page_html = {source_url: first_html}
            pending = [p for p in pages if p != source_url and p not in pages_seen]
            with ThreadPoolExecutor(max_workers=WORKERS) as executor:
                futures = {executor.submit(fetch, page): page for page in pending}
                for future in as_completed(futures):
                    page = futures[future]
                    try:
                        page_html[page] = future.result()
                    except Exception as exc:
                        result["errors"].append({
                            "source": name,
                            "url": page,
                            "error": classify_http_error(exc),
                        })

            for page in pages:
                pages_seen.add(page)
                html = page_html.get(page)
                if html is None:
                    continue
                streams, player_headers, player_count = discover_public_streams(html, page)
                path = urlparse(page).path.rstrip("/")
                slug = path.rsplit("/", 1)[-1] if path else ""
                classification = classify(
                    name=slug.replace("-", " "),
                    group=" ".join(profile_names),
                    slug=slug,
                    extra=html[:4000],
                )
                item = {
                    "page_url": page,
                    "channel_path": path,
                    "source": name,
                    "language": str(source.get("language") or "es-419").strip(),
                    "region": str(source.get("region") or ("España" if source.get("language") == "es-ES" else "Latinoamérica")).strip(),
                    "stream_urls": streams,
                    "stream_headers": (
                        player_headers.get(streams[0], {"Referer": page})
                        if streams else {}
                    ),
                    "has_explicit_stream": bool(streams),
                    "embedded_player_count": player_count,
                    "classification": classification,
                    "requires_validation": True,
                    "safe_to_publish_automatically": False,
                }

                # Profiles son etiquetas de descubrimiento, no una autorización
                # para publicar. El clasificador aporta categorías adicionales.
                buckets = set(profile_names)
                if classification.get("profile"):
                    buckets.add(classification["profile"])
                if not buckets:
                    buckets.add("unclassified")

                for profile in buckets:
                    bucket = result["profiles"].setdefault(profile, [])
                    if len(bucket) >= max_per_profile:
                        continue
                    if not any(x["page_url"] == page for x in bucket):
                        bucket.append(item)
                        source_items += 1

            state["successes"] = int(state.get("successes") or 0) + 1
            state["consecutive_failures"] = 0
            state["last_success"] = now.isoformat()
            state["last_error"] = None
            state["last_pages"] = len(pages)
            state["quarantine_until"] = None
            result["sources"].append({
                "name": name,
                "url": source_url,
                "status": "ok",
                "pages": len(pages),
                "items": source_items,
            })
        except Exception as exc:
            state["failures"] = int(state.get("failures") or 0) + 1
            state["consecutive_failures"] = int(state.get("consecutive_failures") or 0) + 1
            state["last_failure"] = now.isoformat()
            state["last_error"] = classify_http_error(exc)
            if state["consecutive_failures"] >= QUARANTINE_AFTER:
                state["quarantine_until"] = (
                    now + timedelta(hours=QUARANTINE_HOURS)
                ).isoformat()
            result["errors"].append({
                "source": name,
                "url": source_url,
                "error": state["last_error"],
            })
            result["sources"].append({
                "name": name,
                "url": source_url,
                "status": "error",
                "error": state["last_error"],
                "consecutive_failures": state["consecutive_failures"],
            })

    save(HEALTH_FILE, health)
    total = sum(len(v) for v in result["profiles"].values())
    explicit_total = sum(
        1 for items in result["profiles"].values()
        for item in items if item.get("has_explicit_stream")
    )
    result["metrics"] = {
        "pages_inspected": len(pages_seen),
        "candidate_items": total,
        "explicit_stream_candidates": explicit_total,
        "embedded_player_pages": sum(
            int(item.get("embedded_player_count") or 0)
            for items in result["profiles"].values()
            for item in items
        ),
        "errors": len(result["errors"]),
        "sources_ok": sum(1 for x in result["sources"] if x.get("status") == "ok"),
        "sources_quarantined": sum(1 for x in result["sources"] if x.get("status") == "quarantined"),
    }
    save(OUTPUT, result)

    print(f"Teleon discovery: {total} fichas candidatas.")
    print(f"Streams explícitos: {explicit_total}.")
    print(f"Páginas inspeccionadas: {len(pages_seen)}.")
    print(f"Fuentes OK: {result['metrics']['sources_ok']}.")
    print(f"Errores: {len(result['errors'])}.")
    print(f"Salida discovery: {OUTPUT}")
    print(f"Historial fuentes: {HEALTH_FILE}")


if __name__ == "__main__":
    main()
