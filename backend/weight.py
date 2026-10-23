"""Peso por referencia explícita; el escenario publicado nunca es una medición."""
from .yield_experiment import number

SOURCE = "https://arccjournals.com/journal/asian-journal-of-dairy-and-food-research/DR-1991"
LOW, HIGH = 283.491 / 1000, 301.028 / 1000


def fingerprint(records):
    import hashlib, json
    values = [(i, measurement(p), (p.get("result") or {}).get("sample"), (p.get("result") or {}).get("unit"),
               (p.get("result") or {}).get("grains"), p.get("parameters")) for i, p in records if measurement(p)]
    return hashlib.sha256(json.dumps(sorted(values), sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def estimate(count, reference=None):
    if not isinstance(count, int) or isinstance(count, bool) or not 1 <= count <= 100000:
        return {"status": "unavailable", "reason": "Se necesita un conteo positivo de granos revisados."}
    reference = reference or {"mode": "literature"}
    if reference.get("mode") == "lot":
        mass, n = number(reference.get("mass_g")), number(reference.get("count"))
        if mass is None or n is None or not 0 < mass <= 100000 or not 1 <= n <= 100000 or not n.is_integer():
            raise ValueError("Introduce un peso positivo en gramos y un conteo entero de referencia.")
        per = mass / n
        return {"status": "estimated", "method": "promedio del lote", "count": count,
                "per_kernel_g": per, "total_g": round(count * per, 3),
                "reference": {"mode": "lot", "mass_g": mass, "count": int(n), "lot": str(reference.get("lot", ""))[:120]},
                "warning": "Extrapolación del promedio pesado al conteo de la foto. No considera tamaño individual ni tiene margen de error validado; úsala solo con el mismo lote y humedad comparable."}
    if reference.get("mode") != "literature":
        raise ValueError("Referencia de peso no reconocida.")
    return {"status": "scenario", "method": "escenario bibliográfico", "count": count,
            "per_kernel_range_g": [LOW, HIGH], "total_range_g": [round(count * LOW, 3), round(count * HIGH, 3)],
            "reference": {"mode": "literature", "url": SOURCE, "reported_thousand_kernel_g": [283.491, 301.028]},
            "warning": "Rango publicado para cinco variedades cultivadas en Maharashtra (2020–2021). No es un intervalo de confianza, ni un rango universal, ni un peso medido o modelo entrenado en Coroneo. Tu muestra puede quedar fuera."}


def measurement(payload):
    """Validación del peso medido correspondiente al conjunto exacto de granos revisados."""
    record = payload.get("weight_measurement") or {}
    result = payload.get("result") or {}
    mass, count = number(record.get("mass_g")), number(record.get("count"))
    # La firma del servidor vincula el pesaje al conjunto de granos revisado.
    if not payload.get("review", {}).get("reviewed") or mass is None or mass <= 0 or count != len(result.get("grains", [])) or not count:
        return None
    if not str(record.get("lot", "")).strip():
        return None
    return {"mass_g": mass, "count": int(count), "lot": str(record["lot"])[:120],
            "moisture_pct": number(record.get("moisture_pct")), "source": "báscula: granos exactos de la fotografía"}


def training_report(records):
    """Regresión de peso por grano; validación agrupada por lote, sin pesos bibliográficos."""
    import numpy as np
    from .yield_experiment import family
    rows, rejected = [], []
    for identifier, payload in records:
        m = measurement(payload)
        result = payload.get("result") or {}
        grains = result.get("grains") or []
        values = [[number(g.get(k)) for k in ("largo", "ancho", "area")] for g in grains]
        if not m or result.get("unit") != "mm" or payload.get("parameters", {}).get("photoType") != "grains" or not values or any(v is None or v <= 0 for row in values for v in row):
            rejected.append(identifier)
            continue
        features = np.mean(values, axis=0).tolist()
        rows.append({"id": identifier, "family": family(result.get("sample", "")), **m, "features": features})
    from collections import Counter
    duplicates = Counter(r["family"] for r in rows)
    rejected += [r["id"] for r in rows if duplicates[r["family"]] > 1]
    rows = [r for r in rows if duplicates[r["family"]] == 1]
    base = {"status": "blocked", "data_fingerprint": fingerprint(records), "eligible": len(rows), "lots": len({r["lot"] for r in rows}), "rejected_ids": rejected,
            "limits": ["No se entrena con referencias bibliográficas ni extrapolaciones.", "Validación por lote: se prueba en lotes que el modelo no ha visto.", "El error de validación no es un intervalo de confianza individual. Humedad, variedad y campaña pueden cambiar el peso."]}
    if len(rows) < 12 or base["lots"] < 3:
        return {**base, "reason": "Reúne al menos 12 muestras calibradas con peso exacto de báscula, revisión confirmada y al menos tres lotes distintos. Es un mínimo operativo; conviene reunir muchas más."}
    from sklearn.linear_model import Ridge
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import GroupKFold
    x = np.array([r["features"] for r in rows])
    y = np.array([r["mass_g"] / r["count"] for r in rows])
    groups = [r["lot"] for r in rows]
    predictions = []
    for train, test in GroupKFold(n_splits=min(5, base["lots"])).split(x, y, groups):
        model = make_pipeline(StandardScaler(), Ridge(alpha=1.)).fit(x[train], y[train])
        p = model.predict(x[test])
        for index, predicted in zip(test, p):
            row = rows[int(index)]
            predictions.append({"sample_id": row["id"], "actual_g": row["mass_g"], "predicted_g": max(0., float(predicted)) * row["count"], "baseline_g": float(y[train].mean()) * row["count"], "lot": row["lot"]})
    fitted = make_pipeline(StandardScaler(), Ridge(alpha=1.)).fit(x, y)
    return {**base, "status": "completed", "model": "StandardScaler + Ridge(alpha=1), peso por grano",
            "features": ["largo medio mm", "ancho medio mm", "área media mm²"],
            "sample_ids": [r["id"] for r in rows], "validation": predictions,
            "mae_total_g": float(np.mean([abs(p["actual_g"] - p["predicted_g"]) for p in predictions])),
            "baseline_mae_total_g": float(np.mean([abs(p["actual_g"] - p["baseline_g"]) for p in predictions])),
            "parameters": {"mean": fitted[0].mean_.tolist(), "scale": fitted[0].scale_.tolist(), "coef": fitted[1].coef_.tolist(), "intercept": float(fitted[1].intercept_)},
            "training_range": {"min": x.min(axis=0).tolist(), "max": x.max(axis=0).tolist()}}


def predict(result, report):
    import numpy as np
    grains = result.get("grains") or []
    if result.get("unit") != "mm" or not grains:
        raise ValueError("El modelo propio necesita una imagen calibrada en mm y granos revisados.")
    values = [[number(g.get(k)) for k in ["largo", "ancho", "area"]] for g in grains]
    if any(v is None or v <= 0 for row in values for v in row):
        raise ValueError("Hay medidas ausentes o no válidas para predecir peso.")
    x = np.mean(values, axis=0)
    p = report["parameters"]
    per = float(np.dot((x - p["mean"]) / p["scale"], p["coef"]) + p["intercept"])
    if per <= 0:
        raise ValueError("El modelo dio un peso no positivo; usa una referencia de lote y reúne más datos.")
    outside = bool(np.any((x < report["training_range"]["min"]) | (x > report["training_range"]["max"])))
    return {"status": "estimated", "method": "regresión propia experimental", "total_g": round(per * len(grains), 3),
            "per_kernel_g": per, "count": len(grains), "model_id": report["id"], "mae_validation_g": report["mae_total_g"],
            "outside_training_range": outside, "warning": ("Medidas fuera del rango de entrenamiento. " if outside else "") + "Modelo experimental: error absoluto medio de peso total en lotes reservados: " + str(round(report["mae_total_g"], 3)) + " g. No es un intervalo de confianza ni sustituye la báscula."}
