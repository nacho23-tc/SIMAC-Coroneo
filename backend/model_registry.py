"""Versiones locales generadas por SIMAC. Solo se cargan artefactos propios por UUID."""
import hashlib
import json
import uuid
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

_write_lock = threading.RLock()


def write_json(path, value):
    with _write_lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name+'.'+str(uuid.uuid4())+'.tmp')
        try:
            temporary.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False), encoding='utf-8')
            for attempt in range(5):
                try:
                    temporary.replace(path)
                    break
                except PermissionError:
                    if attempt == 4: raise
                    time.sleep(.02)
        finally:
            temporary.unlink(missing_ok=True)


def save_candidate(root, fitted, metadata):
    import joblib
    identifier = str(uuid.uuid4())
    directory = Path(root)/'yield_models'
    directory.mkdir(parents=True, exist_ok=True)
    target = directory/(identifier+'.joblib')
    temporary = target.with_suffix('.tmp')
    joblib.dump(fitted, temporary)
    temporary.replace(target)
    manifest = {**metadata, 'id': identifier, 'created': datetime.now(timezone.utc).isoformat(),
                'experimental': True, 'sha256': hashlib.sha256(target.read_bytes()).hexdigest()}
    write_json(directory/(identifier+'.json'), manifest)
    return identifier


def models(root):
    directory = Path(root)/'yield_models'
    active_path = directory/'active.json'
    warnings = []
    try:
        active = json.loads(active_path.read_text(encoding='utf-8')).get('id') if active_path.exists() else None
    except (ValueError, OSError, AttributeError):
        active = None
        warnings.append('No se pudo leer la selección del modelo activo.')
    candidates = []
    for path in directory.glob('*.json'):
        if path.name == 'active.json': continue
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            if not isinstance(data,dict) or not {'id','created','parameters','test_metrics','mode'}.issubset(data):
                raise ValueError('Ficha incompleta')
            candidates.append({**data, 'active': data['id'] == active})
        except (ValueError,OSError):
            warnings.append('Se omitió una ficha de modelo dañada: '+path.name)
    return {'active_id': active, 'models': sorted(candidates, key=lambda r: r['created'], reverse=True), 'warnings':warnings}


def activate(root, identifier):
    identifier = str(uuid.UUID(identifier))
    directory = Path(root)/'yield_models'
    if not (directory/(identifier+'.json')).exists() or not (directory/(identifier+'.joblib')).exists():
        raise ValueError('No se encontró una versión entrenada para activar.')
    manifest = json.loads((directory/(identifier+'.json')).read_text(encoding='utf-8'))
    required={'mode','columns','threshold','min_grains','sklearn_version','train_families','range_min','range_max','parameters','validation_metrics','test_metrics'}
    if not isinstance(manifest,dict) or not required.issubset(manifest) or manifest.get('sha256') != hashlib.sha256((directory/(identifier+'.joblib')).read_bytes()).hexdigest():
        raise ValueError('La versión está dañada y no se puede activar. Vuelve a entrenarla.')
    write_json(directory/'active.json', {'id': identifier})
    return {'active_id': identifier}


def classify(root, payload):
    try:
        return _classify(root, payload)
    except (OSError, ValueError, KeyError, TypeError, ImportError, EOFError, AttributeError):
        return {'status':'unavailable','label':None,'reason':'El modelo activo no está disponible o está dañado. Selecciona otra versión en Administración de modelos.'}


def _classify(root, payload):
    import numpy as np
    from .yield_experiment import prepare, family
    directory = Path(root)/'yield_models'
    pointer = directory/'active.json'
    if not pointer.exists():
        return {'status': 'pending', 'label': None, 'reason': 'Clasificación pendiente: aún no hay un modelo de rendimiento activo.'}
    identifier = str(uuid.UUID(json.loads(pointer.read_text(encoding='utf-8'))['id']))
    manifest = json.loads((directory/(identifier+'.json')).read_text(encoding='utf-8'))
    data = dict(payload)
    # El modelo de imagen no necesita el objetivo ni una asociación externa para inferir.
    if manifest['mode'] == 'imagen':
        name = (payload.get('result') or {}).get('sample', 'Muestra')
        data['metadata'] = {'key': 'familia', 'identifier': name, 'rows': [{'familia': name}]}
    row = prepare(data, manifest['mode'])
    reasons = list(row['reasons'])
    if row['count'] < manifest['min_grains']:
        reasons.append(f"Se requieren al menos {manifest['min_grains']} granos revisados para este modelo.")
    if reasons:
        return {'status': 'pending', 'label': None, 'model_id': identifier, 'reason': ' '.join(reasons), 'provenance':manifest.get('provenance')}
    import joblib, sklearn
    if sklearn.__version__ != manifest['sklearn_version']:
        return {'status': 'pending', 'label': None, 'reason': 'El modelo requiere actualizarse desde Administración de modelos.'}
    target = directory/(identifier+'.joblib')
    if hashlib.sha256(target.read_bytes()).hexdigest() != manifest['sha256']:
        return {'status': 'pending', 'label': None, 'reason': 'No se pudo verificar el modelo activo. Revisa su versión en Administración.'}
    fitted = joblib.load(target)
    x = np.array([[row['features'][c] for c in manifest['columns']]])
    outside = bool(np.any((x[0] < manifest['range_min']) | (x[0] > manifest['range_max'])))
    known = family(row['family']) in [family(name) for name in manifest['train_families']]
    return {'status': 'experimental', 'label': str(fitted.predict(x)[0]), 'model_id': identifier,
            'threshold': manifest['threshold'], 'outside_training_range': outside, 'known_family': known,
            'reason': 'Clasificación experimental respecto al grupo entrenado. ' + ('Modelo del curso; falta validación en Coroneo.' if manifest.get('provenance') else 'No confirma germinación ni rendimiento futuro.'),
            'provenance': manifest.get('provenance'),
            'validation': manifest['validation_metrics'], 'test': manifest['test_metrics']}
