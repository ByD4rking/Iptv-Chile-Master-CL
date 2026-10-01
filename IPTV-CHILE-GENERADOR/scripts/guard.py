import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GENERATOR = ROOT / "IPTV-CHILE-GENERADOR"
GOD_CANONICAL_SHA256 = "78520768a5e3a114a648702cbb044cd952e9b44019434765222c031219909c96"

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


def god_normalized_sha256(path):
    raw = path.read_bytes()
    # The only permitted post-hardening change to GOD is the two reconnect
    # directives applied by aplicar_reconexion_god.py. Everything else must
    # remain byte-for-byte identical to the canonical historical file.
    raw = re.sub(rb"^#EXTVLCOPT:http-reconnect=true\r?\n", b"", raw, flags=re.MULTILINE)
    raw = re.sub(rb"^#EXTVLCOPT:network-caching=1500\r?\n", b"", raw, flags=re.MULTILINE)
    return hashlib.sha256(raw).hexdigest()


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


def assert_god_integrity():
    god = ROOT / "IPTV-CHILE-MAESTRA_GOD.m3u"
    if not god.exists() or not god.is_file():
        raise SystemExit("PROTECCION GOD: IPTV-CHILE-MAESTRA_GOD.m3u no existe.")
    actual = god_normalized_sha256(god)
    if actual != GOD_CANONICAL_SHA256:
        raise SystemExit(
            "PROTECCION GOD: el contenido histórico fue modificado fuera de las "
            "directivas de reconexión permitidas. "
            f"SHA normalizado esperado={GOD_CANONICAL_SHA256} SHA actual={actual}"
        )
    print(f"BLINDAJE GOD: contenido canónico verificado tras normalizar reconexión ({actual}).")


def main():
    if not GENERATOR.is_dir():
        raise SystemExit(f"No existe el generador: {GENERATOR}")

    assert_god_integrity()

    for path in (ROOT / "IPTV-CHILE-MAESTRA_CORREGIDO.m3u", ROOT / "IPTV-CHILE-MAESTRA_GOD.m3u"):
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
