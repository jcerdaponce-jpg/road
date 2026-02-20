
from pathlib import Path
from typing import Iterable, Tuple, List
from shapely.geometry import LineString, Point, Polygon
import ezdxf
import sys



def crear_dxf(
    lista_de_lineas: List[List[Tuple[float, float]]],
    DXF_FOLDER: str,
    dxf_filename: str = "ruta_ajustada.dxf",
    dxf_layer: str = "Ruta_Ajustada"
) -> Path:
    """
    Exporta las líneas (listas de (x, y)) a un archivo DXF como LWPOLYLINE.
    Retorna el Path del archivo DXF guardado.
    """
    folder_path = Path(DXF_FOLDER)
    folder_path.mkdir(parents=True, exist_ok=True)
    dxf_path = folder_path / dxf_filename

    doc = ezdxf.new(dxfversion="R2010")
    msp = doc.modelspace()

    for filtrados in lista_de_lineas:
        # Sólo exportar polilíneas válidas (>= 2 vértices)
        if len(filtrados) >= 2:
            msp.add_lwpolyline(filtrados, dxfattribs={"layer": 'HV_OHL','color':1, "lineweight": 60, "linetype": "CONTINUOUS", })

    doc.saveas(str(dxf_path))
    print(f"[OK] DXF guardado en: {dxf_path}")

def calcular_longitud_lineas(
    lista_de_lineas
):
    """
    Calcula la longitud de cada línea y el total (en metros si las coords están en UTM).

    Parámetros:
        lista_de_lineas: lista de líneas, donde cada línea es una lista de (x, y).

    Retorna:
        {
            "por_linea": [l1, l2, ...],  # longitudes por línea (float)
            "total": L_total              # suma de longitudes
        }
    """
    longitudes: List[float] = []
    for coords in lista_de_lineas:
        # Necesitamos al menos 2 puntos para medir
        if coords and len(coords) >= 2:
            line = LineString(coords)
            longitudes.append(float(line.length))
        else:
            longitudes.append(0.0)

    total = float(sum(longitudes))
    return {"total": total}


def plot_ohl(
    lista,                          # puede ser [(x,y), ...] o [[(x,y), ...], ...]
    restricciones_poligonos,        # lista de shapely.Polygon o de listas de coords
    DXF_FOLDER: str,                # carpeta donde guardar el DXF
    dxf_filename: str = "ruta_ajustada.dxf",
    simplify_tol: float = 90,
    buffer_m: float = 0          # si no quieres buffer, pon 0.0
) -> List[List[Tuple[float, float]]]:

    """
    Filtra puntos de las líneas que NO estén dentro de las restricciones y exporta un DXF.

    Parámetros:
        lista: una o varias líneas. Cada línea es lista de (x, y).
        restricciones_poligonos: iterable con Polygon shapely o listas de coords por polígono.
        DXF_FOLDER: carpeta destino del DXF.
        dxf_filename: nombre del archivo DXF.
        simplify_tol: tolerancia Douglas–Peucker (misma unidad que coords).
        buffer_m: buffer aplicado a cada restricción. 0.0 = sin buffer.

    Retorna:
        ohl_final: lista de líneas filtradas (cada una lista de (x, y)).
    """
    # --- Normalizar lista (una ruta vs múltiples) ---
    if lista and isinstance(lista, (list, tuple)):
        # Caso: una sola línea [(x,y), ...] → envolver en lista [[(x,y), ...]]
        if lista and isinstance(lista[0], (list, tuple)) and len(lista[0]) == 2 \
           and isinstance(lista[0][0], (int, float)):
            lista = [list(lista)]

    # --- Convertir restricciones a Polygon y aplicar buffer si corresponde ---
    restricciones: List[Polygon] = []
    for poly in restricciones_poligonos:
        if isinstance(poly, Polygon):
            r = poly
        else:
            r = Polygon(poly)  # asumimos iterable de coords
        if buffer_m and buffer_m > 0:
            r = r.buffer(buffer_m)
        restricciones.append(r)

    def fuera_de_restricciones(pto: Tuple[float, float]) -> bool:
        p = Point(pto)
        # True si el punto NO cae dentro de ninguna zona restringida
        return all(not zona.contains(p) for zona in restricciones)

    ohl_final: List[List[Tuple[float, float]]] = []

    for coords in lista:
        # Asegurar floats
        coords = [(float(x), float(y)) for (x, y) in coords]

        # Si hay menos de 2 puntos, no hay nada que simplificar
        if len(coords) < 2:
            ohl_final.append(coords)
            continue

        # ---- Mantener primer y último punto ----
        p0 = coords[0]

        pf = coords[-1]

        # Puntos intermedios
        intermedios = coords[1:-1]

        # Si no hay intermedios, no simplificamos nada
        if len(intermedios) > 1:
            line = LineString(intermedios)
            simplified = line.simplify(tolerance=simplify_tol)
            intermedios_simplificados = list(simplified.coords)
        else:
            intermedios_simplificados = intermedios

        # ---- Reconstruir la línea manteniendo extremos ----
        coords_proc = [p0] + intermedios_simplificados + [pf]

        # Filtrar puntos fuera de restricciones
        filtrados = [pto for pto in coords_proc if fuera_de_restricciones(pto)]
        ohl_final.append(filtrados)

    h=calcular_longitud_lineas(ohl_final)

    # Exportar DXF una sola vez al final
    crear_dxf(ohl_final, DXF_FOLDER, dxf_filename)

    return ohl_final ,h
