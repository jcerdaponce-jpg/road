
import geopandas as gpd
import ezdxf
from shapely.geometry import Polygon, MultiPolygon,LineString

def buffer_caminos_dxf(
    ruta_dxf,
    ancho_camino,
    salida_dxf,
    dxfattribs_contorno={"layer": "Roads", "color": 5, "lineweight": 25},
    linetype_eje="CENTER2",
):
    """
    Genera buffer del camino y mantiene el eje central punteado,
    TODO en la misma capa 'Roads'.
    """

    # 1. Abrir DXF
    doc = ezdxf.readfile(ruta_dxf)
    msp = doc.modelspace()

    buffers = []
    ejes = []

    # 2. Extraer polilíneas
    for e in msp:
        if e.dxftype() in ["LWPOLYLINE", "POLYLINE"]:
            try:
                pts = [(p[0], p[1]) for p in e.get_points()]
            except AttributeError:
                pts = [(v.dxf.location.x, v.dxf.location.y) for v in e.vertices()]

            if len(pts) < 2:
                continue

            linea = LineString(pts)
            ejes.append(pts)   # guardamos eje para dibujarlo luego

            # Buffer
            buffer_geom = linea.buffer(
                ancho_camino / 2.0,
                cap_style=2,      # extremos rectos
                join_style=2,     # esquinas rectas
                resolution=1
            )

            buffers.append(buffer_geom)

    # 3. Crear DXF de salida
    new = ezdxf.new("R2010")
    msp_new = new.modelspace()

    # Asegurar capa Roads
    if "Roads" not in new.layers:
        new.layers.add("Roads", color=5, lineweight=25, linetype="CONTINUOUS")

    # Asegurar tipo de línea DASHED
    if linetype_eje not in new.linetypes:
        new.linetypes.new(
            name=linetype_eje,
            dxfattribs={
                "description": "Dashed line",
                "length": 12.0
            }
        )
    # 4. Dibujar eje punteado
    for pts in ejes:
        msp_new.add_lwpolyline(
            pts,
            close=False,
            dxfattribs={
                "layer": "Roads",
                "color": 2,
                "lineweight": 3,
                "ltscale": 2,
                "linetype": linetype_eje,
            }
        )

    # 5. Dibujar contornos del buffer
    def add_poly(poly):
        exterior = list(poly.exterior.coords)
        msp_new.add_lwpolyline(exterior, close=True, dxfattribs=dxfattribs_contorno)

        for interior in poly.interiors:
            coords = list(interior.coords)
            msp_new.add_lwpolyline(coords, close=True, dxfattribs=dxfattribs_contorno)

    for geom in buffers:
        if isinstance(geom, Polygon):
            add_poly(geom)
        elif isinstance(geom, MultiPolygon):
            for poly in geom.geoms:
                add_poly(poly)

    # 6. Guardar
    new.saveas(salida_dxf)
    print(f"DXF generado: {salida_dxf}")


