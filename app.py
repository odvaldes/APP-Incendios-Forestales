
"""
Created on Wed Jan 21 10:34:42 2026
@author: ovaldes
"""

import streamlit as st
import streamlit.components.v1 as components
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
from typing import Union, List, Dict

from shapely.ops import transform
from pyproj import Transformer # Requerimiento nuevo agregado 'pyproj'


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

      /* Para ocultar el sidebar al Guardar print */
      @media print {
        section[data-testid="stSidebar"] {
          display: none !important;
        }
      }
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
    # 🖨️ BOTÓN: Guardar print (equivale a Ctrl+P -> Guardar como PDF)
    # ============================================================
    st.divider()
    st.header("🖨️ Guardar print (PDF)")

    if "trigger_print" not in st.session_state:
        st.session_state.trigger_print = False

    if st.button("📄 Guardar print", use_container_width=True):
        st.session_state.trigger_print = True

    st.caption("Se abrirá la impresión del navegador. En 'Destino' elige **Guardar como PDF**.")

    if st.session_state.trigger_print:
        components.html(
        """
            <script>
            // Imprime la página principal (no el iframe del componente)
              setTimeout(() => {
                  if (window.parent) {
                          window.parent.print();
                          } else {
                              window.print();
                              }
                              }, 250);
                              </script>
                                  """,
                                  height=0,
                                  width=0,
                                  )
    st.session_state.trigger_print = False
    
# -----------------------------
# FUNCIONES WMS (capabilities)
# -----------------------------
# ✅ NUEVO: función para mostrar el nombre de las regiones
def format_layer_title(name: int) -> str:

    # Verificar que sea un dígito
    if name.isdigit():
        if name in REGIONES_CHILE:
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
    "Selecciona una o más capas para visualizar",
    options=options,
    default=options[:1] if options else []
)
selected_layer = [layers[options.index(s)] for s in selected] if selected else []

# -----------------------------
# MAPA
# -----------------------------
st.subheader("Mapa")

m = build_map(
    selected_layer,
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
      Interpretación: la exposición se determina por el <b>nivel máximo de riesgo encontrado</b> 
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
    if not selected_layer:
        st.warning("Selecciona al menos una capa WMS para calcular exposición.")
    else:
        # Ahora se puede analizar más de una capa para un mismo polígono
        layer_for_analysis = st.multiselect(
            "Capa a analizar",
            options=selected_layer,
            format_func=lambda x: x["title"],
            default=selected_layer,
            key="layer_for_analysis"
        )
        # Botón calcula y GUARDA en session_state
        if st.button("Calcular exposición", type="primary"):
            try:
                feature_for_analysis = st.session_state.polygon_buffer_geojson or st.session_state.polygon_geojson
                poly = geojson_to_shapely(feature_for_analysis)
                bbox = padded_bbox(poly, pad_ratio=0.03)

                size_px = 512
                img = wms_getmap_png(wms_url, layer_for_analysis, bbox, size_px, timeout)
                mask = polygon_mask_in_bbox(poly, bbox, size_px, size_px)

                dominante = predominant_scale_in_polygon(img, mask)

                # ✅ Guardar resultado para que NO se pierda al imprimir / rerun
                st.session_state.resultado_exposicion = {
                    "dominante": dominante,
                    "layer": [l["title"] for l in layer_for_analysis],
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
                  <b>Capa analizada:</b> {" | ".join(lyr)}<br/>
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
