from pathlib import Path
import hashlib
import json

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parent
DATA = BASE / 'data'

def load(name):
    path = DATA / name
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}

def generator_report():
    manifest = load('pipeline_manifest.json')
    quality = load('quality.json')
    status = load('status.json')
    teleon = load('teleon_quality.json')
    m3u = (BASE / 'IPTV-CHILE-GENERADOR.m3u').read_text(encoding='utf-8-sig', errors='replace')
    urls = [x.strip() for x in m3u.splitlines() if x.strip().startswith(('http://', 'https://'))]
    lines = [
        '# Reporte de estado - IPTV-CHILE-GENERADOR',
        '',
        f'- Canales publicados: **{len(urls)}**',
        f'- URLs únicas: **{len(set(urls))}**',
        f'- Candidatos evaluados: **{quality.get("endpoint_candidates", 0)}**',
        f'- Playback OK: **{quality.get("playback_ok", 0)}**',
        f'- Manifest generado: **{manifest.get("generated_channels", 0)} canales**',
        f'- Teleon candidatos validados: **{teleon.get("total_candidates", 0)}**',
        f'- Teleon playback OK: **{teleon.get("playback_ok", 0)}**',
        '',
        'Este reporte pertenece exclusivamente al pipeline Generador y no modifica Principal, GOD o Pluto.',
    ]
    out = ROOT / 'reportes' / 'generador' / 'REPORTE.md'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text('\n'.join(lines) + '\n', encoding='utf-8')

def god_report():
    path = ROOT / 'IPTV-CHILE-MAESTRA_GOD.m3u'
    text = path.read_text(encoding='utf-8-sig', errors='replace')
    urls = [x.strip() for x in text.splitlines() if x.strip().startswith(('http://', 'https://'))]
    extinf = sum(1 for x in text.splitlines() if x.startswith('#EXTINF:'))
    duplicates = len(urls) - len(set(urls))
    reconnect = text.count('#EXTVLCOPT:http-reconnect=true')
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    lines = [
        '# Reporte de estado - GOD',
        '',
        f'- Archivo: {path.as_posix()}',
        f'- Canales: **{extinf}**',
        f'- URLs: **{len(urls)}**',
        f'- Duplicados históricos: **{duplicates}** (permitidos por guard.py)',
        f'- Directivas de reconexión: **{reconnect}**',
        f'- SHA-256: {sha}',
        '',
        'Reporte exclusivo de GOD; no modifica la lista protegida.',
    ]
    out = ROOT / 'reportes' / 'god' / 'REPORTE.md'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text('\n'.join(lines) + '\n', encoding='utf-8')

if __name__ == '__main__':
    generator_report()
    god_report()
    print('Reportes Generador y GOD generados.')