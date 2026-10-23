from __future__ import annotations

import math
import re
from collections import Counter


TARGET = "Yield"
IMAGE = dict(largo_mm="largo", ancho_mm="ancho", area_mm2="area", perimetro_mm="perimetro",
             razon_aspecto="razon_aspecto", circularidad="circularidad", solidez="solidez", L="L", a="a", b="b")
META = ["Days_to_anthesis", "Days_to_silking", "Plant_Height", "Ear_Height", "Tassel_branch_number",
        "Weight_Ear", "Length_Ear", "Diameter_Ear", "Number_Rows", "Kernel_Row", "Diameter_Cob"]
MODES = {"imagen": list(IMAGE), "metadatos": META, "combinado": list(IMAGE) + META}



def family(value):
    name = re.split(r"[/\\]", str(value))[-1].strip()
    name = re.sub(r"\.(jpg|jpeg|png|webp|tiff?|bmp)$", "", name, flags=re.I)
    name = re.sub(r"\s*\(\d+\)$", "", name).strip().casefold()
    matched = re.fullmatch(r'grano[\s_-]*0*(\d+)', name)
    return 'grano_'+str(int(matched[1])) if matched else name


def number(value):
    if isinstance(value,bool):
        return None
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def prepare(payload, mode="combinado"):
    if mode not in MODES:
        raise ValueError("Modo no reconocido.")
    result = payload.get("result") or {}
    metadata = payload.get("metadata") or {}
    rows = metadata.get("rows") or []
    row = rows[0] if len(rows) == 1 else {}
    identifier = row.get(metadata.get("key", ""))
    reasons = []
    if not identifier or family(identifier) != family(metadata.get("identifier", "")):
        reasons.append("Asocia una única fila de metadatos mediante su identificador de familia.")
    if not payload.get("review", {}).get("reviewed"):
        reasons.append("Confirma la revisión de las detecciones para obtener la clasificación.")
    if payload.get("parameters", {}).get("photoType") != "grains":
        reasons.append("Se requiere una fotografía de granos de una sola familia.")
    features = {}
    if mode != "metadatos":
        grains = result.get("grains") or []
        if result.get("unit") != "mm" or any(g.get("unidad") != "mm" for g in grains):
            reasons.append("Calibra la imagen en milímetros y vuelve a analizarla.")
        if not grains:
            reasons.append("No hay granos aceptados.")
        for column, source in IMAGE.items():
            values = [number(g.get(source)) for g in grains]
            if values and all(v is not None for v in values):
                features[column] = round(sum(values) / len(values), 3)
    if mode != "imagen":
        features.update({c: number(row.get(c)) for c in META})
    missing = [c for c in MODES[mode] if features.get(c) is None]
    if missing:
        reasons.append("Faltan entradas numéricas finitas: " + ", ".join(missing))
    target = number(row.get(TARGET))
    # S4: Class está invertida en los datos del curso y no se utiliza.
    if row.get(TARGET) not in (None, "") and (target is None or target < 0):
        reasons.append("Yield debe ser finito y no negativo.")
    return {"family": family(identifier or result.get("sample", "")), "features": features,
            "target": target, "label": None, "count": len(result.get("grains") or []), "ready": not reasons, "reasons": reasons,
            "training_ready": not reasons and target is not None}


def inventory(records, mode):
    prepared = [{"sample_id": identifier, **prepare(payload, mode)} for identifier, payload in records]
    counts = Counter(r["family"] for r in prepared)
    for row in prepared:
        if counts[row["family"]] > 1:
            row["reasons"].append("Familia duplicada en el historial: conserva una sola muestra activa por familia.")
            row["ready"] = row["training_ready"] = False
    return prepared

