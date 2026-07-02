import streamlit as st
from streamlit_folium import st_folium

from src.services.wms_client import fetch_capabilities, parse_layers_from_capabilities, wms_getmap_png
from src.core.geometry import geojson_to_shapely, padded_bbox, polygon_mask_in_bbox, buffer_feature_100m
from src.core.exposure_analysis import predominant_scale_in_polygon, badge_html
from src.mapping.folium_builder import build_map


def render_main_view(wms_url: str, opacity: float, timeout: int):
    """Renderiza la vista principal: capas, mapa, polígono y resultado."""

    # -----------------------------
    # CAPABILITIES + LAYERS
    # -----------------------------
    caps      = None
    layers    = []
    cap_error = None

    try:
        with st.spinner("Leyendo GetCapabilities del WMS..."):
            caps   = fetch_capabilities(wms_url, timeout)
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

    options  = [f'{it["title"]} — ({it["name"]})' for it in layers]
    selected = st.multiselect(
        "Selecciona una o más regiones para visualizar sus capas de incendio",
        options=options,
        default=options[9:10] if options else []
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
        last_active  = map_state.get("last_active_drawing")
        candidate    = last_active or (all_drawings[-1] if all_drawings else None)
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
        st.session_state.expo_result = None
        st.session_state.final_comments = ""  
        st.session_state.final_comments_saved = None  
        st.rerun()

    if ok_clicked:
        st.session_state.expo_result = None
        st.session_state.final_comments = ""  
        st.session_state.final_comments_saved = None  
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
            st.session_state.polygon_ok      = True

            # Crear buffer DESPUÉS de confirmar el polígono
            st.session_state.polygon_buffer_geojson = buffer_feature_100m(
                st.session_state.polygon_geojson
            )

            st.success("✅ Polígono confirmado (manteniendo zoom).")
            st.rerun()

    # -----------------------------
    # SIMBOLOGÍA
    # -----------------------------
    st.markdown("### Simbología niveles de exposición")
    st.markdown(
        """
        <div style="display:flex; gap:10px; flex-wrap:wrap; align-items:center;">

          <span class="badge-tooltip">
            <span class="badge bajo">Bajo</span>
            <div class="tooltip-content tip-left">
              El nivel <b>Bajo</b> de exposición significa que el área presenta
              condiciones mínimas de riesgo ante incendios forestales...
            </div>
          </span>

          <span class="badge-tooltip">
            <span class="badge medio">Medio</span>
            <div class="tooltip-content tip-center">
              El nivel <b>Medio</b> de exposición significa que el área presenta una
              exposición moderada...
            </div>
          </span>

          <span class="badge-tooltip">
            <span class="badge alto">Alto</span>
            <div class="tooltip-content tip-center">
              El nivel <b>Alto</b> de exposición significa que el área presenta una
              exposición significativa a incendios forestales...
            </div>
          </span>

          <span class="badge-tooltip">
            <span class="badge muyalto">Muy Alto</span>
            <div class="tooltip-content tip-center">
              El nivel <b>Muy Alto</b> de exposición significa que el área presenta la
              máxima exposición a incendios forestales...
            </div>
          </span>

          <span class="badge-tooltip">
            <span class="badge sindato">Sin Dato</span>
            <div class="tooltip-content tip-right">
              El nivel <b>Sin Dato</b> significa que no se cuenta con información
              suficiente para clasificar la exposición del área. Esto puede deberse a que...
            </div>
          </span>

        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="muted" style="margin-top:0.35rem;">
          <b>Nota:</b> La exposición se determina por el nivel de exposición de mayor riesgo encontrado 
          dentro del área de análisis (polígono original + buffer de 100m).
        </div>
        """,
        unsafe_allow_html=True
    )
    st.html("<div style='margin-bottom: 1px;'></div>")

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
                    img  = wms_getmap_png(wms_url, st.session_state.selected_layer, bbox, size_px, timeout)
                    mask = polygon_mask_in_bbox(poly, bbox, size_px, size_px)

                    dominante = predominant_scale_in_polygon(img, mask)

                    # Guardar resultado para que NO se pierda al imprimir / rerun
                    st.session_state.expo_result = {
                        "dominante": dominante,
                        "layer": [l["title"] for l in st.session_state.selected_layer],
                    }

                    st.success("✅ Exposición calculada y guardada.")
                    st.rerun()

                except Exception as e:
                    st.error("Ocurrió un error al calcular la exposición.")
                    st.exception(e)

            # Mostrar SIEMPRE el resultado guardado (si existe)
            if st.session_state.expo_result is not None:
                dom = st.session_state.expo_result["dominante"]
                lyr = st.session_state.expo_result["layer"]

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

                # COMENTARIOS: también fuera del if calc, para que siempre aparezca y se imprima
                st.markdown("### 📝 Comentarios finales del análisis")
                st.session_state.final_comments = st.text_area(
                    "Ingrese observaciones, supuestos técnicos o consideraciones adicionales:",
                    value=st.session_state.final_comments,
                    height=150,
                    placeholder=(
                        "Ej: Se observa mayor concentración de exposición Muy Alto en el borde oriente del polígono. "
                        "Se recomienda evaluación detallada en etapa de diseño..."
                    )
                )

                # Botón para confirmar y guardar el comentario
                if st.button("💾 Guardar comentario", use_container_width=False):
                    st.session_state.final_comments_saved = st.session_state.final_comments

                # Mostrar estado del comentario guardado
                if st.session_state.final_comments_saved is not None:
                    if st.session_state.final_comments_saved.strip():
                        st.success("✅ Comentario guardado correctamente.")
                    else:
                        st.info("ℹ️ Comentario guardado vacío, el PDF mostrará 'Sin comentarios'.")

            else:
                st.info("ℹ️ Aún no has calculado la exposición. Presiona “Calcular exposición”.")