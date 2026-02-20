
import math

def punto_recto_en_C(A, B):
    """
    Dados dos puntos A y B que forman la hipotenusa,
    genera los dos posibles puntos C donde el ángulo recto está en C.
    """

    x1, y1 = A
    x2, y2 = B

    # Punto medio M
    mx = (x1 + x2) / 2
    my = (y1 + y2) / 2

    # Vector AB
    vx = x2 - x1
    vy = y2 - y1

    # Longitud de AB
    L = math.hypot(vx, vy)
    if L == 0:
        raise ValueError("A y B no pueden ser iguales.")

    # Distancia desde M hacia C
    d = L / 2

    # Vector unitario perpendicular a AB
    ux = -vy / L
    uy =  vx / L

    # Dos posibles puntos C
    C1 = (mx + ux * d, my + uy * d)
    C2 = (mx - ux * d, my - uy * d)

    return C1, C2


def angulo_vector_direccion(x2, y2, x3, y3):
    """
    Calcula el ángulo entre:
      - Vector fijo (0,0) -> (0,1)
      - Vector real (x2,y2) -> (x3,y3)
    Retorna el ángulo en grados (0° a 180°).
    """

    # Vector fijo hacia arriba
    v1x, v1y = 0, 1

    # Vector real
    v2x = x3 - x2
    print(v2x)
    v2y = y3 - y2

    # Producto punto
    dot = v1x * v2x + v1y * v2y

    # Magnitudes
    mag1 = 1  # |(0,1)| = 1
    mag2 = math.hypot(v2x, v2y)

    if mag2 == 0:
        raise ValueError("El vector real tiene longitud cero.")

    # Coseno del ángulo
    cosang = dot / (mag1 * mag2)
    cosang = max(-1, min(1, cosang))  # evitar errores numéricos

    # Ángulo en grados
    ang = math.degrees(math.acos(cosang))

    return ang

x1=369664.4334380204
y1=4157926.1922907317
x2=381823.956641456
y2=4171129.8699602615
h=punto_recto_en_C((x1,y1),(x2,y2))
print(h)