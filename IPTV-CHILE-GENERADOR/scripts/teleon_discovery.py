import json
import re
import time
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

BASE = Path(__file__).resolve().parent.parent
CONFIG = BASE / "config" / "teleon.json"
OUTPUT = BASE / "data" / "teleon_discovery.json"
TIMEOUT = 20
RETRIES = 3
BACKOFF = (1.0, 2.0, 4.0)


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "a":
            return
        href = dict(attrs).get("href")
        if href:
            self.links.append(href.strip())


def load(path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def fetch(url):
    last_error = None
    for attempt in range(RETRIES):
        try:
            req = Request(
                url,
                headers={
                    "User-Agent": "IPTV-CHILE-GENERADOR/teleon-discovery-1.0",
                    "Accept": "text/html,application/xhtml+xml,text/plain,*/*",
                },
            )
            with urlopen(req, timeout=TIMEOUT) as response:
                if response.status >= 400:
                    raise RuntimeError(f"HTTP {response.status}")
                return response.read().decode("utf-8", errors="replace")
        except Exception as exc:
            last_error = str(exc)
            if attempt < RETRIES - 1:
                time.sleep(BACKOFF[attempt])
    raise RuntimeError(last_error or "error de descarga")


def same_host(url):
    host = (urlparse(url).hostname or "").lower()
    return host in {"teleon.tv", "www.teleon.tv"}


def explicit_streams(html, page_url):
    found = set()
    patterns = [
        r'https?://[^"\\'<>\\s]+\\.m3u8(?:\\?[^"\\'<>\\s]*)?',
        r'https?://[^"\\'<>\\s]+\\.mpd(?:\\?[^"\\'<>\\s]*)?',
    ]
    for pattern in patterns:
        for match in re.findall(pattern, html, flags=re.IGNORECASE):
            found.add(match.replace("\\/", "/"))
    return sorted(found)


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
        # Discovery is deliberately limited to Teleon pages. Assets, downloads,
        # query-only URLs and unrelated hosts are excluded.
        if any(path.lower().endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".gif", ".css", ".js", ".xml", ".json")):
            continue
        pages.add(absolute)
    return sorted(pages)


def main():
    cfg = load(CONFIG, {})
    sources = cfg.get("sources") or []
    max_pages = max(1, int(cfg.get("max_pages", 4)))
    max_per_profile = max(1, int(cfg.get("max_channels_per_profile", 150)))

    result = {
        "schema_version": 1,
        "generated_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        "mode": "discovery_only",
        "published_automatically": False,
        "stream_extraction": "explicit_only",
        "errors": [],
        "profiles": {},
    }

    if not sources:
        raise SystemExit("Teleon no tiene fuentes configuradas.")

    seen_pages = set()
    for source in sources[:max_pages]:
        name = str(source.get("name") or "TELEON").strip()
        profile_names = [str(x).strip() for x in source.get("profiles") or [] if str(x).strip()]
        source_url = str(source.get("url") or "").strip()
        if not source_url or not same_host(source_url):
            result["errors"].append({"source": name, "error": "URL fuera de teleon.tv"})
            continue

        try:
            html = fetch(source_url)
        except Exception as exc:
            result["errors"].append({"source": name, "url": source_url, "error": str(exc)})
            continue

        pages = [source_url] + channel_pages(html, source_url)
        for page in pages:
            if page in seen_pages:
                continue
            seen_pages.add(page)
            try:
                page_html = html if page == source_url else fetch(page)
            except Exception:
                continue

            streams = explicit_streams(page_html, page)
            if not streams:
                continue

            item = {
                "page_url": page,
                "source": name,
                "stream_urls": streams,
                "requires_validation": True,
                "safe_to_publish_automatically": False,
            }
            for profile in profile_names:
                bucket = result["profiles"].setdefault(profile, [])
                if len(bucket) >= max_per_profile:
                    continue
                if not any(x["page_url"] == page for x in bucket):
                    bucket.append(item)

    total = sum(len(v) for v in result["profiles"].values())
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Teleon discovery: {total} páginas con streams explícitos.")
    print(f"Teleon discovery: {len(seen_pages)} páginas inspeccionadas.")
    if result["errors"]:
        print(f"Teleon discovery: {len(result['errors'])} fuentes con error; no se publican candidatos.")
    print(f"Salida: {OUTPUT}")


if __name__ == "__main__":
    main()
