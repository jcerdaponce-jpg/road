
# ---------- utils_dem.py (coloca estas utilidades arriba de tu script o en un módulo aparte) ----------
import math
from osgeo import gdal
from shapely.geometry import Point as ShpPoint




def abrir_dem(raster_path):
    """
    Abre un DEM .tif y devuelve (elevation_array, geotransform).
    """
    dem = gdal.Open(raster_path)
    if dem is None:
        raise RuntimeError(f"No se pudo abrir DEM: {raster_path}")
    band = dem.GetRasterBand(1)
    elevation = band.ReadAsArray()
    transform = dem.GetGeoTransform()  # (x0, pxSizeX, 0, y0, 0, pxSizeY_neg)
    return elevation, transform

def elevacion_xy(x, y, elevation, transform):
    """
    Devuelve la elevación del DEM en coordenadas UTM (x,y).
    """
    px = int((x - transform[0]) / transform[1])
    py = int((y - transform[3]) / transform[5])
    if 0 <= px < elevation.shape[1] and 0 <= py < elevation.shape[0]:
        return float(elevation[py, px])
    return None

def esta_en_zona_restringida(x, y, zonas):
    """
    True si (x,y) cae dentro de cualquier polígono de 'zonas'.
    """
    if not zonas:
        return False
    p = ShpPoint(x, y)
    return any(z.contains(p) for z in zonas)

def factor_pendiente(slope_pct):
    """
    Penalización por pendiente (en %).
    """
    if slope_pct is None: return 0
    s = abs(slope_pct)
    if s <= 0:   return 1.00
    if s <= 5:   return 1.03
    if s <= 10:  return 1.05
    if s <= 15:  return 1.08
    if s <= 20:  return 1.10
    return 10.0

def crear_cuadricula_dem(n1, n2, paso, zonas, elevation, transform, buffer_m=1500):
    """
    Genera puntos de cuadrícula (x,y,elev) evitando 'zonas'.
    """
    min_x = min(n1["x"], n2["x"]) - buffer_m
    max_x = max(n1["x"], n2["x"]) + buffer_m
    min_y = min(n1["y"], n2["y"]) - buffer_m
    max_y = max(n1["y"], n2["y"]) + buffer_m
    puntos, idxmap = [], {}
    idx = 0
    y = min_y
    while y <= max_y:
        x = min_x
        while x <= max_x:
            if not esta_en_zona_restringida(x, y, zonas):
                elev = elevacion_xy(x, y, elevation, transform)
                puntos.append((x, y, elev))
                idxmap[(x, y)] = idx
                idx += 1
            x += paso
        y += paso
    return puntos, idxmap

def construir_grafo_dem(puntos, idxmap, paso):
    """
    Crea mapa de vecinos con coste por pendiente usando DEM.
    """
    vm = {}
    for i, (x, y, elev) in enumerate(puntos):
        vecinos = []
        for dx in (-paso, 0, paso):
            for dy in (-paso, 0, paso):
                if dx == 0 and dy == 0:
                    continue
                nx, ny = x + dx, y + dy
                if (nx, ny) in idxmap:
                    j = idxmap[(nx, ny)]
                    elev2 = puntos[j][2]
                    dist = math.hypot(dx, dy)
                    slope = ((elev2 - elev)/dist*100) if (elev is not None and elev2 is not None and dist > 0) else None
                    cost = dist * factor_pendiente(slope)
                    vecinos.append((j, cost))
        vm[i] = vecinos
    return vm

def calcular_angulo(p1, p2, p3):
    """
    Ángulo (grados) entre segmentos p1->p2 y p2->p3.
    """
    v1 = (p2[0]-p1[0], p2[1]-p1[1])
    v2 = (p3[0]-p2[0], p3[1]-p2[1])
    dot = v1[0]*v2[0] + v1[1]*v2[1]
    m1 = math.hypot(*v1); m2 = math.hypot(*v2)
    if m1 == 0 or m2 == 0: return 0
    c = max(min(dot/(m1*m2), 1), -1)
    return math.degrees(math.acos(c))

def astar_ang(i0, i1, vm, pts, ang_max=90):
    """
    A* con restricción de ángulo máximo en el segmento anterior.
    """
    import heapq
    def h(a,b): return math.hypot(pts[a][0]-pts[b][0], pts[a][1]-pts[b][1])
    openq = [(0,i0)]; came = {}; g = {i0:0.0}
    while openq:
        _, cur = heapq.heappop(openq)
        if cur == i1:
            ruta = []
            while cur in came:
                ruta.append(cur); cur = came[cur]
            ruta.append(i0); return ruta[::-1]
        for v, c in vm.get(cur, []):
            if cur in came and came[cur] in came:
                p1 = pts[came[came[cur]]][:2]
                p2 = pts[came[cur]][:2]
                p3 = pts[cur][:2]
                if calcular_angulo(p1,p2,p3) > ang_max:
                    continue
            tg = g[cur] + c
            if (v not in g) or (tg < g[v]):
                came[v] = cur; g[v] = tg
                heapq.heappush(openq, (tg + h(v,i1), v))
    return []