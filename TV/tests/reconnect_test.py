from pathlib import Path
p = Path(__file__).resolve().parents[1] / "shared" / "player.js"
s = p.read_text(encoding="utf-8")
checks = {
    "catalog": "IPTV-CHILE-GENERADOR.m3u",
    "bounded retries": "retries>=6",
    "exponential backoff": "Math.pow(2,retries)",
    "error recovery": 'addEventListener("error"',
    "stalled recovery": 'addEventListener("stalled"',
    "ended recovery": 'addEventListener("ended"',
}
missing = [name for name, needle in checks.items() if needle not in s]
assert not missing, "faltan controles: " + ", ".join(missing)
print("TV static/reconnect checks: OK")
