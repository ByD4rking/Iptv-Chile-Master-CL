import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GENERATOR = ROOT / "IPTV-CHILE-GENERADOR"
PROTECTED = (
    ROOT / "IPTV-CHILE-MAESTRA_CORREGIDO.m3u",
    ROOT / "IPTV-CHILE-MAESTRA_GOD.m3u",
    ROOT / "pluto" / "output" / "playlists",
    ROOT / "scripts",
)

def digest(path):
    h = hashlib.sha256()
    if path.is_file():
        h.update(path.read_bytes())
    elif path.is_dir():
        for item in sorted(path.rglob("*")):
            if item.is_file():
                h.update(str(item.relative_to(path)).encode())
                h.update(item.read_bytes())
    else:
        h.update(b"<missing>")
    return h.hexdigest()

def main():
    if not GENERATOR.is_dir():
        raise SystemExit(f"No existe el generador: {GENERATOR}")
    for path in PROTECTED:
        print(f"{digest(path)}  {path.relative_to(ROOT)}")
    print("OK: rutas protegidas auditadas.")

if __name__ == "__main__":
    main()
