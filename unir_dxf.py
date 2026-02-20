
from pathlib import Path
from typing import List, Tuple, Optional
import ezdxf
from ezdxf.addons import Importer
from ezdxf.math import Matrix44


def unir_dxf_en_un_archivo(
    rutas_dxf: List[str],
    salida_dxf: str,
    prefix_layers: bool = False,
    offsets_xy: Optional[List[Tuple[float, float]]] = None,
    incluir_paperspace: bool = False,
    dxf_version: str = "R2018",
) -> Path:

    if not rutas_dxf:
        raise ValueError("Debes proporcionar al menos una ruta DXF en 'rutas_dxf'.")

    # Documento destino
    doc_dest = ezdxf.new(dxf_version)
    msp_dest = doc_dest.modelspace()

    for i, ruta in enumerate(rutas_dxf):
        ruta_p = Path(ruta)
        print(f"\n--- Procesando {ruta_p} ---")

        if not ruta_p.exists():
            raise FileNotFoundError(f"No existe el DXF: {ruta_p}")

        # Cargar origen
        doc_src = ezdxf.readfile(str(ruta_p))
        msp_src = doc_src.modelspace()

        # === REPARAR CAPAS FALTANTES ===
        usadas = {e.dxf.layer for e in msp_src if hasattr(e.dxf, "layer")}
        definidas = {layer.dxf.name for layer in doc_src.layers}
        faltantes = usadas - definidas

        for capa in faltantes:
            try:
                print(f"[INFO] Creando capa faltante: {capa}")
                doc_src.layers.new(capa)
            except:
                print(f"[WARN] No se pudo crear capa: {capa}")

        # === PREFIJAR CAPAS ===
        if prefix_layers:
            base = ruta_p.stem
            for layer in list(doc_src.layers):
                old = layer.dxf.name
                if old == "0":
                    continue
                new = f"{base}_{old}"
                if old != new and new not in doc_src.layers:
                    try:
                        doc_src.layers.rename(old, new)
                    except:
                        pass

        # Crear importer
        imp = Importer(doc_src, doc_dest)

        # Entidades del MS
        entidades = list(msp_src)

        # === OFFSET OPCIONAL ===
        if offsets_xy and i < len(offsets_xy):
            dx, dy = offsets_xy[i]
            if dx or dy:
                T = Matrix44.translate(dx, dy, 0)
                for e in entidades:
                    try:
                        e.transform(T)
                    except:
                        pass

        # Importar MS
        imp.import_entities(entidades, msp_dest)

        # PaperSpace opcional
        if incluir_paperspace:
            try:
                imp.import_entities(list(doc_src.paper_space()), doc_dest.paper_space())
            except:
                print(f"[WARN] PaperSpace no se pudo importar para {ruta_p}")

        # Finalizar recursos
        imp.finalize()

    # Guardar DXF unificado
    out_path = Path(salida_dxf)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc_dest.saveas(str(out_path))

    print(f"\nDXF unificado generado correctamente → {out_path}")
    return out_path




'''def unir_dxf_en_un_archivo(
    rutas_dxf: List[str],
    salida_dxf: str,
    prefix_layers: bool = False,
    offsets_xy: Optional[List[Tuple[float, float]]] = None,
    incluir_paperspace: bool = False,
    dxf_version: str = "R2018",
) -> Path:

    """
    Unifica varios DXF (p. ej. 3) en un único archivo DXF.

    Parámetros:
        rutas_dxf: lista con rutas a archivos DXF de entrada (p. ej. 3 rutas).
        salida_dxf: ruta destino del DXF unificado.
        prefix_layers: si True, prefija el nombre de las capas con el nombre del archivo
                       de origen (evita colisiones si distintos DXF usan misma capa).
        offsets_xy: lista de (dx, dy) por archivo para desplazar su geometría antes de importar.
                    Longitud debe coincidir con rutas_dxf. Usa metros si tu DXF está en UTM.
        incluir_paperspace: si True, también importa entidades del PaperSpace.
        dxf_version: versión del DXF destino (por defecto 'R2018').

    Retorna:
        Path al archivo DXF unificado.

    Comportamiento:
      - Crea un doc destino nuevo.
      - Por cada DXF origen: importa todas las entidades del ModelSpace y,
        opcionalmente, del PaperSpace, junto con los recursos dependientes.
      - Si offsets_xy está configurado, aplica un desplazamiento (dx, dy) a las
        entidades del origen antes de importarlas.
      - Si prefix_layers=True, renombra las capas del origen con un prefijo
        derivado del nombre del archivo.

    Requisitos:
        pip install ezdxf
    """
    if not rutas_dxf or len(rutas_dxf) == 0:
        raise ValueError("Debes proporcionar al menos una ruta DXF en 'rutas_dxf'.")

    # Documento destino
    doc_dest = ezdxf.new(dxf_version)
    msp_dest = doc_dest.modelspace()

    for i, ruta in enumerate(rutas_dxf):

        ruta_p = Path(ruta)
        if not ruta_p.exists():
            raise FileNotFoundError(f"No existe el DXF: {ruta_p}")

        # Cargar origen; usa recover si esperas DXF “no totalmente válidos”
        doc_src = ezdxf.readfile(str(ruta_p))
        msp_src = doc_src.modelspace()

        # (Opcional) prefijar capas con el nombre del archivo
        if prefix_layers:
            base = ruta_p.stem
            for layer in doc_src.layers:
                # Intenta renombrar capa añadiendo prefijo "archivo:cap"
                try:
                    layer.dxf.name = f"{base}:{layer.dxf.name}"
                except ezdxf.DXFError:
                    pass

        # Preparar importer
        imp = Importer(doc_src, doc_dest)

        # Recoger todas las entidades del modelspace de origen
        entidades = list(msp_src)

        # (Opcional) aplicar desplazamiento (dx, dy) antes de importar
        if offsets_xy and i < len(offsets_xy):
            dx, dy = offsets_xy[i]
            if (dx != 0.0) or (dy != 0.0):
                T = Matrix44.translate(dx, dy, 0.0)
                for e in entidades:
                    # No todas las entidades soportan transform(); la mayoría sí
                    try:
                        e.transform(T)
                    except Exception:
                        # Si alguna entidad no lo soporta, se importa sin desplazamiento
                        pass

        # Importar entidades al destino (resuelve recursos dependientes)
        imp.import_entities(entidades, msp_dest)

        # (Opcional) importar PaperSpace
        if incluir_paperspace:
            ps_src = doc_src.paper_space()
            imp.import_entities(list(ps_src), doc_dest.paper_space())

        # Finalizar: importa todo lo necesario (layers, blocks, etc.)
        imp.finalize()

    # Guardar DXF destino
    out_path = Path(salida_dxf)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    doc_dest.saveas(str(out_path))'''
