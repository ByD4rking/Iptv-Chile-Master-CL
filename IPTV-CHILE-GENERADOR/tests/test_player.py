from pathlib import Path
import re

PLAYER = Path(__file__).resolve().parents[2] / "player" / "index.html"
APP = PLAYER.parent / "app.js"
text = PLAYER.read_text(encoding="utf-8")
app = APP.read_text(encoding="utf-8")

required = [
    '<video id="video"',
    "beta/v1.1.0-beta.1",
    "raw.githubusercontent.com/ByD4rking/Iptv-Chile-Master-CL/",
    "frame-ancestors 'none'",
]
for needle in required:
    assert needle in text, f"Falta en player/index.html: {needle}"

playlists = [
    "IPTV-CHILE-MAESTRA_CORREGIDO.m3u",
    "IPTV-CHILE-MAESTRA_GOD.m3u",
    "IPTV-CHILE-GENERADOR/IPTV-CHILE-GENERADOR.m3u",
    "pluto/output/playlists/pluto_latam.m3u",
    "pluto/output/playlists/pluto_cl.m3u",
    "pluto/output/playlists/pluto_es.m3u",
    "pluto/output/playlists/pluto_mx.m3u",
    "pluto/output/playlists/pluto_ar.m3u",
    "pluto/output/playlists/pluto_br.m3u",
    "pluto/output/playlists/pluto_us.m3u",
]
for playlist in playlists:
    assert playlist in app, f"Playlist beta no integrada en player/app.js: {playlist}"

assert re.search(r"hls\.js@1\.7\.3", text)
assert "noopener noreferrer" in text
assert '<script src="app.js" defer></script>' in text
assert '<script>' not in text, "El player no debe usar JavaScript inline: el CSP lo bloquea."
assert APP.exists(), "Falta player/app.js"
assert "parseM3U" in app
assert "Hls.isSupported()" in app
assert "new Hls(" in app
assert "hls.destroy()" in app
assert "fetch(url" in app

print(f"OK: player beta validado con {len(playlists)} playlists y arquitectura CSP sin JS inline.")
