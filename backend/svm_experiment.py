"""Adaptación S4; la prueba no participa en la definición del umbral ni selección."""
from collections import Counter
import numpy as np
from .yield_experiment import inventory, MODES, number, family

KERNELS = ["linear", "poly", "rbf", "sigmoid"]
FORBIDDEN = ["Yield", "Yield-media(yield)", "Class", "clase", "Weight_50K", "Weight_AllK", "All_Kernels"]
LIMITS = [
    "Experimental: Alto/Bajo es relativo al umbral de Yield; no certifica calidad, germinación ni t/ha.",
    "Se excluyen Yield, Yield-media(yield), Class, Weight_50K, Weight_AllK y All_Kernels de los predictores. Class se ignora por la inversión advertida en S4.",
    "La distancia SVM es un valor de decisión, no una probabilidad ni una garantía de acierto.",
    "Cambiar ajustes después de mirar la prueba la convierte en exploratoria. Se necesita validación externa.",
    "Fotografía, iluminación y segmentación afectan las medidas; SIMAC no reproduce exactamente el escáner ni el perímetro del notebook.",
    "La mediana se calcula solo con entrenamiento y se conserva para nuevas familias. No define un estándar universal de buen rendimiento.",
]


def metrics(rows):
    return {"correct": sum(r["actual"] == r["predicted"] for r in rows), "total": len(rows),
            "labels": ["Alto", "Bajo"], "confusion": [[sum(r["actual"] == a and r["predicted"] == b for r in rows)
            for b in ["Alto", "Bajo"]] for a in ["Alto", "Bajo"]]}


def run(records, mode="imagen", *, kernel="rbf", c=1., gamma="scale", degree=3,
        threshold=None, min_grains=25, excluded=(), nested=False, artifact_sink=None, prepared_records=None, provenance=None):
    if kernel not in KERNELS + ["logistic", "auto"] or number(c) is None or not .01 <= c <= 1000:
        raise ValueError("Kernel o C fuera de rango.")
    if gamma != "scale" and (number(gamma) is None or not .0001 <= float(gamma) <= 100):
        raise ValueError("Gamma debe ser scale o un número entre 0.0001 y 100.")
    if not 2 <= degree <= 5 or not 0 <= min_grains <= 10000:
        raise ValueError("Grado o conteo mínimo fuera de rango.")
    if threshold is not None and (number(threshold) is None or threshold < 0):
        raise ValueError("Umbral Yield no válido.")
    prepared = inventory(records, mode) if prepared_records is None else prepared_records
    excluded = {family(x) for x in excluded}
    for row in prepared:
        if row["family"] in excluded or row["count"] < min_grains:
            row["reasons"].append("Excluida por el usuario." if row["family"] in excluded else f"Menos de {min_grains} granos revisados.")
            row["ready"] = row["training_ready"] = False
    base = {"status": "blocked", "mode": mode, "samples": prepared, "limits": LIMITS,
            "source": "TrackTalents S4, pasos 27–38; umbral solo de entrenamiento", "forbidden": FORBIDDEN, "seed": 42,
            "provenance": provenance,
            "config": {"kernel": kernel, "C": c, "gamma": gamma, "degree": degree, "min_grains": min_grains, "excluded": sorted(excluded), "nested": nested}}
    eligible = sorted([r for r in prepared if r["training_ready"]], key=lambda r: r["family"])
    if len(eligible) < 12:
        return {**base, "reason": f"Hay {len(eligible)} familias aptas. Se requieren al menos 12 con Yield real para reservar cuatro y validar por parejas."}
    if len(eligible) > 60:
        return {**base, "reason": "El experimento interactivo admite hasta 60 familias. Selecciona un conjunto menor."}
    try:
        import sklearn
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import StandardScaler
        from sklearn.feature_selection import SelectKBest, f_classif
        from sklearn.svm import SVC
        from sklearn.linear_model import LogisticRegression
        from sklearn.model_selection import GridSearchCV, StratifiedKFold
    except ImportError:
        return {**base, "reason": "Instala backend/requirements.txt."}
    order = np.random.default_rng(42).permutation(len(eligible))
    test = [eligible[int(i)] for i in order[:4]]
    train = [eligible[int(i)] for i in order[4:]]
    cutoff = float(np.median([r["target"] for r in train])) if threshold is None else float(threshold)
    for r in prepared:
        r["label"] = ("Alto" if r["target"] > cutoff else "Bajo") if r["target"] is not None else None
    counts = Counter(r["label"] for r in train)
    if min(counts.get("Alto", 0), counts.get("Bajo", 0)) < 3:
        return {**base, "reason": "Deben quedar al menos tres familias por clase en entrenamiento. Reúne más datos o revisa el umbral.", "threshold": cutoff}
    columns = MODES[mode]
    x = np.array([[r["features"][v] for v in columns] for r in train])
    y = np.array([r["label"] for r in train])
    pairs = [(i, j) for i in range(len(y)) for j in range(len(y)) if y[i] == "Alto" and y[j] == "Bajo"]
    if len(pairs) > 100:
        pairs = [pairs[int(i)] for i in np.random.default_rng(42).choice(len(pairs), 100, replace=False)]
    def model(kind):
        estimator = LogisticRegression(class_weight="balanced", C=c, max_iter=1000) if kind == "logistic" else SVC(kernel=kind, C=c, gamma=gamma if gamma == "scale" else float(gamma), degree=degree, class_weight="balanced")
        return Pipeline([("scale", StandardScaler()), ("select", SelectKBest(f_classif, k=min(3, len(columns)))), ("model", estimator)])
    def choose(a, b):
        return GridSearchCV(model("rbf"), {"model__kernel": KERNELS, "model__C": [.1, 1, 10]},
            cv=StratifiedKFold(n_splits=min(3, min(Counter(b).values())), shuffle=True, random_state=42), scoring="balanced_accuracy").fit(a, b)
    def rows_for(fitted, rows):
        if hasattr(fitted, "best_estimator_"):
            fitted = fitted.best_estimator_
        a = np.array([[r["features"][v] for v in columns] for r in rows])
        predictions, decisions = fitted.predict(a), fitted.decision_function(a)
        classes = list(fitted.classes_)
        return [{"sample_id": r["sample_id"], "family": r["family"], "actual": r["label"], "predicted": str(p),
                 "decision": float(d), "positive_class": classes[1], "inside_margin": bool(abs(d) < 1) if not isinstance(fitted.named_steps["model"], LogisticRegression) else False,
                 "outside_training_range": bool(np.any((a[i] < x.min(axis=0)) | (a[i] > x.max(axis=0))))}
                for i, (r, p, d) in enumerate(zip(rows, predictions, decisions))]
    comparison, validations = [], {}
    for kind in KERNELS + ["logistic"] if kernel == "auto" else [kernel]:
        validation = []
        for i, j in pairs:
            indices = [v for v in range(len(train)) if v not in (i, j)]
            validation.extend(rows_for(model(kind).fit(x[indices], y[indices]), [train[i], train[j]]))
        full = model(kind).fit(x, y)
        comparison.append({"kernel": kind, "training": metrics(rows_for(full, train)), "validation": metrics(validation)})
        validations[kind] = validation
    selected = max(comparison, key=lambda r: r["validation"]["correct"])["kernel"] if kernel == "auto" else kernel
    fitted = model(selected).fit(x, y)
    nested_report = None
    if nested:
        outer = []
        for i, j in pairs:
            indices = [v for v in range(len(train)) if v not in (i, j)]
            picked = choose(x[indices], y[indices])
            outer.extend(rows_for(picked, [train[i], train[j]]))
        fitted = choose(x, y).best_estimator_
        selected = fitted.named_steps["model"].kernel
        nested_report = {"metrics": metrics(outer), "predictions": outer}
    used = np.array(columns)[fitted.named_steps["select"].get_support()].tolist()
    new = [r for r in prepared if r["ready"] and r["target"] is None]
    predictions = rows_for(fitted, test)
    correlations = {v: float(abs(np.corrcoef(x[:, i], [r["target"] for r in train])[0, 1])) if np.std(x[:, i]) > 0 and np.std([r["target"] for r in train]) > 0 else 0. for i, v in enumerate(columns)}
    if len(Counter(r["label"] for r in test)) < 2:
        base["limits"] = LIMITS + ["Esta prueba no contiene ambas clases; no permite evaluar las dos. Reúne más familias sin escoger otra semilla por sus resultados."]
    report = {**base, "status": "completed", "sklearn_version": sklearn.__version__, "threshold": cutoff,
            "threshold_source": "mediana de entrenamiento" if threshold is None else "referencia externa del usuario",
            "train_ids": [r["sample_id"] for r in train], "test_ids": [r["sample_id"] for r in test],
            "parameters": {"kernel": selected, "feature": ", ".join(used), "C": float(fitted.named_steps["model"].C)},
            "comparison": comparison, "nested": nested_report,
            "validation": nested_report["predictions"] if nested_report else validations[selected],
            "validation_metrics": nested_report["metrics"] if nested_report else metrics(validations[selected]),
            "validation_kind": "selección anidada por parejas" if nested else "parejas; comparación exploratoria" if kernel == "auto" else "parejas con configuración fija",
            "test": predictions, "test_metrics": metrics(predictions), "predictions": rows_for(fitted, new) if new else [],
            "pair_count": len(pairs), "possible_proxies": [v for v, corr in correlations.items() if corr > .6],
            "test_class_counts": dict(Counter(r["label"] for r in test))}
    if artifact_sink:
        report["model_version"] = artifact_sink(fitted, {"mode": mode, "columns": columns, "threshold": cutoff,
            "min_grains": min_grains, "range_min": x.min(axis=0).tolist(), "range_max": x.max(axis=0).tolist(),
            "train_families": [r["family"] for r in train], "sklearn_version": sklearn.__version__,
            "parameters": report["parameters"], "validation_metrics": report["validation_metrics"], "test_metrics": report["test_metrics"], "provenance": provenance})
    return report
