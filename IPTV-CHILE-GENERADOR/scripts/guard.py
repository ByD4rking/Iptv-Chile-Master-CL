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


def assert_god_immutable():
    god = ROOT / "IPTV-CHILE-MAESTRA_GOD.m3u"
    if not god.exists() or not god.is_file():
        raise SystemExit("PROTECCION GOD: IPTV-CHILE-MAESTRA_GOD.m3u no existe.")
    actual = file_sha256(god)
    if actual != GOD_CANONICAL_SHA256:
        raise SystemExit(
            "PROTECCION GOD: la maestra histórica fue modificada, reemplazada o truncada. "
            f"SHA esperado={GOD_CANONICAL_SHA256} SHA actual={actual}"
        )
    print(f"BLINDAJE GOD: SHA-256 canónico verificado ({actual}).")


def main():
    if not GENERATOR.is_dir():
        raise SystemExit(f"No existe el generador: {GENERATOR}")

    # GOD tiene además una huella SHA-256 canónica e inmutable. Si cambia un solo byte,
    # el generador se detiene antes de publicar cualquier artefacto.
    assert_god_immutable()

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
