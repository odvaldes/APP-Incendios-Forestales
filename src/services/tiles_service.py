import requests
import mercantile
from PIL import Image
from io import BytesIO


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
    r = requests.get(url, timeout=timeout, headers=headers, verify=False)
    r.raise_for_status()
    return Image.open(BytesIO(r.content)).convert("RGBA")


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


def build_base_map_image(
    bbox,                    # (minx, miny, maxx, maxy) en EPSG:4326
    layer_name: str,         # "OpenStreetMap" o "Esri Satélite"
    target_size: int = 1280, # píxeles del lado mayor de la imagen final
    timeout: int = 20,
) -> Image.Image:
    """
    Descarga tiles XYZ para el bbox y devuelve imagen PIL de la capa base (RGBA).
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