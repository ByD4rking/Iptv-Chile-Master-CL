import hashlib
import json
from pathlib import Path

from atomic import atomic_write_json

BASE = Path(__file__).resolve().parent.parent
APPROVED = BASE / "config" / "teleon_approved.json"
CATALOG = BASE / "config" / "catalog.json"


def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def clean(value):
    return str(value or "").strip()


def main():
    cfg = load(APPROVED)
    approved = cfg.get("approved") or []
    if not isinstance(approved, list):
        raise SystemExit("Teleon approval: 'approved' debe ser una lista.")

    catalog = load(CATALOG)
    channels = catalog.get("channels") or []
    ids = {clean(x.get("id")) for x in channels}
    urls = {
        clean(source.get("url"))
        for channel in channels
        for source in channel.get("sources") or []
        if clean(source.get("url"))
    }

    added = 0
    for item in approved:
        if not isinstance(item, dict):
            raise SystemExit("Teleon approval: entrada inválida.")

        page_url = clean(item.get("page_url"))
        stream_url = clean(item.get("stream_url"))
        name = clean(item.get("name"))
        group = clean(item.get("group")) or "Teleon"
        rights_basis = clean(item.get("rights_basis"))

        if not page_url.startswith(("http://", "https://")):
            raise SystemExit(f"Teleon approval: page_url inválida: {page_url}")
        if not stream_url.startswith(("http://", "https://")):
            raise SystemExit(f"Teleon approval: stream_url inválida: {stream_url}")
        if not name:
            raise SystemExit("Teleon approval: canal sin nombre.")
        if not rights_basis:
            raise SystemExit(
                f"Teleon approval: {name} no tiene rights_basis explícito; "
                "no se incorpora."
            )
        if stream_url in urls:
            continue

        channel_id = clean(item.get("id"))
        if not channel_id:
            channel_id = hashlib.sha256(
                f"{name}|{stream_url}".encode("utf-8")
            ).hexdigest()[:20]
        if channel_id in ids:
            raise SystemExit(f"Teleon approval: ID duplicado: {channel_id}")

        logo = clean(item.get("logo"))
        entry = {
            "id": channel_id,
            "name": name,
            "group": group,
            "logo": logo,
            "aliases": list(item.get("aliases") or []),
            "sources": [{
                "url": stream_url,
                "priority": int(item.get("priority") or 100),
                "source": "TELEON_APPROVED",
                "page_url": page_url,
                "rights_basis": rights_basis,
            }],
            "channel_key": f"teleon:{channel_id}",
        }
        channels.append(entry)
        ids.add(channel_id)
        urls.add(stream_url)
        added += 1

    if added:
        catalog["channels"] = channels
        atomic_write_json(CATALOG, catalog)

    print(f"Teleon promotion: {added} canales aprobados incorporados al catálogo.")
    print("OK: la promoción exige URL de stream explícita y rights_basis manual.")


if __name__ == "__main__":
    main()
