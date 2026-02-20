import sys
import math
import re
from sklearn.neighbors import KDTree

#from PLOT import plotting#copiaod
#from C_extraction_road import extraction_road#copiado
from D_astra_ruta_optima import ruta_optima_entre_nodos#copiado
import json
import os
#from D_filtrado_nodos import simplificar_nodos_camino
import plotly.graph_objects as go
import ezdxf
from shapely.geometry import Point, Polygon



import re
from sklearn.neighbors import KDTree
from F_CAD_LAYT import cad_final
from D_astra_ruta_optima import ruta_optima_entre_nodos  # firma extendida con raster_path
import json
import os
import plotly.graph_objects as go
import matplotlib.pyplot as plt
from E_curve_smoothing import main_curve
from E_MST import mst_function
from UTM_GEO import utm_lat_lon
import numpy as np
from scipy.spatial import Delaunay
from b_cad_restriction_blade import main_blade
from B_Rotate_turbine import rotate_platform_wtg
from DEM_FILE import dem_file
import time


def misma_base_wtg(n1: str, n2: str) -> bool:
    t1, id1, _ = parse_nombre(n1)
    t2, id2, _ = parse_nombre(n2)
    return (t1 == 'wtg') and (t2 == 'wtg') and (id1 == id2)

def parse_nombre(nombre: str):
    m = re.match(r'^(wtg)_(\d+)(?:_(entry|out))?$', nombre)
    if m:
        return m.group(1), m.group(2), m.group(3) or ""
    m = re.match(r'^(camino)_(\d+)(?:_(\d+))?$', nombre)
    if m:
        return m.group(1), m.group(2), m.group(3) or ""
    partes = nombre.split('_')
    tipo = partes[0] if partes else ""
    idnum = partes[1] if len(partes) > 1 else ""
    suf = '_'.join(partes[2:]) if len(partes) > 2 else ""
    return tipo, idnum, suf

def camino_consecutivos(n1: str, n2: str) -> bool:
    t1, id1, s1 = parse_nombre(n1)
    t2, id2, s2 = parse_nombre(n2)
    if not (t1 == 'camino' and t2 == 'camino'):
        return False
    if id1 != id2:
        return False
    try:
        return abs(int(s1) - int(s2)) == 1
    except ValueError:
        return False

def base_nombre(nombre,i):
    partes = nombre.split("_")
    return "_".join(partes[:i])

def camino_num(nombre):
    m = re.match(r"camino_(\d+)", nombre)
    return int(m.group(1)) if m else None

def folder_created(folder_name):
    if not os.path.exists(folder_name):
        os.makedirs(folder_name)
        print(f"'{folder_name}' folder successful created.")
    else:
        print(f"'{folder_name}' folder exists already.")
    return

def leer_poligonos_dxf(ruta_dxf: str, buffer_m: float) :
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


# ------------------ FIRMA EXTENDIDA: añadimos raster_path ------------------
def main_road_(zonas_restringidas, Huso_a, Huso_b,
               excavation_price, fill_price,
               entry_exit, pads, preassembly, diameter_blade,
               nodos_caminos, nodos, fundacion_diametro,
               FOLDER_NAME_1, DXF_FOLDER,
               raster_path,path_caminos):  # <-- NUEVO PARÁMETRO
    a_time_total=0
    nodos_geo = {}
    for nombre, (x, y) in nodos.items():
        lon, lat = utm_lat_lon(x, y, Huso_a, Huso_b)
        nodos_geo[nombre] = {"x": x, "y": y, "lon": lon, "lat": lat}


    try:
        path_vol=f"{FOLDER_NAME_1}/vol_platfform.json"
        with open(path_vol, "r", encoding="utf-8") as f:
            lista_material=json.load(f)
        print('Rotate platfform file existing')

    except:
        a_1=time.time()
        lista_material = rotate_platform_wtg( nodos_geo, entry_exit, pads, preassembly,fundacion_diametro, FOLDER_NAME_1, DXF_FOLDER,excavation_price, fill_price, zonas_restringidas,raster_path,path_caminos)

        with open(f"{FOLDER_NAME_1}/vol_platfform.json", "w", encoding="utf-8") as f:
            json.dump(lista_material, f, indent=4)
        b_1=time.time()
        a_time_total=+round((b_1-a_1)/60,3)
        print(f'platfform time: {round((b_1-a_1)/60,3)} minutes')

    file_path_a = f'{FOLDER_NAME_1}/wtg_center.json'
    #dxf_file_a  = f"{DXF_FOLDER}/blade_diameter.dxf"
    #main_blade(file_path_a, diameter_blade, dxf_file_a)

    ruta_dxf = f"{DXF_FOLDER}/PLATFORM.dxf"
    pols_plattform = leer_poligonos_dxf(ruta_dxf, buffer_m=15)

    with open(f"{FOLDER_NAME_1}/wtg_points.json", encoding="utf-8") as f:
        nodos_list = json.load(f)
    nodos_list.extend(nodos_caminos)
    print()
    coords  = np.array([[n["x"], n["y"]] for n in nodos_list], dtype=float)
    nombres = [n["nombre"] for n in nodos_list]
    RS_NAME = 'road_survey'
    idx_rs  = nombres.index(RS_NAME)

    mean = coords.mean(axis=0)
    std  = coords.std(axis=0)
    std[std == 0] = 1.0
    coords_norm = (coords - mean) / std
    tri = Delaunay(coords_norm, qhull_options='QJ')
    if tri.vertex_to_simplex[idx_rs] == -1:
        eps = 1e-8
        coords_norm[idx_rs] = coords_norm[idx_rs] + np.array([eps, -eps])
        tri = Delaunay(coords_norm, qhull_options='QJ')

    edges = set()
    for simplex in tri.simplices:
        for i in range(3):
            a, b = sorted([simplex[i], simplex[(i + 1) % 3]])
            na, nb = nombres[a], nombres[b]
            if RS_NAME in (na, nb):
                edges.add((a, b))
                continue
            if na.endswith('_out') and nb.startswith('camino_'):
                continue
            if na.startswith('camino_') and nb.endswith('_out'):
                continue
            if na.endswith('_out') and nb.endswith('_out'):
                continue
            edges.add((a, b))



    ###############ACACPONER ELCODIGO DE ALINEACION PARA ALINEAS AEROS QUE ESTEN CONECTADOS.
    camino_idxs = np.array([i for i, nom in enumerate(nombres) if nom.startswith('camino_') and i != idx_rs], dtype=int)
    if camino_idxs.size > 0:
        dif   = coords[camino_idxs] - coords[idx_rs]
        dists = np.hypot(dif[:, 0], dif[:, 1])
        k     = np.argmin(dists)
        nearest_camino_idx = int(camino_idxs[k])
        a, b = sorted([idx_rs, nearest_camino_idx])
        edges.add((a, b))
        for (i, j) in list(edges):
            if (i == idx_rs or j == idx_rs) and (min(i, j), max(i, j)) != (a, b):
                edges.discard((i, j))
    else:
        print("[AVISO] No existen nodos 'camino_*' para conectar con 'road_survey'.")


    edges_ordenados = sorted(edges)

    distancias = []
    total_files = len(edges_ordenados)
    aux_ = 1
    ponde=0
    #poner aca un bucle que me cuentes los que son wtg_entry con wtg_exit y conexiones de dos caminos.

    for i, j in edges_ordenados:
        nodo1 = nodos_list[i]

        nodo2 = nodos_list[j]
        n1 = nodo1["nombre"]
        n2 = nodo2["nombre"]

        path_file_a = f"{FOLDER_NAME_1}/{n1}_{n2}_ruta_optima.json"

        if misma_base_wtg(n1, n2):
            a_ = time.time()
            x1, y1 = nodo1["x"], nodo1["y"]
            x2, y2 = nodo2["x"], nodo2["y"]
            distancia_total = round(np.hypot(x2 - x1, y2 - y1), 2)
            slope_promedio = 0.0
            slope_mediana  = 0.0
            slope_ruta     = distancia_total
            slope_ponderado= 0.0
            b_ = time.time()
            print(n1, n2, distancia_total, f"({aux_}/{total_files}).{round(b_ - a_, 1)}s")

        elif n1.startswith("camino_") and n2.startswith("camino_"):
            a_ = time.time()
            x1, y1 = nodo1["x"], nodo1["y"]
            x2, y2 = nodo2["x"], nodo2["y"]
            distancia_total = round(np.hypot(x2 - x1, y2 - y1), 2)
            slope_promedio = 0.0
            slope_mediana  = 0.0
            slope_ruta     = distancia_total
            slope_ponderado= 0.0
            b_ = time.time()
            print(n1, n2, distancia_total, f"({aux_}/{total_files}).{round(b_ - a_, 1)}s")


        elif os.path.exists(path_file_a):
            print(f'file_{path_file_a} existing')
            with open(path_file_a, "r", encoding="utf-8") as f:
                ruta_a = json.load(f)
            distancia_total = ruta_a['distancia']
            slope_promedio  = ruta_a['slope_promedio']
            slope_mediana   = ruta_a["slope_mediana"]
            slope_ruta      = ruta_a["slope_distancia"]
            slope_ponderado = ruta_a["slope_ponderado"]

        else:
            # ---------- LLAMADA EXACTA QUE PEDISTE (con raster_path) ----------
            a_ = time.time()

            ruta_final, distancia_total, slope_promedio, slope_mediana, slope_ruta, slope_ponderado = ruta_optima_entre_nodos(
                nodo1, nodo2, zonas_restringidas, pols_plattform,DXF_FOLDER, FOLDER_NAME_1, raster_path
            )

            b_ = time.time()
            ponde+=round(b_ - a_, 1)
            a_time_total += round((b_ - a_) / 60, 3)
            print(f'Average Interconnection Time  : {round(ponde/aux_,1)} seconds ')
            print(f'Time remaining: {round(((total_files-aux_)*ponde/aux_)/3600,1)} hours' )
            print(n1, n2, distancia_total, f"({aux_}/{total_files}).{round(b_ - a_, 1)}s")

        distancias.append({
            "origen": nodo1,
            "destino": nodo2,
            "distancia": distancia_total,
            "slope_promedio": slope_promedio,
            "slope_mediana": slope_mediana,
            "ruta_ponderada": slope_ruta,
            "slope_ponderado": slope_ponderado
        })

        aux_ += 1
    a_j1=time.time()
    path_delanuay = f"{FOLDER_NAME_1}/distancias_real_delaunay.json"
    with open(path_delanuay, "w", encoding="utf-8") as f:
        json.dump(distancias, f, indent=2)

    try:
        path_e_mst = f"{FOLDER_NAME_1}/e_mst.json"
        with open(path_e_mst, "r", encoding="utf-8") as f:
            out = json.load(f)
            print('Rotate platfform file existing')
    except:
        out = mst_function(
        path_json_conexiones=path_delanuay,
        start_node="road_survey",
        outfile=f"{FOLDER_NAME_1}/e_mst.json",
        algoritmo_mst="prim")
    path_final = f"{FOLDER_NAME_1}/e_mst.json"
    print(f'Total time: {int(a_time_total/60)} hours and {round((a_time_total/60-int(a_time_total/60))*60,2)} minutes %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%')
    h = main_curve(path_final, FOLDER_NAME_1)
    k = cad_final(FOLDER_NAME_1, DXF_FOLDER)
    b1_j1=time.time()
    print(f'Tiempo de ruta calculado: {b1_j1-a_j1} seconds')
    return lista_material
