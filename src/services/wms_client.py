import streamlit as st
import requests
import xml.etree.ElementTree as ET
from io import BytesIO
from typing import List, Dict
from PIL import Image

from config.constants import REGIONES_CHILE


# -----------------------------
# FUNCIONES WMS (capabilities)
# -----------------------------

# Función para mostrar el nombre de las regiones
def format_layer_title(name: str) -> str:
    # Verificar que sea un dígito
    if name.isdigit() and name in REGIONES_CHILE:
        return REGIONES_CHILE[name]

    # Si no coincide, retornar name (número) original
    return f"Región name: {name}"


@st.cache_data(show_spinner=False, ttl=1800)
def fetch_capabilities(url: str, timeout_s: int) -> str:
    cap_url = f"{url}?SERVICE=WMS&REQUEST=GetCapabilities"
    r = requests.get(cap_url, timeout=timeout_s, headers={"User-Agent": "streamlit-wms-viewer"}, verify=False)
    r.raise_for_status()
    return r.text


@st.cache_data(show_spinner=False, ttl=1800)
def parse_layers_from_capabilities(xml_text: str) -> List[Dict]:
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


def wms_getmap_png(wms_url: str, layer_names: list, bbox: tuple, size_px: int, timeout_s: int) -> List[Image.Image]:
    minx, miny, maxx, maxy = bbox
    # Devuelve una lista de imágenes
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
        r = requests.get(wms_url, params=params, timeout=timeout_s, headers={"User-Agent": "streamlit-wms-viewer"}, verify=False)
        r.raise_for_status()
        img.append(Image.open(BytesIO(r.content)).convert("RGBA"))

    return img