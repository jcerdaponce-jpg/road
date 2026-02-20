
from pyproj import Transformer


def utm_lat_lon(x=None, y=None, number=None, huso=None):
    try:
        # Validar que todos los valores estén presentes
        if None in (x, y, number, huso):
            raise ValueError("Faltan uno o más parámetros: x, y, número de zona o huso ('N' o 'S').")

        # Determinar el EPSG según el hemisferio
        if huso.upper() == "S":
            epsg = int(f"327{number}")
        elif huso.upper() == "N":
            epsg = int(f"326{number}")
        else:
            raise ValueError("El huso debe ser 'N' o 'S'.")

        # Crear el transformador
        transformer = Transformer.from_crs(f"EPSG:{epsg}", "EPSG:4326", always_xy=True)

        # Transformar coordenadas
        lon, lat = transformer.transform(x, y)
        return lon, lat

    except Exception as e:
        print(f"Error: {e}")
        return None, None


# Coordenadas UTM (x, y)

