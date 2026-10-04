from pathlib import Path
p = Path(__file__).parents[1] / "shared" / "player.js"
s = p.read_text(encoding="utf-8")
for needle in ("Math.pow(2,retries)", "retries>=6", 'addEventListener("error"', 'addEventListener("stalled"', "IPTV-CHILE-GENERADOR.m3u"):
    assert needle in s, f"faltante: {needle}"
print("TV static/reconnect checks: OK")
