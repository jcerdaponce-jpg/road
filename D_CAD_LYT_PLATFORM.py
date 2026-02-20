import json
import ezdxf
import sys
from ezdxf import colors, const

def generar_autocad(json_file, DXF_FOLDER):


    dxf_file=f'{DXF_FOLDER}/PLATFORM.dxf'

    """
    Lee un archivo JSON con polilíneas y genera un DXF compatible con AutoCAD.

    Parámetros:
    - json_file: ruta al archivo JSON (estructura: {clave: {"geometry": [[coords], ...]}})
    - dxf_file: nombre del archivo DXF de salida
    """
    # 1. Leer el archivo JSON
    with open(json_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 2. Crear un nuevo documento DXF
    doc = ezdxf.new(dxfversion="R2010")
    msp = doc.modelspace()

    # 3. Recorrer cada clave y añadir sus polilíneas
    for clave, contenido in data.items():
        geometries = contenido.get("geometry", [])
        for poly_coords in geometries:
            # Añadir polilínea cerrada en la capa del WTG
            msp.add_lwpolyline(poly_coords, close=True,
 dxfattribs={
                "layer": "Platform",
                "color": 6,                          # 1 = rojo (ACI)
                "lineweight": 25,   # 0.25 mm
                "linetype": "CONTINUOUS",            # opcional: tipo de línea
            }
)

    # 4. Guardar el archivo DXF
    doc.saveas(dxf_file)

    return

