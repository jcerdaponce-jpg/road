
from shapely.geometry import Polygon, LineString
import math
import ezdxf, json, os
from typing import List, Dict, Any, Union, Optional, Tuple
from shapely.geometry import LineString, Point
from shapely import wkt as shapely_wkt
# ============= LECTURAS =============

def safe_leer_poligonos_dxf(ruta_dxf: str, buffer_m: float) -> List[Polygon]:
    """
    Devuelve lista de Polygon (buffer aplicado). Si no existe el archivo o falla la lectura, devuelve [].
    """
    try:
        if not ruta_dxf or not os.path.exists(ruta_dxf):
            return []
        doc = ezdxf.readfile(ruta_dxf)
        msp = doc.modelspace()
        polys: List[Polygon] = []
        for e in msp:
            if e.dxftype() == "LWPOLYLINE" and getattr(e, "closed", False):
                pts = [(p[0], p[1]) for p in e.get_points()]
                if len(pts) >= 3:
                    # buffer_m puede ser 0 (devuelve el mismo polígono), ok.
                    polys.append(Polygon(pts).buffer(buffer_m))
        return polys
    except Exception:
        return []


def safe_leer_poligonos_json(path_json: str, buffer_m: float = 20) -> List[Polygon]:
    """
    Lee FeatureCollection y devuelve lista de Polygon.
    - Si el feature es Polygon/MultiPolygon → buffer(0)
    - Si es LineString → buffer(buffer_m) (sirve para restricciones lineales)
    Si no existe o hay error, devuelve [].
    """
    try:
        if not path_json or not os.path.exists(path_json):
            return []
        with open(path_json, "r", encoding="utf-8") as f:
            data = json.load(f)

        zonas: List[Polygon] = []
        for feat in data.get("features", []) or []:
            geom = feat.get("geometry") or {}
            gtype = geom.get("type")
            coords = geom.get("coordinates")

            if not gtype or coords is None:
                continue

            if gtype == "Polygon":
                zonas.append(Polygon(coords[0]).buffer(0))
            elif gtype == "MultiPolygon":
                for ringset in coords:
                    zonas.append(Polygon(ringset[0]).buffer(0))
            elif gtype == "LineString":
                # Para restricciones como líneas, las engordamos con buffer_m
                zonas.append(LineString(coords).buffer(buffer_m))
        return zonas
    except Exception:
        return []


def safe_leer_geojson_caminos_wkt(path_json: str) -> List[str]:
    """
    Devuelve lista de WKT "<LINESTRING (...)>" a partir de un FeatureCollection con LineString.
    Si falta el archivo o hay error, devuelve [].
    """
    try:
        if not path_json or not os.path.exists(path_json):
            return []
        with open(path_json, "r", encoding="utf-8") as f:
            data = json.load(f)

        out: List[str] = []
        for feat in data.get("features", []) or []:
            geom = feat.get("geometry") or {}
            if geom.get("type") == "LineString":
                coords = geom.get("coordinates") or []
                if not coords:
                    continue
                pairs = ", ".join(f"{x} {y}" for x, y in coords)
                out.append(f"<LINESTRING ({pairs})>")
        return out
    except Exception:
        return []


# ============= CONVERSIÓN DE GEOMETRÍAS =============

def _sanitize_wkt_ls(txt: str) -> Optional[LineString]:
    """
    Convierte un texto tipo "<LINESTRING (...)>" o "LINESTRING (...)" a LineString.
    Si falla, devuelve None.
    """
    try:
        if not txt:
            return None
        s = txt.strip()
        if s.startswith("<") and s.endswith(">"):
            s = s[1:-1]
        geom = shapely_wkt.loads(s)
        return geom if isinstance(geom, LineString) else None
    except Exception:
        return None

from shapely.geometry import Point
from typing import Dict, Any

def leer_lineas_dxf(ruta_dxf):
    lineas = []
    if not ruta_dxf or not os.path.exists(ruta_dxf):
        return lineas

    try:
        doc = ezdxf.readfile(ruta_dxf)
        msp = doc.modelspace()
        for e in msp:
            if e.dxftype() == "LWPOLYLINE":
                pts = [(p[0], p[1]) for p in e.get_points()]
                if len(pts) >= 2:
                    lineas.append(LineString(pts))

            elif e.dxftype() == "POLYLINE":
                pts = [(v.dxf.location.x, v.dxf.location.y) for v in e.vertices()]
                if len(pts) >= 2:
                    lineas.append(LineString(pts))
    except:
        pass

    return lineas

from typing import List, Dict, Any, Optional
from shapely.geometry import LineString, Point

def nodo_cercano_solo_optimos(
    punto_xy,
    lineas_optimas: List[LineString],
) -> Dict[str, Any]:
    """
    Busca el punto más cercano a `punto_xy` sobre las LineString de caminos óptimos.
    - No considera restricciones ni caminos existentes.
    - Si no hay líneas válidas, devuelve un fallback con el punto de entrada.

    Parámetros
    ----------
    punto_xy : tuple[float, float]
        Coordenadas (x, y) en el mismo CRS que las líneas (UTM, metros).
    lineas_optimas : List[LineString]
        Lista de LineString representando los caminos óptimos.

    Retorna
    -------
    dict con:
      - encontrado : bool
      - nodo_xy    : (x, y) del punto más cercano sobre la línea
      - distancia_m: distancia desde `punto_xy` a `nodo_xy`
      - linea_wkt  : WKT de la línea sobre la que cayó el nodo
      - razon/fallback si no hay líneas
    """
    try:
        p = Point(float(punto_xy[0]), float(punto_xy[1]))
    except Exception:
        return {
            "encontrado": False,
            "razon": "punto_xy inválido",
            "fallback": {"punto_entrada_xy": punto_xy},
        }

    # Filtrar solo LineString válidas
    lineas_validas = [ln for ln in (lineas_optimas or []) if isinstance(ln, LineString) and not ln.is_empty]
    if not lineas_validas:
        return {
            "encontrado": False,
            "razon": "No hay líneas óptimas disponibles.",
            "fallback": {"punto_entrada_xy": (p.x, p.y)},
        }

    mejor_nodo: Optional[Point] = None
    mejor_linea: Optional[LineString] = None
    dmin = float("inf")

    for ln in lineas_validas:
        try:
            # Proyecta el punto sobre la línea y obtiene el punto más cercano (nodo)
            pos = ln.project(p)
            cand = ln.interpolate(pos)
            d = p.distance(cand)
            if d < dmin:
                dmin = d
                mejor_nodo = cand
                mejor_linea = ln
        except Exception:
            continue

    if mejor_nodo is None:
        return {
            "encontrado": False,
            "razon": "No se pudo calcular proyección sobre las líneas óptimas.",
            "fallback": {"punto_entrada_xy": (p.x, p.y)},
        }

    return {
        "encontrado": True,
        "nodo_xy": (mejor_nodo.x, mejor_nodo.y),
        "distancia_m": dmin,
        "linea_wkt": mejor_linea.wkt,
    }

def nodo_cercano_fuera_restricciones_safe(
    punto_xy,
    caminos_optimos_polys: List[Polygon],     # de DXF con buffer=0 (→ boundary)
    caminos_existentes_wkt: List[str],        # lista "<LINESTRING (...)>"
    plataformas: List[Polygon],               # polígonos
    restricciones: List[Polygon]              # polígonos (o líneas bufferizadas)
) -> Dict[str, Any]:
    """
    - Funciona aunque alguna de las listas venga vacía.
    - Nunca lanza excepción por listas vacías o tipos inesperados.
    - El nodo devuelto NO cae dentro (ni en borde) de plataformas ni restricciones.
    """

    p = Point(float(punto_xy[0]), float(punto_xy[1]))

    # Construir el conjunto de líneas candidato
    lineas: List[LineString] = []

    # 1) caminos óptimos: si son polígonos (buffer=0), usamos su boundary como línea
    for poly in caminos_optimos_polys or []:
        try:
            if isinstance(poly, Polygon) and not poly.is_empty:
                # boundary puede ser LineString o MultiLineString; tomamos los segmentos principales
                b = poly.boundary
                if isinstance(b, LineString):
                    lineas.append(b)
                else:
                    # MultiLineString → extraer cada parte
                    for part in getattr(b, "geoms", []):
                        if isinstance(part, LineString):
                            lineas.append(part)
        except Exception:
            pass

    # 2) caminos existentes: vienen como WKT; convertir a LineString
    for w in caminos_existentes_wkt or []:
        ls = _sanitize_wkt_ls(w)
        if ls is not None and not ls.is_empty:
            lineas.append(ls)

    # Si no hay ninguna línea, devolvemos fallback sin petar
    if not lineas:
        return {
            "encontrado": False,
            "razon": "No hay caminos disponibles (optimos ni existentes).",
            "fallback": {"punto_entrada_xy": (p.x, p.y)}
        }

    def _esta_en_restriccion(pt: Point) -> bool:
        # Usamos covers para excluir también el borde
        for poly in (plataformas or []):
            try:
                if poly.covers(pt):
                    return True
            except Exception:
                continue
        for poly in (restricciones or []):
            try:
                if poly.covers(pt):
                    return True
            except Exception:
                continue
        return False

    mejor_nodo = None
    mejor_linea = None
    dmin = float("inf")

    for ln in lineas:
        try:
            # Proyección y punto sobre la línea
            pos = ln.project(p)
            cand = ln.interpolate(pos)

            # Filtrar restricciones
            if _esta_en_restriccion(cand):
                continue

            d = p.distance(cand)
            if d < dmin:
                dmin = d
                mejor_nodo = cand
                mejor_linea = ln
        except Exception:
            continue

    if mejor_nodo is None:
        # Fallback 1: ignora restricciones y coge el más cercano (si lo necesitas)
        # (comenta si no quieres este fallback)
        try:
            for ln in lineas:
                pos = ln.project(p)
                cand = ln.interpolate(pos)
                d = p.distance(cand)
                if d < dmin:
                    dmin = d
                    mejor_nodo = cand
                    mejor_linea = ln
            if mejor_nodo is not None:
                return {
                    "encontrado": False,
                    "razon": "Todos los nodos caían en restricciones; devuelvo el más cercano ignorándolas (fallback).",
                    "nodo_xy": (mejor_nodo.x, mejor_nodo.y),
                    "distancia_m": dmin,
                    "linea_wkt": mejor_linea.wkt
                }
        except Exception:
            pass

        # Fallback 2: devuelve el punto de entrada
        return {
            "encontrado": False,
            "razon": "No se encontró nodo fuera de restricciones.",
            "fallback": {"punto_entrada_xy": (p.x, p.y)}
        }

    return {
        "encontrado": True,
        "nodo_xy": (mejor_nodo.x, mejor_nodo.y),
        "distancia_m": dmin,
        "linea_wkt": mejor_linea.wkt
    }





def _to_linestring(obj: Union[LineString, str]) -> Optional[LineString]:
    """Convierte WKT o LineString a LineString."""
    if isinstance(obj, LineString):
        return obj if not obj.is_empty else None
    if isinstance(obj, str):
        s = obj.strip()
        if s.startswith("<") and s.endswith(">"):
            s = s[1:-1]
        try:
            geom = shapely_wkt.loads(s)
            return geom if isinstance(geom, LineString) and not geom.is_empty else None
        except:
            return None
    return None


def _tangent_unit(ln: LineString, s: float, eps: float = 1.0) -> tuple:
    """Calcula un vector tangente unitario en la posición s."""
    L = ln.length
    s1 = max(0, min(L, s - eps))
    s2 = max(0, min(L, s + eps))
    p1 = ln.interpolate(s1)
    p2 = ln.interpolate(s2)
    tx, ty = p2.x - p1.x, p2.y - p1.y
    n = math.hypot(tx, ty)
    if n == 0:
        return (1, 0)
    return (tx / n, ty / n)




def _esta_fuera_de_poligonos(pt: Point, pols_plattform: List[Polygon], pols_restricciones: List[Polygon]) -> bool:
    """True si el punto está fuera (ni dentro ni borde) de todos los polígonos."""
    for poly in (pols_plattform or []):
        try:
            if poly.covers(pt):  # covers cuenta el borde como interior
                return False
        except Exception:
            continue
    for poly in (pols_restricciones or []):
        try:
            if poly.covers(pt):
                return False
        except Exception:
            continue
    return True

def _dist(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    return math.hypot(p1[0] - p2[0], p1[1] - p2[1])

def distancia_a_restricciones(
    nodo_xy,
    pols_plattform: List[Polygon],
    pols_restricciones: List[Polygon]
) -> Dict[str, Any]:
    """
    Calcula la distancia mínima desde 'nodo_xy' a todos los polígonos de:
        - plataformas (pols_plattform)
        - restricciones (pols_restricciones)
    Ambos ya están bufferizados, así que NO hace falta sumar margen.

    Devuelve:
      {
        "dist_min_m": float,
        "idx_poligono": int,
        "tipo": "plattform" o "restriccion",
        "esta_dentro": bool
      }
    """
    p = Point(nodo_xy[0], nodo_xy[1])

    mejor_dist = float("inf")
    mejor_tipo = None
    mejor_idx  = None
    esta_dentro = False

    # 1) plataformas
    for i, poly in enumerate(pols_plattform or []):
        try:
            if poly.covers(p):
                return {
                    "dist_min_m": 0.0,
                    "idx_poligono": i,
                    "tipo": "plattform",
                    "esta_dentro": True
                }
            d = p.distance(poly)
            if d < mejor_dist:
                mejor_dist = d
                mejor_idx = i
                mejor_tipo = "plattform"
        except:
            continue

    # 2) restricciones
    for i, poly in enumerate(pols_restricciones or []):
        try:
            if poly.covers(p):
                return {
                    "dist_min_m": 0.0,
                    "idx_poligono": i,
                    "tipo": "restriccion",
                    "esta_dentro": True
                }
            d = p.distance(poly)
            if d < mejor_dist:
                mejor_dist = d
                mejor_idx = i
                mejor_tipo = "restriccion"
        except:
            continue

    return {
        "dist_min_m": mejor_dist,
        "idx_poligono": mejor_idx,
        "tipo": mejor_tipo,
        "esta_dentro": False
    }


# --- Función principal ---

def seleccionar_nodos_cercanos_filtrados(
    punto_xy: Tuple[float, float],
    pols_caminos_optimos: List[LineString],
    pols_caminos_existentes: List[Union[LineString, str]],
    pols_plattform: List[Polygon],
    pols_restricciones: List[Polygon],
    distancia_offset: float = 200.0,     # distancia perpendicular a la línea (p. ej. 200 m)
    top_k: int = 10,                     # cantidad de nodos a seleccionar
    min_spacing_m: float = 2000.0,       # separación mínima entre nodos elegidos (m)
    eps_tangente: float = 1.0,           # ventana para estimar la tangente (m)
) -> Dict[str, Any]:
    """
    1) Calcula el punto más cercano a 'punto_xy' sobre cada línea (óptima + existente).
    2) Para cada línea en orden de proximidad, genera el nodo a ±'distancia_offset' sobre la normal.
    3) Acepta el primer nodo que esté FUERA de (plattform + restricciones) y respete 'min_spacing_m'
       respecto a los ya aceptados.
    4) Continúa hasta reunir 'top_k' nodos o agotar líneas.

    Devuelve:
      {
        "nodos": [ { "nodo_xy": (x,y), "proyeccion_xy": (x0,y0), "distancia_proyeccion_m": d,
                     "offset_usado_m": distancia_offset, "lado_normal": +1/-1,
                     "tipo_linea": "optimo"/"existente", "linea_wkt": "LINESTRING(...)" }, ... ],
        "n_validos": int,
        "n_intentados": int
      }
    """
    # 0) Punto de entrada
    try:
        p = Point(float(punto_xy[0]), float(punto_xy[1]))
    except Exception:
        return {"nodos": [], "n_validos": 0, "n_intentados": 0, "razon": "punto_xy inválido"}

    # 1) Normalizar líneas (acepta LineString y/o WKT)
    lineas: List[Tuple[LineString, str]] = []  # (geom, tipo)
    for ln in (pols_caminos_optimos or []):
        if isinstance(ln, LineString) and not ln.is_empty:
            lineas.append((ln, "optimo"))
    for obj in (pols_caminos_existentes or []):
        ls = _to_linestring(obj)
        if ls is not None:
            lineas.append((ls, "existente"))

    if not lineas:
        return {"nodos": [], "n_validos": 0, "n_intentados": 0, "razon": "No hay líneas válidas"}

    # 2) Calcular proyección y ordenar por distancia
    candidatos = []
    for ln, tipo in lineas:
        try:
            s = ln.project(p)
            cand = ln.interpolate(s)
            d = p.distance(cand)
            candidatos.append({
                "ln": ln, "tipo": tipo, "s": s, "proy": cand, "d": d,
            })
        except Exception:
            continue

    if not candidatos:
        return {"nodos": [], "n_validos": 0, "n_intentados": 0, "razon": "No se pudo proyectar sobre líneas"}

    candidatos.sort(key=lambda c: c["d"])  # más cercanos primero

    # 3) Iterar candidatos aplicando offset, restricciones y separación mínima
    nodos: List[Dict[str, Any]] = []
    n_intentados = 0

    for cand in candidatos:
        if len(nodos) >= top_k:
            break

        ln   = cand["ln"]
        s    = cand["s"]
        proy = cand["proy"]
        d    = cand["d"]
        n_intentados += 1

        # Tangente y normales
        tx, ty = _tangent_unit(ln, s, eps=eps_tangente)
        n1 = (-ty,  tx)
        n2 = ( ty, -tx)

        # Generar dos posibles nodos (a cada lado de la línea)
        opciones = [
            (+1, Point(proy.x + n1[0] * distancia_offset, proy.y + n1[1] * distancia_offset)),
            (-1, Point(proy.x + n2[0] * distancia_offset, proy.y + n2[1] * distancia_offset)),
        ]

        elegido = None
        for lado, pt in opciones:
            # 3.a) Validar restricciones
            if not _esta_fuera_de_poligonos(pt, pols_plattform, pols_restricciones):
                continue

            # 3.b) Validar separación a nodos ya elegidos
            xy = (pt.x, pt.y)
            if any(_dist(xy, nd["nodo_xy"]) < min_spacing_m for nd in nodos):
                continue

            elegido = {
                "nodo_xy": xy,
                "proyeccion_xy": (proy.x, proy.y),
                "distancia_proyeccion_m": d,
                "offset_usado_m": distancia_offset,
                "lado_normal": lado,
                "tipo_linea": cand["tipo"],
                "linea_wkt": ln.wkt,
            }
            break  # se acepta la primera opción válida para esta línea

        if elegido is not None:
            nodos.append(elegido)

    return {
        "nodos": nodos,
        "n_validos": len(nodos),
        "n_intentados": n_intentados,
    }






def nodo_mas_cercano_optimos_y_existentes(
    punto_xy,
    pols_caminos_optimos: List[LineString],
    pols_caminos_existentes: List[Union[LineString, str]],
    pols_plattform: List[Polygon],          # ← NUEVO: plataformas bufferizadas
    pols_restricciones: List[Polygon],      # ← NUEVO: restricciones bufferizadas
    distancia_offset=150.0,
) -> Dict[str, Any]:

    # Convertir punto de entrada
    try:
        p = Point(float(punto_xy[0]), float(punto_xy[1]))
    except:
        return {"encontrado": False, "razon": "punto inválido", "fallback": punto_xy}

    # Reunir líneas válidas
    lineas = []

    for ln in (pols_caminos_optimos or []):
        if isinstance(ln, LineString) and not ln.is_empty:
            lineas.append(ln)

    for obj in (pols_caminos_existentes or []):
        ls = _to_linestring(obj)
        if ls is not None:
            lineas.append(ls)

    if not lineas:
        return {"encontrado": False, "razon": "no hay líneas", "fallback": punto_xy}

    # 1) Proyección más cercana
    mejor = {"d": float("inf"), "cand": None, "s": None, "ln": None}
    for ln in lineas:
        try:
            s = ln.project(p)
            cand = ln.interpolate(s)
            d = p.distance(cand)
            if d < mejor["d"]:
                mejor.update({"d": d, "cand": cand, "s": s, "ln": ln})
        except:
            continue

    if mejor["cand"] is None:
        return {"encontrado": False, "razon": "sin proyección válida", "fallback": punto_xy}

    ln = mejor["ln"]
    s = mejor["s"]
    cand = mejor["cand"]

    # 2) Tangente y normales
    tx, ty = _tangent_unit(ln, s)
    n1 = (-ty, tx)
    n2 = (ty, -tx)

    # 3) Intentar colocar nodo a 200 m a cada lado
    def esta_fuera_de_restricciones(pt: Point) -> bool:
        for poly in pols_plattform:
            if poly.intersects(pt):
                return False
        for poly in pols_restricciones:
            if poly.intersects(pt):
                return False
        return True

    candidatos = []

    # desplazamiento básico
    for nx, ny in (n1, n2):
        cand_pt = Point(cand.x + nx * distancia_offset,
                        cand.y + ny * distancia_offset)
        candidatos.append(cand_pt)

    # Si ambos fallan (caen dentro), intentamos alejar más (300m, 400m…)
    extra_offsets = [200, 300, 400]

    for off in extra_offsets:
        for nx, ny in (n1, n2):
            candidatos.append(
                Point(cand.x + nx * off, cand.y + ny * off)
            )

    # 4) Seleccionar el primer candidato válido FUERA de todos los polígonos
    for pt in candidatos:
        if esta_fuera_de_restricciones(pt):
            return {
                "encontrado": True,
                "nodo_xy": (pt.x, pt.y),
                "proyeccion_xy": (cand.x, cand.y),
                "distancia_proyeccion_m": mejor["d"],
                "offset_usado_m": distancia_offset,
                "linea_wkt": ln.wkt,
            }

    # 5) Si todos están dentro → fallamos
    return {
        "encontrado": False,
        "razon": "todos los nodos proyectados caen dentro de restricciones",
        "proyeccion_xy": (cand.x, cand.y),
        "fallback": punto_xy
    }


def max_dist_coord(lista):
    # lista: [(dist, (x, y)), ...]
    if not lista:
        return None

    # selecciona el elemento con mayor "dist"
    dist, (x, y) = max(lista, key=lambda elem: elem[0])

    return x,y




def reubicar_cluster(sets,ruta_1="",ruta_2="",ruta_3="",ruta_4=""):
    if os.path.exists(ruta_1):
        pols_plattform = safe_leer_poligonos_dxf(ruta_1, buffer_m=200)
    else:
        pols_plattform = []

    if os.path.exists(ruta_2):
        pols_restricciones = safe_leer_poligonos_json(ruta_2, buffer_m=0)
    else:
        pols_restricciones = []

    if os.path.exists(ruta_3):
        pols_caminos_optimos = leer_lineas_dxf(ruta_3)
    else:
        pols_caminos_optimos = []

    if os.path.exists(ruta_4):
        pols_caminos_existentes = safe_leer_geojson_caminos_wkt(ruta_4)
    else:
        pols_caminos_existentes = []


    cluster_lista=[]

    for p_set in sets:
        res_2 = seleccionar_nodos_cercanos_filtrados(
            punto_xy=p_set,
            pols_caminos_optimos=pols_caminos_optimos,
            pols_caminos_existentes=pols_caminos_existentes,
            pols_plattform=pols_plattform,
            pols_restricciones=pols_restricciones,
            distancia_offset=250,  # “cercano” a la línea, no pegado
            top_k=10,
            min_spacing_m=500  # ← separación entre nodos
        )
        lista = []
        for i, n in enumerate(res_2["nodos"], 1):
            nodo = n["nodo_xy"]
            info_dist = distancia_a_restricciones(nodo, pols_plattform, pols_restricciones)
            lista.append((round(info_dist["dist_min_m"], 3), nodo))
        x, y = max_dist_coord(lista)
        cluster_lista.append((round(x, 2), round(y, 2)))

    return cluster_lista








'''ruta_1 = "salidas/cabeza_mar/DXF_FILES/blade_diameter.dxf"             # plataformas
ruta_2 = "salidas/cabeza_mar/restricciones/restricciones_20260206_004509_utm32719.geojson"  # restricciones
ruta_3 = "salidas/cabeza_mar/DXF_FILES/rutas_optimas.dxf"                # caminos óptimos (DXF)
ruta_4 = "salidas/cabeza_mar/caminos/camino_20260206_004518_utm32719.geojson"  # caminos existentes (GeoJSON)


sets=[(368075.5730833333, 4160951.670333334), (383381.2485875705, 4171881.8658192093), (359363.9853398057, 4149443.6878640777)]

h=reubicar_cluster(sets,ruta_1,ruta_2,ruta_3,ruta_4)'''



