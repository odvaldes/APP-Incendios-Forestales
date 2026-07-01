import streamlit as st
import requests
from typing import List, Dict


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