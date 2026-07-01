import numpy as np
from PIL import Image, ImageDraw
from shapely.geometry import shape, Polygon, MultiPolygon, mapping
from shapely.ops import transform
from pyproj import Transformer
from typing import Union


# -----------------------------
# Geometría + máscara
# -----------------------------
Geom = Union[Polygon, MultiPolygon]


def geojson_to_shapely(feature: dict) -> Geom:
    g = shape(feature.get("geometry"))
    if not isinstance(g, (Polygon, MultiPolygon)):
        raise ValueError("La geometría debe ser Polygon o MultiPolygon.")
    return g


def padded_bbox(poly: Geom, pad_ratio=0.03) -> tuple:
    minx, miny, maxx, maxy = poly.bounds
    dx = (maxx - minx) * pad_ratio or 0.01
    dy = (maxy - miny) * pad_ratio or 0.01
    return (minx - dx, miny - dy, maxx + dx, maxy + dy)


def bbox_with_padding(poly_geom: Geom, pad_ratio: float = 0.25) -> tuple:
    """
    Devuelve (minx, miny, maxx, maxy) con padding alrededor del polígono/buffer.
    pad_ratio=0.25 → 25% de contexto adicional a cada lado.
    """
    minx, miny, maxx, maxy = poly_geom.bounds
    dx = (maxx - minx) * pad_ratio or 0.02
    dy = (maxy - miny) * pad_ratio or 0.02
    return (minx - dx, miny - dy, maxx + dx, maxy + dy)


def make_bbox_square(bbox: tuple) -> tuple:
    """
    Recibe (minx, miny, maxx, maxy) y devuelve un bbox cuadrado
    expandiendo el lado más corto para igualar al lado más largo.
    Así la imagen resultante es cuadrada sin distorsión.
    """
    minx, miny, maxx, maxy = bbox
    dx = maxx - minx
    dy = maxy - miny

    if dx > dy:
        # Expandir en Y para igualar X
        diff = (dx - dy) / 2
        miny -= diff
        maxy += diff
    elif dy > dx:
        # Expandir en X para igualar Y
        diff = (dy - dx) / 2
        minx -= diff
        maxx += diff

    return (minx, miny, maxx, maxy)


def polygon_mask_in_bbox(poly: Geom, bbox: tuple, w: int, h: int) -> np.ndarray:
    minx, miny, maxx, maxy = bbox

    def lonlat_to_px(lon, lat):
        x = (lon - minx) / (maxx - minx) * (w - 1)
        y = (maxy - lat) / (maxy - miny) * (h - 1)
        return (x, y)

    mask_img = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(mask_img)

    def draw_one(p: Polygon):
        ext = [lonlat_to_px(x, y) for x, y in p.exterior.coords]
        draw.polygon(ext, outline=255, fill=255)
        for interior in p.interiors:
            hole = [lonlat_to_px(x, y) for x, y in interior.coords]
            draw.polygon(hole, outline=0, fill=0)

    if isinstance(poly, Polygon):
        draw_one(poly)
    else:
        for p in poly.geoms:
            draw_one(p)

    return np.array(mask_img) > 0


# ✅ 2 funciones relacionadas con la creación del buffer del polígono.
def utm_epsg_from_lonlat(lon: float, lat: float) -> int:
    zone = int((lon + 180) // 6) + 1
    return (32600 + zone) if lat >= 0 else (32700 + zone)


def buffer_feature_100m(feature: dict) -> dict:
    """Recibe un Feature GeoJSON en EPSG:4326 y devuelve otro Feature GeoJSON bufferizado en metros."""
    geom_ll = shape(feature["geometry"])  # shapely geom en lon/lat

    # CRS métrico local (UTM) según centroide
    c = geom_ll.centroid
    epsg_utm = utm_epsg_from_lonlat(c.x, c.y)

    to_utm = Transformer.from_crs("EPSG:4326", f"EPSG:{epsg_utm}", always_xy=True).transform
    to_ll  = Transformer.from_crs(f"EPSG:{epsg_utm}", "EPSG:4326", always_xy=True).transform

    geom_utm = transform(to_utm, geom_ll)
    geom_buf_utm = geom_utm.buffer(100)
    geom_buf_ll = transform(to_ll, geom_buf_utm)

    return {
        "type": "Feature",
        "geometry": mapping(geom_buf_ll),
    }