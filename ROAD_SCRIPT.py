# -*- coding: utf-8 -*-
import json, os, datetime
from pathlib import Path
from shapely.geometry import Polygon, LineString
import re
import streamlit as st
from main_road import main_road_
from typing import Union,List, Dict, Tuple, Optional
#from DEM_FILE import dem_file
import sys
# (1) Lector de restricciones GeoJSON (UTM)

# --- persistir ruta DEM ---

def get_unit_prices(default_exc=5.0, default_fill=5.0):
    try:
        import streamlit as st
        exc = float(st.session_state.get("excavation_price", default_exc))
        fil = float(st.session_state.get("fill_price", default_fill))
        return exc, fil
    except Exception:
        return float(default_exc), float(default_fill)


excavation_price,fill_price=get_unit_prices()


def construir_nodos_wtg(
    wtg_list: List[Dict],
    orden_por_id: bool = True,
    start_index: int = 1,
    redondeo: Optional[int] = None,
    filtrar_ids: Optional[List[str]] = None
) -> Dict[str, Tuple[float, float]]:
    """
    Convierte una lista de dicts con claves ('id','utm_x','utm_y') a:
        nodos = {"wtg_1": (utm_x, utm_y), "wtg_2": (...), ...}

    Parámetros:
        wtg_list: lista de dicts con al menos ('id','utm_x','utm_y').
        orden_por_id: si True, ordena por número extraído de 'id' (WTG_44 -> 44).
        start_index: índice inicial para 'wtg_{i}'.
        redondeo: si no es None, redondea las coordenadas a 'redondeo' decimales.
        filtrar_ids: lista opcional de IDs a incluir.

    Retorna:
        dict: {"wtg_i": (x, y), ...}
    """
    # Filtrar si se pide
    datos = wtg_list
    if filtrar_ids:
        keep = set(filtrar_ids)
        datos = [d for d in datos if d.get("id") in keep]

    # Función para extraer número de 'WTG_44' -> 44 (si existe)
    def num_de_id(id_str: str) -> int:
        m = re.search(r"(\d+)", id_str or "")
        return int(m.group(1)) if m else 0

    # Orden
    if orden_por_id:
        datos = sorted(datos, key=lambda d: num_de_id(d.get("id", "")))

    # Construcción
    nodos = {}
    idx = start_index
    for d in datos:
        x = float(d["utm_x"])
        y = float(d["utm_y"])
        if redondeo is not None:
            x = round(x, redondeo)
            y = round(y, redondeo)
        nodos[f"wtg_{idx}"] = (x, y)
        idx += 1

    return nodos

# Función para simplificar nodos manteniendo el formato original
def simplificar_nodos_camino(nodos, tolerancia=4):
    # Convertir lista de nodos a lista de coordenadas
    coords = [(nodo['x'], nodo['y']) for nodo in nodos]

    # Crear línea y simplificar
    line = LineString(coords)
    simplified = line.simplify(tolerance=tolerancia, preserve_topology=False)

    # Reconstruir lista de nodos con formato original
    nodos_simplificados = []
    for i, (x, y) in enumerate(simplified.coords):
        nodos_simplificados.append({
            'nombre': f"camino_{str(i+1).zfill(4)}",
            'x': x,
            'y': y
        })

    return nodos_simplificados

def extraction_road_from_json(geojson_or_path: Union[str, dict],
                              Huso_a: int = None,
                              Huso_b: str = None,
                              add_lonlat: bool = False) -> List[Dict]:
    """
    Lee un GeoJSON (FeatureCollection) con features tipo camino (LineString/MultiLineString)
    y devuelve una lista 'nodos' con el mismo formato que la función DXF original:

        [{"nombre": "camino_0001", "x": 434906.6594, "y": 4732888.2771}, ...]

    Parámetros:
        geojson_or_path: dict del GeoJSON o ruta a archivo .json
        Huso_a: número de huso (ej. 13) si se desea conversión lon/lat
        Huso_b: hemisferio ('N' o 'S') si se desea conversión lon/lat
        add_lonlat: si True, añade "lon" y "lat" a cada nodo (requiere utm_lat_lon)

    Retorna:
        nodos: List[Dict] con claves ("nombre", "x", "y") y opcional ("lon", "lat")
    """
    # --- Cargar el objeto GeoJSON ---
    if isinstance(geojson_or_path, str):
        with open(geojson_or_path, "r", encoding="utf-8") as f:
            gj = json.load(f)
    elif isinstance(geojson_or_path, dict):
        gj = geojson_or_path
    else:
        raise ValueError("geojson_or_path debe ser dict o ruta a archivo .json")

    if gj.get("type") != "FeatureCollection":
        raise ValueError("Se esperaba 'type' == 'FeatureCollection' en la raíz.")

    features = gj.get("features", [])
    if not features:
        return []  # Sin features, sin nodos

    # Intentamos deducir EPSG si hace falta (no es obligatorio para nodos x/y)
    epsg = None
    # Primero properties.utm_epsg si existe
    for f in features:
        props = f.get("properties", {}) or {}
        if isinstance(props.get("utm_epsg"), int):
            epsg = props["utm_epsg"]
            break
    # Si no, miramos meta.crs tipo "EPSG:32613"
    if epsg is None:
        meta = gj.get("meta", {}) or {}
        crs_txt = meta.get("crs")
        if isinstance(crs_txt, str) and crs_txt.startswith("EPSG:"):
            try:
                epsg = int(crs_txt.split(":")[1])
            except Exception:
                epsg = None

    # --- Construcción de nodos ---
    nodos: List[Dict] = []
    contador = 0

    def agregar_coords(coords_list):
        nonlocal contador, nodos
        for c in coords_list:
            if not (isinstance(c, list) or isinstance(c, tuple)) or len(c) < 2:
                continue
            x = float(c[0])
            y = float(c[1])
            contador += 1
            item = {
                "nombre": f"camino_{contador:04d}",
                "x": x,
                "y": y
            }
            # Opcional: lon/lat (requiere utm_lat_lon + Huso_a/Huso_b)
            if add_lonlat:
                if Huso_a is None or Huso_b is None:
                    raise ValueError("Para lon/lat, provee Huso_a (int) y Huso_b ('N'/'S').")
                # lon, lat = utm_lat_lon(x, y, number=Huso_a, huso=Huso_b)
                # item["lon"] = lon
                # item["lat"] = lat
                # (Dejado en comentario para no romper si no está disponible UTM_GEO)
            nodos.append(item)

    for feat in features:
        geom = feat.get("geometry", {}) or {}
        gtype = geom.get("type")
        coords = geom.get("coordinates", [])

        if gtype == "LineString":
            agregar_coords(coords)

        elif gtype == "MultiLineString":
            for line in coords:  # cada 'line' es una lista de puntos
                agregar_coords(line)

        else:
            # Ignora geometrías que no son caminos
            continue

    return nodos


def leer_poligonos_json(path_json, buffer_m=20):
    zonas = []
    try:
        with open(path_json, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        st.error(f"FALTA_RESTRICCIONES: {e}")
        st.stop
    for feat in data.get('features', []):
        geom = feat.get('geometry') or {}
        gtype = geom.get('type')
        coords = geom.get('coordinates')
        if gtype == 'Polygon' and coords:
            zonas.append(Polygon(coords[0]).buffer(0))
        elif gtype == 'LineString' and coords:
            zonas.append(LineString(coords).buffer(buffer_m))
    return zonas

# (2) Lectores de puntos (grid_on y cluster_set)
def grid_on_(path):
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    for feature in data.get('features', []):
        props = feature.get('properties', {}) or {}
        geom  = feature.get('geometry', {}) or {}
        if geom.get('type') == 'Point':
            coords = geom.get('coordinates', [])
            if len(coords) >= 2:   # <-- corregido
                return {"nombre": props.get('tipo','grid_on'),
                        "x": float(coords[0]), "y": float(coords[1])}
    return None

def cluster_set_xy(path):
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    sim = data.get('Simulation SET', {}) or {}
    x = sim.get('x'); y = sim.get('y')
    return {"nombre": "Cluster_set", "x": float(x), "y": float(y)}

def road_survey(path):
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Acceder a la primera feature y sus coordenadas
    features = data.get("features", [])
    if not features:
        raise ValueError("No hay features en el GeoJSON.")

    geometry = features[0].get("geometry", {})
    coords = geometry.get("coordinates", [])
    if len(coords) < 2:
        raise ValueError("Coordenadas inválidas en el GeoJSON.")

    x, y = coords[0], coords[1]

    # Devolver el resultado como dict
    return {"road_survey": (x, y)}

def wtg_xy(path):
    return
# --- rutas ---

def road_script_main(niveles_tension,datos_wtg,grid_on,road_survey_path,restricciones,camino_dir,nodos_wtg,raster_path,FOLDER_NAME_1,DXF_FOLDER,path_caminos):#falta carpeta dxf_file

    '''niveles_tension = './salidas/pronghorn/pronghorn-e490b1c7/config/niveles_tension_20251217_112602.json'
    datos_wtg = './salidas/pronghorn/pronghorn-e490b1c7/config/wtg_cfg_pronghorn_pronghorn-e490b1c7_20251217_112835.json'
    grid_on = './salidas/pronghorn/grid_on/grid_on_20251217_112813_utm32613.geojson'
    road_survey_path='./salidas/pronghorn/ruad_survey/ruad_survey_20251217_112751_utm32613.geojson'
    restricciones = './salidas/pronghorn/restricciones/restricciones_20251217_112755_utm32613.geojson'
    resultados_MV = './salidas/pronghorn/JSON_FILES/MV_COLLECTOR_RESULTS.json'
    raster_path = './salidas/pronghorn/RASTER_FILE/tn_curvas_20251216_120305.tif'
    camino_dir = './salidas/pronghorn/caminos/camino_20251217_112753_utm32613.geojson'
    nodos_wtg='./salidas/pronghorn/puntos/coords_min_excel_20251217_112817.json'
    raster_path='./salidas/pronghorn/RASTER_FILE/tn_curvas_20251217_112542.tif'''
    # --- prueba de lectura restricciones ---
    try:
        zonas_restringidas = leer_poligonos_json(restricciones, buffer_m=20)
    except Exception as e:
        st.error(f"FALTAN RESTRICCIONES {e}")
        st.stop()
    nodos_caminos_1=extraction_road_from_json(camino_dir)
    print(len(nodos_caminos_1))
    nodos_caminos=simplificar_nodos_camino(nodos_caminos_1,0.5)
    print(len(nodos_caminos))

    with open(niveles_tension, encoding="utf-8") as f:
        datos_tension = json.load(f)

    with open(datos_wtg, encoding="utf-8") as f:
        datos_a = json.load(f)

    with open(nodos_wtg, encoding="utf-8") as f:
        nodos_wtg= json.load(f)

    nodos_final={**construir_nodos_wtg(nodos_wtg),**road_survey(road_survey_path)}


    HUSO_a=datos_tension.get('huso')
    HUSO_b = 'N' if datos_tension.get('hemisferio') == 'Norte' else 'S'
    Name_project=datos_tension.get('proj_name')
    Project_id=datos_tension.get('project_id')
    session_id=datos_tension.get('session_id')

    entry_exit={"entry_point": tuple(datos_a['platform']['entry_point']),"exit_point":tuple(datos_a['platform']['exit_point'])}
    pads= {k: tuple(v) for k, v in datos_a['platform']['pads'].items()}
    preassembly = {k: tuple(v) for k, v in datos_a['platform']['preassembly'].items()}
    diameter_blade = datos_a.get('diameter_blade_m')
    fundacion_diametro  = datos_a.get('platform', {}).get('platform_diameter_m') # None en tu dict'''




    lista_material_1= main_road_(zonas_restringidas, HUSO_a, HUSO_b, excavation_price, fill_price,
        entry_exit, pads, preassembly, diameter_blade,
        nodos_caminos, nodos_final, fundacion_diametro,
        FOLDER_NAME_1, DXF_FOLDER,
        raster_path,path_caminos  # <-- pásalo
       )


    #print(H)

    return lista_material_1








