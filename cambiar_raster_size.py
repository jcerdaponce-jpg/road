
from osgeo import gdal

src = "COLORADA.tif"
dst = "COLORADA_px1m.tif"


from osgeo import gdal, osr
import csv
import os
from typing import Optional, Tuple, List
import pandas as pd

def elevation_at_xy_ds(ds, x: float, y: float, interp: str = "nearest") -> Tuple[Optional[float], bool]:
    """
    Devuelve elevación en (x,y) usando el dataset GDAL ya abierto.
    Retorna: (elevation, is_nodata)
    """
    gt = ds.GetGeoTransform()
    origin_x, px_w, rot_x, origin_y, rot_y, px_h = gt

    band = ds.GetRasterBand(1)
    nodata = band.GetNoDataValue()

    # Transformación general (soporta rasters rotados)
    det = px_w * px_h - rot_x * rot_y
    col_f = ((x - origin_x) * px_h - (y - origin_y) * rot_x) / det
    row_f = ((y - origin_y) * px_w - (x - origin_x) * rot_y) / det

    if interp == "nearest":
        col = int(round(col_f))
        row = int(round(row_f))
        if not (0 <= col < ds.RasterXSize and 0 <= row < ds.RasterYSize):
            return (None, True)
        val = band.ReadAsArray(col, row, 1, 1)
        elev = float(val[0, 0])
        return (None if (nodata is not None and elev == nodata) else elev, (nodata is not None and elev == nodata))

    elif interp == "bilinear":
        c0 = int(col_f)
        r0 = int(row_f)
        c1 = c0 + 1
        r1 = r0 + 1
        if not (0 <= c0 < ds.RasterXSize and 0 <= c1 < ds.RasterXSize and
                0 <= r0 < ds.RasterYSize and 0 <= r1 < ds.RasterYSize):
            return (None, True)
        window = band.ReadAsArray(c0, r0, 2, 2).astype(float)  # (2,2)
        if nodata is not None and any(window.flatten() == nodata):
            # cae a nearest del centro si hay nodata en vecinos
            col = int(round(col_f))
            row = int(round(row_f))
            if not (0 <= col < ds.RasterXSize and 0 <= row < ds.RasterYSize):
                return (None, True)
            elev = float(band.ReadAsArray(col, row, 1, 1)[0, 0])
            return (None if (nodata is not None and elev == nodata) else elev, (nodata is not None and elev == nodata))
        dc = col_f - c0
        dr = row_f - r0
        elev = (window[0,0] * (1-dc) * (1-dr) +
                window[0,1] * dc * (1-dr) +
                window[1,0] * (1-dc) * dr +
                window[1,1] * dc * dr)
        return (float(elev), False)
    else:
        raise ValueError("interp debe ser 'nearest' o 'bilinear'.")

def get_epsg_from_dataset(ds) -> Optional[int]:
    """Intenta obtener el EPSG del dataset a partir del WKT."""
    srs = osr.SpatialReference()
    srs.ImportFromWkt(ds.GetProjection())
    try:
        srs.AutoIdentifyEPSG()
    except Exception:
        pass
    auth = srs.GetAuthorityCode(None)
    return int(auth) if auth is not None else None

def transform_point(x: float, y: float, epsg_src: int, epsg_dst: int) -> Tuple[float, float]:
    """Transforma (x,y) de EPSG origen a EPSG destino usando OSR."""
    src = osr.SpatialReference(); src.ImportFromEPSG(epsg_src)
    dst = osr.SpatialReference(); dst.ImportFromEPSG(epsg_dst)
    ct = osr.CoordinateTransformation(src, dst)
    X, Y, _ = ct.TransformPoint(x, y)
    return X, Y

def get_heights_from_csv(
    raster_path: str,
    csv_path: str,
    x_col: str = "Posicion_X",
    y_col: str = "Posicion_Y",
    id_col: Optional[str] = "WTG",
    epsg_points: Optional[int] = None,
    interp: str = "bilinear",
    out_csv: Optional[str] = None
) -> pd.DataFrame:
    """
    Lee un CSV con coordenadas y devuelve un DataFrame con elevaciones.
    - Si epsg_points es None, asume que las coordenadas están en el mismo CRS que el raster.
    - interp: 'nearest' o 'bilinear'
    - out_csv: si se especifica, guarda el resultado en ese CSV.
    Retorna: DataFrame con columnas [id_col?, x, y, elev, is_nodata]
    """
    gdal.UseExceptions()
    ds = gdal.Open(raster_path, gdal.GA_ReadOnly)
    if ds is None:
        raise RuntimeError(f"No se pudo abrir el raster: {raster_path}")

    epsg_raster = get_epsg_from_dataset(ds)
    # Cargar CSV
    rows: List[dict] = []
    with open(csv_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                x = float(row[x_col]); y = float(row[y_col])
                label = row[id_col] if id_col and id_col in row else None
                # Transformar si epsg_points está definido y difiere del raster
                if epsg_points and epsg_raster and epsg_points != epsg_raster:
                    x_r, y_r = transform_point(x, y, epsg_src=epsg_points, epsg_dst=epsg_raster)
                else:
                    x_r, y_r = x, y
                elev, is_nd = elevation_at_xy_ds(ds, x_r, y_r, interp=interp)
                rows.append({
                    id_col if id_col else "id": label,
                    "x_input": x, "y_input": y,
                    "x_raster": x_r, "y_raster": y_r,
                    "elev_m": elev, "is_nodata": bool(is_nd)
                })
            except Exception as e:
                rows.append({
                    id_col if id_col else "id": row.get(id_col, None),
                    "x_input": row.get(x_col, None), "y_input": row.get(y_col, None),
                    "x_raster": None, "y_raster": None,
                    "elev_m": None, "is_nodata": True,
                    "error": f"{type(e).__name__}: {e}"
                })
    df = pd.DataFrame(rows)
    if out_csv:
        df.to_csv(out_csv, index=False, encoding="utf-8")
    return df


df_alturas = get_heights_from_csv(
    raster_path="COLORADA.tif",
    csv_path="wtg_coords.csv",
    x_col="Posicion_X",
    y_col="Posicion_Y",
    id_col="WTG",
    epsg_points=None,        # mismo CRS que el raster
    interp="bilinear",
    out_csv="wtg_alturas.csv"
)
print(df_alturas.head())



###REDUCIR RESOLUCION......####
'''gdal.Warp(
    dst, src,
    xRes=1, yRes=1,               # tamaño de píxel objetivo (m)
    resampleAlg="bilinear",         # DEM continuo
    multithread=True,
    warpOptions=["NUM_THREADS=ALL_CPUS"],
    creationOptions=[
        "TILED=YES","BLOCKXSIZE=512","BLOCKYSIZE=512",
        "COMPRESS=LZW","PREDICTOR=2","BIGTIFF=IF_SAFER"
    ]
)
print("Salida:", dst)'''

'''csv_path = "wtg_coords.csv"      # CSV con columnas Posicion_X, Posicion_Y
raster_src = "COLORADA.tif"      # Raster grande a recortar
buffer_m = 3000                  # buffer en metros
raster_dst = "COLORADA_recorte.tif"  # salida recortada

# === Leer coordenadas UTM del CSV ===
x_vals = []
y_vals = []

with open(csv_path, newline='', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    # Se esperan columnas "Posicion_X" y "Posicion_Y"
    for row in reader:
        try:
            x = float(row["Posicion_X"])  # <- del CSV provisto
            y = float(row["Posicion_Y"])  # <- del CSV provisto
            x_vals.append(x)
            y_vals.append(y)
        except Exception:
            # ignora filas con valores no numéricos
            pass

if not x_vals or not y_vals:
    raise RuntimeError("No se encontraron coordenadas válidas en el CSV (Posicion_X/Posicion_Y).")

min_x = min(x_vals)
max_x = max(x_vals)
min_y = min(y_vals)
max_y = max(y_vals)

# === Extensión mínima envolvente (bounding box) ===
bbox_width = max_x - min_x
bbox_height = max_y - min_y

# Hacemos el cuadro con buffer:
# 1) centro del bbox
cx = (min_x + max_x) / 2.0
cy = (min_y + max_y) / 2.0

# 2) semilado del cuadrado:
#    tomamos el semilado como max(semi-ancho, semi-alto) + buffer
half_side = max(bbox_width, bbox_height) / 2.0 + buffer_m

# 3) límites del cuadrado
win_min_x = cx - half_side
win_max_x = cx + half_side
win_min_y = cy - half_side
win_max_y = cy + half_side

# === Abrir raster fuente y validar CRS/GeoTransform ===
gdal.UseExceptions()
ds = gdal.Open(raster_src, gdal.GA_ReadOnly)
if ds is None:
    raise RuntimeError(f"No se pudo abrir el raster: {raster_src}")

gt = ds.GetGeoTransform()
proj_wkt = ds.GetProjection()

# Nota: este recorte usa coordenadas del CRS del raster (UTM).
# Para gdal.Translate con 'projWin', el orden es: [ulx, uly, lrx, lry]
ulx = win_min_x
uly = win_max_y
lrx = win_max_x
lry = win_min_y

# === Recortar con gdal.Translate (projWin) ===
# Creamos salida tilada y comprimida para achicar tamaño final.
translate_opts = gdal.TranslateOptions(
    projWin=[ulx, uly, lrx, lry],
    format="GTiff",
    creationOptions=[
        "TILED=YES",
        "BLOCKXSIZE=512",
        "BLOCKYSIZE=512",
        "COMPRESS=LZW",
        "PREDICTOR=2",
        "BIGTIFF=IF_SAFER"
    ]
)

dst_ds = gdal.Translate(raster_dst, ds, options=translate_opts)
if dst_ds is None or not os.path.exists(raster_dst):
    raise RuntimeError("gdal.Translate falló: no se generó el raster recortado.")

print("Recorte listo:")
print(f" - Entrada : {raster_src}")
print(f" - Salida  : {raster_dst}")
print(f" - Cuadro   : UL({ulx:.2f}, {uly:.2f})  LR({lrx:.2f}, {lry:.2f})")'''

