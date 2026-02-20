
import ezdxf
from ezdxf.addons import Importer
from ezdxf.math import Matrix44
from pathlib import Path

def unir_3_dxf(dxf1: str, dxf2: str, dxf3: str, salida: str,
               offsets=((0,0), (0,0), (0,0)),
               prefix_layers=True):
    """
    Une exactamente 3 archivos DXF en uno solo.

    Parámetros:
        dxf1, dxf2, dxf3: rutas de entrada
        salida: archivo DXF de salida
        offsets: desplazamientos (dx,dy) para cada archivo
        prefix_layers: si True, agrega prefijo a capas del archivo origen
    """

    rutas = [dxf1, dxf2, dxf3]

    # Crear DXF destino
    doc_dest = ezdxf.new("R2018")
    msp_dest = doc_dest.modelspace()

    for i, ruta in enumerate(rutas):
        ruta_p = Path(ruta)
        print(f"\n--- Procesando: {ruta_p} ---")

        if not ruta_p.exists():
            raise FileNotFoundError(f"No existe el DXF: {ruta}")

        try:
            # Cargar usando recover (mejor para planos GIS o CAD antiguos)
            doc_src, auditor = ezdxf.recover(str(ruta_p))
            if auditor.has_fixes:
                print(f"[Aviso] El DXF tenía errores reparados por el auditor.")

        except Exception as e:
            print(f"[ERROR] No se pudo leer {ruta}: {e}")
            raise

        # Prefijo opcional para evitar colisiones de capas
        if prefix_layers:
            base = ruta_p.stem
            for layer in list(doc_src.layers):
                old = layer.dxf.name
                if old == "0":
                    continue
                new = f"{base}_{old}"
                try:
                    doc_src.layers.rename(old, new)
                except Exception:
                    pass  # Si falla, el importer lo resolverá solo

        # Preparar Importer
        imp = Importer(doc_src, doc_dest)

        # Obtener entidades de MS
        msp_src = doc_src.modelspace()
        entidades = list(msp_src)

        # Desplazamiento opcional
        dx, dy = offsets[i]
        if dx != 0 or dy != 0:
            T = Matrix44.translate(dx, dy, 0)
            ok, fail = 0, 0
            for e in entidades:
                try:
                    e.transform(T)
                    ok += 1
                except:
                    fail += 1
            print(f"Transformadas: {ok}, fallidas: {fail}")

        # Importar entidades
        try:
            imp.import_entities(entidades, msp_dest)
        except Exception as e:
            print(f"[ERROR] Fallo importando entidades desde {ruta}: {e}")
            raise

        # Importar capas, bloques y demás
        try:
            imp.finalize()
        except Exception as e:
            print(f"[ERROR] Fallo en finalizar() para {ruta}: {e}")
            raise

    # Guardar
    salida_p = Path(salida)
    salida_p.parent.mkdir(parents=True, exist_ok=True)
    doc_dest.saveas(str(salida_p))
    print(f"\nDXF unificado generado: {salida_p}")

    return salida_p




def unir_2_dxf(dxf1: str, dxf2: str, salida: str,
               offsets=((0,0), (0,0)),
               prefix_layers=True):
    """
    Une 2 DXF en uno solo.
    Ideal para probar si uno de los planos está causando fallos.
    """

    rutas = [dxf1, dxf2]

    print("\n========== INICIO PRUEBA UNIÓN DE 2 DXF ==========\n")

    # Crear DXF destino
    doc_dest = ezdxf.new("R2018")
    msp_dest = doc_dest.modelspace()

    for i, ruta in enumerate(rutas):
        ruta_p = Path(ruta)
        print(f"\n--- Procesando: {ruta_p} ---")

        if not ruta_p.exists():
            raise FileNotFoundError(f"No existe el DXF: {ruta}")

        # Cargar DXF (modo compatibilidad)
        try:
            doc_src = ezdxf.readfile(str(ruta_p))
        except Exception as e:
            print(f"[ERROR] No se pudo leer {ruta}: {e}")
            raise

        # Prefijar capas para evitar colisiones
        if prefix_layers:
            base = ruta_p.stem
            for layer in list(doc_src.layers):
                old = layer.dxf.name
                if old == "0":
                    continue
                new = f"{base}_{old}"
                try:
                    doc_src.layers.rename(old, new)
                except:
                    pass

        # Preparar importer
        imp = Importer(doc_src, doc_dest)

        # Recoger entidades del MS
        msp_src = doc_src.modelspace()
        entidades = list(msp_src)

        # Aplicar offset
        dx, dy = offsets[i]
        if dx != 0 or dy != 0:
            T = Matrix44.translate(dx, dy, 0)
            ok, fail = 0, 0
            for e in entidades:
                try:
                    e.transform(T)
                    ok += 1
                except:
                    fail += 1
            print(f"Transformadas: {ok}, fallidas: {fail}")

        # Importación de entidades
        try:
            imp.import_entities(entidades, msp_dest)
        except Exception as e:
            print(f"[ERROR] Fallo importando {ruta}: {e}")
            raise

        # Finalizar recursos del import
        try:
            imp.finalize()
        except Exception as e:
            print(f"[ERROR] Fallo en finalize() del archivo {ruta}: {e}")
            raise

    # Guardar archivo destino
    salida_p = Path(salida)
    salida_p.parent.mkdir(parents=True, exist_ok=True)
    doc_dest.saveas(str(salida_p))

    print(f"\nDXF unificado generado correctamente → {salida_p}")
    print("\n========== FIN ==========")

    return salida_p


def unir_3_1_dxf(dxf1: str, dxf2: str,dxf3:str, salida: str,
               offsets=((0,0), (0,0)),
               prefix_layers=True):
    """
    Une 2 DXF en uno solo.
    Ideal para probar si uno de los planos está causando fallos.
    """

    rutas = [dxf1, dxf2,dxf3]

    print("\n========== INICIO PRUEBA UNIÓN DE 2 DXF ==========\n")

    # Crear DXF destino
    doc_dest = ezdxf.new("R2018")
    msp_dest = doc_dest.modelspace()

    for i, ruta in enumerate(rutas):
        ruta_p = Path(ruta)
        print(f"\n--- Procesando: {ruta_p} ---")

        if not ruta_p.exists():
            raise FileNotFoundError(f"No existe el DXF: {ruta}")

        # Cargar DXF (modo compatibilidad)
        try:
            doc_src = ezdxf.readfile(str(ruta_p))
        except Exception as e:
            print(f"[ERROR] No se pudo leer {ruta}: {e}")
            raise

        # Prefijar capas para evitar colisiones
        if prefix_layers:
            base = ruta_p.stem
            for layer in list(doc_src.layers):
                old = layer.dxf.name
                if old == "0":
                    continue
                new = f"{base}_{old}"
                try:
                    doc_src.layers.rename(old, new)
                except:
                    pass

        # Preparar importer
        imp = Importer(doc_src, doc_dest)

        # Recoger entidades del MS
        msp_src = doc_src.modelspace()
        entidades = list(msp_src)

        # Aplicar offset
        dx, dy = offsets[i]
        if dx != 0 or dy != 0:
            T = Matrix44.translate(dx, dy, 0)
            ok, fail = 0, 0
            for e in entidades:
                try:
                    e.transform(T)
                    ok += 1
                except:
                    fail += 1
            print(f"Transformadas: {ok}, fallidas: {fail}")

        # Importación de entidades
        try:
            imp.import_entities(entidades, msp_dest)
        except Exception as e:
            print(f"[ERROR] Fallo importando {ruta}: {e}")
            raise

        # Finalizar recursos del import
        try:
            imp.finalize()
        except Exception as e:
            print(f"[ERROR] Fallo en finalize() del archivo {ruta}: {e}")
            raise

    # Guardar archivo destino
    salida_p = Path(salida)
    salida_p.parent.mkdir(parents=True, exist_ok=True)
    doc_dest.saveas(str(salida_p))

    print(f"\nDXF unificado generado correctamente → {salida_p}")
    print("\n========== FIN ==========")

    return salida_p

unir_3_1_dxf(  "rutas_optimas.dxf", "camino_existente.dxf",    "PLATFORM.dxf",    "unido_3_2.dxf",    offsets=((0,0), (0,0), (0,0)),   # si estás en UTM 13N
    prefix_layers=True)
