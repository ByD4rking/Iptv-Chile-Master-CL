from pathlib import Path
import re

PLAYER = Path(__file__).resolve().parents[2] / "player" / "index.html"
text = PLAYER.read_text(encoding="utf-8")

required = [
    "<video id=\"video\"",
    "Hls.isSupported()",
    "beta/v1.1.0-beta.1",
    "raw.githubusercontent.com/ByD4rking/Iptv-Chile-Master-CL/",
    "frame-ancestors 'none'",
]
for needle in required:
    assert needle in text, f"Falta en player: {needle}"

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
    assert playlist in text, f"Playlist beta no integrada en player: {playlist}"

assert re.search(r"hls\.js@1\.7\.3", text)
assert "noopener noreferrer" in text
print(f"OK: player beta validado con {len(playlists)} playlists.")

assert '<script src="app.js" defer></script>' in text
assert '<script>' not in text, "El player no debe usar JavaScript inline: el CSP lo bloquea."
assert (PLAYER.parent / "app.js").exists(), "Falta player/app.js"
app=(PLAYER.parent / "app.js").read_text(encoding="utf-8")
assert "parseM3U" in app and "Hls.isSupported()" in app
