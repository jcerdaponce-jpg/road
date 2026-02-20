import ezdxf


def mover_y_rotar_bloque(
        ruta_dxf,
        nombre_bloque,
        nueva_posicion,
        nueva_rotacion,
        salida_dxf):
    # 1. Cargar el DXF
    doc = ezdxf.readfile(ruta_dxf)
    msp = doc.modelspace()

    # 2. Buscar referencias al bloque
    for insercion in msp.query(f'INSERT[name=="{nombre_bloque}"]'):
        # Mostrar datos actuales
        #print("Posición original:", insercion.dxf.insert)
        #print("Rotación original:", insercion.dxf.rotation)

        # 3. Asignar nueva posición y rotación
        insercion.dxf.insert = nueva_posicion  # (x, y, z)
        insercion.dxf.rotation = nueva_rotacion  # grados

    # 4. Guardar resultado
    doc.saveas(salida_dxf)
    #print(f"DXF actualizado guardado como: {salida_dxf}")

'''ruta_dxf="assets/SETs/set_1s_1d.dxf"
nombre_bloque="set_1s_1d"
nueva_posicion=(368075.6,4160952,0)
nueva_rotacion=180
#E=0,N=90
# grados
salida_dxf="mapa_modificado_1.dxf"
#mover_y_rotar_bloque(ruta_dxf, nombre_bloque, nueva_posicion, nueva_rotacion, salida_dxf)
ruta_dxf="assets/SETs/set_2s_1d.dxf"
nombre_bloque="set_2s_1d"
nueva_posicion=(368075.6,4160952,0)
nueva_rotacion=180                 # grados
salida_dxf="mapa_modificado_2.dxf"

#mover_y_rotar_bloque(ruta_dxf, nombre_bloque, nueva_posicion, nueva_rotacion, salida_dxf)

ruta_dxf="assets/SETs/set_2s_2d.dxf"
nombre_bloque="set_2s_2d"
nueva_posicion=(368075.6,4160952,0)
nueva_rotacion=180               # grados
salida_dxf="mapa_modificado_3.dxf"

#mover_y_rotar_bloque(ruta_dxf, nombre_bloque, nueva_posicion, nueva_rotacion, salida_dxf)'''