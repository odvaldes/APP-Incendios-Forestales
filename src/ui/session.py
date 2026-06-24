import streamlit as st
from config.constants import DEFAULT_MAP_CENTER, DEFAULT_MAP_ZOOM


# -----------------------------
# SESSION STATE
# -----------------------------
def init_session_state():
    """Inicializa todas las variables de session_state."""

    if "polygon_ok" not in st.session_state:
        st.session_state.polygon_ok = False
    if "polygon_geojson" not in st.session_state:
        st.session_state.polygon_geojson = None  # confirmado
    if "polygon_draft" not in st.session_state:
        st.session_state.polygon_draft = None    # último dibujo (borrador)

    # Comentarios finales persistentes
    if "comentarios_finales" not in st.session_state:
        st.session_state.comentarios_finales = ""

    # Persistencia de vista y buscador (solo se cambia con buscador, no con pan/zoom)
    if "map_center" not in st.session_state:
        st.session_state.map_center = DEFAULT_MAP_CENTER
    if "map_zoom" not in st.session_state:
        st.session_state.map_zoom = DEFAULT_MAP_ZOOM

    if "search_point" not in st.session_state:
        st.session_state.search_point = None  # (lat, lon)
    if "search_label" not in st.session_state:
        st.session_state.search_label = None
    if "search_addr" not in st.session_state:
        st.session_state.search_addr = ""
    if "search_results" not in st.session_state:
        st.session_state.search_results = None

    # Guardar resultado de exposición para que persista en reruns (y se imprima)
    if "resultado_exposicion" not in st.session_state:
        st.session_state.resultado_exposicion = None  # dict con dominante, capa, etc.

    # Guardar la figura del buffer en reruns.
    if "polygon_buffer_geojson" not in st.session_state:
        st.session_state.polygon_buffer_geojson = None

    if "selected_layer" not in st.session_state:
        st.session_state.selected_layer = []

    # Rastrea capa base activa.
    if "active_base_layer" not in st.session_state:
        st.session_state.active_base_layer = "Esri Satélite"

    if "addr_poly_pdf" not in st.session_state:
        st.session_state.addr_poly_pdf = ""
    
    