"""Importación explícita de agregados reales del curso; nunca fabrica granos ni pesajes."""
import hashlib
import json
from pathlib import Path
import numpy as np
from .yield_experiment import IMAGE, MODES, family, number
from .svm_experiment import run
from .model_registry import save_candidate, activate, write_json


def read_table(path, sheet):
    from openpyxl import load_workbook
    book = load_workbook(path, read_only=True, data_only=True)
    rows = iter(book[sheet].values)
    headers = next(rows)
    result = [{str(k): v for k, v in zip(headers, row) if k is not None} for row in rows if row and row[0] is not None]
    book.close()
    return result


def train_sources(root, characteristics, metadata):
    root = Path(root)
    images = read_table(characteristics, 'familias')
    metas = read_table(metadata, 'Sheet1')
    by_family = {family(row['nombre_imagen']): row for row in metas}
    if len(by_family) != len(metas): raise ValueError('Identificadores de metadatos duplicados.')
    provenance = {'dataset': 'TrackTalents · archivos del curso', 'local_validation': False,
                  'sources': [{'name': p.name, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in [Path(characteristics), Path(metadata)]],
                  'exclusions': {'grano_05': 'Segmentación defectuosa advertida en S4', 'grano_14': 'Recorte/conteo defectuoso advertido en S4'}}
    joined = []
    for image in images:
        name = family(image.get('familia'))
        if name not in by_family or name in {family(k) for k in provenance['exclusions']}: continue
        merged = {**by_family[name], **image}
        if not number(merged.get('n_granos')) or number(merged['n_granos']) < 25: continue
        joined.append((name, merged))
    reports = {}
    for mode in ['imagen', 'metadatos']:
        prepared = []
        for name, row in joined:
            features = {c: number(row.get(c)) for c in MODES[mode]}
            target = number(row.get('Yield'))
            if target is None or any(v is None for v in features.values()): raise ValueError('Faltan valores en los agregados de entrenamiento.')
            prepared.append({'sample_id': 'curso:'+name, 'family': name, 'features': features, 'target': target, 'label': None,
                             'count': int(row['n_granos']), 'ready': True, 'training_ready': True, 'reasons': []})
        report = run([], mode, kernel='auto', nested=True, prepared_records=prepared, provenance=provenance,
                     artifact_sink=lambda fitted, meta: save_candidate(root, fitted, meta))
        if report['status'] != 'completed': raise ValueError(report['reason'])
        write_json(root/'yield_experiments'/(report['model_version']+'.json'), {**report, 'id': report['model_version']})
        reports[mode] = report
    # El modelo de planta admite fotografías sin escala con metadatos reales asociados.
    activate(root, reports['metadatos']['model_version'])
    from sklearn.linear_model import Ridge
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import LeaveOneOut
    usable = [(name, row) for name, row in joined if number(row.get('Weight_50K')) is not None]
    x = np.array([[row[c] for c in ['largo_mm','ancho_mm','area_mm2']] for _, row in usable], dtype=float)
    y = np.array([row['Weight_50K']/50 for _, row in usable], dtype=float)
    predicted = np.zeros(len(y)); baseline = np.zeros(len(y))
    for train, test in LeaveOneOut().split(x):
        fitted = make_pipeline(StandardScaler(), Ridge(alpha=1.)).fit(x[train], y[train])
        predicted[test] = fitted.predict(x[test]); baseline[test] = y[train].mean()
    fitted = make_pipeline(StandardScaler(), Ridge(alpha=1.)).fit(x, y)
    weight = {'id':'curso-peso-v1', 'status':'completed', 'provenance':provenance, 'eligible':len(y),
              'validation_kind':'una familia fuera; no validación por lote local', 'mae_total_g':float(np.mean(np.abs(y-predicted))*50),
              'baseline_mae_total_g':float(np.mean(np.abs(y-baseline))*50), 'reference_count':50,
              'parameters':{'mean':fitted[0].mean_.tolist(),'scale':fitted[0].scale_.tolist(),'coef':fitted[1].coef_.tolist(),'intercept':float(fitted[1].intercept_)},
              'training_range':{'min':x.min(axis=0).tolist(),'max':x.max(axis=0).tolist()},
              'validation':[{'family':name,'actual_50_g':float(y[i]*50),'predicted_50_g':float(predicted[i]*50)} for i,(name,_) in enumerate(usable)]}
    # El historial conserva la evaluación y la activación del predictor se realiza por separado.
    weight['enabled'] = weight['mae_total_g'] < weight['baseline_mae_total_g']
    write_json(root/'course_weight.json', weight)
    write_json(root/'course_training.json', {'provenance':provenance,'families':len(joined),
        'models':{mode:{'id':r['model_version'],'test':r['test_metrics'],'validation':r['validation_metrics']} for mode,r in reports.items()},
        'weight':{k:weight[k] for k in ['enabled','mae_total_g','baseline_mae_total_g']}})
    return json.loads((root/'course_training.json').read_text(encoding='utf-8'))
