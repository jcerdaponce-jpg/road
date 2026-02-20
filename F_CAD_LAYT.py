

import json
import os
import ezdxf
import sys

def cad_final(FOLDER_NAME_1,DXF_FOLDER):
    # Cargar rutas desde archivos JSON
    filename = f"{FOLDER_NAME_1}/e_mst.json"
    with open(filename, "r", encoding="utf-8") as f:
        rutas = json.load(f)

    # Crear un nuevo archivo DXF
    doc = ezdxf.new(dxfversion="R2018")
    msp = doc.modelspace()



    for ruta in rutas:
        origen = ruta["origen"]["nombre"]
        destino = ruta["destino"]["nombre"]


        # Ignorar si origen o destino empiezan con "camino"
        if origen.startswith("camino") and destino.startswith("camino"):
            continue

        ruta_json = f"{FOLDER_NAME_1}/{origen}_{destino}_final_curve.json"
        if not os.path.exists(ruta_json):
            ruta_json = f"{FOLDER_NAME_1}/{destino}_{origen}_final_curve.json"
        if not os.path.exists(ruta_json):
            continue

        # Leer puntos
        with open(ruta_json, "r", encoding="utf-8") as jsonfile:
            data = json.load(jsonfile)




            puntos = [(float(row["x"]), float(row["y"])) for row in data]

        # Dibujar polilínea
        if len(puntos) >= 2:
            msp.add_lwpolyline(puntos, dxfattribs={"layer": "Roads",'color':5, "lineweight": 25,})

    # Verificar contenido


    # Guardar DXF
    output_filename = f"{DXF_FOLDER}/rutas_optimas.dxf"
    doc.saveas(output_filename)
    print(f"Archivo DXF guardado como {output_filename}")
    return
