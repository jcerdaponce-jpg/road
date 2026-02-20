
from ohl_functions import circuit_length
from HV_OHL_SCRIPT import ruta_optima_entre_nodos
from PLOT_OHL import plot_ohl
from aux_functions import orientation_to_angle,  coord_in_out, path_file,orientation_to_angle_2
import json, os, datetime
from shapely.geometry import Polygon, LineString
from shapely.ops import unary_union
from mover_set import mover_y_rotar_bloque
from typing import List, Dict, Tuple,Any,TypedDict, Iterable,Optional
import ezdxf
import math

def obtener_high_voltage():
    import streamlit as st
    return st.session_state.get("high_voltage", 220.0)


def angulo_vector_direccion(x2, y2, x3, y3):

    # Vector fijo hacia arriba (Norte)
    v1x, v1y = 0, 1

    # Vector real
    magnitud=math.sqrt((x2-x3)**2 + (y2-y3)**2)
    v2x = (x3 - x2)/magnitud
    v2y = (y3 - y2)/magnitud

    # Producto punto
    dot = v1x * v2x + v1y * v2y

    # Producto cruzado (2D)
    cross = v1x * v2y - v1y * v2x

    # Magnitud del vector real
    mag2 = math.hypot(v2x, v2y)
    if mag2 == 0:
        raise ValueError("El vector real tiene longitud cero.")

    # Ángulo firmado (-180 a 180)
    ang = math.degrees(math.atan2(cross, dot))

    return ang


'''def obtener_io_por_nombre(
    sets: List[Dict],
    nombre: str,
    raise_if_missing: bool = True
) -> Optional[Tuple[float,float,float, float, float, float,float,float,float,float,Any]]:
    for item in sets:
        if item.get('nombre') == nombre:
            try:
                return {'x_center':float(item['x_center']),
                        'y_center':float(item['y_center']),
                    'x_in':float(item['x_in']),
                        'y_in':float(item['y_in']),
                        'x_out':float(item['x_out']),
                        'y_out':float(item['y_out']),
                        'x_in_aux':float(item['x_in_aux']),
                        'y_in_aux':float(item['y_in_aux']),
                        'x_out_aux':float(item['x_out_aux']),
                        'y_out_aux':float(item['y_out_aux']),
                        'angle_2':float(item['rotacion_2']),
                        'type':item["type"]}
            except KeyError as e:
                raise KeyError(f"Falta la clave {e} en el set '{nombre}'.") from e
            except (TypeError, ValueError) as e:
                raise ValueError(f"Valores no numéricos en el set '{nombre}'.") from e

    if raise_if_missing:
        raise ValueError(f"No se encontró un set con nombre '{nombre}'.")
    return None'''

class IOOut(TypedDict):
    x_in: float
    y_in: float
    x_out: float
    y_out: float
    x_in_aux: float
    y_in_aux: float
    x_out_aux: float
    y_out_aux: float
    type: str
    # agrega campos si los usas (angle_2, x_center, etc.)

def obtener_io_por_nombre(sets: Iterable[Dict[str, Any]], nombre: str) -> IOOut:
    for item in sets:
        if item.get('nombre') == nombre:
            # Asegurate de castear a float aquí para homogeneizar
            return {
                'x_in': float(item['x_in']),
                'y_in': float(item['y_in']),
                'x_out': float(item['x_out']),
                'y_out': float(item['y_out']),
                'x_in_aux': float(item['x_in_aux']),
                'y_in_aux': float(item['y_in_aux']),
                'x_out_aux': float(item['x_out_aux']),
                'y_out_aux': float(item['y_out_aux']),
                'type': str(item['type']),
            }
    raise KeyError(f"No existe item con nombre={nombre!r}")



# (1) Lector de restricciones GeoJSON (UTM)
def leer_poligonos_json(path_json, buffer_m=20):
    zonas = []
    with open(path_json, 'r', encoding='utf-8') as f:
        data = json.load(f)
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
            if len(coords) >= 2:
                return {"nombre": props.get('tipo','grid_on'), "x": float(coords[0]), "y": float(coords[1])}
    return None

def cluster_set_xy(path):
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    sim = data.get('Simulation SET', {}) or {}
    x = sim.get('x'); y = sim.get('y')
    return {"nombre": "Cluster_set", "x": float(x), "y": float(y)}
def lib_set(sets,conexiones,tipos_por_set):
    sets_por_id = {s.id: s for s in sets}

    # 2. Diccionario de orientaciones
    orientaciones_por_set = {}
    for c in conexiones:
        orientaciones_por_set[c["origen"]] = c["orientacion_origen"]
        orientaciones_por_set[c["destino"]] = c["orientacion_destino"]

    # 3. Construir la lista final
    lista_final = []
    for set_id, set_obj in sets_por_id.items():
        lista_final.append({
            "id": set_id,
            "x": set_obj.utm_x,
            "y": set_obj.utm_y,
            "tipo_set": tipos_por_set.get(set_id),
            "orientacion": orientaciones_por_set.get(set_id)  # None si no aparece en conexiones
        })

    # Mostrar resultado

    return lista_final

def pertenece_a(link: dict, nombre: str) -> str:
    """
    Retorna 'origen', 'destino' o 'ninguno' según dónde aparezca el SET.
    """
    if link.get('origen') == nombre:
        return 'origen'
    elif link.get('destino') == nombre:
        return 'destino'
    else:
        return 'ninguno'
def leer_poligonos_dxf(ruta_dxf: str, buffer_m: float) -> Optional[List[Polygon]]:
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

    return poligonos

def main_ohl_main(raster_path,restricciones_path,conexiones,tipos_por_set,sets,DXF_FILES):
    #print('adentro de hv_ohl')

    zonas_restringidas = leer_poligonos_json(restricciones_path, buffer_m=0) + leer_poligonos_dxf(ruta_dxf=f'{DXF_FILES}/blade_diameter.dxf',buffer_m=150)
    #print(len(zonas_restringidas))
    libreria=lib_set(sets,conexiones,tipos_por_set)
    lista_set=[]
    for i in libreria:
        i_id=i["id"]
        i_x=i["x"]
        i_y=i["y"]
        i_type=i["tipo_set"]
        i_orient=orientation_to_angle(i["orientacion"])
        i_orient_2 = orientation_to_angle_2(i["orientacion"])
        x_in,y_in,x_out,y_out,x_in_aux,y_in_aux,x_out_aux,y_out_aux=coord_in_out(set=i_type,x=i_x,y=i_y,angle=i_orient)
        #x_in_r, y_in_r, x_out_r, y_out_r, x_in_aux_r, y_in_aux_r, x_out_aux_r, y_out_aux_r
        lista_set.append({
            'nombre':i_id,
            'type':i_type,
            'x_center':i_x,
            'y_center':i_y,
            'x_in':x_in,
            'y_in':y_in,
            'x_out':x_out,
            'y_out':y_out,
            'x_in_aux':x_in_aux,
            'y_in_aux':y_in_aux,
            'x_out_aux':x_out_aux,
            'y_out_aux':y_out_aux,
            'rotacion':i_orient,
            'rotacion_2':i_orient_2,})
        path_file_uno,bloque=path_file(i_type)
        path_file_out=f'{DXF_FILES}/{i_id}.dxf'
        mover_y_rotar_bloque(ruta_dxf=path_file_uno,nombre_bloque=bloque,nueva_posicion=(i_x,i_y),nueva_rotacion=i_orient,salida_dxf=path_file_out)


    count=1
    ohl_list=[]
    list_files=[]
    ohl_cord=[]
    for i_set in conexiones:

        print('%%%%%%%%%%%%%%%%%%')
        origen=i_set['origen']
        destino=i_set['destino']
        power_conection=i_set['power']/1000
        set_1=pertenece_a(i_set,origen)
        set_2=pertenece_a(i_set,destino)
        if set_1 == 'origen':
            cord = obtener_io_por_nombre(lista_set, origen)
            nodo_1={'nombre':origen,'x':cord.get('x_out'),'y':cord.get('y_out')}
            x_1=cord.get('x_out')
            y_1 =cord.get('y_out')
            x_2=cord.get('x_out_aux')
            y_2=cord.get('y_out_aux')
            angle_origen=angulo_vector_direccion(x_2, y_2, x_1, y_1)
            #print(angle_origen)


        if set_2=='destino':
            cord = obtener_io_por_nombre(lista_set, destino)
            nodo_2={'nombre':destino,'x':cord.get('x_in'),'y':cord.get('y_in')}
            tipo = cord.get('type')
            #print(tipo,'salida')
            x_1 = cord.get('x_in')
            y_1 = cord.get('y_in')
            x_2 = cord.get('x_in_aux')
            y_2 = cord.get('y_in_aux')
            angle_destino = angulo_vector_direccion(x_1, y_1, x_2, y_2)
            #print(angle_destino,x_1,y_1,x_2,y_2)
        linea_ruta = ruta_optima_entre_nodos(nodo1=nodo_1, nodo2=nodo_2, direccion_salida=angle_origen,
                                             direccion_llegada=angle_destino, zonas_restringidas=zonas_restringidas,
                                        raster_path=raster_path)

        name=f'ruta_ohl_{count}.dxf'
        list_files.append(name)
        u, v = plot_ohl(linea_ruta, zonas_restringidas, DXF_FILES,name)
        #u son las coordenadas hay que hacer las
        ohl_cord.append(u)
        #print(power_conection)
        #print(type(v['total']))
        AT_V=obtener_high_voltage()
        lista_aux={'OHL':count,'origen':origen,'destino':destino}
        #print(AT_V,lista_aux)
        lista_circuit=circuit_length(power_conection, AT_V, v['total'])
        #print(lista_circuit)
        ohl_list.append({**lista_aux,**lista_circuit})
        count += 1


    return ohl_list,list_files,ohl_cord
