
from pathlib import Path
from typing import Iterable, Union
import json
import pandas as pd
import streamlit as st
import os


def crear_excel_4_hojas_vertical_desde_rutas(json2_path:Union[str, Path, None],
    json3_path: Union[str, Path, None],
    output_xlsx: Union[str, Path, None],
    columnas: Iterable[str] = ("Campo", "Valor")
) -> Path:
    numero_sets=len(st.session_state.get('todos_sets'))
    ruta_excel=f'RESULTADOS/resultados_circuitos_opcion1_{numero_sets}_SETs.xlsx'

    try:
        df = pd.read_excel(ruta_excel)
        cable_120 = round(df["WTGs fuera de radio\SET calculadas. Criterio 10.5km 3 SETs, opción 1_Supply 120mm2 (km)"].sum(),2)
        cable_300 = round(df["WTGs fuera de radio\SET calculadas. Criterio 10.5km 3 SETs, opción 1_Supply 300mm2 (km)"].sum(),2)
        cable_630 = round(df["WTGs fuera de radio\SET calculadas. Criterio 10.5km 3 SETs, opción 1_Supply 630mm2 (km)"].sum(),2)


    except FileNotFoundError:

        df = None
        cable_120 =0
        cable_300 = 0
        cable_630 =0
    except Exception as e:

        df = None
        cable_120 = 0
        cable_300 = 0
        cable_630 = 0

    # Asegurar objetos Path
    if output_xlsx is None:
        raise ValueError("output_xlsx no puede ser None")

    output_xlsx = Path(output_xlsx)
    output_xlsx.parent.mkdir(parents=True, exist_ok=True)

    # --- 1) Cargar JSON principal (si existe) ---
    if json2_path is not None and Path(json2_path).exists():
        with open(json2_path, "r", encoding="utf-8") as f:
            data_root_a = json.load(f)
    else:
        data_root_a = {}


    if json3_path is not None and Path(json3_path).exists():
        with open(json3_path, "r", encoding="utf-8") as f:
            data_root = json.load(f)
    else:
        data_root = {}

    # --- 2) Extraer paths internos del JSON (si existen) ---
    print(st.session_state["bay_line_ohl"],'bahia de linea')
    data_project = data_root.get("Project", {})
    civil_data={'Fill Platform [m3]':round(data_root['Total Relleno Plataforma[m3]'],3),
                'Cut Platform [m3]':round(data_root['Total Excavacion Plataforma[m3]'],3),
                'New Roads [km]':data_root['Total Camino[km]'],
                'Existing Roads [km]':data_root['Total Camino Existente [km]']}
    set_data={'High Level Voltage [kV]':st.session_state.get("high_voltage", 220.0),
              'Medium Level Voltage [kV]':st.session_state.get("medium_voltage", 33.0),
              f'Main transformer three windings {st.session_state.get("medium_voltage", 33.0)}/{st.session_state.get("medium_voltage", 33.0)}/{st.session_state.get("high_voltage", 220.0)}':st.session_state["total_trafo"],
              f'Bay of main tranformer {st.session_state.get("high_voltage", 220.0)} [kV]':st.session_state["total_trafo"],
              f'Bay of line {st.session_state.get("high_voltage", 220.0)} [kV]':st.session_state["bay_line_ohl"],
              'Shelter Building':st.session_state["total_shelter"],
              'HV busbar arrangement':len(st.session_state.get('todos_sets'))}
    length_ohl_simple=0
    length_ohl_double=0
    for i in data_root_a:
        length_ohl_simple+=i[f'ohl_simple_circuito_{st.session_state.get("high_voltage", 220.0)}_kV [km]']
        length_ohl_double += i[f'ohl_doble_circuito_{st.session_state.get("high_voltage", 220.0)}_kV [km]']
    ohl_data={'High Level Voltage [kV]':st.session_state.get("high_voltage", 220.0),
              f'{st.session_state.get("high_voltage", 220.0)} [kV] Simple Circuit [km]':length_ohl_simple,
              f'{st.session_state.get("high_voltage", 220.0)} [kV] Double Circuit [km]':length_ohl_double,
              'End of Line Structure': 'pending',
              'Angle structure':'pending',
              'Suspension structure':'pending',
              f'Insulator suspension chain {st.session_state.get("high_voltage", 220.0)}': 'pending',
              f'Insulator anchor chain {st.session_state.get("high_voltage", 220.0)}': 'pending'}
    mv_data={'MV Volatge Level [kV]':st.session_state.get("medium_voltage", 33.0),
                                      'Cable 120mm2 [km]':cable_120,
    'Cable 300mm2 [km]': cable_300,
    'Cable 630mm2 [km]': cable_630 }
    rutas = {
        "Data Project": data_project,
        "Civil": civil_data,
        "MV collector":mv_data ,
        "Substation":set_data ,
        "HV_OHL":ohl_data
    }

    # --- 3) Convertir a DataFrames verticales ---
    hojas = {}
    for nombre_hoja, contenido in rutas.items():

        if isinstance(contenido, dict):
            filas = list(contenido.items())

        elif isinstance(contenido, list):
            # lista de dicts → convertir a texto para mantener formato vertical
            filas = [(f"item_{i}", json.dumps(item, ensure_ascii=False)) for i, item in enumerate(contenido)]

        else:
            # vacío / None
            filas = []

        df = pd.DataFrame(filas, columns=columnas)
        hojas[nombre_hoja] = df

    # --- 4) Escribir Excel ---
    with pd.ExcelWriter(output_xlsx, engine="openpyxl") as writer:
        for nombre_hoja, df in hojas.items():
            df.to_excel(writer, sheet_name=nombre_hoja[:31], index=False)

    return #output_xlsx


# Función auxiliar para cargar JSON seguro
def cargar_json_si_existe(path):
    if path and Path(path).exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
    return None
