
# -*- coding: utf-8 -*-
"""
Ruta óptima entre nodos cumpliendo DG200853_O (Delta4000 Transport, Access Roads and Crane Guidelines)
— A* + restricciones de pendiente y curvatura — usando DEM explícito (raster_path).
"""

import statistics
import heapq
import json
import os
from typing import Dict, List, Tuple, Optional

from ezdxf.lldxf.const import DXFValueError
from osgeo import gdal, ogr
import ezdxf
from shapely.geometry import Point, Polygon

import math
import numpy as np
from typing import Optional

# --- Módulos locales ---

# al inicio o justo antes de usar el DEM:
from DEM_FILE import dem_file


from UTM_GEO import utm_lat_lon
try:
    from curve_smoothing import curve_smoothing  # opcional
except ImportError:
    curve_smoothing = None

# --- Parámetros DG (ajustables) ---
DG = {"max_slope_straight":6,     # %
    "max_slope_curve":10,        # % para giros < 135°
    "curve_angle_threshold": 135,# °
    "min_curve_radius":60,        # m
    "usable_width": 6.0,          # m (informativo)
    "clear_obstacle_width": 8.0,  # m (informativo)
    "clearance_height": 6.0       # m (informativo)
}


# --- Malla y buffers ---

BUFFER_CUADRICULA   = 150  # [m]
BUFFER_DXF          = 25  # [m]

# =========================
# DEM INICIALIZADO EXPLÍCITO
# =========================
DEM_DS   = None
ELEVATION= None
TRANSFORM= None

def init_dem(raster_path: Optional[str] = None):
    """Inicializa el DEM a partir de raster_path (si es None, fallback a dem_file())."""
    global DEM_DS, ELEVATION, TRANSFORM
    if DEM_DS is not None:
        return
    path = raster_path if raster_path else dem_file()  # fallback si no se pasa
    if not path or not os.path.isfile(path):
        raise FileNotFoundError(f"DEM no encontrado: {path}")
    ds = gdal.Open(path)
    if ds is None:
        raise RuntimeError(f"GDAL no pudo abrir el DEM: {path}")
    band = ds.GetRasterBand(1)
    ELEVATION = band.ReadAsArray()
    TRANSFORM = ds.GetGeoTransform()   # (ox, px_w, rot_x, oy, rot_y, px_h)
    DEM_DS = ds
    print(f"[DEM] Cargado para ROAD: {path}")
    print(f"[DEM] Tamaño: {ELEVATION.shape}, GT: {TRANSFORM}")

# --- Elevación (nearest o bilinear) ---


from bisect import bisect_right

def get_mesh_spacing(default_mesh=30):
    try:
        import streamlit as st
        PASO_MALLA_DEFAULT = float(st.session_state.get("mesh_spacing", default_mesh))
        PASO_CAMINO_DEFAULT = float(st.session_state.get("mesh_spacing", default_mesh))

        return PASO_MALLA_DEFAULT,PASO_CAMINO_DEFAULT
    except Exception:
        return float(PASO_MALLA_DEFAULT), float(PASO_CAMINO_DEFAULT)

PASO_MALLA_DEFAULT,PASO_CAMINO_DEFAULT=get_mesh_spacing()







def get_factor_penalizacion_bins7(slope_value: float) -> float:
    """
    7 factores y 6 cortes configurables en 'st.session_state["slope_bins_7"]'.
    Reglas:
      - s == 0  -> idx 0
      - s  > 0  -> idx = bisect_right(cortes, s), acotado a 1..6
    """
    s = abs(float(slope_value))

    try:
        import streamlit as st
        factors = st.session_state.get("factor_penalizacion", [1, 2, 3, 4, 5, 6, 7])
        bins    = st.session_state.get("slope_bins_7",        [0, 3, 6, 9, 12, 15])
    except Exception:
        # Fallback si corres fuera de Streamlit
        factors = [1, 2, 3, 4, 5, 6, 7]
        bins    = [0, 3, 6, 9, 12, 15]

    # Sanitización por si el usuario cambió tamaños accidentalmente
    if len(factors) != 7:
        factors = (factors + [factors[-1]] * 7)[:7]
    if len(bins) != 6:
        bins = [0, 3, 6, 9, 12, 15]

    if s == 0.0:
        idx = 0
    else:
        idx = bisect_right(bins, s)      # 1..6 si cae dentro / >6 si supera el último corte
        idx = min(max(idx, 1), 6)        # asegurar 1..6 para s>0

    return float(factors[idx])


# Suponiendo que ELEVATION es un np.ndarray y TRANSFORM es una tupla estilo Affine:
# TRANSFORM = (ox, px_w, rot_x, oy, rot_y, px_h)
# Además, si conoces el valor de NoData del raster, puedes asignarlo aquí:
NODATA: Optional[float] = None  # e.g., NODATA = -9999.0 si aplica

def obtener_elevacion( x: float,  y: float,    interpolate: bool = False,    default_value: float = 150.0,    clamp: bool = False
) -> float:
    """
    Devuelve la elevación en (x, y).
    - Si el punto cae fuera del raster:
        * clamp=True  -> usa el valor del borde más cercano (sin interpolar).
        * clamp=False -> devuelve default_value.
    - Si interpolate=True, hace bilineal; si no hay 4 celdas válidas, devuelve default_value.
    - Si encuentra NoData/NaN, devuelve default_value.
    """
    if ELEVATION is None or TRANSFORM is None:
        raise RuntimeError("DEM no inicializado. Llama a init_dem(raster_path).")

    ox, px_w, _, oy, _, px_h = TRANSFORM
    # Columnas/filas flotantes (px_h suele ser negativo)
    col_f = (x - ox) / px_w
    row_f = (y - oy) / px_h

    n_rows, n_cols = ELEVATION.shape

    def in_bounds(r: int, c: int) -> bool:
        return 0 <= r < n_rows and 0 <= c < n_cols

    def is_nodata(z: float) -> bool:
        if z is None:
            return True
        if isinstance(z, float) and (math.isnan(z) if not isinstance(z, np.floating) else np.isnan(z)):
            return True
        if NODATA is not None and z == NODATA:
            return True
        return False

    # Índices enteros cercanos
    col = int(math.floor(col_f))
    row = int(math.floor(row_f))

    # Si no interpolas
    if not interpolate:
        if in_bounds(row, col):
            z = float(ELEVATION[row, col])
            return default_value if is_nodata(z) else z
        # Fuera de raster
        if clamp:
            # Encaja a borde
            row_c = min(max(row, 0), n_rows - 1)
            col_c = min(max(col, 0), n_cols - 1)
            z = float(ELEVATION[row_c, col_c])
            return default_value if is_nodata(z) else z
        else:
            return default_value

    # Interpolación bilineal
    col0 = math.floor(col_f); col1 = col0 + 1
    row0 = math.floor(row_f); row1 = row0 + 1

    # Verifica que las 4 celdas existan; si no, decide según clamp
    corners_in = (
        in_bounds(row0, col0) and in_bounds(row0, col1) and
        in_bounds(row1, col0) and in_bounds(row1, col1)
    )
    if not corners_in:
        if clamp:
            # Para bilineal con clamping real, habría que recomputar pesos con índices encajados.
            # Simplificación: devuelve el valor encajado más cercano (sin interpolar).
            row_c = min(max(int(round(row_f)), 0), n_rows - 1)
            col_c = min(max(int(round(col_f)), 0), n_cols - 1)
            z = float(ELEVATION[row_c, col_c])
            return default_value if is_nodata(z) else z
        else:
            return default_value

    # Pesos
    dx = col_f - col0
    dy = row_f - row0

    z00 = float(ELEVATION[row0, col0])
    z10 = float(ELEVATION[row0, col1])
    z01 = float(ELEVATION[row1, col0])
    z11 = float(ELEVATION[row1, col1])

    # Si alguna esquina es NoData/NaN -> default
    if any(is_nodata(zv) for zv in (z00, z10, z01, z11)):
        return default_value

    z = (
        z00 * (1 - dx) * (1 - dy) +
        z10 * dx * (1 - dy) +
        z01 * (1 - dx) * dy +
        z11 * dx * dy
    )

    # Validación final
    if is_nodata(z) or not math.isfinite(z):
        return default_value

    return float(z)





# --- DXF restricciones ---
def leer_poligonos_dxf(ruta_dxf: str, buffer_m: float) -> Optional[List[Polygon]]:
    if not os.path.exists(ruta_dxf):
        return None
    doc = ezdxf.readfile(ruta_dxf)
    msp = doc.modelspace()
    poligonos = []
    poligonos_datos = []
    for entity in msp:
        if entity.dxftype() == "LWPOLYLINE" and entity.closed:
            pts = [(p[0], p[1]) for p in entity.get_points()]
            if len(pts) >= 3:
                poligonos.append(Polygon(pts).buffer(buffer_m))
                poligonos_datos.append(pts)
    os.makedirs("restrictions", exist_ok=True)
    with open("poligonos_extraidos.json", "w") as f:
        json.dump(poligonos_datos, f, indent=4)
    for idx, pts in enumerate(poligonos_datos, start=1):
        restrictions = []
        for x, y in pts:
            lon, lat = utm_lat_lon(x, y, number=13, huso="N")
            restrictions.append({"x": x, "y": y, "lon": lon, "lat": lat})
        with open(f"restrictions/{idx}_restrictions.json", "w") as f:
            json.dump(restrictions, f, indent=4)
    return poligonos

# --- DXF export ---

def exportar_dxf(ruta_pts, nombre_a, nombre_b, DXF_FOLDER):
    os.makedirs("DXF_FILES", exist_ok=True)
    output_dxf = f"{DXF_FOLDER}/{nombre_a}_{nombre_b}_ruta_optima.dxf"

    driver = ogr.GetDriverByName("DXF")
    if os.path.exists(output_dxf):
        driver.DeleteDataSource(output_dxf)

    # >>> 3D: LineString 25D (con Z)
    ds = driver.CreateDataSource(output_dxf)
    layer = ds.CreateLayer("ruta", geom_type=ogr.wkbLineString25D)

    line = ogr.Geometry(ogr.wkbLineString25D)
    for p in ruta_pts:
        x = p["x"]; y = p["y"]
        z = float(p.get("z", 0.0))  # si por cualquier motivo faltara z
        line.AddPoint(x, y, z)

    feature = ogr.Feature(layer.GetLayerDefn())
    feature.SetGeometry(line)
    layer.CreateFeature(feature)

    feature = None
    ds = None
    print(f"Ruta exportada a DXF (3D): {output_dxf}")


# --- DXF de puntos (debug) ---
def dxf_puntos_3d(ruta_salida, puntos_xyz,
                  capa="Puntos", color_aci=1, pdmode=34, pdsize=1.5):
    out_dir = os.path.dirname(os.path.abspath(ruta_salida))
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)
    doc = ezdxf.new("R2010")
    try:
        doc.layers.new(name=capa, dxfattribs={"color": color_aci})
    except DXFValueError:
        pass
    doc.header["$PDMODE"] = pdmode
    doc.header["$PDSIZE"] = pdsize
    msp = doc.modelspace()
    for p in puntos_xyz:
        if len(p) == 2:
            x, y = p; z = 0.0
        else:
            x, y, z = p
        msp.add_point((x, y, z), dxfattribs={"layer": capa, "color": color_aci})
    doc.saveas(ruta_salida)
    return ruta_salida

# --- Cuadrícula ---
def esta_en_zona_restringida(x: float, y: float, zonas: Optional[List[Polygon]]) -> bool:
    if zonas is None:
        return False
    p = Point(x, y)
    return any(z.contains(p) for z in zonas)

def crear_cuadricula(nodo1: Dict, nodo2: Dict, paso_malla: float,
                     zonas_restringidas: Optional[List[Polygon]],
                     buffer: float, debug: bool = True) -> Tuple[List[Tuple[float, float, Optional[float]]], Dict[Tuple[float, float], int]]:
    min_x = min(nodo1["x"], nodo2["x"]) - buffer
    max_x = max(nodo1["x"], nodo2["x"]) + buffer
    min_y = min(nodo1["y"], nodo2["y"]) - buffer
    max_y = max(nodo1["y"], nodo2["y"]) + buffer

    puntos: List[Tuple[float, float, Optional[float]]] = []
    index_map: Dict[Tuple[float, float], int] = {}
    idx = 0
    y = min_y

    print('%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%')
    while y <= max_y:
        x = min_x
        while x <= max_x:
            if not esta_en_zona_restringida(x, y, zonas_restringidas):
                elev = obtener_elevacion(x, y, interpolate=False, default_value=150.0, clamp=True)
                puntos.append((x, y, elev))
                index_map[(x, y)] = idx
                idx += 1
            x += paso_malla
        y += paso_malla

    if debug:
        dxf_puntos_3d('DXF_FILES/puntos.dxf', puntos)

    return puntos, index_map

# --- Geometría ---
def angulo_entre(p_prev, p_act, p_next) -> float:
    v1 = (p_prev[0] - p_act[0], p_prev[1] - p_act[1])
    v2 = (p_next[0] - p_act[0], p_next[1] - p_act[1])
    dot = v1[0]*v2[0] + v1[1]*v2[1]
    mag1 = math.hypot(*v1)
    mag2 = math.hypot(*v2)
    if mag1 == 0 or mag2 == 0:
        return 180.0
    cos_t = max(min(dot/(mag1*mag2), 1.0), -1.0)
    return math.degrees(math.acos(cos_t))

def radio_circunferencia(p1, p2, p3) -> float:
    a = math.dist(p1, p2); b = math.dist(p2, p3); c = math.dist(p1, p3)
    s = (a + b + c) / 2.0
    area_sq = max(s*(s-a)*(s-b)*(s-c), 0.0)
    if area_sq == 0.0:
        return float('inf')
    area = math.sqrt(area_sq)
    return (a*b*c) / (4.0*area)

# --- Grafo ---

def construir_grafo(puntos, index_map, paso_malla):
    z_cache = {}
    def z_at(x, y):
        key = (x, y)
        if key not in z_cache:
            z_cache[key] = obtener_elevacion(x, y, interpolate=False, default_value=150.0, clamp=True)
        return z_cache[key]
    vecinos_map = {}
    for idx, (x, y, elev) in enumerate(puntos):
        vecinos = []
        for dx, dy in [(paso_malla,0), (-paso_malla,0), (0,paso_malla), (0,-paso_malla)]:
            nx, ny = x + dx, y + dy
            if (nx, ny) in index_map:
                nidx = index_map[(nx, ny)]
                dist = math.hypot(dx, dy)
                if dist > 0:
                    z1 = z_at(x, y)
                    z2 = z_at(nx, ny)
                    pendiente = ((z2 - z1) / dist) * 100.0 if (z1 is not None and z2 is not None) else None
                    vecinos.append((nidx, dist, pendiente))
        vecinos_map[idx] = vecinos
    return vecinos_map
'''for dx in [-paso_malla, 0, paso_malla]:
            for dy in [-paso_malla, 0, paso_malla]:
                if dx == 0 and dy == 0:
                    continue
                nx, ny = x + dx, y + dy
                if (nx, ny) in index_map:
                    nidx = index_map[(nx, ny)]
                    x2, y2, elev2 = puntos[nidx]
                    dist = math.hypot(dx, dy)
                    pendiente = None
                    if dist > 0:
                        z1 = obtener_elevacion(x, y, interpolate=True)
                        z2 = obtener_elevacion(x2, y2, interpolate=True)
                        if z1 is not None and z2 is not None:
                            pendiente = (z2 - z1) / dist * 100.0
                    vecinos.append((nidx, dist, pendiente))
        vecinos_map[idx] = vecinos
    return vecinos_map'''


# --- Heurística ---
def h_euclid(puntos, a, b):
    return math.hypot(puntos[a][0] - puntos[b][0], puntos[a][1] - puntos[b][1])

# --- Umbral por ángulo ---
def umbral_pendiente_por_angulo(ang: float) -> float:
    return DG["max_slope_curve"] if ang < DG["curve_angle_threshold"] else DG["max_slope_straight"]

# --- Densificar ---
def densificar_segmento(p1, p2, paso):
    x1, y1 = p1; x2, y2 = p2
    dx, dy = x2 - x1, y2 - y1
    L = math.hypot(dx, dy)
    if L == 0:
        return [p1]
    n = max(1, int(math.ceil(L / paso)))
    ux, uy = dx / L, dy / L
    pts = [(x1 + ux * paso * i, y1 + uy * paso * i) for i in range(n)]
    if pts[-1] != (x2, y2):
        pts.append((x2, y2))
    return pts

# --- A* ---
def astar(idx_inicio, idx_fin, vecinos_map, puntos):
    open_set: List[Tuple[float, int]] = []
    heapq.heappush(open_set, (0.0, idx_inicio))
    came_from: Dict[int, int] = {}
    gscore: Dict[int, float] = {idx_inicio: 0.0}
    while open_set:
        _, actual = heapq.heappop(open_set)
        if actual == idx_fin:
            ruta = [actual]
            while actual in came_from:
                actual = came_from[actual]
                ruta.append(actual)

            return ruta[::-1], gscore[idx_fin]
        for vecino, dist, slope in vecinos_map.get(actual, []):
            if slope is None:
                continue
            penalizacion_curva = 0.0
            ang = 180.0
            rad = float('inf')
            if actual in came_from:
                prev = came_from[actual]
                p_prev = puntos[prev][:2]
                p_act  = puntos[actual][:2]
                p_next = puntos[vecino][:2]
                ang = angulo_entre(p_prev, p_act, p_next)
                rad = radio_circunferencia(p_prev, p_act, p_next)
            #if rad < DG["min_curve_radius"]:
              #  continue
            umbral = umbral_pendiente_por_angulo(ang)

            #if abs(slope) > umbral*6:
             #   continue
            if ang < DG["curve_angle_threshold"]:
                penalizacion_curva += 2 * (DG["curve_angle_threshold"] - ang) / DG["curve_angle_threshold"]
            if math.isfinite(rad):
                penalizacion_curva += 2 * (DG["min_curve_radius"] / max(rad, DG["min_curve_radius"])) * 0.5
            s = abs(slope)
            factor_pendiente = get_factor_penalizacion_bins7(s)

            costo_tramo = dist * factor_pendiente + penalizacion_curva
            tentative_g = gscore[actual] + costo_tramo
            if vecino not in gscore or tentative_g < gscore[vecino]:
                came_from[vecino] = actual
                gscore[vecino] = tentative_g
                fscore = tentative_g + h_euclid(puntos, vecino, idx_fin)
                heapq.heappush(open_set, (fscore, vecino))
    return [],float('inf')  # no hay ruta

# --- Utilidades ---
def encontrar_nodo_mas_cercano(coord, puntos):
    return min(range(len(puntos)), key=lambda i: math.hypot(puntos[i][0] - coord["x"], puntos[i][1] - coord["y"]))

def _normaliza_nombre(n: str) -> str:
    if not n: return n
    n2 = n.strip().lower().replace(" ", "_")
    if n2.endswith("_in"):
        n2 = n2[:-3] + "_entry"
    return n2

def _parsea_wtg(nombre: str):
    if not nombre: return None
    n = _normaliza_nombre(nombre)
    if not n.startswith("wtg_"): return None
    if n.endswith("_entry"): return (n[:-6], "entry")
    if n.endswith("_out"):   return (n[:-4], "out")
    return None

def buscar_pareja_wtg(nombre_nodo: str, nodos_wtg: list) -> Optional[dict]:
    info = _parsea_wtg(nombre_nodo)
    if not info: return None
    base, rol = info
    objetivo = base + ("_out" if rol == "entry" else "_entry")
    objetivo = _normaliza_nombre(objetivo)
    for n in nodos_wtg:
        if _normaliza_nombre(n.get("nombre", "")) == objetivo:
            return n
    return None

def _angulo_vecs(v1, v2):
    x1, y1 = v1; x2, y2 = v2
    dot = x1 * x2 + y1 * y2
    n1 = math.hypot(x1, y1); n2 = math.hypot(x2, y2)
    if n1 == 0 or n2 == 0: return 0.0
    c = max(min(dot/(n1*n2), 1.0), -1.0)
    return math.degrees(math.acos(c))

def aplicar_buffer_entre_nodos(n1, n2, nodos_wtg,
                               distancia_buffer=25,
                               desplazamiento_adicional=30,
                               ang_max=60.0):
    delta = float(distancia_buffer) + float(desplazamiento_adicional)
    def mover_hacia(a, b):
        if b is None: return 0.0, 0.0
        dx, dy = a['x'] - b['x'], a['y'] - b['y']
        L = math.hypot(dx, dy)
        if L == 0: return 0.0, 0.0
        return dx / L, dy / L

    # n1
    if n1['nombre'].startswith("wtg"):
        pareja_n1 = buscar_pareja_wtg(n1.get("nombre",""), nodos_wtg)
        ux_1, uy_1 = mover_hacia(n1, pareja_n1)
        if ux_1 == 0 and uy_1 == 0:
            ux_1, uy_1 = mover_hacia(n2, n1)
    else:
        ux_1, uy_1 = mover_hacia(n2, n1)
        if ux_1 == 0 and uy_1 == 0:
            ux_1, uy_1 = mover_hacia(n1, n2)
    n1m = {"nombre": n1["nombre"], "x": n1["x"] + ux_1*delta, "y": n1["y"] + uy_1*delta}

    # n2
    if n2['nombre'].startswith("wtg"):
        pareja_n2 = buscar_pareja_wtg(n2.get("nombre",""), nodos_wtg)
        ux_2, uy_2 = mover_hacia(n2, pareja_n2)
        if ux_2 == 0 and uy_2 == 0:
            ux_2, uy_2 = mover_hacia(n1, n2)
    else:
        ux_2, uy_2 = mover_hacia(n1, n2)
        if ux_2 == 0 and uy_2 == 0:
            ux_2, uy_2 = mover_hacia(n2, n1)
    n2m = {"nombre": n2["nombre"], "x": n2["x"] + ux_2*delta, "y": n2["y"] + uy_2*delta}

    # Control de ángulo inicial
    v_entry = (n1m["x"] - n1["x"], n1m["y"] - n1["y"])
    v_seg   = (n2m["x"] - n1m["x"], n2m["y"] - n1m["y"])
    ang = _angulo_vecs(v_entry, v_seg)
    if ang > ang_max:
        factor = 0.85
        intentos = 12
        delta_min = 1.0
        while ang > ang_max and intentos > 0 and delta > delta_min:
            delta *= factor
            n1m["x"] = n1["x"] + ux_1*delta
            n1m["y"] = n1["y"] + uy_1*delta
            v_entry = (n1m["x"] - n1["x"], n1m["y"] - n1["y"])
            v_seg   = (n2m["x"] - n1m["x"], n2m["y"] - n1m["y"])
            ang = _angulo_vecs(v_entry, v_seg)
            intentos -= 1
    return n1m, n2m

# --- Export JSON/GeoJSON ---

def exportar_json_geo(ruta_pts: List[Dict], nombre_a: str, nombre_b: str, export_geojson: bool = True):
    os.makedirs("CSV_files", exist_ok=True)
    path = f"CSV_files/{nombre_a}_{nombre_b}_ruta_optima.json"
    with open(path, "w") as f:
        json.dump(ruta_pts, f, indent=4)

    if export_geojson:
        # Si hay z en los puntos, la incluimos como tercer valor de coordenada
        def _coord(p):
            if "z" in p and p["z"] is not None:
                return [p["lon"], p["lat"], float(p["z"])]
            return [p["lon"], p["lat"]]

        fc = {
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "properties": {"name": f"{nombre_a}-{nombre_b}"},
                "geometry": {
                    "type": "LineString",
                    "coordinates": [_coord(p) for p in ruta_pts]
                }
            }]
        }
        with open(f"CSV_files/{nombre_a}_{nombre_b}_ruta_optima.geojson", "w") as f:
            json.dump(fc, f, indent=2)


# =========================
# FUNCIÓN PRINCIPAL (con raster_path)
# =========================
def ruta_optima_entre_nodos(nodo1: Dict, nodo2: Dict, zonas_restringidas,
                            DXF_FOLDER: str, FOLDER_NAME_1: str,
                            raster_path: str | None = None,
                            paso_malla: float = PASO_MALLA_DEFAULT,
                            paso_camino: float = PASO_CAMINO_DEFAULT,
                            buffer_cuadricula: float = BUFFER_CUADRICULA):

    # 1) DEM explícito
    init_dem(raster_path)

    # 2) Validación y preparación
    ruta_dxf = f"{DXF_FOLDER}/PLATFORM.dxf"
    initial = dict(nodo1); final = dict(nodo2)
    with open(f"{FOLDER_NAME_1}/wtg_points.json", encoding="utf-8") as f:
        nodos_wtg = json.load(f)
    n1, n2 = aplicar_buffer_entre_nodos(nodo1, nodo2, nodos_wtg,
                                        distancia_buffer=25, desplazamiento_adicional=30)

    # 3) Zonas restringidas (sumar DXF si existe)
    zonas: Optional[List[Polygon]] = []
    pols = leer_poligonos_dxf(ruta_dxf, buffer_m=BUFFER_DXF)
    if pols: zonas.extend(pols)
    if isinstance(zonas_restringidas, list) and zonas_restringidas:
        zonas.extend(zonas_restringidas)
    zonas = zonas or None

    # 4) Cuadrícula, grafo y A*
    puntos, index_map = crear_cuadricula(n1, n2, paso_malla, zonas, buffer=buffer_cuadricula, debug=False)

    vecinos_map = construir_grafo(puntos, index_map, paso_malla)
    idx_inicio = encontrar_nodo_mas_cercano(n1, puntos)
    idx_fin    = encontrar_nodo_mas_cercano(n2, puntos)

    ruta_indices, coste_total = astar(idx_inicio, idx_fin, vecinos_map, puntos)


    # 5) Ruta y métricas
    ruta_final: List[Dict] = []

    lon_i, lat_i = utm_lat_lon(initial["x"], initial["y"], number=13, huso="N")
    z_i =obtener_elevacion(initial["x"], initial["y"], interpolate=False, default_value=150.0, clamp=True)
    ruta_final.append({"x": initial["x"], "y": initial["y"], "z": z_i, "lon": lon_i, "lat": lat_i})

    for idx in ruta_indices:

        x, y = puntos[idx][:2]
        lon, lat = utm_lat_lon(x, y, number=13, huso="N")


        z = obtener_elevacion(x, y, interpolate=False, default_value=150.0, clamp=True)

        ruta_final.append({"x": x, "y": y, "z": z, "lon": lon, "lat": lat})


    # Punto final (con Z)
    lon_f, lat_f = utm_lat_lon(final["x"], final["y"], number=13, huso="N")
    z_f = obtener_elevacion(final["x"], final["y"], interpolate=False, default_value=150.0, clamp=True)
    ruta_final.append({"x": final["x"], "y": final["y"], "z": z_f, "lon": lon_f, "lat": lat_f})

    slopes: List[float] = []
    slope_dist_acum = 0.0
    distancia_final = 0.0
    for i in range(len(ruta_final) - 1):
        xa, ya, za = ruta_final[i]["x"], ruta_final[i]["y"], ruta_final[i]["z"]
        xb, yb, zb = ruta_final[i + 1]["x"], ruta_final[i + 1]["y"], ruta_final[i + 1]["z"]
        dist = math.hypot(xb - xa, yb - ya)
        if dist <= 0 or za is None or zb is None:
            continue

        slope = abs(zb - za) / dist * 100.0
        slopes.append(slope)
        distancia_final += dist

    if len(ruta_final) > 2:
        slope_promedio = round(sum(slopes)/len(slopes), 2) if slopes else None
        slope_mediana  = round(statistics.median(slopes), 2) if slopes else None
        slope_ponderado= round(slope_dist_acum/max(distancia_final, 1e-9), 3) if distancia_final > 0 else None
    else:
        slope_promedio = 1e9
        slope_mediana  = 1e9
        slope_ponderado= 1e9
        coste_total= 1e9

    if coste_total >10000:
        coste_total=distancia_final*80

    output_data = {
        "ruta": ruta_final,
        "distancia": distancia_final,
        "slope_promedio": slope_promedio,
        "slope_mediana": slope_mediana,
        "slope_distancia": round(coste_total, 3),
        "slope_ponderado": slope_ponderado
    }


    exportar_dxf(ruta_final, n1['nombre'], n2['nombre'], DXF_FOLDER)
    os.makedirs("CSV_files", exist_ok=True)
    with open(f"{FOLDER_NAME_1}/{n1['nombre']}_{n2['nombre']}_ruta_optima.json", "w") as f:
        json.dump(output_data, f, indent=4)

    return (ruta_final, distancia_final, slope_promedio, slope_mediana, round(coste_total, 3), slope_ponderado)
