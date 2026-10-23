"""Mediciones 2D. Cellpose es opcional; el método clásico siempre se identifica."""
from __future__ import annotations

import base64
import colorsys
import csv
import io
import math
import os
from pathlib import Path
from functools import lru_cache

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from skimage import color, filters, measure, morphology, transform


@lru_cache(maxsize=1)
def cellpose_model():
    os.environ.setdefault("CELLPOSE_LOCAL_MODELS_PATH", str(Path(__file__).resolve().parent.parent / "data" / "models"))
    from cellpose import models
    import torch
    return models.Cellpose(gpu=torch.cuda.is_available(), model_type="cyto3")


def analyze(image: Image.Image, *, method: str, roi: tuple[float, float, float, float],
            diameter: float | None, min_area: int, max_side: int,
            scale_pixels: float | None, scale_mm: float | None, sample: str, supplied_masks=None) -> dict:
    width, height = image.size
    left, top, right, bottom = roi
    x0, y0, x1, y1 = int(left * width), int(top * height), int(right * width), int(bottom * height)
    crop = np.asarray(image.crop((x0, y0, x1, y1)).convert("RGB"))
    h, w = crop.shape[:2]
    if min(h, w) < 32:
        raise ValueError("El recorte es demasiado pequeño; amplía la zona de análisis.")
    factor = min(1.0, max_side / max(h, w))
    # Misma escala física en ambos ejes, corrigiendo el redondeo de la reducción.
    wh, ww = max(1, round(h * factor)), max(1, round(w * factor))
    rgb = transform.resize(crop, (wh, ww), anti_aliasing=True, preserve_range=True) / 255
    gray = color.rgb2gray(rgb)
    warnings = []
    used_diameter = None
    if supplied_masks is not None:
        masks = supplied_masks
        if masks.shape != gray.shape:
            raise ValueError("La máscara no coincide con la imagen de trabajo.")
        method_label = "Segmentación revisada"
    elif method == "cellpose":
        masks, _, _, diameters = cellpose_model().eval(
            gray, diameter=diameter, channels=[0, 0], flow_threshold=0.4,
            cellprob_threshold=0.0,
        )
        used_diameter = float(np.ravel(diameters)[0])
        method_label = "Cellpose 3 · cyto3"
    else:
        if float(np.ptp(gray)) < 0.01:
            masks = np.zeros(gray.shape, dtype=np.int32)
        else:
            foreground = gray > filters.threshold_otsu(gray)
            foreground = morphology.remove_small_holes(foreground, area_threshold=64)
            masks = measure.label(foreground)
        method_label = "Umbral automático · método clásico"
        warnings.append("El método clásico requiere granos separados y fondo oscuro. Puede unir granos que se tocan; no utiliza una red neuronal.")
    calibrated = scale_pixels is not None and scale_mm is not None
    unit = "mm" if calibrated else "px"
    original_unit = scale_mm / scale_pixels if calibrated else 1.0
    sy, sx = (h / wh) * original_unit, (w / ww) * original_unit
    lab = color.rgb2lab(rgb)
    props = measure.regionprops(masks)
    raw_colored = np.zeros((wh, ww, 3), dtype=np.uint8)
    for i, prop in enumerate(props, 1):
        raw_colored[prop.coords[:, 0], prop.coords[:, 1]] = np.array(colorsys.hsv_to_rgb(i / max(1, len(props)), .9, .95)) * 255
    accepted = [p for p in props if p.area >= min_area and p.axis_minor_length > 0
                and p.axis_major_length / p.axis_minor_length <= 3.0]
    if supplied_masks is not None:
        accepted = [p for p in props if p.axis_minor_length > 0]
    accepted.sort(key=lambda p: (round(p.centroid[0] / 60), p.centroid[1]))
    overlay = Image.fromarray(np.uint8(np.clip(rgb, 0, 1) * 255)).convert("RGB")
    pixels = np.asarray(overlay).copy()
    rows = []
    colored = np.zeros((wh, ww, 3), dtype=np.uint8)
    dimensions = overlay.copy()
    dim_draw = ImageDraw.Draw(dimensions)
    for number, p in enumerate(accepted, 1):
        ys, xs = p.coords[:, 0], p.coords[:, 1]
        # Ejes equivalentes a una elipse calculados en las unidades de salida.
        coords = np.column_stack((ys * sy, xs * sx))
        eigenvalues = np.linalg.eigvalsh(np.cov(coords, rowvar=False, bias=True))
        length, breadth = 4 * np.sqrt(np.maximum(eigenvalues[::-1], 0))
        _, vectors = np.linalg.eigh(np.cov(coords, rowvar=False, bias=True))
        center = np.array(p.centroid)
        for axis, size, stroke in [(vectors[:, 1], length, '#48e0ff'), (vectors[:, 0], breadth, '#ffb54c')]:
            offset = axis * size / 2 / np.array([sy, sx])
            start, end = center - offset, center + offset
            dim_draw.line((start[1], start[0], end[1], end[0]), fill=stroke, width=3)
        dim_draw.text((center[1]+5, center[0]+5), str(number), fill='white', stroke_width=1, stroke_fill='black')
        colored[ys, xs] = np.array(colorsys.hsv_to_rgb((number * 0.61803398875) % 1, .8, .95)) * 255
        mean_rgb = rgb[ys, xs].mean(axis=0)
        mean_lab = lab[ys, xs].mean(axis=0)
        touches = p.bbox[0] == 0 or p.bbox[1] == 0 or p.bbox[2] == wh or p.bbox[3] == ww
        # Contornos en coordenadas físicas para respetar ambos factores de escala.
        local = np.pad(p.image, 1)
        perimeter = 0.0
        for contour in measure.find_contours(local, .5):
            delta = np.diff(contour * np.array([sy, sx]), axis=0)
            perimeter += float(np.linalg.norm(delta, axis=1).sum())
        area = float(p.area * sx * sy)
        rows.append({
            "muestra": sample, "grano": number, "unidad": unit,
            "limites": [p.bbox[1] / ww, p.bbox[0] / wh, p.bbox[3] / ww, p.bbox[2] / wh],
            "centro_x": round(float(p.centroid[1] / ww), 6),
            "centro_y": round(float(p.centroid[0] / wh), 6),
            "largo": round(float(length), 3), "ancho": round(float(breadth), 3),
            "area": round(float(p.area * sx * sy), 3),
            "perimetro": round(perimeter, 3),
            "circularidad": round(4 * math.pi * area / perimeter ** 2, 3) if perimeter else None,
            "razon_aspecto": round(float(length / breadth), 3),
            "solidez": round(float(p.solidity), 3),
            "color_hex": "#" + "".join(f"{round(float(c) * 255):02x}" for c in mean_rgb),
            "L": round(float(mean_lab[0]), 3), "a": round(float(mean_lab[1]), 3),
            "b": round(float(mean_lab[2]), 3), "toca_borde": touches,
        })
        mask = masks == p.label
        boundary = mask & ~morphology.erosion(mask)
        pixels[boundary] = (235, 208, 100)
    overlay = Image.fromarray(pixels)
    draw = ImageDraw.Draw(overlay)
    font = ImageFont.load_default(size=max(16, max(ww, wh) // 65))
    for n, p in enumerate(accepted, 1):
        y, x = p.centroid
        draw.ellipse((x-4, y-4, x+4, y+4), fill="#f3d66c")
        draw.text((x+7, y-12), str(n), fill="white", font=font, stroke_width=2, stroke_fill="#173e32")
    if any(r["toca_borde"] for r in rows):
        warnings.append("Hay objetos que tocan el borde del recorte. Sus medidas pueden estar incompletas.")
    if not calibrated:
        warnings.append("Sin calibración: las medidas están en píxeles de la imagen original, no en milímetros.")
    warnings.append("El color corresponde a esta fotografía; la iluminación afecta la comparación entre muestras.")
    if not rows:
        warnings.append("No se encontraron granos que cumplan los filtros. Revisa el fondo, el recorte y el área mínima.")
    def encode(picture):
        buffer = io.BytesIO()
        picture.save(buffer, format="PNG")
        return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()
    stream = io.StringIO(newline="")
    fields = list(rows[0]) if rows else ["muestra", "grano", "unidad", "largo", "ancho", "area"]
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    # Impide interpretar los nombres de muestra como fórmulas al abrir CSV en Excel.
    for row in rows:
        writer.writerow({k: "'" + v if isinstance(v, str) and v.lstrip().startswith(("=", "+", "-", "@")) else v for k, v in row.items()})
    saved_masks = np.zeros((wh, ww), dtype=np.uint16)
    for number, prop in enumerate(accepted, 1):
        saved_masks[masks == prop.label] = number
    return {
        "editable_masks": encode(Image.fromarray(saved_masks)),
        "sample": sample, "method": method_label, "count": len(rows),
        "raw_count": len(props), "discarded": len(props) - len(rows), "unit": unit,
        "mean_length": round(float(np.mean([r["largo"] for r in rows])), 3) if rows else None,
        "mean_area": round(float(np.mean([r["area"] for r in rows])), 3) if rows else None,
        "weight": None, "weight_status": "Pendiente de entrenar y validar con pesos reales",
        "diameter_work_px": used_diameter, "working_size": [ww, wh],
        "original_size": [width, height], "warnings": warnings, "grains": rows,
        "overlay": encode(overlay),
        "stages": {
            "crop": encode(Image.fromarray(np.uint8(rgb * 255))),
            "gray": encode(Image.fromarray(np.uint8(np.clip(gray, 0, 1) * 255))),
            "raw_masks": encode(Image.fromarray(raw_colored)),
            "segmentation": encode(Image.fromarray(colored)),
            "dimensions": encode(dimensions),
        },
        "csv": stream.getvalue(),
    }
