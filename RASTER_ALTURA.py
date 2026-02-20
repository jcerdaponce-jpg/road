
from osgeo import gdal, osr
import sys

def obtener_elevacion(raster_path, x, y):
    """
    Devuelve la elevación del raster en la coordenada (x, y).
    Las coordenadas deben estar en el mismo sistema de referencia que el raster.
    """

    # Abrir raster
    ds = gdal.Open(raster_path)
    if ds is None:
        raise RuntimeError(f"No se pudo abrir el raster: {raster_path}")

    # Banda (asumimos banda 1 para DEM)
    band = ds.GetRasterBand(1)
    nodata = band.GetNoDataValue()

    # Transformación georreferenciada del raster
    gt = ds.GetGeoTransform()
    # gt = (x_min, pixel_width, 0, y_max, 0, pixel_height negativa)

    # Convertir coordenadas reales (x,y) → índice de píxel (col, row)
    col = int((x - gt[0]) / gt[1])
    row = int((y - gt[3]) / gt[5])  # gt[5] suele ser negativo

    # Validar que la coordenada cae dentro del raster
    if not (0 <= col < ds.RasterXSize and 0 <= row < ds.RasterYSize):
        return None

    # Leer el valor de elevación
    elev = band.ReadAsArray(col, row, 1, 1)[0, 0]

    # Comprobar NoData
    if nodata is not None and elev == nodata:
        return None

    return float(elev)
# -*- coding: utf-8 -*-
# Imprime información tipo `gdalinfo` de un raster usando solo la API de GDAL en Python.
# Uso:
#   python info_raster.py colorada.tif
#
# También puedes importar la función `imprimir_info_raster(ruta)` en tu código.



def info_raster(raster_path):
    gdal.UseExceptions()

    ds = gdal.Open(raster_path, gdal.GA_ReadOnly)
    if ds is None:
        raise RuntimeError(f"No se pudo abrir el raster: {raster_path}")

    print("====================================")
    print(f"Archivo: {raster_path}")
    print("====================================")

    # Tamaño
    print(f"Tamaño: {ds.RasterXSize} x {ds.RasterYSize} px, Bandas: {ds.RasterCount}")

    # GeoTransform
    gt = ds.GetGeoTransform()
    x_min = gt[0]
    px_w = gt[1]
    rot_x = gt[2]
    y_max = gt[3]
    rot_y = gt[4]
    px_h = gt[5]

    x_max = x_min + ds.RasterXSize * px_w
    y_min = y_max + ds.RasterYSize * px_h

    print("\nGeoTransform:")
    print(f"  Origen (xmin, ymax): ({x_min:.3f}, {y_max:.3f})")
    print(f"  Pixel Size (dx, dy): ({px_w:.3f}, {px_h:.3f})")
    print(f"  Rotación: ({rot_x}, {rot_y})")
    print("  Extensión:")
    print(f"    X: [{x_min:.3f}, {x_max:.3f}]")
    print(f"    Y: [{y_min:.3f}, {y_max:.3f}]")

    # Proyección
    print("\nCRS:")
    srs = osr.SpatialReference()
    srs.ImportFromWkt(ds.GetProjectionRef())
    auth = srs.GetAuthorityCode(None)
    if auth:
        print(f"  EPSG:{auth}")
    print(f"  WKT: {ds.GetProjectionRef()}")

    # Bandas
    for i in range(1, ds.RasterCount + 1):
        b = ds.GetRasterBand(i)
        print(f"\nBanda {i}:")
        print(f"  Tipo: {gdal.GetDataTypeName(b.DataType)}")
        nodata = b.GetNoDataValue()
        print(f"  NoData: {nodata}")

        # Estadísticas
        try:
            stats = b.GetStatistics(True, True)
            print(f"  Min={stats[0]:.3f}, Max={stats[1]:.3f}, Mean={stats[2]:.3f}, Std={stats[3]:.3f}")
        except:
            print("  No se pudieron computar estadísticas")

    ds = None


# Ejemplo:
if __name__ == "__main__":
    raster=("COLORADA_px1m.tif")
    info_raster(raster)
    x = 578431.0699
    y = 940982.88

    z = obtener_elevacion(raster, x, y)
    print("Elevación:", z)



