
"""
Created on Wed Jan 21 10:34:42 2026
@author: ovaldes
"""

import streamlit as st
import requests
import xml.etree.ElementTree as ET
import folium
from folium.plugins import Draw
from streamlit_folium import st_folium

import numpy as np
from PIL import Image, ImageDraw
from shapely.geometry import shape, Polygon, MultiPolygon, mapping
from io import BytesIO
import warnings
import math
from typing import Union, List, Dict

from shapely.ops import transform
from pyproj import Transformer # Requerimiento nuevo agregado 'pyproj'

import mercantile

# ReportLab
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage, Table, TableStyle
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from datetime import datetime
from zoneinfo import ZoneInfo


warnings.filterwarnings("ignore", category=DeprecationWarning)

st.set_page_config(page_title="Visor WMS SENAPRED", layout="wide")

DEFAULT_WMS = "https://visor-grd.senapred.gob.cl/arcgis/services/SIIE/Amenaza_Incendio_2025/MapServer/WMSServer"

# =========================
# MAPEO DE REGIONES DE CHILE
# =========================
REGIONES_CHILE = {
    "0": "R. de Magallanes",
    "1": "R. de Aysén",
    "2": "R. de Los Lagos",
    "3": "R. de Los Ríos",
    "4": "R. de La Araucanía",
    "5": "R. del Biobío",
    "6": "R. de Ñuble",
    "7": "R. del Maule",
    "8": "R. de O'Higgins",
    "9": "R. Metropolitana",
    "10": "R. de Valparaíso",
    "11": "R. de Coquimbo",
    "12": "R. de Atacama",
    "13": "R. de Antofagasta",
    "14": "R. de Tarapacá",
    "15": "R. de Arica y Parinacota",
}

# =========================
# COLORES RGB ANCLA
# =========================
ANCHORS_RGB = {
        1: np.array([ 76, 175,  80], dtype=np.float32),  # Bajo
        2: np.array([255, 235,  59], dtype=np.float32),  # Medio
        3: np.array([255, 165,   0], dtype=np.float32),  # Alto
        4: np.array([220,  50,  50], dtype=np.float32),  # Muy alto
    }

# =========================
# CSS PRO
# =========================
st.markdown(
    """
    <style>
      .block-container { 
        padding-top: 3.5rem;   /* ⬅️ BAJA TODO EL CONTENIDO */
        padding-bottom: 1.2rem; 
      }
      h2 { margin-top: 0.6rem; margin-bottom: 0.35rem; }
      h3 { margin-top: 0.6rem; margin-bottom: 0.35rem; }
      .stAlert { margin-top: 0.35rem; margin-bottom: 0.35rem; }
      .badge {
        display: inline-block;
        padding: 0.35rem 0.65rem;
        border-radius: 999px;
        font-weight: 700;
        font-size: 0.95rem;
        line-height: 1.2;
        color: white;
      }
      .bajo { background: #2E7D32; }
      .medio { background: #F9A825; }
      .alto { background: #Ef6C00; }
      .muyalto { background: #F00E02; }
      .sindato { background: #9CA3AF; }
      .muted { color: #6b7280; font-size: 0.9rem; }
      .tight { margin-top: 0.2rem; }
    </style>
    """,
    unsafe_allow_html=True
)

# =========================
# HEADER CON LOGO
# =========================
col_title, col_logo = st.columns([8, 1], vertical_alignment="center")
with col_title:
    st.markdown(
        """
        <div style='background-color:#003DA5; padding: 12px; border-radius: 6px;'>
            <h2 style='color:white; text-align:left; margin: 0;'>
                🌍 Visor de Exposición a la Amenaza de Incendios Forestales 
            </h2>
        </div>
        """,
        unsafe_allow_html=True
    )
with col_logo:
    st.image("Logo/logo.png", width=130)

# -----------------------------
# SESSION STATE
# -----------------------------
if "polygon_ok" not in st.session_state:
    st.session_state.polygon_ok = False
if "polygon_geojson" not in st.session_state:
    st.session_state.polygon_geojson = None  # confirmado
if "polygon_draft" not in st.session_state:
    st.session_state.polygon_draft = None    # último dibujo (borrador)

# ✅ NUEVO: comentarios finales persistentes
if "comentarios_finales" not in st.session_state:
    st.session_state.comentarios_finales = ""

# Persistencia de vista y buscador (solo se cambia con buscador, no con pan/zoom)
if "map_center" not in st.session_state:
    st.session_state.map_center = [-33.45, -70.66]
if "map_zoom" not in st.session_state:
    st.session_state.map_zoom = 5

if "search_point" not in st.session_state:
    st.session_state.search_point = None  # (lat, lon)
if "search_label" not in st.session_state:
    st.session_state.search_label = None
if "search_addr" not in st.session_state: # ✅ NUEVO: para guardar la dirección que se busca 
    st.session_state.search_addr = ""
# ✅ NUEVO: guardar resultado de exposición para que persista en reruns (y se imprima)
if "resultado_exposicion" not in st.session_state:
    st.session_state.resultado_exposicion = None  # dict con dominante, capa, etc.

# ✅ NUEVO: guardar la figura del buffer en reruns.
if "polygon_buffer_geojson" not in st.session_state:
    st.session_state.polygon_buffer_geojson = None

if "selected_layer" not in st.session_state:
    st.session_state.selected_layer = []

# ✅ NUEVO: rastrea capa base activa.
if "active_base_layer" not in st.session_state:
    st.session_state.active_base_layer = "Esri Satélite"

# -----------------------------
# BUSCADOR DE DIRECCIONES (Nominatim / OSM)
# -----------------------------
@st.cache_data(show_spinner=False, ttl=3600)
def geocode_nominatim(query: str, limit: int = 6) -> List[Dict]:
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": query,
        "format": "json",
        "addressdetails": 1,
        "limit": limit,
        "countrycodes": "cl",
    }
    headers = {"User-Agent": "streamlit-visor-senapred/1.0 (contact: user)"}
    r = requests.get(url, params=params, headers=headers, timeout=20)
    r.raise_for_status()
    return r.json()

# =========================
# FUNCIONES DE TILES (capa base estática)
# =========================

def _tile_url_osm(x: int, y: int, z: int) -> str:
    """URL de tile OSM."""
    servers = ["a", "b", "c"]
    s = servers[(x + y + z) % 3]
    return f"https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"

def _tile_url_esri(x: int, y: int, z: int) -> str:
    """URL de tile Esri Satélite."""
    return (
        f"https://server.arcgisonline.com/ArcGIS/rest/services/"
        f"World_Imagery/MapServer/tile/{z}/{y}/{x}"
    )

def _download_tile(url: str, timeout: int = 15) -> Image.Image:
    """Descarga un tile y devuelve imagen RGBA."""
    headers = {"User-Agent": "streamlit-visor-senapred/1.0"}
    r = requests.get(url, timeout=timeout, headers=headers)
    r.raise_for_status()
    return Image.open(BytesIO(r.content)).convert("RGBA")

def bbox_with_padding(poly_geom, pad_ratio: float = 0.25):
    """
    Devuelve (minx, miny, maxx, maxy) con padding alrededor del polígono/buffer.
    pad_ratio=0.25 → 25% de contexto adicional a cada lado.
    """
    minx, miny, maxx, maxy = poly_geom.bounds
    dx = (maxx - minx) * pad_ratio or 0.02
    dy = (maxy - miny) * pad_ratio or 0.02
    return (minx - dx, miny - dy, maxx + dx, maxy + dy)

def choose_zoom_for_bbox(minx, miny, maxx, maxy, target_px: int = 800) -> int:
    """
    Elige el nivel de zoom más alto que permite que el bbox quepa en target_px píxeles.
    Usa la fórmula de mercantile/Web Mercator.
    """
    for z in range(18, 4, -1):
        # Número de tiles en x e y para este bbox y zoom
        tiles = list(mercantile.tiles(minx, miny, maxx, maxy, zooms=z))
        xs = {t.x for t in tiles}
        ys = {t.y for t in tiles}
        n_tiles_x = max(xs) - min(xs) + 1
        n_tiles_y = max(ys) - min(ys) + 1
        px_x = n_tiles_x * 256
        px_y = n_tiles_y * 256
        if px_x <= target_px * 2 and px_y <= target_px * 2:
            return z
    return 8

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

def build_base_map_image(
    bbox,                    # (minx, miny, maxx, maxy) en EPSG:4326
    layer_name: str,         # "OpenStreetMap" o "Esri Satélite"
    target_size: int = 1280, # píxeles del lado mayor de la imagen final
    timeout: int = 20,
) -> tuple[Image.Image, tuple]:
    """
    Descarga tiles XYZ para el bbox y devuelve:
      - imagen PIL de la capa base (RGBA)
      - bbox real cubierto por los tiles descargados (para usarlo en WMS y polígono)
    """
    minx, miny, maxx, maxy = bbox
    z = choose_zoom_for_bbox(minx, miny, maxx, maxy, target_px=target_size)

    tiles = list(mercantile.tiles(minx, miny, maxx, maxy, zooms=z))
    if not tiles:
        raise ValueError("No se encontraron tiles para el bbox indicado.")

    xs = sorted({t.x for t in tiles})
    ys = sorted({t.y for t in tiles})
    x_min_t, x_max_t = min(xs), max(xs)
    y_min_t, y_max_t = min(ys), max(ys)

    n_x = x_max_t - x_min_t + 1
    n_y = y_max_t - y_min_t + 1

    canvas = Image.new("RGBA", (n_x * 256, n_y * 256), (255, 255, 255, 255))

    # Selector de URL según capa base
    url_fn = _tile_url_osm if "OpenStreetMap" in layer_name else _tile_url_esri

    for tile in tiles:
        url = url_fn(tile.x, tile.y, z)
        try:
            img_tile = _download_tile(url, timeout)
        except Exception:
            img_tile = Image.new("RGBA", (256, 256), (200, 200, 200, 255))
        px = (tile.x - x_min_t) * 256
        py = (tile.y - y_min_t) * 256
        canvas.paste(img_tile, (px, py))

    # BBox real cubierto por los tiles descargados
    ul = mercantile.ul(x_min_t, y_min_t, z)
    br = mercantile.ul(x_max_t + 1, y_max_t + 1, z)
    real_bbox = (ul.lng, br.lat, br.lng, ul.lat)  # (minx, miny, maxx, maxy)

    # Recortar al bbox solicitado
    def lon_to_px(lon):
        return int((lon - real_bbox[0]) / (real_bbox[2] - real_bbox[0]) * canvas.width)
    def lat_to_py(lat):
        return int((real_bbox[3] - lat) / (real_bbox[3] - real_bbox[1]) * canvas.height)

    x0 = max(lon_to_px(minx), 0)
    y0 = max(lat_to_py(maxy), 0)
    x1 = min(lon_to_px(maxx), canvas.width)
    y1 = min(lat_to_py(miny), canvas.height)

    cropped = canvas.crop((x0, y0, x1, y1))

    # Redimensionar al target manteniendo aspecto
    w, h = cropped.size
    if w == 0 or h == 0:
        cropped = canvas
        w, h = canvas.size

    ratio = target_size / max(w, h)
    new_w, new_h = int(w * ratio), int(h * ratio)
    cropped = cropped.resize((new_w, new_h), Image.LANCZOS)

    return cropped
    
# -----------------------------
# FUNCIONES WMS (capabilities)
# -----------------------------
# ✅ NUEVO: función para mostrar el nombre de las regiones
def format_layer_title(name: int) -> str:
    # Verificar que sea un dígito
    if name.isdigit() and name in REGIONES_CHILE:
        return REGIONES_CHILE[name]
    
    # Si no coincide, retornar name (número) original
    return f"Región name: {name}"

@st.cache_data(show_spinner=False, ttl=1800)
def fetch_capabilities(url: str, timeout_s: int) -> str:
    cap_url = f"{url}?SERVICE=WMS&REQUEST=GetCapabilities"
    r = requests.get(cap_url, timeout=timeout_s, headers={"User-Agent": "streamlit-wms-viewer"})
    r.raise_for_status()
    return r.text

@st.cache_data(show_spinner=False, ttl=1800)
def parse_layers_from_capabilities(xml_text: str):
    root = ET.fromstring(xml_text)

    ns = ""
    if root.tag.startswith("{"):
        ns = root.tag.split("}")[0] + "}"

    capability = root.find(f".//{ns}Capability")
    if capability is None:
        return []

    top_layer = capability.find(f"{ns}Layer")
    if top_layer is None:
        return []

    out = []
    for lyr in top_layer.findall(f".//{ns}Layer"):
        name_el = lyr.find(f"{ns}Name")
        if name_el is not None and name_el.text:
            nm = name_el.text.strip()
            tt = format_layer_title(nm)
            out.append({"name": nm, "title": tt})

    seen, dedup = set(), []
    for x in out:
        if x["name"] not in seen:
            dedup.append(x)
            seen.add(x["name"])
    return dedup

# -----------------------------
# Geometría + GetMap + máscara + clasificación por color
# -----------------------------
Geom = Union[Polygon, MultiPolygon]

def geojson_to_shapely(feature) -> Geom:
    g = shape(feature.get("geometry"))
    if not isinstance(g, (Polygon, MultiPolygon)):
        raise ValueError("La geometría debe ser Polygon o MultiPolygon.")
    return g

def padded_bbox(poly: Geom, pad_ratio=0.03):
    minx, miny, maxx, maxy = poly.bounds
    dx = (maxx - minx) * pad_ratio or 0.01
    dy = (maxy - miny) * pad_ratio or 0.01
    return (minx - dx, miny - dy, maxx + dx, maxy + dy)

def polygon_mask_in_bbox(poly: Geom, bbox, w: int, h: int) -> np.ndarray:
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

def wms_getmap_png(wms_url: str, layer_names: list, bbox, size_px: int, timeout_s: int) -> list:
    minx, miny, maxx, maxy = bbox
    # Ahora devuele una lista de imagenes
    img = []    
    for lyr in layer_names:
        params = {
            "SERVICE": "WMS",
            "REQUEST": "GetMap",
            "VERSION": "1.1.1",
            "LAYERS": lyr["name"],
            "STYLES": "",
            "SRS": "EPSG:4326",
            "BBOX": f"{minx},{miny},{maxx},{maxy}",
            "WIDTH": str(size_px),
            "HEIGHT": str(size_px),
            "FORMAT": "image/png",
            "TRANSPARENT": "TRUE",
        }
        r = requests.get(wms_url, params=params, timeout=timeout_s, headers={"User-Agent": "streamlit-wms-viewer"})
        r.raise_for_status()
        img.append(Image.open(BytesIO(r.content)).convert("RGBA"))

    return img

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

# ✅ Modificada: Función para devolver la escala de mayor riesgo según rgb.
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

    is_red = ((h >= 345) | (h < 18)) & (s > 0.20) & (v > 0.20)
    is_orange = (h >= 18) & (h < 60) & (s > 0.18) & (v > 0.18)

    assigned[(assigned == 4) & is_orange] = 3
    assigned[(assigned == 3) & is_red] = 4

    return np.unique(assigned)[-1]

# ✅ Modificada: Función para devolver la escala de mayor riesgo dentro de un polígono.
def predominant_scale_in_polygon(imgs_rgba: list[Image.Image], mask_bool: np.ndarray) -> str:
    cats = ["Sin dato", "Bajo", "Medio", "Alto", "Muy Alto"]
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

        # Encontrar el mayor riesgo dentro de la lista de imagenes
        if priority > highest_priority:
            highest_priority = priority
    
    return cats[highest_priority]

def badge_html(level: str) -> str:
    cls = {"Bajo": "bajo", "Medio": "medio", "Alto": "alto", "Muy Alto": "muyalto", "Sin dato": "sindato"}.get(level, "muted")
    return f'<span class="badge {cls}">{level}</span>'


# ✅ NUEVO: 2 funciones relacionadas con la creación del buffer del polígono.
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

def _draw_polygon_on_image(
    draw: ImageDraw.Draw,
    poly: Geom,
    bbox: tuple,
    w: int,
    h: int,
    outline_color: tuple,
    fill_color: tuple,
    line_width: int = 3,
):
    """Dibuja un Polygon o MultiPolygon sobre un ImageDraw."""
    def draw_one(p: Polygon):
        ext_px = _geom_to_px(p.exterior.coords, bbox, w, h)
        if len(ext_px) < 2:
            return
        # Relleno semitransparente
        overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ov_draw = ImageDraw.Draw(overlay)
        ov_draw.polygon(ext_px, fill=fill_color)
        return overlay, ext_px

    polys_to_draw = poly.geoms if isinstance(poly, MultiPolygon) else [poly]

    overlays = []
    outlines = []
    for p in polys_to_draw:
        ext_px = _geom_to_px(p.exterior.coords, bbox, w, h)
        if len(ext_px) < 2:
            continue
        overlays.append(ext_px)
        outlines.append(ext_px)

    return overlays, outlines

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
    bbox = make_bbox_square(bbox)          # ← NUEVO: forzar bbox cuadrado

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


# =========================
# GENERACIÓN DEL PDF CON REPORTLAB
# =========================

def generate_pdf(map_image: Image.Image) -> bytes:

    # ==========================================================
    # Estilos para el PDF
    # ==========================================================

    # ── Estilos de texto ───────────────────────────────────────────
    title_style = ParagraphStyle(
        name="TituloPrincipal",
        fontName="Helvetica-Bold",
        fontSize=16,
        textColor=colors.HexColor('#1A3C6E'),
        alignment=TA_CENTER,
        spaceAfter=0,
        spaceBefore=0,
        leading=20,
    )

    map_title_style = ParagraphStyle(
        name="TituloMapa",
        fontName="Helvetica-Bold",
        fontSize=16,
        textColor=colors.HexColor('#1A3C6E'),
        alignment=TA_LEFT,
        spaceAfter=4,
        spaceBefore=0,
        leading=16,
    )

    # ── Estilos de texto de la leyenda ─────────────────────────────
    legend_title_style = ParagraphStyle(
        name="TituloLeyenda",
        fontName="Helvetica-Bold",
        fontSize=14,
        textColor=colors.HexColor('#1A3C6E'),
        alignment=TA_LEFT,
        spaceAfter=0,
        spaceBefore=0,
        leading=15,
    )

    legend_label_style = ParagraphStyle(
        name="EtiquetaLeyenda",
        fontName="Helvetica",
        fontSize=12,
        textColor=colors.HexColor('#1A1A1A'),
        alignment=TA_LEFT,
        spaceAfter=0,
        spaceBefore=0,
        leading=14,
    )

    # ==========================================================
    # Dimensiones del documento
    # ==========================================================

    buffer = BytesIO()

    page_w, page_h = letter     # ancho y altura total del documento
    side_margin = 2.5 * cm      # margen de los lados
    header_h = 2 * cm       # altura total de la zona del header
    footer_h = 2 * cm       # altura total de la zona del footer
    header_gap = 0.4 * cm       # separación visual entre header y contenido
    footer_gap = 0.3 * cm       # separación visual entre contenido y footer

    # ── Margen del contendedor del contenido ─────────────────────── 
    top_margin = header_h + header_gap
    bottom_margin = footer_h + footer_gap
    usable_w = page_w - 2 * side_margin

    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=side_margin,
        rightMargin=side_margin,
        topMargin=top_margin,
        bottomMargin=bottom_margin,
    )

    # ── Story para construcción del documento ───────────────────────
    story = []

    # ==========================================================
    # Header y Footer
    # ==========================================================

    # ── Header ───────────────────────────────────────────
    def draw_header(canvas_obj, doc_obj):
        canvas_obj.saveState()

        header_top = page_h              # borde superior del header
        header_bottom = page_h - header_h   # borde inferior del header
        header_mid_y = (header_top + header_bottom) / 2  # centro vertical del header

        # ── Logo izquierda ─────────────────────────────────────
        logo_path = "Logo/logo.png"
        logo_h = 1.6 * cm             # ocupa el 160% del alto del header

        pil_logo = Image.open(logo_path)
        logo_orig_w, logo_orig_h = pil_logo.size
        logo_aspect = logo_orig_w / logo_orig_h

        logo_w = logo_h * logo_aspect            # ancho proporcional
        logo_x = side_margin                          # alineado al margen izquierdo
        logo_y = header_mid_y - logo_h / 2      # centrado verticalmente en el header

        try:
            canvas_obj.drawImage(
                logo_path,
                x=logo_x,
                y=logo_y,
                width=logo_w,
                height=logo_h,
                preserveAspectRatio=True,
                mask="auto",                # respeta canal alpha del PNG
            )
        except Exception:
            pass                            # si el logo no existe, omitir

        # ── Texto derecha ──────────────────────────────────────
        line1 = "Visor de Exposición a la Amenaza de Incendios Forestales"
        line2 = "Ministerio de Desarrollo Social y Familia"
        text_x = page_w - side_margin     # alineado al margen derecho

        # Texto línea 1
        canvas_obj.setFont("Helvetica-Bold", 8)
        canvas_obj.setFillColor(colors.HexColor('#1A3C6E'))
        canvas_obj.drawRightString(
            text_x,
            header_mid_y + 0.15 * cm,
            line1,
        )

        # Texto línea 2
        canvas_obj.setFont("Helvetica", 7)
        canvas_obj.setFillColor(colors.HexColor('#6B7280'))
        canvas_obj.drawRightString(
            text_x,
            header_mid_y - 0.25 * cm,
            line2,
        )

        # ── Línea separadora  ───────────────────────────────────
        line_y = header_bottom - 0.10 * cm
        canvas_obj.setStrokeColor(colors.HexColor('#D1D5DB'))
        canvas_obj.setLineWidth(0.5)
        canvas_obj.line(
            side_margin,
            line_y,
            page_w - side_margin,
            line_y
        )

        canvas_obj.restoreState()

    # ── Footer ───────────────────────────────────────────
    def draw_footer(canvas_obj, doc_obj):
        canvas_obj.saveState()

        footer_top = footer_h        # borde superior del footer
        footer_y_text = footer_h / 2      # posición Y del texto de página

        # ── Línea separadora ──────────────────────────────
        canvas_obj.setStrokeColor(colors.HexColor('#D1D5DB'))
        canvas_obj.setLineWidth(0.5)
        canvas_obj.line(
            side_margin,              
            footer_top,                        
            page_w - side_margin,       
            footer_top,
        )

        # ── Número de página ───────────────────────────────────
        page_num = canvas_obj.getPageNumber()
        canvas_obj.setFont("Helvetica", 8)
        canvas_obj.setFillColor(colors.HexColor('#6B7280'))
        canvas_obj.drawRightString(
            page_w - side_margin,                   
            footer_y_text,
            f"Página {page_num}",
        )

        canvas_obj.restoreState()

    # ── Header y Footer ───────────────────────────────────────────
    def draw_header_footer(canvas_obj, doc_obj):
        draw_header(canvas_obj, doc_obj)
        draw_footer(canvas_obj, doc_obj)

    # ==========================================================
    # Añadir Títulos
    # ==========================================================

    # ── Título principal ────────────────────────────────────
    story.append(Paragraph(
        "<b>Visor de Exposición a la Amenaza de Incendios Forestales</b>",
        title_style
    ))
    story.append(Spacer(1, 0.4 * cm))

    # ── Título para el mapa ─────────────────────────────────
    story.append(Paragraph(
        "Mapa exposición a incendios del proyecto",
        map_title_style
    ))
    story.append(Spacer(1, 0.3 * cm))

    # ==========================================================
    # Añadir imagen del mapa
    # ==========================================================

    # ── Dimensiones de la imagen ────────────────────────────────
    map_box_size = usable_w

    img_w, img_h = map_image.size
    side = min(img_w, img_h)
    left = (img_w - side) // 2
    top  = (img_h - side) // 2
    right = left + side
    bottom = top  + side
    map_cropped = map_image.crop((left, top, right, bottom))

    # ── Cargar imagen del mapa ─────────────────────────────────
    img_buf = BytesIO()
    map_cropped.save(img_buf, format="PNG", dpi=(150, 150))
    img_buf.seek(0)

    # ── Crear contorno alrededor de la imagen ──────────────────
    rl_img = RLImage(img_buf, width=map_box_size, height=map_box_size)
    rl_img_container = [[rl_img]]
    rl_img_table = Table(rl_img_container)
    rl_img_table.setStyle(TableStyle([
    ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#000000")), 
    ('BOTTOMPADDING', (0,0), (-1,-1), 0),
    ('TOPPADDING', (0,0), (-1,-1), 0),
    ('LEFTPADDING', (0,0), (-1,-1), 0),
    ('RIGHTPADDING', (0,0), (-1,-1), 0),
    ]))

    story.append(rl_img_table)
    story.append(Spacer(1, 0.3 * cm))

    # ==========================================================
    # Añadir leyenda exposición de incendios (Tabla)
    # ==========================================================
    
    legend_items_data = [
        ("Bajo",     colors.HexColor('#AACEAC')),
        ("Medio",    colors.HexColor('#F1FB7B')),
        ("Alto",     colors.HexColor('#F7A248')),
        ("Muy Alto", colors.HexColor('#F0261C')),
    ]

    # ── Dimensiones leyenda ─────────────────────────────────
    color_box_size = 0.55 * cm          # lado del cuadrado de color
    col_gap = 0.22 * cm          # espacio entre cuadrado y etiqueta
    row0_h = 0.55 * cm          # alto de la fila del título
    row1_h = 1 * cm          # alto de la fila de ítems
    item_col_w = (usable_w / 4) / 1.4      # ancho equitativo para cada item

    # ── Fila 0 de la tabla: título "Exposición" ────────────────
    row0 = [Paragraph("Exposición", legend_title_style)] + [""] * (4 - 1)

    def make_item_cell(label: str, box_color) -> Table:
        # ── Crear micro tabla 1×2: [ cuadrado de color ] [ etiqueta de texto ] ────

        color_cell = ""                                     # El color del cuadrado se verá con TableStyle
        text_cell = Paragraph(label, legend_label_style)       # Etiqueta de texto

        box_col_w = color_box_size                           # Ancho disponible para el cuadrado de color
        text_col_w = item_col_w - color_box_size - col_gap       # Ancho disponible para el texto

        inner = Table(
            [[color_cell, text_cell]],
            colWidths=[box_col_w, text_col_w],
            rowHeights=[color_box_size],
        )

        # ── Estilo para el cuadrado de color ──────────────────────────
        inner.setStyle(TableStyle([
            # Color de fondo del cuadrado
            ("BACKGROUND",    (0, 0), (0, 0), box_color),
            # Borde fino del cuadrado
            ("BOX",           (0, 0), (0, 0), 0.5, colors.HexColor('#282828')),
            # Alineación vertical centrada en toda la micro tabla
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            # Padding cero en el cuadrado
            ("LEFTPADDING",   (0, 0), (0, 0), 0),
            ("RIGHTPADDING",  (0, 0), (0, 0), 0),
            ("TOPPADDING",    (0, 0), (0, 0), 0),
            ("BOTTOMPADDING", (0, 0), (0, 0), 0),
            # Padding izquierdo en la etiqueta (separa el cuadrado)
            ("LEFTPADDING",   (1, 0), (1, 0), col_gap),
            ("RIGHTPADDING",  (1, 0), (1, 0), 0),
            ("TOPPADDING",    (1, 0), (1, 0), 0),
            ("BOTTOMPADDING", (1, 0), (1, 0), 0),
        ]))

        return inner

    # ── Fila 1 de la tabla: ítems (cuadrado de color + etiqueta) ──────────────────
    row1 = [make_item_cell(label, color) for label, color in legend_items_data]

    # ── Crear tabla leyenda de 2 filas ─────────────────────────────────
    legend_table = Table(
        [row0, row1],
        colWidths=[item_col_w] * 4,
        rowHeights=[row0_h, row1_h],
        hAlign='LEFT'
    )

    legend_table.setStyle(TableStyle([
        # Alineación vertical centrada en todas las celdas
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        # Sin padding en ninguna celda de la tabla principal
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
        ("TOPPADDING",    (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))

    story.append(legend_table)

    # ==========================================================
    # Construir PDF final con header y footer
    # ==========================================================

    doc.build(
        story,
        onFirstPage=draw_header_footer,    
        onLaterPages=draw_header_footer,   
    )
    buffer.seek(0)

    return buffer.read()

# -----------------------------
# MAPA (FIX anti-desaparición) 
# -----------------------------
# MODIFICADO: función cambiada para mostrar el polígono original + el buffer.
def add_saved_polygon(m: folium.Map):
    # 1) Polígono original (confirmado o borrador)
    original = st.session_state.polygon_geojson or st.session_state.polygon_draft
    if original:
        folium.GeoJson(
            original,
            name="Polígono (original)",
            style_function=lambda _: {
                "color": "#111827",
                "weight": 2,
                "fillColor": "#60a5fa",
                "fillOpacity": 0.20,
            },
        ).add_to(m)

    # 2) Buffer (solo si existe)
    buf = st.session_state.get("polygon_buffer_geojson")
    if buf:
        folium.GeoJson(
            buf,
            name="Buffer 100 m",
            style_function=lambda _: {
                "color": "#dc2626",
                "weight": 2,
                "dashArray": "6,4",
                "fillColor": "#dc2626",
                "fillOpacity": 0.14,
            },
        ).add_to(m)

# ✅ NUEVO: Leyenda de cada color de exposición en el mapa.
def add_exposure_legend(m: folium.Map):
    legend_html = """
    <div style="
        position: fixed;
        bottom: 62px;
        left: 10px;
        z-index: 9999;
        background-color: white;
        background-clip: padding-box;
        padding: 10px 10px;
        border: 2px solid rgba(0,0,0,0.3);
        border-radius: 6px;
        font-size: 14px;
        ">
        
        <div style="font-weight:700; color: black; text-align: center;">Exposición</div>
        
        <hr style="margin: 6px -10px; border-top: 1px solid #000000;">

        <div style="display:flex; align-items:center; margin-bottom:4px; color: black">
            <svg width="17" height="17" style="margin-right:8px;">
            <rect x="0" y="0" width="17" height="17" fill="#AACEAC" stroke="#111827" stroke-width="1"/>
            </svg>
            Bajo
        </div>
        <div style="display:flex; align-items:center; margin-bottom:4px; color: black">
            <svg width="17" height="17" style="margin-right:8px;">
            <rect x="0" y="0" width="17" height="17" fill="#F1FB7B" stroke="#111827" stroke-width="1"/>
            </svg>
            Medio
        </div>
        <div style="display:flex; align-items:center; margin-bottom:4px; color: black">
            <svg width="17" height="17" style="margin-right:8px;">
            <rect x="0" y="0" width="17" height="17" fill="#F7A248" stroke="#111827" stroke-width="1"/>
            </svg>
            Alto
        </div>
        <div style="display:flex; align-items:center; color: black">
            <svg width="17" height="17" style="margin-right:8px;">
            <rect x="0" y="0" width="17" height="17" fill="#F0261C" stroke="#111827" stroke-width="1"/>
            </svg>
            Muy Alto
        </div>
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))

def build_map(selected_layer, opacity: float, wms_url: str, center, zoom, search_point=None, search_label=None):
    m = folium.Map(location=center, zoom_start=int(zoom), control_scale=True, tiles=None, max_zoom=22)

    folium.TileLayer(
        tiles="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        attr="© OpenStreetMap contributors",
        name="OpenStreetMap",
        overlay=False,
        control=True,
        max_zoom=22
    ).add_to(m)

    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri",
        name="Esri Satélite",
        overlay=False,
        control=True,
        max_zoom=22
    ).add_to(m)

    for lyr in selected_layer or []:
        folium.raster_layers.WmsTileLayer(
            url=wms_url,
            name=lyr["title"],
            layers=lyr["name"],
            fmt="image/png",
            transparent=True,
            version="1.3.0",
            opacity=opacity,
            attr="SENAPRED / ArcGIS WMS",
            overlay=True,
            control=True,
            show=True
        ).add_to(m)

    if search_point:
        folium.Marker(
            location=[search_point[0], search_point[1]],
            popup=search_label or "Ubicación buscada",
            tooltip="Ubicación buscada"
        ).add_to(m)

    add_saved_polygon(m)

    Draw(
        position="topleft",
        draw_options={"polyline": False, "rectangle": True, "circle": False, "circlemarker": False, "marker": False, "polygon": True},
        edit_options={"edit": True, "remove": True},
    ).add_to(m)

    folium.LayerControl(collapsed=False).add_to(m)
    add_exposure_legend(m)
    return m


# -----------------------------
# SIDEBAR
# -----------------------------
with st.sidebar:
    st.header("Fuente de datos")
    wms_url = st.text_input("URL del servicio WMS", value=DEFAULT_WMS)
    timeout = 25
    st.markdown(
    """
    • <a href="https://sni.gob.cl/storage/docs/Metodologia_RRD_290925.pdf" target="_blank">
      Metodología RRD
    </a><br/>
    • <a href="https://sni.gob.cl/storage/docs/Manual_de_escalas_IRD_Incendios_Forestales_Sep2025.pdf" target="_blank">
      Manual de escalas IRD – Incendios Forestales
    </a><br/>
    • <a href="https://sni.gob.cl/storage/docs/zip/PlanillasRRDD_2025.zip" target="_blank">
      Planillas de cálculo IRD
    </a>
    """,
        unsafe_allow_html=True
    )

    st.divider()
    
    opacity = st.slider("Opacidad capas WMS", 0.0, 1.0, 0.75, 0.05)

    st.divider()
    st.header("🔎 Buscar dirección")

    # Formulario para buscar dirección.
    with st.form(key="buscar_direccion", border=False):
    
        st.session_state.search_addr = st.text_input(
            "Dirección / lugar (Chile)",
            value=st.session_state.search_addr,
            placeholder="Ej: Av. Libertador Bernardo O'Higgins 1111, Santiago"
        )

        addr = st.session_state.search_addr
        colA, colB = st.columns([1, 1])

        with colA:
            do_search = st.form_submit_button("Buscar", use_container_width=True)
        with colB:
            clear_search = st.form_submit_button("Limpiar", use_container_width=True)

    # Limpiar búsqueda
    if clear_search:
        st.session_state.search_point = None
        st.session_state.search_label = None
        st.session_state.search_results = None  # ✅ NUEVO: Limpiar resultados guardados
        st.session_state.search_addr = ""
        st.rerun()

    # Ejecutar búsqueda y GUARDAR resultados
    if do_search and addr.strip():
        try:
            results = geocode_nominatim(addr.strip(), limit=6)
            if not results:
                st.warning("No se encontraron resultados. Prueba con más detalle (comuna/ciudad).")
                st.session_state.search_results = None
            else:
                st.session_state.search_results = results # ✅ NUEVO: GUARDAR resultados en session_state
                st.success(f"✅ Se encontraron {len(results)} resultado(s)")
        except Exception as e:
            st.error("Error al buscar dirección.")
            st.exception(e)
            st.session_state.search_results = None

    # ✅ NUEVO: MOSTRAR selectbox SIEMPRE que haya resultados guardados
    if st.session_state.get("search_results"):
        results = st.session_state.search_results
        
        options_geo = [
            f'{r.get("display_name","(sin nombre)")}  [lat={r.get("lat")}, lon={r.get("lon")}]'
            for r in results
        ]
        
        # ✅ El selectbox ahora persiste entre reruns
        chosen = st.selectbox(
            "Resultados de búsqueda",
            options_geo,
            index=0,
            key="selectbox_geocode"  # ✅ Key para mantener estado
        )
        
        # ✅ Botón para aplicar la selección
        if st.button("📍 Ir a esta ubicación", use_container_width=True):
            idx = options_geo.index(chosen)
            lat = float(results[idx]["lat"])
            lon = float(results[idx]["lon"])

            st.session_state.search_point = (lat, lon)
            st.session_state.search_label = results[idx].get("display_name", addr.strip())

            # ✅ NO usar zoom 30 (Leaflet no llega); usa 14 aprox
            st.session_state.map_center = [lat, lon]
            st.session_state.map_zoom = 14

            st.success("Ubicación centrada en el mapa ✅")
            st.rerun()

    # ============================================================
    # 🖨️ BOTÓN: Generar PDF
    # ============================================================
    st.divider()
    st.header("📄 Generar reporte PDF")

    can_generate = (
        st.session_state.polygon_ok
        and st.session_state.polygon_geojson is not None
        and st.session_state.polygon_buffer_geojson is not None
    )

    if not can_generate:
        st.info("Dibuja y confirma un polígono para habilitar el reporte.")
    else:
        # ── Selector de capa base para el PDF ─────────────────────────
        base_layer_choice = st.radio(
            "🗺️ Capa base para el mapa",
            options=["OpenStreetMap", "Esri Satélite"],
            index=1,
            key="base_layer_radio",
            help="Esta selección define la capa base que se usará en el PDF generado.",
            label_visibility="visible",
        )
        st.session_state.active_base_layer = base_layer_choice

        if st.button("🖨️ Generar PDF", use_container_width=True, type="primary"):
            with st.spinner("Generando PDF…"):
                try:
                    map_img = compose_map_image(st.session_state.polygon_geojson, st.session_state.polygon_buffer_geojson,
                                                st.session_state.selected_layer, wms_url, st.session_state.active_base_layer,
                                                opacity, target_px = 1280, timeout = timeout)

                    pdf_bytes = generate_pdf(map_img)

                    today = datetime.now(ZoneInfo("America/Santiago"))
                    pdf_name = today.strftime("reporte_exposicion_incendio-%Y-%m-%d_%H%M.pdf")

                    st.download_button(
                        label = "⬇️ Descargar PDF",
                        data = pdf_bytes,
                        file_name = pdf_name,
                        mime = "application/pdf",
                        use_container_width = True,
                    )
                    st.success("✅ PDF generado correctamente.")

                except Exception as e:
                    st.error("Error al generar el PDF.")
                    st.exception(e)


# -----------------------------
# CAPABILITIES + LAYERS
# -----------------------------
caps = None
layers = []
cap_error = None

try:
    with st.spinner("Leyendo GetCapabilities del WMS..."):
        caps = fetch_capabilities(wms_url, timeout)
        layers = parse_layers_from_capabilities(caps)
except Exception as e:
    cap_error = e

st.subheader("Capas (directas del WMS)")

if cap_error:
    st.error("No se pudo leer GetCapabilities del WMS.")
    st.exception(cap_error)
    st.stop()

if not layers:
    st.warning("El WMS respondió, pero no se detectaron capas con <Name> en GetCapabilities.")
    with st.expander("Ver Capabilities (primeras 1500 letras)"):
        st.code((caps or "")[:1500])
    st.stop()

options = [f'{it["title"]} — ({it["name"]})' for it in layers]
selected = st.multiselect(
    "Selecciona una o más regiones para visualizar sus capas de incendio",
    options=options,
    default=options[:1] if options else []
)
st.session_state.selected_layer = [layers[options.index(s)] for s in selected] if selected else []

# -----------------------------
# MAPA
# -----------------------------
st.subheader("Mapa")

m = build_map(
    st.session_state.selected_layer,
    opacity,
    wms_url,
    st.session_state.map_center,
    st.session_state.map_zoom,
    search_point=st.session_state.search_point,
    search_label=st.session_state.search_label
)

map_state = st_folium(
    m,
    width=None,
    height=620,
    key="mapa_directo",
    returned_objects=["all_drawings", "last_active_drawing", "center", "zoom"]
)

if map_state:
    all_drawings = map_state.get("all_drawings") or []
    last_active = map_state.get("last_active_drawing")
    candidate = last_active or (all_drawings[-1] if all_drawings else None)
    if candidate:
        st.session_state.polygon_draft = candidate


# -----------------------------
# POLÍGONO
# -----------------------------
st.subheader("Polígono del proyecto")

btn_col1, btn_col2, btn_col3 = st.columns([1, 1, 2], gap="small")
with btn_col1:
    ok_clicked = st.button("🟢 OK polígono", use_container_width=True)
with btn_col2:
    clear_clicked = st.button("🧹 Limpiar", use_container_width=True)
with btn_col3:
    st.markdown('<div class="muted">Dibuja/edita en el mapa. OK fija el polígono.</div>', unsafe_allow_html=True)

if clear_clicked:
    st.session_state.polygon_ok = False
    st.session_state.polygon_geojson = None
    st.session_state.polygon_draft = None
    st.session_state.polygon_buffer_geojson = None
    st.session_state.resultado_exposicion    = None
    st.rerun()

if ok_clicked:
    st.session_state.resultado_exposicion = None
    prev = st.session_state.get("mapa_directo", {})
    if isinstance(prev, dict):
        c = prev.get("center")
        z = prev.get("zoom")
        if isinstance(c, dict) and "lat" in c and "lng" in c:
            st.session_state.map_center = [float(c["lat"]), float(c["lng"])]
        if z is not None:
            st.session_state.map_zoom = int(z)

    if not st.session_state.polygon_draft:
        st.error("No hay un polígono dibujado. Dibuja uno en el mapa y vuelve a presionar OK.")
    else:
        st.session_state.polygon_geojson = st.session_state.polygon_draft
        st.session_state.polygon_ok = True
        
        # ✅ Crear buffer DESPUÉS de confirmar el polígono
        st.session_state.polygon_buffer_geojson = buffer_feature_100m(
            st.session_state.polygon_geojson
        )
        
        st.success("✅ Polígono confirmado (manteniendo zoom).")
        st.rerun()

# -----------------------------
# SIMBOLOGÍA
# -----------------------------
st.markdown("### Simbología de categorías de exposición")
st.markdown(
    """
    <div style="display:flex; gap:10px; flex-wrap:wrap; align-items:center;">
      <span class="badge bajo">Bajo</span>
      <span class="badge medio">Medio</span>
      <span class="badge alto">Alto</span>
      <span class="badge muyalto">Muy Alto</span>
      <span class="badge sindato">Sin dato</span>
    </div>
    <div class="muted" style="margin-top:0.35rem;">
      Interpretación: la exposición se determina por el <b>nivel de exposición de mayor riesgo encontrado</b> 
      dentro del área de análisis (polígono original + buffer de 100m).
    </div>
    """,
    unsafe_allow_html=True
)

# -----------------------------
# RESULTADO
# -----------------------------
# -----------------------------
# RESULTADO (PERSISTENTE)
# -----------------------------
if st.session_state.polygon_ok and st.session_state.polygon_geojson:
    if not st.session_state.selected_layer:
        st.warning("Selecciona al menos una capa WMS para calcular exposición.")
    else:
        # Botón calcula y GUARDA en session_state
        if st.button("Calcular exposición", type="primary"):
            try:
                feature_for_analysis = st.session_state.polygon_buffer_geojson or st.session_state.polygon_geojson
                poly = geojson_to_shapely(feature_for_analysis)
                bbox = padded_bbox(poly, pad_ratio=0.03)

                size_px = 512
                img = wms_getmap_png(wms_url, st.session_state.selected_layer, bbox, size_px, timeout)
                mask = polygon_mask_in_bbox(poly, bbox, size_px, size_px)

                dominante = predominant_scale_in_polygon(img, mask)

                # ✅ Guardar resultado para que NO se pierda al imprimir / rerun
                st.session_state.resultado_exposicion = {
                    "dominante": dominante,
                    "layer": [l["title"] for l in st.session_state.selected_layer],
                }

                st.success("✅ Exposición calculada y guardada.")

            except Exception as e:
                st.error("Ocurrió un error al calcular la exposición.")
                st.exception(e)

        # ✅ Mostrar SIEMPRE el resultado guardado (si existe)
        if st.session_state.resultado_exposicion is not None:
            dom = st.session_state.resultado_exposicion["dominante"]
            lyr = st.session_state.resultado_exposicion["layer"]

            st.markdown(
                f"""
                <div class="tight">
                  {badge_html(dom)}
                </div>
                <div class="tight" style="margin-top:0.5rem;">
                  <b>Región analizada:</b> {" | ".join(lyr)}<br/>
                  El Polígono o emplazamiento del proyecto presenta una exposición a la amenaza de incendios forestales <b>{dom}</b>.
                </div>
                """,
                unsafe_allow_html=True
            )

            # ✅ COMENTARIOS: también fuera del if calc, para que siempre aparezca y se imprima
            st.markdown("### 📝 Comentarios finales del análisis")
            st.session_state.comentarios_finales = st.text_area(
                "Ingrese observaciones, supuestos técnicos o consideraciones adicionales:",
                value=st.session_state.comentarios_finales,
                height=150,
                placeholder=(
                    "Ej: Se observa mayor concentración de exposición Muy Alto en el borde oriente del polígono. "
                    "Se recomienda evaluación detallada en etapa de diseño..."
                )
            )

            st.caption("✅ Este resultado y comentarios quedan guardados y se incluyen en el print (Ctrl+P / Guardar como PDF).")

        else:
            st.info("Aún no has calculado la exposición. Presiona “Calcular exposición”.")
            
st.markdown(
    """
    <hr style="margin-top: 2rem; margin-bottom: 0.75rem;">
    <div style="text-align:center; color:#6b7280; font-size:0.9rem;">
      © Orietta Valdés Rojas, Analista de Metodologías del Ministerio de Desarrollo Social y Familia
    </div>
    """,
    unsafe_allow_html=True
)
