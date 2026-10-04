from pathlib import Path
p = Path("TV/shared/player.js")
assert p.is_file(), f"no existe {p}"
s = p.read_text(encoding="utf-8")
assert "IPTV-CHILE-GENERADOR.m3u" in s
assert "retries>=6" in s
assert "Math.pow(2,retries)" in s
assert 'addEventListener("error"' in s
assert 'addEventListener("stalled"' in s
assert 'addEventListener("ended"' in s
print("TV static/reconnect checks: OK")
