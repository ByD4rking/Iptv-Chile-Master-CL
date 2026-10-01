import html
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

BASE = Path(__file__).resolve().parent.parent
CONFIG = BASE / "config" / "teleon.json"
OUTPUT = BASE / "data" / "teleon_discovery.json"
TIMEOUT = 20
RETRIES = 3
BACKOFF = (1.0, 2.0, 4.0)

DEFAULT_TERMS = {
    "anime_kids": [
        "anime", "cartoon", "animation", "animacion", "dibujos", "kids",
        "disney", "disney jr", "nick", "nickelodeon", "cartoon network",
        "boomerang", "pokemon", "inazuma"
    ],
    "competition_entertainment": [
        "wipeout", "wipout", "ninja warrior", "american ninja warrior",
        "superhuman", "juego de la oca", "minute to win it",
        "minuto para ganar", "takeshi", "humor amarillo", "competencia",
        "concursos", "game show", "reality", "entretenimiento"
    ],
}


def load(path):
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def fetch(url):
    last = None
    for attempt in range(RETRIES):
        try:
            req = Request(
                url,
                headers={
                    "User-Agent": "IPTV-CHILE-GENERADOR/TELEON-DISCOVERY-1.0",
                    "Accept": "text/html,application/xhtml+xml",
                },
            )
            with urlopen(req, timeout=TIMEOUT) as response:
                if response.status >= 400:
                    raise RuntimeError(f"HTTP {response.status}")
                return response.read().decode("utf-8", "replace")
        except HTTPError as exc:
            last = f"HTTP {exc.code}"
            if exc.code not in {408, 425, 429, 500, 502, 503, 504}:
                raise
        except Exception as exc:
            last = str(exc)
        if attempt < RETRIES - 1:
            time.sleep(BACKOFF[attempt])
    raise RuntimeError(f"Teleon no disponible tras {RETRIES} intentos: {last}")


def clean(value):
    value = html.unescape(str(value or ""))
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def slug_from_href(href):
    href = html.unescape(href or "")
    match = re.search(r"https?://(?:www\.)?teleon\.tv(?:/[^\s\"']*)?/live-tv/([^\"'?#]+)", href)
    if match:
        return match.group(1).strip("/")
    match = re.search(r"(?:^|/)live-tv/([^\"'?#]+)/?", href)
    return match.group(1).strip("/") if match else ""


def discover_from_page(source_name, page_url, profiles):
    text = fetch(page_url)
    results = []
    seen = set()

    # Teleon exposes channel pages as ordinary public links. We only collect
    # those links and metadata; we do not bypass its player, tokens, DRM or
    # client-side session mechanisms.
    for match in re.finditer(
        r'<a[^>]+href=["\']([^"\']*?/live-tv/[^"\']+)["\'][^>]*>(.*?)</a>',
        text,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        href, label_html = match.groups()
        slug = slug_from_href(href)
        if not slug:
            continue
        label = clean(label_html)
        if not label or label.lower().startswith(("watch ", "▶ watch ")):
            label = clean(re.sub(r"^(?:▶\s*)?watch\s+", "", label, flags=re.I))
        page = href if href.startswith("http") else "https://teleon.tv" + (href if href.startswith("/") else "/" + href)

        haystack = f"{label} {slug}".lower()
        matched_profiles = [
            profile for profile in profiles
            if any(term.lower() in haystack for term in DEFAULT_TERMS.get(profile, []))
        ]
        if not matched_profiles:
            continue

        key = page.split("#", 1)[0]
        if key in seen:
            continue
        seen.add(key)
        results.append({
            "name": label or slug.replace("-", " ").title(),
            "group": "",
            "page_url": page,
            "stream_urls": [],
            "source": source_name,
            "matched_profiles": matched_profiles,
            "stream_url_found": False,
            "requires_validation": True,
            "safe_to_publish_automatically": False,
        })
    return results


def main():
    cfg = load(CONFIG)
    all_items = []
    errors = []
    max_channels = int(cfg.get("max_channels_per_profile", 150))
    for source in cfg.get("sources", []):
        try:
            items = discover_from_page(
                str(source.get("name") or "TELEON").strip(),
                str(source.get("url") or "").strip(),
                list(source.get("profiles") or []),
            )
            all_items.extend(items)
            print(f"[OK] {source.get('name')}: {len(items)} candidatos")
        except Exception as exc:
            errors.append({"source": source.get("name"), "url": source.get("url"), "error": str(exc)})
            print(f"[ERROR] {source.get('name')}: {exc}")

    profiles = {profile: [] for source in cfg.get("sources", []) for profile in source.get("profiles", [])}
    for item in all_items:
        for profile in item["matched_profiles"]:
            if len(profiles.setdefault(profile, [])) < max_channels:
                profiles[profile].append(item)

    output = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "discovery_only",
        "published_automatically": False,
        "stream_extraction": "explicit_only",
        "profiles": profiles,
        "errors": errors,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    total = sum(len(v) for v in profiles.values())
    stream_candidates = sum(1 for v in profiles.values() for x in v if x.get("stream_url_found"))
    print(f"Teleon: {total} candidatos de páginas; {stream_candidates} con stream URL explícita.")
    print("Teleon queda en descubrimiento: no modifica catalog.json ni publica automáticamente.")


if __name__ == "__main__":
    main()
