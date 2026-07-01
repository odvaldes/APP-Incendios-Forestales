import streamlit as st

from config.constants import DEFAULT_WMS, DEFAULT_TIMEOUT
from src.services.geocoding import geocode_nominatim
from src.mapping.map_renderer import compose_map_image
from src.pdf.generator import generate_pdf


def render_sidebar() -> tuple:
    """
    Renderiza el sidebar completo.
    Retorna (wms_url, opacity, timeout) para uso en la vista principal.
    """
    with st.sidebar:
        st.header("Fuente de datos")
        wms_url = st.text_input("URL del servicio WMS", value=DEFAULT_WMS)
        timeout = DEFAULT_TIMEOUT
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
            st.session_state.search_point   = None
            st.session_state.search_label   = None
            st.session_state.search_results = None
            st.session_state.search_addr    = ""
            st.rerun()

        # Ejecutar búsqueda y GUARDAR resultados
        if do_search and addr.strip():
            try:
                results = geocode_nominatim(addr.strip(), limit=6)
                if not results:
                    st.warning("No se encontraron resultados. Prueba con más detalle (comuna/ciudad).")
                    st.session_state.search_results = None
                else:
                    st.session_state.search_results = results  # GUARDAR resultados en session_state
                    st.success(f"✅ Se encontraron {len(results)} resultado(s)")
            except Exception as e:
                st.error("Error al buscar dirección.")
                st.exception(e)
                st.session_state.search_results = None

        # MOSTRAR selectbox SIEMPRE que haya resultados guardados
        if st.session_state.get("search_results"):
            results = st.session_state.search_results

            options_geo = [
                f'{r.get("display_name","(sin nombre)")}  [lat={r.get("lat")}, lon={r.get("lon")}]'
                for r in results
            ]

            # El selectbox ahora persiste entre reruns
            chosen = st.selectbox(
                "Resultados de búsqueda",
                options_geo,
                index=0,
                key="selectbox_geocode"
            )

            # Botón para aplicar la selección
            if st.button("📍 Ir a esta ubicación", use_container_width=True):
                idx = options_geo.index(chosen)
                lat = float(results[idx]["lat"])
                lon = float(results[idx]["lon"])

                st.session_state.search_point = (lat, lon)
                st.session_state.search_label = results[idx].get("display_name", addr.strip())

                st.session_state.map_center = [lat, lon]
                st.session_state.map_zoom   = 14

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
            and st.session_state.expo_result is not None
        )

        if not can_generate:
            st.info("Dibuja y confirma un polígono para habilitar el reporte.")
        else:
            # ── Selector de capa base para el PDF ─────────────────────────
            st.session_state.base_layer_pdf = st.radio(
                "🗺️ Capa base para el mapa",
                options=["OpenStreetMap", "Esri Satélite"],
                index=1,
                key="base_layer_radio",
                help="Esta selección define la capa base que se usará en el mapa del PDF generado.",
                label_visibility="visible",
            )

            st.session_state.addr_poly_pdf = st.text_input(
                "📍 Dirección del proyecto",
                value="",
                placeholder="Ej: Av. Libertador Bernardo O'Higgins 1111, Santiago",
                help="Se mostrará esta direción en el PDF generado.",
            )

            if st.button("🖨️ Generar PDF", use_container_width=True, type="primary"):
                with st.spinner("Generando PDF…"):
                    try:
                        map_img = compose_map_image(
                            st.session_state.polygon_geojson,
                            st.session_state.polygon_buffer_geojson,
                            st.session_state.selected_layer,
                            wms_url,
                            st.session_state.base_layer_pdf,
                            opacity,
                            target_px=1280,
                            timeout=timeout
                        )

                        pdf_bytes, pdf_name = generate_pdf(map_img,
                                                           st.session_state.addr_poly_pdf,
                                                           st.session_state.expo_result,
                                                           st.session_state.final_comments_saved)

                        st.download_button(
                            label="⬇️ Descargar PDF",
                            data=pdf_bytes,
                            file_name=pdf_name,
                            mime="application/pdf",
                            use_container_width=True,
                        )
                        st.success("✅ PDF generado correctamente.")

                    except Exception as e:
                        st.error("Error al generar el PDF.")
                        st.exception(e)

    return wms_url, opacity, timeout