from functools import lru_cache

from osgeo import gdal

import numpy as np

def saber_info_raster(archivo):
    ruta = "COLORADA.tif"
    ds = gdal.Open(ruta)
    proj = ds.GetProjection()
    if ds is None:
        print("No se pudo abrir el raster.")
    else:
        # GeoTransform: [originX, pixelWidth, 0, originY, 0, pixelHeight]
        gt = ds.GetGeoTransform()
        pixel_width = gt[1]  # tamaño del píxel en X (metros si UTM)
        pixel_height = abs(gt[5])  # tamaño del píxel en Y (positivo)

        print(f"Tamaño de píxel: {pixel_width:.3f} m × {pixel_height:.3f} m")
    return

def cambiar_formato(entrada,salida):
    src = gdal.Open(entrada)
    gdal.Translate(salida, src, format="GTiff")



    return

def recortar_por_coords(entrada, salida, ulx, uly, lrx, lry):
    gdal.Translate(
        salida,
        entrada,
        projWin=[ulx, uly, lrx, lry],  # (xmin, ymax, xmax, ymin)
        format="GTiff"
    )


entrada ="GIS/cdm.tif"
salida = "GIS/cmd_recortado.tif"
ulx=339777.067
uly=4190621.86
lrx=421616.633
lry=4135652.502
cambiar_formato(entrada,salida)

