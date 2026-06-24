import math
import numpy as np
from PIL import Image, ImageDraw
from shapely.geometry import Polygon, MultiPolygon
from typing import Union

from src.core.geometry import geojson_to_shapely, bbox_with_padding, make_bbox_square
from src.services.tiles_service import build_base_map_image
from src.services.wms_client import wms_getmap_png


Geom = Union[Polygon, MultiPolygon]


# =========================
# COMPOSICIÓN DE IMAGEN DEL MAPA PARA PDF
# =========================

def _geom_to_px(geom_coords, bbox, w: int, h: int):
    """Convierte lista de (lon, lat) a píxeles en la imagen."""
    minx, miny, maxx, maxy = bbox
    return [
        (
            (lon - minx) / (maxx - minx) * w,
            (maxy - lat) / (maxy - miny) * h,
        )
        for lon, lat in geom_coords
    ]


def _draw_dashed_line(draw: ImageDraw.Draw, points, color, width=3,
                      dash_len=12, gap_len=8):
    """Dibuja una polilínea punteada/guionada."""
    for i in range(len(points) - 1):
        x0, y0 = points[i]
        x1, y1 = points[i + 1]
        seg_len = math.hypot(x1 - x0, y1 - y0)
        if seg_len == 0:
            continue
        dx = (x1 - x0) / seg_len
        dy = (y1 - y0) / seg_len
        pos = 0.0
        drawing = True
        while pos < seg_len:
            seg_end = min(pos + (dash_len if drawing else gap_len), seg_len)
            if drawing:
                sx = x0 + dx * pos
                sy = y0 + dy * pos
                ex = x0 + dx * seg_end
                ey = y0 + dy * seg_end
                draw.line([(sx, sy), (ex, ey)], fill=color, width=width)
            pos = seg_end
            drawing = not drawing


def compose_map_image(polygon_geojson: dict, buffer_geojson: dict,
                      wms_layers: list, wms_url: str, base_layer_name: str,
                      wms_opacity: float = 0.75, target_px: int = 1280,
                      timeout: int = 25) -> Image.Image:

    # Geometrías del polígono y su buffer.
    buf_geom  = geojson_to_shapely(buffer_geojson)
    orig_geom = geojson_to_shapely(polygon_geojson)

    # Bbox con padding generoso (25 %) y luego forzar cuadrado
    bbox = bbox_with_padding(buf_geom, pad_ratio=0.25)
    bbox = make_bbox_square(bbox)

    # ── 2. Capa base ───────────────────────────────────────────────
    base_img = build_base_map_image(
        bbox, base_layer_name, target_size=target_px, timeout=timeout
    )
    w, h = base_img.size

    # ── 3. Capas WMS ───────────────────────────────────────────────
    if wms_layers:
        wms_imgs = wms_getmap_png(wms_url, wms_layers, bbox, max(w, h), timeout)

        for wms_img in wms_imgs:
            wms_resized = wms_img.resize((w, h), Image.LANCZOS)

            r_ch, g_ch, b_ch, a_ch = wms_resized.split()
            a_arr = np.array(a_ch, dtype=np.float32)
            a_arr = (a_arr * wms_opacity).clip(0, 255).astype(np.uint8)
            wms_resized = Image.merge("RGBA", (r_ch, g_ch, b_ch,
                                               Image.fromarray(a_arr)))
            base_img = Image.alpha_composite(base_img.convert("RGBA"), wms_resized)

    base_img = base_img.convert("RGBA")

    # ── 4. Dibujar polígono original ───────────────────────────────
    fill_orig    = (96, 165, 250, 60)
    outline_orig = (17, 24, 39, 230)

    overlay_orig = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    od           = ImageDraw.Draw(overlay_orig)

    polys_orig = orig_geom.geoms if isinstance(orig_geom, MultiPolygon) else [orig_geom]
    for p in polys_orig:
        pts = _geom_to_px(p.exterior.coords, bbox, w, h)
        if len(pts) >= 3:
            od.polygon(pts, fill=fill_orig)

    base_img = Image.alpha_composite(base_img, overlay_orig)

    final_draw = ImageDraw.Draw(base_img)
    for p in polys_orig:
        pts = _geom_to_px(p.exterior.coords, bbox, w, h)
        if len(pts) >= 2:
            final_draw.line(pts + [pts[0]], fill=outline_orig, width=3)

    # ── 5. Dibujar buffer (rojo guionado) ──────────────────────────
    fill_buf    = (220, 38, 38, 45)
    outline_buf = (220, 38, 38, 230)

    overlay_buf = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    bd          = ImageDraw.Draw(overlay_buf)

    polys_buf = buf_geom.geoms if isinstance(buf_geom, MultiPolygon) else [buf_geom]
    for p in polys_buf:
        pts = _geom_to_px(p.exterior.coords, bbox, w, h)
        if len(pts) >= 3:
            bd.polygon(pts, fill=fill_buf)

    base_img    = Image.alpha_composite(base_img, overlay_buf)
    final_draw2 = ImageDraw.Draw(base_img)

    for p in polys_buf:
        pts = _geom_to_px(p.exterior.coords, bbox, w, h)
        if len(pts) >= 2:
            _draw_dashed_line(final_draw2, pts + [pts[0]],
                              color=outline_buf, width=3,
                              dash_len=14, gap_len=7)

    return base_img.convert("RGB")