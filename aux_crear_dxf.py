
def crear_dxf(
    lista_de_lineas: List[List[Tuple[float, float]]],
    DXF_FOLDER: str,
    dxf_filename: str = "ruta_ajustada.dxf",
    dxf_layer: str = "Ruta_Ajustada"
) -> Path:
    """
    Exporta las líneas (listas de (x, y)) a un archivo DXF como LWPOLYLINE.
    Retorna el Path del archivo DXF guardado.
    """
    folder_path = Path(DXF_FOLDER)
    folder_path.mkdir(parents=True, exist_ok=True)
    dxf_path = folder_path / dxf_filename

    doc = ezdxf.new(dxfversion="R2010")
    msp = doc.modelspace()

    for filtrados in lista_de_lineas:
        # Sólo exportar polilíneas válidas (>= 2 vértices)
        if len(filtrados) >= 2:
            msp.add_lwpolyline(filtrados, dxfattribs={"layer": 'HV_OHL','color':1, "lineweight": 60, "linetype": "CONTINUOUS", })

    doc.saveas(str(dxf_path))
    print(f"[OK] DXF guardado en: {dxf_path}")