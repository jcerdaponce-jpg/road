import math
import csv
import heapq

from matplotlib import pyplot as plt
from osgeo import gdal

import json
#from UTM_GEO import utm_lat_lon
import os
import ezdxf
#from PLOT_OHL import plot_ohl
from shapely.geometry import Point, Polygon
import time
# Parámetros
start_time = time.time()
paso =100
print(paso)
angulo_maximo =90# grados

def dem_file(path: str) -> str:
    """run.exe
    Verifica y devuelve la ruta al archivo DEM.
    Lanza ValueError si path es vacío o FileNotFoundError si no existe.
    """
    if not path:
        raise ValueError("La ruta del DEM no puede ser vacía.")
    ruta_dem = os.path.abspath(path)
    if not os.path.isfile(ruta_dem):
        raise FileNotFoundError(f"No se encontró el DEM en: {ruta_dem}")
    print(f"[DEM] Usando raster: {ruta_dem}")
    return ruta_dem


#--- Variables globales (inicialmente None) ---
dem_ds = None       # handler GDAL opcional
elevation = None    # numpy array 2D
transform = None    # tuple geotransform
nodata = None       # float o None

def init_dem(raster_path: str):
    """
    Inicializa las variables globales elevation, transform, nodata y dem_ds.
    Debe llamarse una vez antes de usar obtener_elevacion si dependes de globals.
    """
    global dem_ds, elevation, transform, nodata

    if not raster_path:
        raise ValueError("raster_path vacío.")
    raster_path = os.path.abspath(raster_path)
    if not os.path.isfile(raster_path):
        raise FileNotFoundError(f"No existe DEM en: {raster_path}")

    dem_ds = gdal.Open(raster_path)
    if dem_ds is None:
        raise RuntimeError(f"GDAL no pudo abrir el DEM: {raster_path}")

    band = dem_ds.GetRasterBand(1)
    elevation = band.ReadAsArray()
    transform = dem_ds.GetGeoTransform()
    nodata = band.GetNoDataValue()

    if elevation is None or transform is None:
        raise RuntimeError("No se pudo leer elevation/transform del DEM.")

    print(f"[DEM] Cargado: {raster_path}")
    print(f"[DEM] Tamaño: {elevation.shape}, NoData: {nodata}, GT: {transform}")



def obtener_elevacion(x: float, y: float):
    """
    Usa las variables globales elevation/transform ya inicializadas.
    Retorna elevación o None si fuera de rango/NoData.
    """
    global elevation, transform, nodata

    if elevation is None or transform is None:
        raise RuntimeError("DEM no inicializado. Llama a init_dem(ruta_dem) primero.")

    # Si tu raster es north-up (sin rotación). Si hay rotación, ver patrón 2.
    px = (x - transform[0]) / transform[1]
    py = (y - transform[3]) / transform[5]  # suele ser negativo en north-up

    ix = int((px // 1))  # equivalente a floor para positivos, usa math.floor si prefieres
    iy = int((py // 1))

    h, w = elevation.shape
    if 0 <= ix < w and 0 <= iy < h:
        val = float(elevation[iy, ix])
        if nodata is not None:
            # Manejo de NoData
            if val == nodata:
                return None
        return val
    return None


# Penalización por pendiente
elevation_factors = [1, 1.03, 1.05, 1.08,1.5, 10]
def obtener_factor_pendiente(slope):
    if slope is None:
        return 0
    slope = abs(slope)
    if slope <= 0: return elevation_factors[0]
    elif slope <= 5: return elevation_factors[1]
    elif slope <= 10: return elevation_factors[2]
    elif slope <= 15: return elevation_factors[3]
    elif slope <= 20: return elevation_factors[4]
    else: return elevation_factors[5]

# Leer polígonos desde archivo DXF
def leer_poligonos_dxf(ruta_dxf, buffer):
    if not os.path.exists(ruta_dxf):
        return None
    doc = ezdxf.readfile(ruta_dxf)
    msp = doc.modelspace()
    poligonos = []
    for entity in msp:
        if entity.dxftype() == 'LWPOLYLINE' and entity.closed:
            puntos = [(p[0], p[1]) for p in entity.get_points()]
            if len(puntos) >= 3:
                poligonos.append(Polygon(puntos).buffer(buffer))
    return poligonos

# Verificar si un punto está dentro de alguna zona restringida
def esta_en_zona_restringida(x, y, zonas):
    if zonas is None:
        return False
    punto = Point(x, y)
    return any(zona.contains(punto) for zona in zonas)

# Crear cuadrícula de puntos
def crear_cuadricula(nodo1, nodo2, paso, zonas_restringidas, buffer=500):
    min_x = min(nodo1["x"], nodo2["x"]) - buffer
    max_x = max(nodo1["x"], nodo2["x"]) + buffer
    min_y = min(nodo1["y"], nodo2["y"]) - buffer
    max_y = max(nodo1["y"], nodo2["y"]) + buffer

    puntos = []
    index_map = {}
    idx = 0
    y = min_y
    while y <= max_y:
        x = min_x
        while x <= max_x:
            if not esta_en_zona_restringida(x, y, zonas_restringidas):
                elev = obtener_elevacion(x, y)
                puntos.append((x, y, elev))
                index_map[(x, y)] = idx
                idx += 1
            x += paso
        y += paso

    return puntos, index_map

# Construir grafo conectando vecinos
def construir_grafo(puntos, index_map, paso):
    vecinos_map = {}
    for idx, (x, y, elev) in enumerate(puntos):
        vecinos = []
        for dx in [-paso, 0, paso]:
            for dy in [-paso, 0, paso]:
                if dx == 0 and dy == 0:
                    continue
                nx = x + dx
                ny = y + dy
                if (nx, ny) in index_map:
                    nidx = index_map[(nx, ny)]
                    elev2 = puntos[nidx][2]
                    dist = math.sqrt(dx**2 + dy**2)
                    pendiente = (elev2 - elev) / dist * 100 if elev is not None and elev2 is not None else None
                    factor = obtener_factor_pendiente(pendiente)
                    costo = dist * factor
                    vecinos.append((nidx, costo))
        vecinos_map[idx] = vecinos
    return vecinos_map

# Nodo más cercano a una coordenada
def encontrar_nodo_mas_cercano(coord, puntos):
    return min(range(len(puntos)), key=lambda i: math.hypot(puntos[i][0] - coord["x"], puntos[i][1] - coord["y"]))

# Calcular ángulo entre tres puntos
def calcular_angulo(p1, p2, p3):
    v1 = (p2[0] - p1[0], p2[1] - p1[1])
    v2 = (p3[0] - p2[0], p3[1] - p2[1])
    dot = v1[0]*v2[0] + v1[1]*v2[1]
    mag1 = math.hypot(*v1)
    mag2 = math.hypot(*v2)
    if mag1 == 0 or mag2 == 0:
        return 0
    cos_angle = max(min(dot / (mag1 * mag2), 1), -1)
    angle = math.degrees(math.acos(cos_angle))
    return angle

# Algoritmo A* con restricción de ángulo
def astar(inicio, fin, vecinos_map, puntos):
    def heuristica(a, b):
        return math.hypot(puntos[a][0] - puntos[b][0], puntos[a][1] - puntos[b][1])

    open_set = []
    heapq.heappush(open_set, (0, inicio))
    came_from = {}
    g_score = {inicio: 0}

    while open_set:
        _, actual = heapq.heappop(open_set)
        if actual == fin:
            ruta = []
            while actual in came_from:
                ruta.append(actual)
                actual = came_from[actual]
            ruta.append(inicio)
            return ruta[::-1]

        for vecino, costo in vecinos_map.get(actual, []):
            if actual in came_from and came_from[actual] in came_from:
                p1 = puntos[came_from[came_from[actual]]][:2]
                p2 = puntos[came_from[actual]][:2]
                p3 = puntos[actual][:2]
                angulo = calcular_angulo(p1, p2, p3)
                #if angulo > angulo_maximo:
                 #   continue
            tentative_g = g_score[actual] + costo
            if vecino not in g_score or tentative_g < g_score[vecino]:
                came_from[vecino] = actual
                g_score[vecino] = tentative_g
                f_score = tentative_g + heuristica(vecino, fin)
                heapq.heappush(open_set, (f_score, vecino))
    return []

# Avanzar desde un punto en una dirección
def avanzar_desde_punto(punto, direccion, distancia):
    dx = distancia * math.sin(math.radians(direccion))
    dy = distancia * math.cos(math.radians(direccion))
    return {"x": punto["x"] + dx, "y": punto["y"] + dy}

# Función principal
def ruta_optima_entre_nodos(nodo1, nodo2, direccion_salida, direccion_llegada,zonas_restringidas,raster_path):
    global elevation, transform
    if elevation is None or transform is None:
        init_dem(raster_path)

    # Avance inicial desde nodo1
    p1 = avanzar_desde_punto(nodo1, direccion_salida, 60)
    #p2 = avanzar_desde_punto(p1, direccion_salida, 60)
    nuevo_inicio = {"nombre": "set1", "x": p1["x"], "y": p1["y"]}

    # Retroceso desde nodo2
    p3 = avanzar_desde_punto(nodo2, direccion_llegada, 60)
    nuevo_final = {"nombre": "set2", "x": p3["x"], "y": p3["y"]}

    puntos, index_map = crear_cuadricula(nuevo_inicio, nuevo_final, paso, zonas_restringidas, buffer=1500)
    vecinos_map = construir_grafo(puntos, index_map, paso)
    idx_inicio = encontrar_nodo_mas_cercano(nuevo_inicio, puntos)
    idx_fin = encontrar_nodo_mas_cercano(nuevo_final, puntos)

    ruta_indices = astar(idx_inicio, idx_fin, vecinos_map, puntos)
    ruta_final = [{"x": puntos[idx][0], "y": puntos[idx][1]} for idx in ruta_indices]

    # Agregar tramos iniciales y finales
    ruta_final = [nodo1, p1] + ruta_final + [p3, nodo2]

    coords = [(p["x"], p["y"]) for p in ruta_final if "x" in p and "y" in p]


    return coords





