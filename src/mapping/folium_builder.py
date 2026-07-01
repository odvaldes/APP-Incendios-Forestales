import folium
import streamlit as st
from folium.plugins import Draw


# -----------------------------
# MAPA (FIX anti-desaparición)
# -----------------------------

# Función cambiada para mostrar el polígono original + el buffer.
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


# Leyenda de cada color de exposición en el mapa.
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