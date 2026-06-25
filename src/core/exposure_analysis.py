import numpy as np
from PIL import Image
from typing import Union
from shapely.geometry import Polygon, MultiPolygon

from config.constants import ANCHORS_RGB, EXPOSURE_LEVELS


Geom = Union[Polygon, MultiPolygon]


def badge_html(level: str) -> str:
    cls = {"Bajo": "bajo", "Medio": "medio", "Alto": "alto", "Muy Alto": "muyalto", "Sin Dato": "sindato"}.get(level, "muted")
    return f'<span class="badge {cls}">{level}</span>'


def rgb_to_hsv_np(rgb_arr_uint8: np.ndarray) -> np.ndarray:
    rgb = rgb_arr_uint8.astype(np.float32) / 255.0
    r, g, b = rgb[:, 0], rgb[:, 1], rgb[:, 2]
    cmax = np.max(rgb, axis=1)
    cmin = np.min(rgb, axis=1)
    delta = cmax - cmin

    h = np.zeros_like(cmax)
    mask = delta > 1e-6
    idx = (cmax == r) & mask
    h[idx] = (60 * ((g[idx] - b[idx]) / delta[idx]) + 360) % 360
    idx = (cmax == g) & mask
    h[idx] = 60 * ((b[idx] - r[idx]) / delta[idx]) + 120
    idx = (cmax == b) & mask
    h[idx] = 60 * ((r[idx] - g[idx]) / delta[idx]) + 240

    s = np.zeros_like(cmax)
    nz = cmax > 1e-6
    s[nz] = delta[nz] / cmax[nz]
    v = cmax
    return np.stack([h, s, v], axis=1)


# Función para devolver la escala de mayor riesgo según rgb.
def find_highest_scale_from_rgb(rgb_arr_uint8: np.ndarray) -> int:
    rgb = rgb_arr_uint8.astype(np.float32)

    # Descartar pixeles muy oscuros o pocos saturados
    r, g, b = rgb[:, 0], rgb[:, 1], rgb[:, 2]
    mx = np.maximum(np.maximum(r, g), b)
    mn = np.minimum(np.minimum(r, g), b)
    sat = (mx - mn) / (mx + 1e-6)
    valid = (mx > 55) & (sat > 0.10)

    if not np.any(valid):
        return 0

    rgbv = rgb[valid]

    dists, labels = [], []
    for k, a in ANCHORS_RGB.items():
        dists.append(np.sum((rgbv - a) ** 2, axis=1))
        labels.append(k)

    dists = np.vstack(dists)
    idx = np.argmin(dists, axis=0)
    assigned = np.array([labels[i] for i in idx], dtype=object)

    hsv = rgb_to_hsv_np(rgbv.astype(np.uint8))
    h, s, v = hsv[:, 0], hsv[:, 1], hsv[:, 2]

    is_red    = ((h >= 345) | (h < 18)) & (s > 0.20) & (v > 0.20)
    is_orange = (h >= 18) & (h < 60)   & (s > 0.18) & (v > 0.18)

    assigned[(assigned == 4) & is_orange] = 3
    assigned[(assigned == 3) & is_red]    = 4

    return np.unique(assigned)[-1]


# Función para devolver la escala de mayor riesgo dentro de un polígono.
def predominant_scale_in_polygon(imgs_rgba: list[Image.Image], mask_bool: np.ndarray) -> str:
    highest_priority = 0

    # Iterar sobre cada imagen en la lista
    for img_rgba in imgs_rgba:
        arr = np.asarray(img_rgba)
        pixels = arr[mask_bool]
        pixels = pixels[pixels[:, 3] > 0]

        if pixels.size == 0:  # Si la imagen no tiene pixeles, pasar a la siguiente.
            continue

        rgb = pixels[:, :3].astype(np.uint8)
        priority = find_highest_scale_from_rgb(rgb)

        # Encontrar el mayor riesgo dentro de la lista de imágenes
        if priority > highest_priority:
            highest_priority = priority

    return EXPOSURE_LEVELS[highest_priority]