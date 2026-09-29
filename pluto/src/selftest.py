from __future__ import annotations

"""Static and structural self-test for the Pluto generator/server.

This test deliberately uses only Python's standard library so it can run before
the runtime dependencies are installed and catch malformed source early.
"""

import ast
import compileall
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
EXPECTED_SERVER_ROUTES = {
    "/",
    "/channels",
    "/playlist.m3u",
    "/stream/<channel_id>",
    "/pluto-master/<channel_id>.m3u8",
    "/pluto-proxy/<channel_id>/<encoded_url>",
}


def fail(message: str) -> None:
    raise SystemExit(f"SELFTEST ERROR: {message}")


def main() -> None:
    py_files = sorted(ROOT.glob("*.py"))
    if not py_files:
        fail("no se encontraron archivos Python en pluto/src")

    for path in py_files:
        raw = path.read_bytes()
        if b"\x00" in raw:
            fail(f"{path.name}: contiene bytes NUL")
        try:
            source = raw.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            fail(f"{path.name}: UTF-8 inválido: {exc}")
        try:
            tree = ast.parse(source, filename=str(path))
            compile(tree, str(path), "exec")
        except (SyntaxError, ValueError, TypeError) as exc:
            fail(f"{path.name}: sintaxis Python inválida: {exc}")

        # Detecta accidentalmente código pegado después de un guard principal.
        guards = [
            node for node in tree.body
            if isinstance(node, ast.If)
            and isinstance(node.test, ast.Compare)
            and any(
                isinstance(op, ast.Eq) for op in node.test.ops
            )
            and isinstance(node.test.left, ast.Name)
            and node.test.left.id == "__name__"
        ]
        if len(guards) > 1:
            fail(f"{path.name}: múltiples guards __name__ == '__main__'")

    if not compileall.compile_dir(str(ROOT), quiet=1, force=True):
        fail("compileall falló")

    server = (ROOT / "server.py").read_text(encoding="utf-8-sig")
    required_fragments = (
        "def _fetch(",
        "def _rewrite_playlist(",
        "def _refresh_jwt(",
        '@app.get("/pluto-master/<channel_id>.m3u8")',
        '@app.get("/pluto-proxy/<channel_id>/<encoded_url>")',
        'threaded=True',
        'os.getenv("PLUTO_HOST"',
        'os.getenv("PLUTO_PORT"',
    )
    for fragment in required_fragments:
        if fragment not in server:
            fail(f"server.py: falta estructura requerida: {fragment}")

    if "127.0.0.1:5000/stream/" in server:
        fail("server.py: la playlist no debe apuntar a localhost del dispositivo cliente")

    # El servidor debe mantener la reescritura de atributos URI de HLS.
    if not re.search(r"re\.sub\(r['\"]URI=", server):
        fail("server.py: falta reescritura de URI internas HLS")

    print(f"SELFTEST OK: {len(py_files)} archivos Python sin errores de sintaxis.")
    print("SELFTEST OK: compileall correcto.")
    print("SELFTEST OK: servidor Pluto conserva proxy, renovación JWT y acceso LAN.")


if __name__ == "__main__":
    main()
