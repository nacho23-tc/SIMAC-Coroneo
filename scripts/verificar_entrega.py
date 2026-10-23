
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'tmp' / 'entrega' / 'INVENTARIO_PUBLICACION.json'


def git(*args, input_data=None):
    executable = shutil.which('git')
    if not executable:
        raise RuntimeError('Instala Git o agrega su ejecutable al PATH.')
    result = subprocess.run([executable, '-c', 'core.quotepath=false', *args], cwd=ROOT,
                            input=input_data, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode not in (0, 1):
        raise RuntimeError('No se pudo consultar Git; ejecuta git init si esta copia aún no es un repositorio.')
    return result


def main():
    paths = sorted(set(p.decode('utf-8') for p in git('ls-files', '--cached', '--others', '--exclude-standard', '-z').stdout.split(b'\0') if p))
    # El informe no se enumera a sí mismo para evitar un inventario recursivo.
    paths = [p for p in paths if (ROOT / p).resolve() != OUTPUT]
    findings = []
    inventory = []
    approved_resources = {}
    resource_manifest = ROOT / 'docs' / 'RECURSOS_DEMOSTRACION.json'
    if resource_manifest.exists():
        approved_resources = {item['archivo']: item for item in json.loads(resource_manifest.read_text(encoding='utf-8'))}

    protected = re.compile(r'(^|/)(?:data|node_modules|dist|tmp|\.venv[^/]*|__pycache__)(/|$)|(^|/)\.env(?:\..*)?$|\.(?:sqlite3?|db|joblib|pkl|pem|key)$')
    secret_pattern = re.compile(r'\b(?:gsk_[A-Za-z0-9_-]{20,}|sk-(?:proj-)?[A-Za-z0-9_-]{20,}|AIza[A-Za-z0-9_-]{25,})|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----')
    local_values = []
    env_path = ROOT / '.env'
    if env_path.exists():
        for line in env_path.read_text(encoding='utf-8-sig').splitlines():
            name, sep, value = line.partition('=')
            value = value.strip().strip('"\'')
            if sep and re.search(r'(?:KEY|TOKEN|PASSWORD|SECRET)', name, re.I) and len(value) >= 12:
                local_values.append(value.encode())
    for relative in paths:
        path = ROOT / relative
        if not path.is_file():
            continue
        if protected.search(relative) and path.name != '.env.example' and relative not in approved_resources and not relative.startswith('dist/'):
            findings.append({'archivo': relative, 'tipo': 'archivo_privado_candidato'})
        raw = path.read_bytes()
        if any(value in raw for value in local_values):
            findings.append({'archivo': relative, 'tipo': 'valor_de_credencial_local'})
        if path.suffix.lower() in {'.py', '.tsx', '.ts', '.js', '.json', '.md', '.txt', '.html', '.ps1', '.yml', '.yaml', '.toml', '.example'}:
            text = raw.decode('utf-8-sig', errors='replace')
            for line_number, line in enumerate(text.splitlines(), 1):
                if secret_pattern.search(line):
                    findings.append({'archivo': relative, 'linea': line_number, 'tipo': 'posible_credencial'})
        resource = approved_resources.get(relative)
        if resource and hashlib.sha256(raw).hexdigest() != resource['sha256']:
            findings.append({'archivo': relative, 'tipo': 'recurso_de_demo_modificado_desde_revision'})
        transport = resource.get('tipo') if resource else 'Git'
        if len(raw) > 100 * 1024 * 1024 and transport != 'Git LFS':
            findings.append({'archivo': relative, 'tipo': 'archivo_grande_sin_lfs'})
        inventory.append({'archivo': relative, 'bytes': len(raw), 'transporte': transport})
    checks = []
    for directory in ['muestras', 'reportes']:
        manifest = ROOT / directory / 'manifest.json'
        try:
            entries = json.loads(manifest.read_text(encoding='utf-8'))
            valid = len(entries) == 7 and {e['muestra'] for e in entries} == {f'SIMAC-{n:03}' for n in range(1, 8)}
            for entry in entries:
                path = ROOT / directory / entry['archivo']
                valid = valid and path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == entry['sha256']
            checks.append({'comprobacion': directory + '_7_evidencias', 'correcta': valid})
        except (OSError, ValueError, KeyError):
            checks.append({'comprobacion': directory + '_7_evidencias', 'correcta': False})
    try:
        entries = json.loads((ROOT / 'public/Visual/catalogo.json').read_text(encoding='utf-8'))
        valid = len(entries) == 80 and len({e['code'] for e in entries}) == 80
        for entry in entries:
            path = ROOT / 'public/Visual' / entry['file']
            valid = valid and path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == entry['sha256']
        checks.append({'comprobacion': 'catalogo_80_fotografias', 'correcta': valid})
        for name in ['galleryData.json', 'collectionPhotos.json']:
            entries = json.loads((ROOT / 'src' / name).read_text(encoding='utf-8'))
            valid = all((ROOT / 'public' / entry[key].lstrip('/')).is_file()
                        for entry in entries for key in (['photo', 'overlay', 'dimensions'] if name == 'galleryData.json' else ['src']))
            checks.append({'comprobacion': name + '_recursos', 'correcta': valid})
    except (OSError, ValueError, KeyError):
        checks.append({'comprobacion': 'catalogos', 'correcta': False})
    pdf_manifest = ROOT / 'reportes' / 'manifest_pdf.json'
    if pdf_manifest.exists():
        entries = json.loads(pdf_manifest.read_text(encoding='utf-8'))
        valid = len(entries) >= 7 and {f'SIMAC-{n:03}' for n in range(1,8)} <= {e['muestra'] for e in entries}
        for entry in entries:
            path = ROOT / 'reportes' / entry['archivo']
            valid = valid and path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == entry['sha256']
        checks.append({'comprobacion': 'pdf_originales', 'correcta': valid})
    if approved_resources:
        valid = all((ROOT / name).is_file() for name in approved_resources)
        checks.append({'comprobacion': 'recursos_demostracion', 'correcta': valid})
        for name, item in approved_resources.items():
            if item.get('tipo') == 'Git LFS':
                attributes = git('check-attr', 'filter', '--', name).stdout.decode()
                if not attributes.strip().endswith(': lfs'):
                    findings.append({'archivo': name, 'tipo': 'falta_configuracion_git_lfs'})
    required = ['README.md', '.gitignore', '.env.example', 'package.json', 'package-lock.json', 'vite.config.ts', 'tsconfig.json',
                'index.html', 'backend/main.py', 'backend/requirements.txt', 'backend/requirements-lock.txt', 'src/main.tsx',
                'docs/RECURSOS_DEMOSTRACION.json']
    checks.append({'comprobacion': 'archivos_necesarios', 'correcta': all((ROOT / p).is_file() for p in required)})
    ignored_examples = ['.env', '.evn', 'data/archivo_nuevo_no_revisado.sqlite3', 'node_modules/react/index.js',
                        '.venv-cellpose/pyvenv.cfg', 'backend/__pycache__/main.pyc']
    ignored = git('check-ignore', '--no-index', '--stdin', '-z', input_data=b'\0'.join(p.encode() for p in ignored_examples) + b'\0').stdout
    checks.append({'comprobacion': 'exclusiones_privadas', 'correcta': set(ignored.split(b'\0')) >= {p.encode() for p in ignored_examples}})
    checks.append({'comprobacion': 'ejemplo_env_incluido', 'correcta': '.env.example' in paths})
    safe = not findings and all(c['correcta'] for c in checks)
    data = {'estado_tecnico': 'sin_hallazgos_en_revision_automatica' if safe else 'requiere_revision',
            'publicacion_autorizada': False,
            'nota': 'Inventario local de candidatos, no archivos publicados. No demuestra permisos de terceros ni ausencia absoluta de datos sensibles. No enumera este propio informe.',
            'archivos_candidatos': inventory, 'total_archivos': len(inventory),
            'total_bytes': sum(i['bytes'] for i in inventory), 'hallazgos_sin_valores': findings, 'comprobaciones': checks,
            'exclusiones': ['.env y variantes', 'datos nuevos no revisados', 'node_modules/', 'entornos virtuales', 'tmp/', 'caches y logs']}
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'archivos_candidatos': len(inventory), 'hallazgos': len(findings),
                      'comprobaciones_correctas': sum(c['correcta'] for c in checks), 'comprobaciones': len(checks),
                      'publicado': False}, ensure_ascii=True))
    for finding in findings:
        print(json.dumps(finding, ensure_ascii=True))
    for check in checks:
        if not check['correcta']:
            print(json.dumps(check, ensure_ascii=True))
    return 0 if safe else 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except RuntimeError as error:
        print(str(error), file=sys.stderr)
        sys.exit(2)
