
"""
Created on Wed Jan 21 10:34:42 2026
@author: ovaldes
"""

import warnings
import streamlit as st

warnings.filterwarnings("ignore", category=DeprecationWarning)

st.set_page_config(page_title="Visor WMS SENAPRED", layout="wide")

from src.ui.session import init_session_state
from src.ui.sidebar import render_sidebar
from src.ui.main_view import render_main_view


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
    st.image("assets/logo.png", width=130)

# -----------------------------
# SESSION STATE
# -----------------------------
init_session_state()

# =========================
# CSS
# =========================
with open("assets/styles.css") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# -----------------------------
# SIDEBAR → retorna parámetros necesarios para la vista principal
# -----------------------------
wms_url, opacity, timeout = render_sidebar()

# -----------------------------
# VISTA PRINCIPAL
# -----------------------------
render_main_view(wms_url, opacity, timeout)

# -----------------------------
# FOOTER DE LA APP
# -----------------------------
st.markdown(
    """
    <hr style="margin-top: 2rem; margin-bottom: 0.75rem;">
    <div style="text-align:center; color:#6b7280; font-size:0.9rem;">
      © Orietta Valdés Rojas, Analista de Metodologías del Ministerio de Desarrollo Social y Familia
    </div>
    """,
    unsafe_allow_html=True
)