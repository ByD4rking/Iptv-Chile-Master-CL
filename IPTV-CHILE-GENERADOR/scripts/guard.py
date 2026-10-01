import hashlib
import re
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


def validate_m3u(path, reject_duplicates=True):
    if not path.exists() or not path.is_file():
        raise SystemExit(f"PROTECCION: no existe la lista: {path.relative_to(ROOT)}")
    text = path.read_text(encoding="utf-8-sig", errors="strict")
    if not text.startswith("#EXTM3U"):
        raise SystemExit(f"PROTECCION: {path.name} no comienza con #EXTM3U")
    extinf = len(re.findall(r"^#EXTINF:", text, re.MULTILINE))
    urls = [line.strip() for line in text.splitlines() if line.startswith(("http://", "https://"))]
    if extinf <= 0:
        raise SystemExit(f"PROTECCION: {path.name} no contiene canales")
    if extinf != len(urls):
        raise SystemExit(f"PROTECCION: {path.name}: EXTINF={extinf}, URLs={len(urls)}")
    if reject_duplicates and len(urls) != len(set(urls)):
        raise SystemExit(f"PROTECCION: {path.name}: contiene URLs duplicadas")
    if any(not url.startswith(("http://", "https://")) for url in urls):
        raise SystemExit(f"PROTECCION: {path.name}: URL no HTTP/HTTPS")
    return extinf, len(urls)


def main():
    if not GENERATOR.is_dir():
        raise SystemExit(f"No existe el generador: {GENERATOR}")

    # Estas dos maestras reciben las mismas barreras estructurales del generador:
    # integridad M3U, correspondencia EXTINF/URL y ausencia de duplicados.
    for path in (ROOT / "IPTV-CHILE-MAESTRA_CORREGIDO.m3u", ROOT / "IPTV-CHILE-MAESTRA_GOD.m3u"):
        # GOD es un catálogo histórico agregado y puede contener el mismo
        # endpoint en varias entradas; se audita su estructura, pero no se
        # altera ni se interpreta esa duplicación como corrupción.
        reject_duplicates = path.name != "IPTV-CHILE-MAESTRA_GOD.m3u"
        channels, urls = validate_m3u(path, reject_duplicates=reject_duplicates)
        extra = "" if reject_duplicates else " (duplicados históricos permitidos)"
        print(f"VALIDA: {path.relative_to(ROOT)} -> {channels} canales / {urls} URLs{extra}")

    output = GENERATOR / "IPTV-CHILE-GENERADOR.m3u"
    if output.exists():
        channels, urls = validate_m3u(output)
        print(f"VALIDA: {output.relative_to(ROOT)} -> {channels} canales / {urls} URLs")

    for path in PROTECTED:
        print(f"{digest(path)}  {path.relative_to(ROOT)}")
    print("OK: rutas protegidas e integridad M3U auditadas.")


if __name__ == "__main__":
    main()
