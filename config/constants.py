import numpy as np

# =========================
# WMS
# =========================
DEFAULT_WMS = "https://visor-grd.senapred.gob.cl/arcgis/services/SIIE/Amenaza_Incendio_2025/MapServer/WMSServer"
DEFAULT_TIMEOUT = 25

# =========================
# MAPA
# =========================
DEFAULT_MAP_CENTER = [-33.45, -70.66]
DEFAULT_MAP_ZOOM   = 5

# =========================
# PDF
# =========================
PDF_TARGET_PX = 1280
PDF_DPI       = 150
LOGO_PATH     = "assets/logo.png"

# =========================
# MAPEO DE REGIONES DE CHILE
# =========================
REGIONES_CHILE = {
    "0":  "R. de Magallanes",
    "1":  "R. de Aysén",
    "2":  "R. de Los Lagos",
    "3":  "R. de Los Ríos",
    "4":  "R. de La Araucanía",
    "5":  "R. del Biobío",
    "6":  "R. de Ñuble",
    "7":  "R. del Maule",
    "8":  "R. de O'Higgins",
    "9":  "R. Metropolitana",
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

# Niveles de exposición (índice = prioridad)
EXPOSURE_LEVELS = ["Sin Dato", "Bajo", "Medio", "Alto", "Muy Alto"]