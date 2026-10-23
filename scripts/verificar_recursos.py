"""Verificación de los recursos de demostración descargados antes del primer inicio."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    entries = json.loads((ROOT / 'docs/RECURSOS_DEMOSTRACION.json').read_text(encoding='utf-8'))
    failures = []
    for entry in entries:
        path = ROOT / entry['archivo']
        if not path.is_file():
            failures.append({'archivo': entry['archivo'], 'motivo': 'no encontrado'})
            continue
        with path.open('rb') as source:
            header = source.read(150)
            source.seek(0)
            digest = hashlib.file_digest(source, 'sha256').hexdigest()
        if header.startswith(b'version https://git-lfs.github.com/spec/v1'):
            failures.append({'archivo': entry['archivo'], 'motivo': 'solo puntero LFS; ejecuta git lfs pull'})
        elif digest != entry['sha256']:
            failures.append({'archivo': entry['archivo'], 'motivo': 'contenido distinto de la instantanea'})
    print(json.dumps({'recursos': len(entries), 'correctos': len(entries) - len(failures), 'problemas': failures}, ensure_ascii=True))
    if failures:
        print('Antes del primer inicio, ejecuta git lfs pull y vuelve a verificar. Si ya usaste la aplicación, sus datos pueden haber cambiado legítimamente; no los sobrescribas sin respaldo.')
    return 1 if failures else 0


if __name__ == '__main__':
    sys.exit(main())
