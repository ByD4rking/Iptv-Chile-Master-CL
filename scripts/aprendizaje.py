import json
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
ARCHIVO = BASE / "scripts" / "aprendizaje.json"


def cargar():
    if not ARCHIVO.exists():
        return {}

    try:
        texto = ARCHIVO.read_text(
            encoding="utf-8",
            errors="ignore"
        ).strip()

        if not texto:
            return {}

        datos = json.loads(texto)

        if isinstance(datos, dict):
            return datos

    except Exception as e:
        print(f"[APRENDIZAJE] Error leyendo historial: {e}")

    return {}


def guardar(datos):
    ARCHIVO.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    temporal = ARCHIVO.with_suffix(".tmp")

    temporal.write_text(
        json.dumps(
            datos,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

    temporal.replace(ARCHIVO)


def registrar(url, nombre="", resultado=False):
    datos = cargar()

    ahora = datetime.now(
        timezone.utc
    ).isoformat()

    if url not in datos:
        datos[url] = {
            "nombre": nombre,
            "comprobaciones": 0,
            "ok": 0,
            "fallos": 0,
            "primera_vez": ahora,
            "ultima_comprobacion": None,
            "ultima_ok": None,
            "ultimo_fallo": None
        }

    canal = datos[url]

    if nombre:
        canal["nombre"] = nombre

    canal["comprobaciones"] += 1
    canal["ultima_comprobacion"] = ahora

    if resultado:
        canal["ok"] += 1
        canal["ultima_ok"] = ahora
    else:
        canal["fallos"] += 1
        canal["ultimo_fallo"] = ahora

    guardar(datos)


def registrar_lote(resultados):
    """
    resultados:
        [
            {
                "url": "...",
                "nombre": "...",
                "ok": True
            }
        ]
    """

    datos = cargar()

    ahora = datetime.now(
        timezone.utc
    ).isoformat()

    for item in resultados:

        url = item.get("url")

        if not url:
            continue

        nombre = item.get(
            "nombre",
            ""
        )

        resultado = bool(
            item.get("ok", False)
        )

        if url not in datos:

            datos[url] = {
                "nombre": nombre,
                "comprobaciones": 0,
                "ok": 0,
                "fallos": 0,
                "primera_vez": ahora,
                "ultima_comprobacion": None,
                "ultima_ok": None,
                "ultimo_fallo": None
            }

        canal = datos[url]

        if nombre:
            canal["nombre"] = nombre

        canal["comprobaciones"] += 1
        canal["ultima_comprobacion"] = ahora

        if resultado:

            canal["ok"] += 1
            canal["ultima_ok"] = ahora

        else:

            canal["fallos"] += 1
            canal["ultimo_fallo"] = ahora

    guardar(datos)


def obtener(url):
    datos = cargar()

    return datos.get(url)


def porcentaje(url):
    canal = obtener(url)

    if not canal:
        return None

    total = canal.get(
        "comprobaciones",
        0
    )

    if total <= 0:
        return None

    ok = canal.get(
        "ok",
        0
    )

    return round(
        (ok / total) * 100,
        2
    )


def resumen():
    datos = cargar()

    total = len(datos)

    comprobaciones = sum(
        item.get("comprobaciones", 0)
        for item in datos.values()
    )

    ok = sum(
        item.get("ok", 0)
        for item in datos.values()
    )

    fallos = sum(
        item.get("fallos", 0)
        for item in datos.values()
    )

    return {
        "canales": total,
        "comprobaciones": comprobaciones,
        "ok": ok,
        "fallos": fallos
    }


if __name__ == "__main__":

    print("=" * 60)
    print(" IPTV CHILE MASTER - SISTEMA DE APRENDIZAJE")
    print("=" * 60)

    datos = cargar()

    print(
        f"Canales registrados: {len(datos)}"
    )

    print(
        resumen()
    )