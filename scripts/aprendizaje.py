import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
ARCHIVO = BASE / "scripts" / "aprendizaje.json"

VERSION = 2
RETENCION_DIAS = 120
MAX_ENTRADAS = 12000


def _ahora():
    return datetime.now(timezone.utc)


def _iso(dt):
    return dt.isoformat()


def cargar():
    if not ARCHIVO.exists():
        return {}

    try:
        texto = ARCHIVO.read_text(
            encoding="utf-8-sig",
            errors="ignore"
        ).strip()

        if not texto:
            return {}

        datos = json.loads(texto)

        if not isinstance(datos, dict):
            return {}

        if datos.get("_meta", {}).get("version") != VERSION:
            return {}

        return {
            url: registro
            for url, registro in datos.items()
            if not url.startswith("_")
            and isinstance(registro, dict)
        }

    except Exception as e:
        print(f"[APRENDIZAJE] Error leyendo historial: {e}")
        return {}


def _guardar(datos):
    ARCHIVO.parent.mkdir(parents=True, exist_ok=True)

    ahora = _ahora()
    salida = {
        "_meta": {
            "version": VERSION,
            "actualizado": _iso(ahora),
            "entradas": len(datos),
        }
    }
    salida.update(datos)

    temporal = ARCHIVO.with_suffix(".tmp")
    temporal.write_text(
        json.dumps(
            salida,
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    temporal.replace(ARCHIVO)


def _nuevo(nombre, ahora):
    return {
        "n": 0,
        "ok": 0,
        "fail": 0,
        "streak_ok": 0,
        "streak_fail": 0,
        "last": _iso(ahora),
        "last_ok": None,
        "last_fail": None,
        "nombre": nombre or "",
    }


def _actualizar(registro, nombre, ok, ahora):
    if nombre:
        registro["nombre"] = nombre

    registro["n"] = int(registro.get("n", 0)) + 1
    registro["last"] = _iso(ahora)

    if ok:
        registro["ok"] = int(registro.get("ok", 0)) + 1
        registro["streak_ok"] = int(registro.get("streak_ok", 0)) + 1
        registro["streak_fail"] = 0
        registro["last_ok"] = _iso(ahora)
    else:
        registro["fail"] = int(registro.get("fail", 0)) + 1
        registro["streak_fail"] = int(registro.get("streak_fail", 0)) + 1
        registro["streak_ok"] = 0
        registro["last_fail"] = _iso(ahora)


def registrar(url, nombre="", resultado=False):
    registrar_lote([
        {
            "url": url,
            "nombre": nombre,
            "ok": resultado,
        }
    ])


def registrar_lote(resultados):
    """
    Aprende por URL, no por nombre.

    Cada ejecución cuenta como una sola observación por URL, aunque
    la misma URL aparezca repetida en más de una lista.
    """
    datos = cargar()
    ahora = _ahora()

    unicos = {}
    for item in resultados:
        url = (item.get("url") or "").strip()
        if not url:
            continue
        unicos[url] = {
            "nombre": item.get("nombre", ""),
            "ok": bool(item.get("ok", False)),
        }

    for url, item in unicos.items():
        registro = datos.get(url)
        if not isinstance(registro, dict):
            registro = _nuevo(item["nombre"], ahora)
            datos[url] = registro

        _actualizar(
            registro,
            item["nombre"],
            item["ok"],
            ahora,
        )

    limite = ahora - timedelta(days=RETENCION_DIAS)
    conservar = {}

    for url, registro in datos.items():
        try:
            ultima = datetime.fromisoformat(
                registro.get("last", "")
            )
        except Exception:
            continue

        if ultima >= limite:
            conservar[url] = registro

    if len(conservar) > MAX_ENTRADAS:
        ordenados = sorted(
            conservar.items(),
            key=lambda x: x[1].get("last", ""),
            reverse=True,
        )
        conservar = dict(ordenados[:MAX_ENTRADAS])

    _guardar(conservar)

    print(
        f"[APRENDIZAJE] {len(unicos)} observaciones nuevas | "
        f"{len(conservar)} URLs aprendidas"
    )


def obtener(url):
    return cargar().get(url)


def porcentaje(url):
    canal = obtener(url)
    if not canal:
        return None

    total = int(canal.get("n", 0))
    if total <= 0:
        return None

    ok = int(canal.get("ok", 0))
    return round((ok / total) * 100, 2)


def estado(url):
    canal = obtener(url)
    if not canal:
        return "NUEVO"

    n = int(canal.get("n", 0))
    ok = int(canal.get("ok", 0))
    fail_streak = int(canal.get("streak_fail", 0))

    if n < 3:
        return "NUEVO"

    if fail_streak >= 3:
        return "CAIDO_REPETIDO"

    fiabilidad = (ok / n) * 100

    if fiabilidad >= 90:
        return "ESTABLE"

    if fiabilidad >= 60:
        return "INTERMITENTE"

    return "INESTABLE"


def perfil(url):
    canal = obtener(url)
    if not canal:
        return {
            "estado": "NUEVO",
            "fiabilidad": None,
            "comprobaciones": 0,
            "racha_fallos": 0,
            "racha_ok": 0,
        }

    n = int(canal.get("n", 0))
    ok = int(canal.get("ok", 0))

    return {
        "estado": estado(url),
        "fiabilidad": round((ok / n) * 100, 2) if n else None,
        "comprobaciones": n,
        "racha_fallos": int(canal.get("streak_fail", 0)),
        "racha_ok": int(canal.get("streak_ok", 0)),
    }


def parametros_verificacion(url, timeout, reintentos):
    """
    La experiencia anterior modifica la siguiente comprobación.

    - URL nueva: parámetros normales.
    - URL intermitente/inestrable: más reintentos y +1 s de timeout.
    - URL caída repetidamente: un solo reintento para confirmar.
    - URL estable: parámetros normales.
    """
    p = perfil(url)
    estado_actual = p["estado"]

    if estado_actual in {"INTERMITENTE", "INESTABLE"}:
        return min(timeout + 1, 8), max(reintentos, 2)

    if estado_actual == "CAIDO_REPETIDO":
        return timeout, max(reintentos, 1)

    return timeout, reintentos


def resumen():
    datos = cargar()

    total = len(datos)
    comprobaciones = sum(int(x.get("n", 0)) for x in datos.values())
    ok = sum(int(x.get("ok", 0)) for x in datos.values())
    fallos = sum(int(x.get("fail", 0)) for x in datos.values())

    estados = {}
    for url in datos:
        e = estado(url)
        estados[e] = estados.get(e, 0) + 1

    return {
        "canales": total,
        "comprobaciones": comprobaciones,
        "ok": ok,
        "fallos": fallos,
        "estados": estados,
    }


if __name__ == "__main__":
    print("=" * 60)
    print(" IPTV CHILE MASTER - SISTEMA DE APRENDIZAJE v2")
    print("=" * 60)
    print(json.dumps(resumen(), ensure_ascii=False, indent=2))
