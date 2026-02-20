


import ezdxf

import json
from typing import List, Dict, Any, Literal,Tuple
from shapely.geometry import Point  # <-- requerido por polygon_circular



def polygon_circular(nodes: list, diameter: float, resolution: int = 10) -> List[Tuple[str, list]]:
    """
    Genera para cada nodo un polígono circular (aprox. de círculo) con Shapely.
    resolution=16 => ~64 lados (4*resolution).
    Retorna: lista de tuplas (id, coords), donde coords es lista de (x,y) cerrada (último = primero).
    """
    radius = diameter / 2.0
    polys = []
    for n in nodes:
        pid = n["nombre"]
        x, y = float(n["x"]), float(n["y"])
        poly = Point(x, y).buffer(radius, resolution=resolution)
        coords = list(poly.exterior.coords)  # incluye cierre
        polys.append((pid, coords))
    return polys

def write_dxf_lwpoly(polys: List[Tuple[str, list]], dxf_file: str, layer_name: str = "WTG_CIRCULOS",
                     insunits: int = 6):
    """
    Escribe un DXF con una LWPOLYLINE cerrada por polígono.
    - Quita el último punto duplicado (porque close=True ya cierra).
    - Asegura capa y unidades.
    """
    doc = ezdxf.new(dxfversion="R2010", setup=True)
    doc.header["$INSUNITS"] = insunits  # 6 = metros
    if layer_name not in doc.layers:
        doc.layers.add(name=layer_name, color=50, linetype="CONTINUOUS")
    msp = doc.modelspace()

    for pid, coords in polys:
        if len(coords) >= 2 and coords[0] == coords[-1]:
            coords = coords[:-1]  # quitar cierre duplicado
        # Añadir polilínea cerrada en la capa deseada
        msp.add_lwpolyline(coords, format="xy", close=True, dxfattribs={"layer": layer_name})
        # (Opcional) Etiqueta con el nombre:
        # msp.add_text(pid, dxfattribs={"height": 2.5, "layer": layer_name}).set_pos(coords[0])

    doc.saveas(dxf_file)
    print(f"DXF generado: {dxf_file} | capa={layer_name} | polígonos={len(polys)}")

def _normalizar_nodos(
    raw: List[Dict[str, Any]],
    prefer: Literal["utm", "geo", "raw"] = "utm"
) -> List[Dict[str, Any]]:
    """
    Convierte una lista de objetos con esquema {id, lat, lon, utm_x, utm_y}
    a la forma esperada por polygon_circular: [{nombre, x, y}], en unidades planas.
    prefer="utm"  -> usa utm_x / utm_y (metros)  ✅ recomendado para DXF en metros
    prefer="geo"  -> usa lon / lat (grados)      ❌ NO recomendado si el diámetro está en metros
    prefer="raw"  -> intenta x / y si ya viniera con esos nombres
    """
    nodos = []
    for i, n in enumerate(raw, start=1):
        nombre = n.get("id") or n.get("nombre") or f"N{i}"

        x = y = None
        if prefer == "utm" and ("utm_x" in n and "utm_y" in n):
            x, y = n["utm_x"], n["utm_y"]
        elif prefer == "geo" and ("lon" in n and "lat" in n):
            # OJO: grados; si usas esto, tu 'diameter' (m) no sería coherente.
            x, y = n["lon"], n["lat"]
        elif prefer == "raw" and ("x" in n and "y" in n):
            x, y = n["x"], n["y"]
        else:
            # Fallback por si faltan campos bajo la preferencia indicada
            if "utm_x" in n and "utm_y" in n:
                x, y = n["utm_x"], n["utm_y"]
            elif "lon" in n and "lat" in n:
                x, y = n["lon"], n["lat"]
            elif "x" in n and "y" in n:
                x, y = n["x"], n["y"]

        if x is None or y is None:
            raise ValueError(
                f"Nodo {nombre}: faltan coordenadas compatibles. "
                f"Se esperaban ('utm_x','utm_y') o ('lon','lat') o ('x','y')."
            )

        nodos.append({"nombre": str(nombre), "x": float(x), "y": float(y)})

    if not nodos:
        raise ValueError("No se encontraron nodos válidos en el JSON.")

    return nodos

# --- main_blade ajustado a tu JSON adjunto ---
def main_blade(
    file_path: str,
    diameter: float,
    dxf_file: str,
    resolution: int = 10,
    coord_preference: Literal["utm", "geo", "raw"] = "utm"
):
    """
    Lee el JSON con objetos {id, lat, lon, utm_x, utm_y}, lo normaliza a {nombre,x,y} en unidades planas,
    genera polígonos circulares (diámetro en metros) y los exporta a DXF (insunits=6).
    """
    # 1) Leer JSON
    with open(file_path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    if not isinstance(raw, list):
        raise TypeError(
            "JSON inválido: se esperaba una LISTA de objetos (id/lat/lon/utm_x/utm_y)."
        )

    # 2) Normalizar a {nombre,x,y} (por defecto, UTM en metros)
    nodes = _normalizar_nodos(raw, prefer=coord_preference)

    # 3) Geometría con Shapely
    polys = polygon_circular(nodes, diameter, resolution=resolution)

    # 4) DXF con ezdxf
    write_dxf_lwpoly(polys, dxf_file, layer_name="DIAMETER_BLADE", insunits=6)

'''def main_blade(file_path: str, diameter: float, dxf_file: str, resolution: int = 10):
    # Leer JSON
    with open(file_path, "r", encoding="utf-8") as f:
        nodos = json.load(f)
    assert isinstance(nodos, list) and all({"nombre","x","y"} <= set(n) for n in nodos), \
        "JSON inválido: se espera lista de objetos con campos 'nombre','x','y'."

    # Geometría con Shapely
    polys = polygon_circular(nodos, diameter, resolution=resolution)

    # DXF con ezdxf
    write_dxf_lwpoly(polys, dxf_file, layer_name="WTG_DIAMETER", insunits=6)'''





