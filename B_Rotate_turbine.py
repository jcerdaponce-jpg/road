# -*- coding: utf-8 -*-
"""
Orientación automática de plataformas WTG minimizando coste (excavación+relleno),
respetando restricciones y alineando la entrada hacia el camino. Incluye
alineación por vecindad para WTGs interiores.

Requisitos:
- shapely, numpy, triangle, osgeo.gdal, plotly (para plots opcionales)
- módulos locales: D_astra_ruta_optima, D_CAD_LYT_PLATFORM

Autoría: adaptado a partir del archivo provisto por el usuario.
"""

import math
import logging
import os
import sys
import json
import time
from typing import List, Dict, Any, Tuple, Sequence, Union, Optional

import numpy as np
import matplotlib.pyplot as plt
import plotly.graph_objects as go

from shapely.affinity import rotate
from shapely.geometry import Point, LineString, Polygon, MultiPolygon, box, mapping
from shapely.ops import unary_union
from shapely.ops import triangulate as shp_triangulate  # (no se usa si usamos 'triangle')
from osgeo import gdal, ogr, osr
import triangle as tr
from scipy.spatial import Delaunay

# deps locales
from D_astra_ruta_optima import leer_poligonos_dxf
from D_CAD_LYT_PLATFORM import generar_autocad

# -------------------------------------------------
# Reloj simple
# -------------------------------------------------
start_time = time.time()


# =================================================
# Triangulación con Triangle (PSLG)
# =================================================
def triangulate_cdt(geom: Union[Polygon, MultiPolygon], flags: str = "pqa30a7"):
    """Triangulación constrained Delaunay via 'triangle' con PSLG saneado."""
    # Saneo por self-intersections / orientación extraña
    if not geom.is_valid:
        geom = geom.buffer(0)

    data = polygon_to_pslg(geom)

    # Degenerado → vacío
    if ("segments" not in data) or (len(data["segments"]) == 0) or (len(data["vertices"]) < 3):
        return [], np.empty((0, 2), dtype=float)

    # Ejecutar Triangle
    t = tr.triangulate(data, flags)

    # Geometría diminuta → sin triángulos
    if ("triangles" not in t) or (len(t["triangles"]) == 0):
        return [], t.get("vertices", np.empty((0, 2), dtype=float))

    triangles = []
    verts = t["vertices"]
    for tri_idx in t["triangles"]:
        pts = verts[tri_idx]
        triangles.append(Polygon(pts))
    return triangles, verts


def polygon_to_pslg(geom: Union[Polygon, MultiPolygon], snap_tol: float = 1e-8) -> Dict[str, np.ndarray]:
    """
    Convierte Polygon o MultiPolygon en PSLG válido para Triangle.
    - Elimina el punto de cierre duplicado del anillo de Shapely.
    - Suprime vértices consecutivos casi idénticos (tolerancia).
    - Cierra el ring creando el segmento final i -> (i+1)%n.
    - Devuelve 'holes' sólo si existen (no devuelve None).
    """
    vertices: List[List[float]] = []
    segments: List[List[int]] = []
    holes: List[List[float]] = []

    def _clean_coords(coords: Sequence[Tuple[float, float]], tol: float) -> List[List[float]]:
        """Elimina duplicados consecutivos por tolerancia."""
        cleaned: List[List[float]] = []
        for x, y in coords:
            if not cleaned:
                cleaned.append([x, y])
            else:
                px, py = cleaned[-1]
                if (abs(x - px) > tol) or (abs(y - py) > tol):
                    cleaned.append([x, y])
        # quitar cierre duplicado
        if len(cleaned) >= 2:
            x0, y0 = cleaned[0]
            xn, yn = cleaned[-1]
            if (abs(xn - x0) <= tol) and (abs(yn - y0) <= tol):
                cleaned.pop()
        return cleaned

    def add_ring(ring, vert_offset: int) -> int:
        # Quitar cierre repetido
        coords = list(ring.coords)[:-1]
        # Limpieza de duplicados consecutivos
        coords = _clean_coords(coords, snap_tol)
        n = len(coords)
        if n < 3:
            return 0  # Ring degenerado → ignorar
        # Agregar vértices
        for c in coords:
            vertices.append([c[0], c[1]])
        # Crear segmentos cerrando con módulo
        for i in range(n):
            a = vert_offset + i
            b = vert_offset + ((i + 1) % n)
            segments.append([a, b])
        return n

    polys = list(geom.geoms) if isinstance(geom, MultiPolygon) else [geom]
    v_offset = 0
    for poly in polys:
        # Exterior
        n_ext = add_ring(poly.exterior, v_offset)
        v_offset += n_ext
        # Interiores (agujeros)
        for interior in poly.interiors:
            # Punto representativo del agujero
            hx, hy = interior.representative_point().coords[0]
            holes.append([hx, hy])
            n_int = add_ring(interior, v_offset)
            v_offset += n_int

    data = {
        "vertices": np.array(vertices, dtype=float),
        "segments": np.array(segments, dtype=int),
    }
    if holes:
        data["holes"] = np.array(holes, dtype=float)
    return data


# =================================================
# Utilidades de archivos / plots
# =================================================
def _ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def save_orientation_plot(
    wtg_name: str,
    center_xy: Tuple[float, float],
    entry_pt: Tuple[float, float],
    exit_pt: Tuple[float, float],
    road_line: Optional[LineString],   # shapely LineString o None
    road_node: Optional[Point],        # shapely Point o None
    angle_deg: float,
    out_folder: str = "PLOT"
):
    """Guarda un HTML con centro, entry/out, camino y nodo elegido."""
    _ensure_dir(out_folder)

    fig = go.Figure()

    # Camino
    if road_line is not None:
        xs, ys = road_line.xy
        fig.add_trace(go.Scatter(
            x=list(xs), y=list(ys),
            mode='lines', name='Camino',
            line=dict(color='gray', width=2)
        ))

    # Nodo objetivo
    if road_node is not None:
        fig.add_trace(go.Scatter(
            x=[road_node.x], y=[road_node.y],
            mode='markers', name='Nodo camino',
            marker=dict(color='orange', size=10, symbol='x')
        ))

    # Centro WTG
    cx, cy = center_xy
    fig.add_trace(go.Scatter(
        x=[cx], y=[cy],
        mode='markers', name='WTG center',
        marker=dict(color='black', size=8)
    ))

    # Entry / Out
    fig.add_trace(go.Scatter(
        x=[cx, entry_pt[0]], y=[cy, entry_pt[1]],
        mode='lines+markers', name='Entry',
        line=dict(color='green', width=3),
        marker=dict(color='green', size=6)
    ))
    fig.add_trace(go.Scatter(
        x=[cx, exit_pt[0]], y=[cy, exit_pt[1]],
        mode='lines+markers', name='Out',
        line=dict(color='red', width=3, dash='dot'),
        marker=dict(color='red', size=6)
    ))

    fig.update_layout(
        title=f"Orientación plataforma – {wtg_name} – {angle_deg:.1f}°",
        xaxis_title="X (m)", yaxis_title="Y (m)",
        xaxis=dict(scaleanchor="y", scaleratio=1),
        template="plotly_white",
        legend=dict(orientation="h", y=1.08)
    )

    out_path = os.path.join(out_folder, f"orientacion_{wtg_name}_{int(round(angle_deg))}.html")
    fig.write_html(out_path, include_plotlyjs="cdn", full_html=True)
    print(f"[PLOT] Guardado: {out_path}")


def plot_triangulation(
    geom: Union[Polygon, MultiPolygon],
    points: np.ndarray,
    triangles: List[Polygon],
    titulo: str = "Triangulación"
):
    """Gráfica rápida de triangulación (debug)."""
    fig, ax = plt.subplots(figsize=(8, 8))
    # Geometría original
    if isinstance(geom, MultiPolygon):
        for g in geom.geoms:
            xg, yg = g.exterior.xy
            ax.plot(xg, yg, color='black', lw=2)
    else:
        xg, yg = geom.exterior.xy
        ax.plot(xg, yg, color='black', lw=2)
    # Triángulos
    for t in triangles:
        xt, yt = t.exterior.xy
        ax.fill(xt, yt, facecolor='lightblue', edgecolor='steelblue', alpha=0.5)
    # Puntos
    if len(points) > 0:
        ax.scatter(points[:, 0], points[:, 1], color='red', s=10)
    ax.set_aspect('equal')
    ax.set_title(titulo)
    ax.grid(True, ls='--', alpha=0.4)
    plt.show()


# =================================================
# Triangulación “envoltorio”
# =================================================
def triangulate_geometry(geom, step_interior: Optional[float] = None, step_borde: Optional[float] = None, flags: str = "pqa30a7"):
    """
    Compatibilidad hacia atrás con llamadas legacy que pasan step_interior/step_borde.
    Por ahora esos pasos no se usan; el control de densidad se hace con flags (ej. 'a', 'q').
    """
    tris, pts = triangulate_cdt(geom, flags=flags)
    return tris, pts


# =================================================
# Cotas y costes
# =================================================
def generar_cotas_referencia(
    z_min: float, z_max: float,
    paso_metros: Optional[float] = None,
    paso_porcentaje: Optional[float] = None
) -> List[float]:
    """
    Genera lista de cotas entre z_min y z_max.
    - paso_metros > 0 -> cotas cada 'paso_metros' m.
    - paso_porcentaje > 0 -> cotas según porcentaje (0–100).
    - Si ambos None -> [z_min, z_max].
    """
    if z_max <= z_min:
        return [z_min]

    if paso_metros is not None and paso_metros > 0:
        dz = z_max - z_min
        n = int(dz // paso_metros)
        niveles = [z_min + i * paso_metros for i in range(n + 1)]
        if niveles[-1] < z_max:
            niveles.append(z_max)
        return niveles

    if paso_porcentaje is not None and paso_porcentaje > 0:
        p = paso_porcentaje / 100.0
        k = int(1.0 // p) if p > 0 else 0
        niveles = [z_min + i * p * (z_max - z_min) for i in range(k + 1)]
        if niveles[-1] < z_max:
            niveles.append(z_max)
        return niveles

    return [z_min, z_max]


def volumen_excavacion_por_cota(cota_ref: float, muestras: List[dict]) -> float:
    """
    Excavación = max(0, z - cota_ref), promediada por triángulo * área.
    'muestras' es lista de dicts: grupo, triangulo, nodo, x, y, altura.
    """
    triangulos: Dict[Tuple[Any, Any], List[Tuple[float, float, float]]] = {}
    for s in muestras:
        clave = (s["grupo"], s["triangulo"])
        triangulos.setdefault(clave, [])
        triangulos[clave].append((s["x"], s["y"], s["altura"]))

    volumen = 0.0
    for verts in triangulos.values():
        if len(verts) < 3:
            continue
        (x1, y1, z1), (x2, y2, z2), (x3, y3, z3) = verts[:3]
        area = abs(0.5 * (x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2)))
        e1 = max(0.0, z1 - cota_ref)
        e2 = max(0.0, z2 - cota_ref)
        e3 = max(0.0, z3 - cota_ref)
        h_prom = (e1 + e2 + e3) / 3.0
        volumen += h_prom * area
    return volumen


def calcular_costos_con_angulo(excavacion, relleno, precio_exc, precio_rel) -> Dict[str, Any]:
    costo_excavacion = excavacion[1] * precio_exc
    costo_relleno = relleno[1] * precio_rel
    if costo_excavacion < costo_relleno:
        menor = "Excavación"
        angulo_menor = excavacion[0]
    elif costo_relleno < costo_excavacion:
        menor = "Relleno"
        angulo_menor = relleno[0]
    else:
        menor = "Iguales"
        angulo_menor = None
    return {
        "Costo Excavación": costo_excavacion,
        "Costo Relleno": costo_relleno,
        "Menor Costo": menor,
        "angulo_menor": angulo_menor
    }


# =================================================
# Geometría: entry/out y rotaciones
# =================================================
def dist_x_y(v: Tuple[float, float], angulo_rad: float) -> Tuple[float, float]:
    x, y = v
    x_rot = x * math.cos(angulo_rad) - y * math.sin(angulo_rad)
    y_rot = x * math.sin(angulo_rad) + y * math.cos(angulo_rad)
    return x_rot, y_rot


def angulo_(punto: Tuple[float, float], angulo_grados: float, entry_exit: dict, extra: Optional[Tuple[float, float]] = None):
    angulo_rad = math.radians(angulo_grados)
    entrada = dist_x_y(entry_exit["entry_point"], angulo_rad)
    salida = dist_x_y(entry_exit["exit_point"], angulo_rad)
    entry_point = (punto[0] + entrada[0], punto[1] + entrada[1])
    exit_point = (punto[0] + salida[0], punto[1] + salida[1])
    if extra:
        extra_rot = dist_x_y(extra, angulo_rad)
        extra_point = (punto[0] + extra_rot[0], punto[1] + extra_rot[1])
        return entry_point, exit_point, extra_point
    return entry_point, exit_point


def volumen_cota(
    maximo_: float,
    minimo_: float,
    fill_price: float,
    excavation_price: float,
    resultados: List[Dict[str, Any]],
    porcentajes: Sequence[float] = (0.0, 0.1, 0.2, 0.3, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0),
) -> Tuple[List[float], List[float], List[float], List[float]]:
    """Coste por cota: calcula vol_exc y vol_fill, y coste total por cota."""
    # Agrupar nodos en triángulos
    grupos: Dict[Any, Dict[Any, List[Tuple[float, float, float]]]] = {}
    for it in resultados:
        h = it.get("altura")
        if h is None:
            continue
        g_id = it["grupo"]
        t_id = it["triangulo"]
        x = float(it["x"])
        y = float(it["y"])
        z = float(h)
        grupos.setdefault(g_id, {}).setdefault(t_id, []).append((x, y, z))

    # Precalcular por triángulo
    tri_data: Dict[Any, Dict[Any, Dict[str, float]]] = {}
    for g_id, tris in grupos.items():
        for t_id, pts in tris.items():
            if len(pts) != 3:
                continue
            (x1, y1, h1), (x2, y2, h2), (x3, y3, h3) = pts
            area = abs(0.5 * (x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2)))
            if area == 0.0:
                continue
            h_avg = (h1 + h2 + h3) / 3.0
            tri_data.setdefault(g_id, {})[t_id] = {"area": area, "h_avg_orig": h_avg}

    vol_exc_list: List[float] = []
    vol_fill_list: List[float] = []
    total_cost_list: List[float] = []
    cota_list: List[float] = []

    for p in porcentajes:
        cota_ref = (maximo_ - minimo_) * float(p) + minimo_
        vol_exc = 0.0
        vol_fill = 0.0
        for g_id, tris in tri_data.items():
            for t_id, info in tris.items():
                area = info["area"]
                h_avg_adj = info["h_avg_orig"] - cota_ref
                vol = abs(h_avg_adj * area)
                if h_avg_adj < 0.0:
                    vol_fill += vol
                else:
                    vol_exc += vol
        cost = vol_exc * excavation_price + vol_fill * fill_price
        vol_exc_list.append(vol_exc)
        vol_fill_list.append(vol_fill)
        total_cost_list.append(cost)
        cota_list.append(cota_ref)

    return vol_exc_list, vol_fill_list, total_cost_list, cota_list


# Pasos de triangulación (no se usan directamente; flags controlan densidad)
step_interior = 1
step_borde = 1


def get_elevation(x: float, y: float, elevation_array: Optional[np.ndarray], transform: Optional[Tuple[float, ...]]) -> Optional[float]:
    """
    Convierte coordenadas (x, y) a índices del raster y devuelve la altura.
    Soporta píxeles con pixelHeight negativo (GeoTIFF típico).
    """
    if elevation_array is None or transform is None:
        return None

    originX, pixelWidth, rot1, originY, rot2, pixelHeight = transform
    col = int((x - originX) / pixelWidth)
    row = int((y - originY) / pixelHeight)

    if (0 <= row < elevation_array.shape[0]) and (0 <= col < elevation_array.shape[1]):
        return float(elevation_array[row, col])
    else:
        return None  # fuera del raster


def iter_triangles(triangulacion: List[List[Polygon]]):
    """
    Itera sobre todos los triángulos en 'triangulacion', que puede ser:
    - lista de Polygon
    - lista de listas de Polygon
    Devuelve un generador de (idx_grupo, idx_tri, tri_polygon)
    """
    for gi, grupo in enumerate(triangulacion):
        if isinstance(grupo, Polygon):
            yield gi, 0, grupo
        else:
            for ti, tri in enumerate(grupo):
                if isinstance(tri, Polygon):
                    yield gi, ti, tri


def tiangulation_plot(triangulacion: List[List[Polygon]], name: str, angulo: float, relleno=None, excavacion=None):
    fig = go.Figure()
    for grupo in triangulacion:
        for tri in grupo:
            if isinstance(tri, Polygon):
                x, y = tri.exterior.xy
                fig.add_trace(go.Scatter(
                    x=list(x),
                    y=list(y),
                    mode='lines',
                    fill='toself',
                    line=dict(color='steelblue'),
                    fillcolor='lightblue',
                    opacity=0.6
                ))
    fig.update_layout(
        title='Triangulación de todas las áreas',
        xaxis_title='Coordenada X',
        yaxis_title='Coordenada Y',
        xaxis=dict(scaleanchor="y", scaleratio=1),
        template='plotly_white'
    )
    outp = f'PLOT/triangulacion_WTG_{name}_{angulo}.html'
    fig.write_html(outp, include_plotlyjs="cdn", full_html=True)
    print(f"[PLOT] Guardado: {outp}")
    return


def triangle_vertices(tri: Polygon) -> List[Tuple[float, float]]:
    """Devuelve los 3 vértices del triángulo (sin el punto repetido de cierre)."""
    coords = list(tri.exterior.coords)
    return coords[:-1] if len(coords) >= 4 else coords


def crear_box(punto_base: Tuple[float, float], offset_1_x: float, offset_1_y: float, offset_2_x: float, offset_2_y: float) -> Polygon:
    ax = punto_base[0] + offset_1_x
    ay = punto_base[1] + offset_1_y
    bx = punto_base[0] + offset_2_x
    by = punto_base[1] + offset_2_y
    return box(ax, ay, bx, by)


def crear_circle_fundacion(punto_base: Tuple[float, float], diametro: float) -> Polygon:
    return Point(punto_base[0], punto_base[1]).buffer(diametro / 2.0)


def crear_circle(punto_base: Tuple[float, float], offset_1_x: float, offset_1_y: float, diameter: float) -> Polygon:
    ax = punto_base[0] + offset_1_x
    ay = punto_base[1] + offset_1_y
    return Point(ax, ay).buffer(diameter / 2.0)


def file_(path: str, uno: str, coordenadas_uno: List[float], folder_: str):
    """Crea wtg_points.json y wtg_center.json (una sola vez el punto 'uno')."""
    with open(path, "r", encoding="utf-8") as f:
        wtg_data = json.load(f)

    result: List[Dict[str, Any]] = []
    center: List[Dict[str, Any]] = []

    # Añadir 'uno' (referencia) SOLO una vez
    result.append({"nombre": uno, "x": coordenadas_uno[0], "y": coordenadas_uno[1]})
    center.append({"nombre": uno, "x": coordenadas_uno[0], "y": coordenadas_uno[1]})

    for wtg_name, values in wtg_data.items():
        # Generar tres entradas: entry, center, out
        result.append({"nombre": f"{wtg_name}_entry", "x": values["entry_x"], "y": values["entry_y"]})
        center.append({"nombre": f"{wtg_name}_center", "x": values["center_x"], "y": values["center_y"]})
        result.append({"nombre": f"{wtg_name}_out", "x": values["exit_x"], "y": values["exit_y"]})

    with open(f"{folder_}/wtg_points.json", "w", encoding="utf-8") as out:
        json.dump(result, out, indent=2)
    with open(f"{folder_}/wtg_center.json", "w", encoding="utf-8") as out:
        json.dump(center, out, indent=2)
    print(f"[FILES] wtg_points.json & wtg_center.json creados en {folder_}")


# =================================================
# Caminos (GeoJSON) y reproyección
# =================================================
def load_caminos(path_caminos: str) -> Tuple[List[LineString], Optional[int]]:
    """
    Carga polilíneas de caminos desde un GeoJSON (como el que compartiste).
    Devuelve (lineas, epsg_caminos).
    """
    with open(path_caminos, "r", encoding="utf-8") as f:
        data = json.load(f)

    lineas: List[LineString] = []
    epsg_caminos: Optional[int] = None

    meta_crs = (data.get("meta") or {}).get("crs")
    if meta_crs and isinstance(meta_crs, str) and meta_crs.upper().startswith("EPSG:"):
        try:
            epsg_caminos = int(meta_crs.split(":")[1])
        except Exception:
            epsg_caminos = None

    for feat in data.get("features", []):
        if (feat.get("geometry") or {}).get("type") == "LineString":
            coords = feat["geometry"]["coordinates"]  # UTM [x, y]
            lineas.append(LineString(coords))
            if epsg_caminos is None:
                # fallback desde propiedades
                epsg_caminos = feat.get("properties", {}).get("utm_epsg", None)

    return lineas, (int(epsg_caminos) if epsg_caminos is not None else None)


def reproject_lines_utm(lineas: List[LineString], epsg_src: Optional[int], epsg_dst: Optional[int]) -> List[LineString]:
    """Reproyecta las polilíneas si epsg_src != epsg_dst (opcional)."""
    if not epsg_src or not epsg_dst or epsg_src == epsg_dst:
        return lineas

    s_src = osr.SpatialReference(); s_src.ImportFromEPSG(epsg_src)
    s_dst = osr.SpatialReference(); s_dst.ImportFromEPSG(epsg_dst)
    ct = osr.CoordinateTransformation(s_src, s_dst)

    def _tx_line(line: LineString) -> LineString:
        xs, ys = line.xy
        coords_tx = [ct.TransformPoint(x, y)[:2] for x, y in zip(xs, ys)]
        return LineString(coords_tx)

    return [_tx_line(ln) for ln in lineas]


def nearest_polyline(center_pt: Point, lineas: List[LineString]) -> Tuple[Optional[LineString], float]:
    """Devuelve la polilínea más cercana al centro del WTG por distancia geométrica."""
    mejor_linea = None
    mejor_dist = float("inf")
    for ln in lineas:
        d = ln.distance(center_pt)
        if d < mejor_dist:
            mejor_dist = d
            mejor_linea = ln
    return mejor_linea, mejor_dist


def nearest_vertex_on_line(ref_pt: Point, linea: LineString) -> Tuple[Point, float]:
    """(Legacy) Vértice más cercano en la polilínea. Mantenido por compatibilidad."""
    best = None
    best_d = float("inf")
    for (xv, yv) in linea.coords:
        p = Point(xv, yv)
        d = ref_pt.distance(p)
        if d < best_d:
            best_d = d
            best = p
    return best, best_d


def nearest_point_on_line(ref_pt: Point, linea: LineString) -> Tuple[Point, float]:
    """Punto perpendicular real (proyección ortogonal) del WTG sobre la polilínea."""
    d = linea.project(ref_pt)
    p = linea.interpolate(d)
    return p, ref_pt.distance(p)


def angle_to_align_entry(entry_vec_xy: Tuple[float, float],
                         center_xy: Tuple[float, float],
                         target_xy: Tuple[float, float]) -> float:
    """Ángulo (grados) para alinear el vector 'entry' (offset relativo) hacia 'target' desde 'center'."""
    ex, ey = entry_vec_xy
    cx, cy = center_xy
    tx, ty = target_xy
    desired = math.degrees(math.atan2(ty - cy, tx - cx))
    base = math.degrees(math.atan2(ey, ex))
    theta = (desired - base) % 360.0
    return theta


def build_geoms(punto_xy: Tuple[float, float], angulo_deg: float,
                pads: dict, preassembly: dict, fundacion_diametro: float) -> List[Polygon]:
    """Construye geometrías rotadas (fundación, pads, preassembly) para checks."""
    geoms: List[Polygon] = []
    fundacion_area = crear_circle_fundacion(punto_xy, fundacion_diametro)
    geoms.append(fundacion_area)
    for _, (ax, ay, bx, by) in pads.items():
        g = crear_box(punto_xy, ax, ay, bx, by)
        geoms.append(rotate(g, angulo_deg, origin=(punto_xy[0], punto_xy[1])))
    for _, (ax, ay, diameter) in preassembly.items():
        if diameter > 0:
            cir = crear_circle(punto_xy, ax, ay, diameter)
            geoms.append(rotate(cir, angulo_deg, origin=(punto_xy[0], punto_xy[1])))
    return geoms


def postprocessing(punto: Tuple[float, float], angulo: float,
                   fundacion_diametro: float, pads: dict, preassembly: dict) -> List[Polygon]:
    polygon: List[Polygon] = []
    fundacion_coordenadas = crear_circle_fundacion(punto, fundacion_diametro)
    polygon.append(fundacion_coordenadas)
    for _, (ax, ay, bx, by) in pads.items():
        g = crear_box(punto, ax, ay, bx, by)
        g_rot = rotate(g, angulo, origin=(punto[0], punto[1]))
        polygon.append(g_rot)
    for _, (ax, ay, diameter) in preassembly.items():
        if diameter > 0:
            cir = crear_circle(punto, ax, ay, diameter)
            cir_rot = rotate(cir, angulo, origin=(punto[0], punto[1]))
            polygon.append(cir_rot)
    return polygon


# =================================================
# Evaluación de ángulos y búsqueda
# =================================================
def eval_angle_with_entry_priority(angulo_deg: float,
                                   punto_xy: Tuple[float, float],
                                   entry_exit: dict,
                                   pads: dict,
                                   preassembly: dict,
                                   fundacion_diametro: float,
                                   zonas_restringidas: List[Polygon],
                                   target_node_xy: Tuple[float, float]) -> Tuple[bool, float, float, Tuple]:
    """
    Evalúa un ángulo:
    - True si NO intersecta restricciones y dist(entry) < dist(out) al 'target_node'.
    - Devuelve también dist_entry, dist_out y (entry_pt, exit_pt).
    """
    # 1) Intersecciones
    geoms = build_geoms(punto_xy, angulo_deg, pads, preassembly, fundacion_diametro)
    if any(any(g.intersects(z) for z in zonas_restringidas) for g in geoms):
        return False, float("inf"), float("inf"), (None, None)

    # 2) Puntos entry/out rotados
    entry_pt, exit_pt = angulo_(punto_xy, angulo_deg, entry_exit)[:2]
    ex, ey = entry_pt
    ox, oy = exit_pt
    tx, ty = target_node_xy

    # 3) Distancias al nodo de camino
    dist_entry = math.hypot(tx - ex, ty - ey)
    dist_out = math.hypot(tx - ox, ty - oy)

    # 4) Prioridad: entry debe ser más cercano
    ok = dist_entry < dist_out
    return ok, dist_entry, dist_out, (entry_pt, exit_pt)


def search_best_angle(theta_pref: float,
                      punto_xy: Tuple[float, float],
                      entry_exit: dict,
                      pads: dict,
                      preassembly: dict,
                      fundacion_diametro: float,
                      zonas_restringidas: List[Polygon],
                      target_node_xy: Tuple[float, float],
                      deltas: Tuple[int, ...] = (0, 5, 10, 15, 20, 25, 30, -5, -10, -15, -20, -25, -30)) -> Tuple[float, dict]:
    """Búsqueda simple (sin costeo DEM)."""
    best = {
        "angle": None,
        "dist_entry": float("inf"),
        "dist_out": float("inf"),
        "delta": float("inf"),
        "entry_pt": None,
        "exit_pt": None
    }
    for d in deltas:
        ang = (theta_pref + d) % 360.0
        ok, de, do, (ep, xp) = eval_angle_with_entry_priority(
            ang, punto_xy, entry_exit, pads, preassembly, fundacion_diametro,
            zonas_restringidas, target_node_xy
        )
        if not ok:
            continue
        if (de < best["dist_entry"]) or (math.isclose(de, best["dist_entry"], rel_tol=1e-9, abs_tol=1e-6) and abs(d) < best["delta"]):
            best.update({
                "angle": ang,
                "dist_entry": de,
                "dist_out": do,
                "delta": abs(d),
                "entry_pt": ep,
                "exit_pt": xp
            })
    if best["angle"] is None:
        return theta_pref, {"ok": False}
    else:
        return best["angle"], {
            "ok": True,
            "dist_entry": best["dist_entry"],
            "dist_out": best["dist_out"],
            "delta": best["delta"],
            "entry_pt": best["entry_pt"],
            "exit_pt": best["exit_pt"]
        }


# ======= utilidades de orientación por vecindad =======
def circ_mean(angulos_deg: List[float], pesos: Optional[List[float]] = None) -> Optional[float]:
    """Media circular (grados 0..360)."""
    if not angulos_deg:
        return None
    pesos = pesos or [1.0] * len(angulos_deg)
    X = sum(w * math.cos(math.radians(a)) for a, w in zip(angulos_deg, pesos))
    Y = sum(w * math.sin(math.radians(a)) for a, w in zip(angulos_deg, pesos))
    if X == 0 and Y == 0:
        return None
    return (math.degrees(math.atan2(Y, X)) + 360.0) % 360.0


def wrap_diff_deg(a: float, b: float) -> float:
    """Diferencia angular mínima |a-b| en grados (0..180)."""
    d = (a - b + 180.0) % 360.0 - 180.0
    return abs(d)


def blend_angles(theta_road: float, theta_neighbors: Optional[float], alpha: float = 0.6) -> float:
    """Preferente mixto: alpha*camino + (1-alpha)*vecinos (promedio vectorial)."""
    if theta_neighbors is None:
        return theta_road
    xr, yr = math.cos(math.radians(theta_road)), math.sin(math.radians(theta_road))
    xn, yn = math.cos(math.radians(theta_neighbors)), math.sin(math.radians(theta_neighbors))
    x = alpha * xr + (1.0 - alpha) * xn
    y = alpha * yr + (1.0 - alpha) * yn
    if x == 0 and y == 0:
        return theta_road
    return (math.degrees(math.atan2(y, x)) + 360.0) % 360.0


def search_best_angle_cost(theta_pref: float,
                           punto_xy: Tuple[float, float],
                           entry_exit: dict,
                           pads: dict,
                           preassembly: dict,
                           fundacion_diametro: float,
                           zonas_restringidas: List[Polygon],
                           target_node_xy: Tuple[float, float],
                           ELEVATION: Optional[np.ndarray], TRANSFORM: Optional[Tuple[float, ...]],
                           excavation_price: float, fill_price: float,
                           clave_debug: Optional[str] = None,
                           deltas: Tuple[int, ...] = (0, 5, 10, 15, 20, 25, 30, -5, -10, -15, -20, -25, -30),
                           vecinos_elegidos: Optional[List[Tuple[float, float]]] = None,
                           lam_smooth: float = 0.0
                           ) -> Tuple[float, Dict[str, Any]]:
    """
    Explora ángulos cercanos al preferente. Filtra por:
    - no intersectar restricciones
    - dist(entry) < dist(out)
    Entre los factibles, elige el de menor coste_total = coste_tierras + lam_smooth * penal_vecinos.
    En empate: menor |delta|, luego menor dist_entry.
    """
    candidatos: List[Dict[str, Any]] = []
    for d in deltas:
        ang = (theta_pref + d) % 360.0
        ok, de, do, _ = eval_angle_with_entry_priority(
            ang, punto_xy, entry_exit, pads, preassembly, fundacion_diametro,
            zonas_restringidas, target_node_xy
        )
        if not ok:
            continue

        # Calcular coste por DEM (volúmenes) y elegir mejor cota para este candidato
        info_coste = compute_cost_for_angle(
            ang, punto_xy, pads, preassembly, fundacion_diametro,
            ELEVATION, TRANSFORM,
            excavation_price, fill_price,
            clave_debug=clave_debug
        )

        # Penalización de suavidad respecto a vecinos (si se pasa)
        penal = 0.0
        if vecinos_elegidos:
            # vecinos_elegidos: [(ang_vecino_deg, peso), ...]
            penal = sum(w * (wrap_diff_deg(ang, a_n) ** 2) for a_n, w in vecinos_elegidos)

        coste_tierras = float(info_coste.get("mejor coste", float("inf")))
        coste_total = coste_tierras + float(lam_smooth) * penal

        candidatos.append({
            "ang": ang,
            "delta": abs(d),
            "dist_entry": de,
            "dist_out": do,
            "coste": info_coste,
            "coste_total": coste_total
        })

    if not candidatos:
        # No hay factibles: devolvemos preferente y marcamos flag
        return theta_pref, {"ok": False}

    # ---- ORDENACIÓN por menor coste_total (tierras + suavidad), luego desempates ----
    candidatos.sort(key=lambda c: (c["coste_total"], c["delta"], c["dist_entry"]))

    mejor = candidatos[0]
    cinfo = mejor["coste"]

    # Reconstruir desglose de costes (compatibilidad con tu flujo)
    vol_exc = float(cinfo.get("volumen excavacion", 0.0))
    vol_fill = float(cinfo.get("volumen relleno", 0.0))
    cost_exc = vol_exc * float(excavation_price)
    cost_fill = vol_fill * float(fill_price)
    total = float(cinfo.get("mejor coste", cost_exc + cost_fill))
    resumen_dict = {
        "Costo Excavación": cost_exc,
        "Costo Relleno": cost_fill,
        "Menor Costo": "Total",
        "angulo_menor": float(mejor["ang"]),
        "cota": cinfo.get("cota"),
        "volumen excavacion": vol_exc,
        "volumen relleno": vol_fill,
        "mejor coste": total
    }

    return mejor["ang"], {
        "ok": True,
        "dist_entry": mejor["dist_entry"],
        "dist_out": mejor["dist_out"],
        "delta": mejor["delta"],
        "cost_resume": resumen_dict,
        "coste_total": mejor["coste_total"]
    }


def compute_cost_for_angle(angulo_deg: float,
                           punto_xy: Tuple[float, float],
                           pads: dict, preassembly: dict, fundacion_diametro: float,
                           ELEVATION: Optional[np.ndarray], TRANSFORM: Optional[Tuple[float, ...]],
                           excavation_price: float, fill_price: float,
                           clave_debug: Optional[str] = None,
                           level_step_abs: Optional[float] = None,
                           level_step_percent: Optional[float] = None) -> Dict[str, Any]:
    """Calcula volúmenes y coste del ángulo dado (elige la cota de menor coste)."""

    # Construir geometrías rotadas
    geoms_rot: List[Polygon] = []
    fundacion_area = crear_circle_fundacion(punto_xy, fundacion_diametro)
    geoms_rot.append(fundacion_area)
    for _, (ax, ay, bx, by) in pads.items():
        g = crear_box(punto_xy, ax, ay, bx, by)
        geoms_rot.append(rotate(g, angulo_deg, origin=(punto_xy[0], punto_xy[1])))
    for _, (ax, ay, diameter) in preassembly.items():
        if diameter > 0:
            cir = crear_circle(punto_xy, ax, ay, diameter)
            geoms_rot.append(rotate(cir, angulo_deg, origin=(punto_xy[0], punto_xy[1])))

    # Triangulación y alturas
    triangulacion = [triangulate_geometry(g, step_interior, step_borde)[0] for g in geoms_rot]
    resultados: List[Dict[str, Any]] = []
    alturas_1: List[float] = []

    for gi, ti, tri in iter_triangles(triangulacion):
        verts = triangle_vertices(tri)
        for ni, (x, y) in enumerate(verts):
            h = get_elevation(x, y, ELEVATION, TRANSFORM)
            if h is None:
                # si no hay DEM o fuera de raster, asumimos 0 (o podrías saltarte este punto)
                h = 0.0
            resultados.append({"grupo": gi, "triangulo": ti, "nodo": ni, "x": x, "y": y, "altura": h})
            alturas_1.append(h)

    minimo_ = min(alturas_1) if alturas_1 else 0.0
    maximo_ = max(alturas_1) if alturas_1 else 0.0

    vol_exc_list, vol_fill_list, total_cost_list, cota_list = volumen_cota(
        maximo_, minimo_, fill_price, excavation_price, resultados,
        porcentajes=(0.0, 0.1, 0.2, 0.3, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0)
    )

    minimo_costo = min(total_cost_list) if total_cost_list else 0.0
    idx_min = total_cost_list.index(minimo_costo) if total_cost_list else 0

    return {
        "angulo": angulo_deg,
        "volumen excavacion": vol_exc_list[idx_min] if vol_exc_list else 0.0,
        "volumen relleno": vol_fill_list[idx_min] if vol_fill_list else 0.0,
        "mejor coste": total_cost_list[idx_min] if total_cost_list else 0.0,
        "cota": cota_list[idx_min] if cota_list else 0.0
    }


# =================================================
# Pipeline principal
# =================================================
def rotate_platform_wtg(
    nodos: Dict[str, Dict[str, float]],
    entry_exit: dict,
    pads: dict,
    preassembly: dict,
    fundacion_diametro: float,
    folder_: str,
    DXF_FOLDER: str,
    excavation_price: float,
    fill_price: float,
    zonas_restringidas: Optional[List[Polygon]],
    raster_path: Optional[str],
    path_caminos: str,
    wtg_epsg: Optional[int] = None,
    save_plots: bool = False,
    plot_candidates: bool = False,
    # nuevos parámetros de alineación por vecindad (opcionales)
    alpha_blend: float = 0.6,     # 60% camino / 40% vecinos
    lam_smooth: float = 0.0,      # penalización suavidad (0 = sin suavidad)
    neigh_radius: float = 500.0,  # radio de vecinos (m)
    neigh_k: int = 3              # máximo vecinos a usar
) -> Dict[str, Any]:
    """
    Orienta la plataforma de cada WTG:
    - Solo considera ángulos con dist(entry) < dist(out) respecto al nodo de camino más cercano (perpendicular).
    - Entre esos, elige el de menor coste (excavación+relleno) + penalización de suavidad (opcional).
    - Devuelve 'lista_material' como antes.
    """

    zonas_restringidas = zonas_restringidas or []

    # DEM (si se pasa)
    ELEVATION: Optional[np.ndarray] = None
    TRANSFORM: Optional[Tuple[float, ...]] = None
    if raster_path:
        ds = gdal.Open(raster_path)
        if ds is None:
            logging.warning(f"[DEM] No se pudo abrir: {raster_path}")
        else:
            band = ds.GetRasterBand(1)
            if band is None:
                logging.warning("[DEM] Raster sin banda 1")
            else:
                ELEVATION = band.ReadAsArray()
                TRANSFORM = ds.GetGeoTransform()

    # Caminos
    lineas, epsg_caminos = load_caminos(path_caminos)
    if wtg_epsg and epsg_caminos and wtg_epsg != epsg_caminos:
        lineas = reproject_lines_utm(lineas, epsg_src=epsg_caminos, epsg_dst=wtg_epsg)

    # Contenedores de salida
    geojson_resultados: Dict[str, Any] = {}
    json_data_: Dict[str, Any] = {}
    lista_material: Dict[str, Any] = {}

    # Ángulos ya resueltos (para vecindad)
    angles_solved: Dict[str, float] = {}

    # Detectar nodo 'uno' (tu referencia/SET) y retirarlo
    uno = None
    coordenadas_uno = None
    for clave, datos in list(nodos.items()):
        if not clave.startswith("wtg"):
            uno = clave
            coordenadas_uno = [datos["x"], datos["y"]]
            del nodos[uno]
            break

    # Distancia de cada WTG al camino (para ordenar fachada→interior)
    wtg_dist: Dict[str, float] = {}
    for clave, datos in nodos.items():
        if clave.startswith("wtg"):
            center_pt = Point(datos["x"], datos["y"])
            best_line, dmin = nearest_polyline(center_pt, lineas)
            wtg_dist[clave] = float(dmin) if dmin is not None else float("inf")

    orden_wtgs = sorted(
        [k for k in nodos.keys() if k.startswith("wtg")],
        key=lambda k: wtg_dist.get(k, float("inf"))
    )

    # Bucle por WTG
    for clave in orden_wtgs:
        datos = nodos[clave]
        punto = [datos["x"], datos["y"]]
        center_pt = Point(punto[0], punto[1])
        best_line, _ = nearest_polyline(center_pt, lineas)

        if best_line is None:
            # Fallback sin caminos: ángulo 0 y costeo 0
            mejor_angulo = 0.0
            info_busqueda = {"ok": False, "dist_entry": None, "dist_out": None, "delta": None, "cost_resume": None}
            entry_pt, exit_pt = angulo_(punto, mejor_angulo, entry_exit)[:2]
            resumen_costos = {
                "Costo Excavación": 0.0, "Costo Relleno": 0.0,
                "Menor Costo": "Iguales", "angulo_menor": mejor_angulo
            }

        else:
            # Nodo objetivo correcto = proyección ortogonal del WTG al camino
            target_node, _ = nearest_point_on_line(center_pt, best_line)

            # Preferente por camino
            x, y = punto[0], punto[1]
            theta_road = angle_to_align_entry(entry_exit["entry_point"], (x, y), (target_node.x, target_node.y))

            # Preferente por vecindad (si hay vecinos resueltos)
            vecinos_ids: List[str] = []
            pesos_vecinos: List[float] = []
            if angles_solved:
                for vid, angv in angles_solved.items():
                    px, py = nodos[vid]["x"], nodos[vid]["y"]
                    d = math.hypot(px - x, py - y)
                    if d <= float(neigh_radius):
                        vecinos_ids.append(vid)
                        pesos_vecinos.append(1.0 / (d + 1e-6))

                # limitar a k más cercanos por peso
                if len(vecinos_ids) > neigh_k:
                    orden_local = sorted(range(len(vecinos_ids)), key=lambda i: -pesos_vecinos[i])[:neigh_k]
                    vecinos_ids = [vecinos_ids[i] for i in orden_local]
                    pesos_vecinos = [pesos_vecinos[i] for i in orden_local]

            theta_neigh = circ_mean([angles_solved[j] for j in vecinos_ids], pesos=pesos_vecinos) if vecinos_ids else None
            theta_pref_mix = blend_angles(theta_road, theta_neigh, alpha=alpha_blend)

            # Lista (ángulo_vecino, peso) para penalización de suavidad
            vecinos_elegidos = [(angles_solved[j], w) for j, w in zip(vecinos_ids, pesos_vecinos)] if vecinos_ids else []

            # Buscar mejor ángulo por coste + suavidad entre los que cumplen dist(entry) < dist(out)
            mejor_angulo, info_busqueda = search_best_angle_cost(
                theta_pref_mix, (x, y), entry_exit,
                pads, preassembly, fundacion_diametro,
                zonas_restringidas,
                (target_node.x, target_node.y),
                ELEVATION, TRANSFORM,
                excavation_price, fill_price,
                clave_debug=clave,
                deltas=(0, 5, 10, 15, 20, 25, 30, -5, -10, -15, -20, -25, -30),
                vecinos_elegidos=vecinos_elegidos,
                lam_smooth=float(lam_smooth)
            )

            # Entry/Exit finales
            entry_pt, exit_pt = angulo_(punto, mejor_angulo, entry_exit)[:2]

            # Resumen de costes (si fue factible, incluir cost_resume)
            if info_busqueda.get("ok", False):
                resumen_costos = info_busqueda.get("cost_resume")
            else:
                # Si no hubo factibles (no debería ser lo normal), calcula coste informativo del preferente
                info_pref = compute_cost_for_angle(
                    mejor_angulo, (punto[0], punto[1]), pads, preassembly, fundacion_diametro,
                    ELEVATION, TRANSFORM, excavation_price, fill_price, clave_debug=clave
                )
                vol_exc = float(info_pref.get("volumen excavacion", 0.0))
                vol_fill = float(info_pref.get("volumen relleno", 0.0))
                cost_exc = vol_exc * float(excavation_price)
                cost_fill = vol_fill * float(fill_price)
                total = float(info_pref.get("mejor coste", cost_exc + cost_fill))
                resumen_costos = {
                    "Costo Excavación": cost_exc,
                    "Costo Relleno": cost_fill,
                    "Menor Costo": "Total",
                    "angulo_menor": float(mejor_angulo),
                    "cota": info_pref.get("cota"),
                    "volumen excavacion": vol_exc,
                    "volumen relleno": vol_fill,
                    "mejor coste": total
                }

        # Guardar ángulo resuelto para vecindad
        angles_solved[clave] = float(mejor_angulo)

        # ---- PLOTS opcionales ----
        if save_plots:
            # A) Plot de orientación (entry/out + camino + nodo)
            try:
                save_orientation_plot(
                    wtg_name=clave,
                    center_xy=(punto[0], punto[1]),
                    entry_pt=entry_pt,
                    exit_pt=exit_pt,
                    road_line=best_line if best_line is not None else None,
                    road_node=target_node if best_line is not None else None,
                    angle_deg=mejor_angulo,
                    out_folder="PLOT"
                )
            except Exception as e:
                print(f"[WARN] No se pudo guardar orientation plot: {e}")

            # B) Plot de triangulación del ángulo elegido (opcional)
            try:
                geoms_rot = []
                fund_area = crear_circle_fundacion(punto, fundacion_diametro)
                geoms_rot.append(fund_area)
                for _, (ax, ay, bx, by) in pads.items():
                    g = crear_box(punto, ax, ay, bx, by)
                    geoms_rot.append(rotate(g, mejor_angulo, origin=(punto[0], punto[1])))
                for _, (ax, ay, diameter) in preassembly.items():
                    if diameter > 0:
                        cir = crear_circle(punto, ax, ay, diameter)
                        geoms_rot.append(rotate(cir, mejor_angulo, origin=(punto[0], punto[1])))
                triangulacion = [triangulate_geometry(g, step_interior, step_borde)[0] for g in geoms_rot]
                tiangulation_plot(triangulacion, clave, mejor_angulo)
            except Exception as e:
                print(f"[WARN] No se pudo generar triangulación para plot: {e}")

        # Postprocesar geometrías rotadas para CAD/JSON
        post = postprocessing(punto, mejor_angulo, fundacion_diametro, pads, preassembly)
        poligono = [list(i.exterior.coords) for i in post]
        json_data_[clave] = {'geometry': poligono}

        # Guardar resultados por WTG
        geojson_resultados[clave] = {
            "center_x": punto[0], "center_y": punto[1],
            "angle": float(mejor_angulo),
            "entry_x": entry_pt[0], "entry_y": entry_pt[1],
            "exit_x": exit_pt[0], "exit_y": exit_pt[1],
            "entry_vs_out": {
                "constraint_ok": bool(info_busqueda.get("ok", False)),
                "dist_entry": info_busqueda.get("dist_entry", None),
                "dist_out": info_busqueda.get("dist_out", None),
                "delta_deg": info_busqueda.get("delta", None),
            }
        }

        # ✅ lista_material (como antes)
        lista_material[clave] = {
            "minimo": resumen_costos,  # dict con costos y 'angulo_menor'
            "fill_price": float(fill_price),
            "excavation_price": float(excavation_price),
            "mejor angulo": resumen_costos.get("angulo_menor", float(mejor_angulo))
        }

        # Logging simple
        print(clave)
        print(lista_material[clave])

    # Exportar JSON/DXF
    _ensure_dir(folder_)
    path_ = f"{folder_}/WTG_PLATFORM.json"
    with open(path_, "w") as f:
        json.dump(geojson_resultados, f, indent=2)

    file_name_ = f"{folder_}/platfform_poly.json"
    with open(file_name_, "w") as f:
        json.dump(json_data_, f, indent=2)

    if uno is not None and coordenadas_uno is not None:
        file_(path_, uno, coordenadas_uno, folder_)

    _ensure_dir(DXF_FOLDER)
    generar_autocad(file_name_, DXF_FOLDER)

    # 🔙 Retorno limpio
    return lista_material