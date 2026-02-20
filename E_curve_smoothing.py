import pandas as pd
import csv
import os
import json
from UTM_GEO import utm_lat_lon
from scipy.signal import savgol_filter
import sys
# Cargar el archivo original


def curve_smoothing(data, origen, destino,FOLDER_NAME_1):
    if origen.startswith("camino") and destino.startswith("camino"):
        return  # Termina la función sin hacer nada
    with open(data, "r") as f:
        datos = json.load(f)



    lista_de_puntos = [{"x": punto["x"], "y": punto["y"]} for punto in datos['ruta']]

    # Guardar los puntos originales en CSV
    os.makedirs("CSV_files", exist_ok=True)
    with open(f"{FOLDER_NAME_1}/ruta_para_suavizar.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["x", "y"])
        writer.writeheader()
        for i in lista_de_puntos:
            writer.writerow({"x": i["x"], "y": i["y"]})

    df = pd.read_csv(f"{FOLDER_NAME_1}/ruta_para_suavizar.csv")

    # Número de muestras reales en el DataFrame (por si difiere de lista_de_puntos)
    n = len(df)
    polyorder = 2  # puedes ajustar, pero siempre debe ser < window_length

    # Tu lógica original, pero usando impar: 7 cuando hay suficientes puntos, 3 en caso contrario
    window_target = 7 if len(lista_de_puntos) > 6 else 3  # impar deseado

    def choose_window_length(n, target, polyorder):
        """
        Devuelve una ventana impar válida para savgol_filter:
        - impar
        - >= 3
        - > polyorder
        - <= n
        Si no es posible, devuelve None
        """
        # Limitar al tamaño de la serie
        w = min(target, n if n % 2 == 1 else n - 1)  # impar y <= n
        # Asegurar mínimo 3
        w = max(w, 3 if 3 % 2 == 1 else 5)
        # Asegurar > polyorder
        if w <= polyorder:
            w = polyorder + 1 if (polyorder + 1) % 2 == 1 else polyorder + 2
            # Mantener <= n
            w = min(w, n if n % 2 == 1 else n - 1)

        # Si aún así no hay ventana válida (por ejemplo n < 3)
        if w < 3 or w > n or w % 2 == 0 or w <= polyorder:
            return None
        return w

    window_length = choose_window_length(n, window_target, polyorder)

    # Suavizado por media móvil centrada (buen pre-filtro; min_periods=1 para bordes)
    df['x'] = df['x'].rolling(window=window_length or 3, center=True, min_periods=1).mean()
    df['y'] = df['y'].rolling(window=window_length or 3, center=True, min_periods=1).mean()

    # Relleno de extremos y NaN residuales
    df['x'] = df['x'].ffill().bfill()
    df['y'] = df['y'].ffill().bfill()

    # Savitzky–Golay (si hay ventana válida); usar .to_numpy() evita warnings con dtype
    if window_length is not None:
        df['x'] = savgol_filter(df['x'].to_numpy(), window_length=window_length, polyorder=polyorder, mode='interp')
        df['y'] = savgol_filter(df['y'].to_numpy(), window_length=window_length, polyorder=polyorder, mode='interp')
    # else: con muy pocos puntos, nos quedamos solo con el rolling

    # Si necesitas la lista de diccionarios
    ruta_suavizada = df.to_dict(orient='records')


    # Convertir a coordenadas geográficas
    ruta_final_actualizada = []

    # Agregar punto inicial original
    lon_ini, lat_ini = utm_lat_lon(lista_de_puntos[0]['x'], lista_de_puntos[0]['y'], number=13, huso='N')
    ruta_final_actualizada.append({
        "x": lista_de_puntos[0]['x'],
        "y": lista_de_puntos[0]['y'],
        "lon": lon_ini,
        "lat": lat_ini
    })

    # Agregar puntos suavizados
    for punto in ruta_suavizada:
        lon, lat = utm_lat_lon(punto['x'], punto['y'], number=13, huso='N')
        ruta_final_actualizada.append({
            "x": punto['x'],
            "y": punto['y'],
            "lon": lon,
            "lat": lat
        })

    # Agregar punto final original
    lon_fin, lat_fin = utm_lat_lon(lista_de_puntos[-1]['x'], lista_de_puntos[-1]['y'], number=13, huso='N')
    ruta_final_actualizada.append({
        "x": lista_de_puntos[-1]['x'],
        "y": lista_de_puntos[-1]['y'],
        "lon": lon_fin,
        "lat": lat_fin
    })


    with open(f"{FOLDER_NAME_1}/{origen}_{destino}_final_curve.json", "w") as f:
        json.dump(ruta_final_actualizada, f, indent=4)

    return


def main_curve(path_final,FOLDER_NAME_1):

    with open(path_final, "r") as f:
        data = json.load(f)

    for i in data:

        origen = i["origen"]["nombre"]
        final = i["destino"]["nombre"]

        if origen.startswith("camino_") and final.startswith("camino_"):
            continue
        if origen.startswith("road_survey") and final.startswith("camino_"):
            continue
        if origen.startswith("camino_") and final.startswith("road_survey"):
            continue

        h1 = f"{FOLDER_NAME_1}/{origen}_{final}_ruta_optima.json"
        h2 = f"{FOLDER_NAME_1}/{final}_{origen}_ruta_optima.json"

        if os.path.exists(h1):
            h = h1


        elif os.path.exists(h2):
            h = h2

        else:
            #print(f"No se encontró archivo para {origen} y {final}")
            continue


        curve = curve_smoothing(h, origen, final,FOLDER_NAME_1)


    return







