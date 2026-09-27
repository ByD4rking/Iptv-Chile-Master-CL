from __future__ import annotations

import json
import re
from pathlib import Path

from client import PlutoClient


BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "output"


GROUPS = (
    "Anime & Gaming",
    "Comedia",
    "Competencia",
    "Curiosidad",
    "Deportes",
    "Entretenimiento",
    "Estilo De Vida",
    "Investigación",
    "Infantil",
    "Música",
    "Noticias",
    "Novelas",
    "Películas",
    "Reality",
    "Retro",
    "Series",
    "South Park",
    "Teen",
    "Zona Paranormal",
    "Otros",
)

KEYWORDS = {
    "South Park": ("south park",),
    "Zona Paranormal": ("paranormal", "misterio", "ghost", "fantasma", "terror", "haunted", "exorc"),
    "Anime & Gaming": ("anime", "animax", "gaming", "game", "videojuego", "tokusato", "naruto", "pokemon", "dragon ball"),
    "Infantil": ("infantil", "kids", "kid", "baby", "nick", "nickelodeon", "nick jr", "disney junior", "cartoon", "bob esponja", "spongebob", "paw patrol", "peppa"),
    "Deportes": ("deporte", "sport", "futbol", "fútbol", "football", "soccer", "nba", "nfl", "mlb", "ufc", "tennis", "tenis", "golf", "box", "wrestling", "lucha"),
    "Noticias": ("noticia", "news", "cnn", "reuters", "24 horas", "teleSUR", "telesur"),
    "Música": ("music", "música", "mtv", "vh1", "vevo", "concert", "concierto", "hits", "rock", "pop"),
    "Novelas": ("novela", "novelas", "telenovela", "telenovelas", "romance", "dramático", "drama"),
    "Reality": ("reality", "reality tv", "love island", "survivor", "big brother", "masterchef", "master chef"),
    "Competencia": ("competencia", "challenge", "game show", "concurso", "concurso", "batal", "battle"),
    "Comedia": ("comedia", "comedy", "laugh", "simpson", "chavo", "chespirito", "just for laughs", "south park"),
    "Retro": ("retro", "classic", "clásico", "vintage", "old", "años 80", "años 90"),
    "Teen": ("teen", "adolesc", "youth", "young"),
    "Películas": ("película", "peliculas", "movie", "movies", "cine", "film", "acción", "accion", "thriller", "western", "sci-fi"),
    "Investigación": ("investigación", "investigacion", "investigation", "crime", "crimen", "forensic", "forense", "detective"),
    "Curiosidad": ("curios", "amazing", "wonders", "science", "ciencia", "history", "historia"),
    "Estilo De Vida": ("lifestyle", "estilo de vida", "cocina", "cooking", "food", "comida", "viaje", "travel", "hogar", "home", "fashion", "moda"),
    "Entretenimiento": ("entretenimiento", "entertainment", "talk", "show", "celebrity", "celebridades"),
    "Series": ("series", "serie", "sitcom", "crime drama"),
}


def classify_channel(channel: dict) -> str:
    text = " ".join(
        str(channel.get(key) or "")
        for key in ("name", "slug", "description", "category")
    ).lower()
    text = re.sub(r"\s+", " ", text).strip()

    for group in GROUPS[:-1]:
        for keyword in KEYWORDS.get(group, ()):
            if keyword in text:
                return group

    raw = str(channel.get("category") or "").lower()
    if "sport" in raw:
        return "Deportes"
    if "news" in raw:
        return "Noticias"
    if "music" in raw:
        return "Música"
    if "kids" in raw or "child" in raw:
        return "Infantil"
    if "movie" in raw or "film" in raw:
        return "Películas"
    if "series" in raw:
        return "Series"

    return "Otros"


def normalize_channel(client: PlutoClient, channel: dict) -> dict:
    channel_id = channel.get("id", "")
    category = classify_channel(channel)

    return {
        "id": channel_id,
        "name": channel.get("name", ""),
        "slug": channel.get("slug", ""),
        "description": channel.get("description", ""),
        "number": channel.get("number"),
        "category": category,
        "source_category": channel.get("category"),
        "country": channel.get("country"),
        "region": channel.get("region"),
        "language": channel.get("language"),
        "logo": channel.get("logo", ""),
        "stream": client.build_stream_url(channel_id),
    }


def fetch_channels() -> list[dict]:
    client = PlutoClient()
    print("Obteniendo canales de Pluto...")
    channels = client.get_channels()

    normalized = []
    seen_ids = set()

    for channel in channels:
        channel_id = channel.get("id")

        if not channel_id or channel_id in seen_ids:
            continue

        try:
            item = normalize_channel(client, channel)
            normalized.append(item)
            seen_ids.add(channel_id)
        except Exception as exc:
            print(f"No se pudo procesar {channel_id}: {exc}")

    return normalized


def save_channels(channels: list[dict]) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_file = OUTPUT_DIR / "channels.json"

    output_file.write_text(
        json.dumps(channels, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    return output_file


if __name__ == "__main__":
    channels = fetch_channels()
    output_file = save_channels(channels)

    print()
    print("================================")
    print("GENERACIÓN DE CANALES COMPLETA")
    print("================================")
    print(f"Canales válidos: {len(channels)}")
    print(f"Archivo: {output_file}")

    counts = {}
    for channel in channels:
        group = channel["category"]
        counts[group] = counts.get(group, 0) + 1

    for group in GROUPS:
        print(f"{group}: {counts.get(group, 0)}")
