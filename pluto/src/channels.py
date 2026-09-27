from __future__ import annotations

import json
import re
from pathlib import Path

from client import PlutoClient


BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "output"


CL_OVERRIDES = {
    "Adrenalina Pura TV": "Entretenimiento",
    "Runtime": "Series",
    "Pluto TV A La Mexicana": "Novelas",
    "CSI: Miami": "Investigación",
    "NCIS": "Investigación",
    "Los Asesinatos de Midsomer": "Investigación",
    "Números": "Investigación",
    "Blue Bloods": "Series",
    "Rookie Blue: Policías Novatos": "Series",
    "The Walking Dead by AMC": "Series",
    "Pluto TV Star Trek": "Series",
    "Z Nation": "Series",
    "Relic Hunter": "Series",
    "El Capo": "Novelas",
    "Celia": "Novelas",
    "Hechiceras": "Series",
    "Hechizada": "Series",
    "Mi Bella Genio": "Retro",
    "MacGyver": "Retro",
    "Los Pitufos": "Infantil",
    "Corazón": "Novelas",
    "Cuando los Ángeles Caen": "Novelas",
    "Sin Tetas No Hay Paraíso": "Novelas",
    "La Selección": "Novelas",
    "RCN Más": "Entretenimiento",
    "Mi Gorda Bella": "Novelas",
    "Juana La Virgen": "Novelas",
    "Pluto TV Amor y Mentiras": "Novelas",
    "Hells Kitchen": "Reality",
    "Minuto Para Ganar": "Competencia",
    "Wipe Out": "Competencia",
    "Desafío Super Humanos": "Competencia",
    "Shockwave": "Cine",
    "Pluto TV Naturaleza": "Curiosidad",
    "Monstruos de Rio": "Curiosidad",
    "NatureTime": "Curiosidad",
    "Paisajes por Stingray": "Estilo De Vida",
    "El Encantador de Perros": "Estilo De Vida",
    "Pluto TV Aventura": "Entretenimiento",
    "Ice Pilots": "Curiosidad",
    "Pluto TV Velocidad": "Deportes",
    "Obsesión por los Autos": "Estilo De Vida",
    "Motorvision TV": "Deportes",
    "Pluto TV Vida Real": "Reality",
    "COPS": "Investigación",
    "Dog el cazarrecompensas": "Reality",
    "Empeños a lo bestia": "Reality",
    "Pluto TV Documentales": "Curiosidad",
    "I Shouldn't Be Alive": "Curiosidad",
    "Smithsonian Channel Pluto TV": "Curiosidad",
    "Archivos Extraterrestres": "Zona Paranormal",
    "Pluto TV Investiga": "Investigación",
    "Los archivos del FBI": "Investigación",
    "Dr. G": "Investigación",
    "TeleFórmula": "Noticias",
    "Milenio Televisión": "Noticias",
    "C4 en Alerta": "Noticias",
    "Pluto TV Peleas": "Deportes",
    "PFL MMA": "Deportes",
    "FIFA+": "Deportes",
    "Realmadrid TV": "Deportes",
    "Top Barça": "Deportes",
    "Red Bull TV": "Deportes",
    "Daria": "Comedia",
    "La Familia del Barrio": "Comedia",
    "Mr. Bean Animated": "Comedia",
    "Enchufe.TV": "Comedia",
    "Pluto TV Humor": "Comedia",
    "FailArmy": "Comedia",
    "The Pet Collective": "Entretenimiento",
    "Revive Gran Hermano": "Reality",
    "Azteca Internacional": "Entretenimiento",
    "Canal 6 CdMX": "Noticias",
    "Canal Claro": "Entretenimiento",
    "Al Ritmo del Jaripeo": "Música",
    "Hermanos a la Obra": "Estilo De Vida",
    "Tastemade": "Estilo De Vida",
    "Dulce by elGourmet": "Estilo De Vida",
    "Plato del Dia by elGourmet": "Estilo De Vida",
    "Hunter x Hunter": "Anime",
    "Death Note": "Anime",
    "JoJo’s Bizarre Adventure": "Anime",
    "Yu-Gi-Oh": "Anime",
    "Captain Tsubasa": "Anime",
    "Inuyasha": "Anime",
    "Kenan y Kel": "Comedia",
    "Pluto TV Junior": "Infantil",
    "Avatar: La Leyenda de Aang": "Infantil",
    "Rugrats": "Infantil",
    "Los Padrinos Mágicos": "Infantil",
    "Las Tortugas Ninja": "Infantil",
    "TikTok Radio en Español": "Música",
    "Stingray Éxitos Regional Mexicano": "Música",
    "Karaoke por Stingray": "Música",
}

GROUPS = (
    "Anime",
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
    "Cine",
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
    "Anime": ("anime", "animax", "tokusato", "naruto", "pokemon", "dragon ball", "one piece", "bleach", "my hero", "jujutsu", "gaming", "game", "videojuego"),
    "Infantil": ("infantil", "kids", "kid", "baby", "nick", "nickelodeon", "nick jr", "disney junior", "cartoon", "bob esponja", "spongebob", "paw patrol", "peppa"),
    "Deportes": ("deporte", "sport", "futbol", "fútbol", "football", "soccer", "nba", "nfl", "mlb", "ufc", "tennis", "tenis", "golf", "box", "wrestling", "lucha"),
    "Noticias": ("noticia", "news", "cnn", "reuters", "24 horas", "teleSUR", "telesur"),
    "Música": ("music", "música", "mtv", "vh1", "vevo", "concert", "concierto", "hits", "rock", "pop", "radio", "karaoke"),
    "Novelas": ("novela", "novelas", "telenovela", "telenovelas", "romance", "dramático", "drama"),
    "Reality": ("reality", "reality tv", "love island", "survivor", "big brother", "masterchef", "master chef", "gran hermano", "vida real"),
    "Competencia": ("competencia", "challenge", "game show", "concurso", "concurso", "batal", "battle"),
    "Comedia": ("comedia", "comedy", "laugh", "simpson", "chavo", "chespirito", "just for laughs", "south park"),
    "Retro": ("retro", "classic", "clásico", "vintage", "old", "años 80", "años 90"),
    "Teen": ("teen", "adolesc", "youth", "young"),
    "Cine": ("película", "peliculas", "movie", "movies", "cine", "film", "acción", "accion", "thriller", "western", "sci-fi"),
    "Investigación": ("investigación", "investigacion", "investigation", "crime", "crimen", "forensic", "forense", "detective"),
    "Curiosidad": ("curios", "amazing", "wonders", "science", "ciencia", "history", "historia"),
    "Estilo De Vida": ("lifestyle", "estilo de vida", "cocina", "cooking", "food", "comida", "viaje", "travel", "hogar", "home", "fashion", "moda"),
    "Entretenimiento": ("entretenimiento", "entertainment", "talk", "show", "celebrity", "celebridades"),
    "Series": ("series", "serie", "sitcom", "crime drama", "star trek", "walking dead", "z nation"),
}


def classify_channel(channel: dict) -> str:
    name = str(channel.get("name") or "").strip()
    if name in CL_OVERRIDES:
        return CL_OVERRIDES[name]
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
