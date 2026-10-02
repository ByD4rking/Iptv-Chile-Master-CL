from pathlib import Path
import re
PLAYER=Path(__file__).resolve().parents[2]/"player"/"index.html"
text=PLAYER.read_text(encoding="utf-8")
for needle in ["<video id=\"video\"","parseM3U","Hls.isSupported()","beta/v1.1.0-beta.1","IPTV-CHILE-MAESTRA_CORREGIDO.m3u","IPTV-CHILE-MAESTRA_GOD.m3u","IPTV-CHILE-GENERADOR/IPTV-CHILE-GENERADOR.m3u","pluto/output/playlists/pluto_latam.m3u","pluto/output/playlists/pluto_us.m3u","frame-ancestors 'none'"]:
    assert needle in text, f"Falta en player: {needle}"
assert re.search(r"hls\.js@1\.7\.3",text)
print("OK: player beta validado.")
