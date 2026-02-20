import math
def orientation_to_angle_2(ori: str) -> float:
    mapping = {
        "N": 0,#90,
        "NE": 45,
        "E": -90,
        "SE": -45,
        "S": 180,
        "SW": -45,
        "W": -90,
        "NW":180-45
    }
    return mapping.get(ori, None)  # retorna None si no existe
def orientation_to_angle(ori: str) -> float:
    mapping = {
        "N": 90,
        "NE": 45,
        "E": 0,
        "SE": 315,
        "S": 270,
        "SW": 225,
        "W": 180,
        "NW": 135
    }
    return mapping.get(ori, None)  # retorna None si no existe

def rotate_point(xc, yc, xp, yp, angle_deg):
    theta = math.radians(angle_deg)
    xr = xc + (xp - xc) * math.cos(theta) - (yp - yc) * math.sin(theta)
    yr = yc + (xp - xc) * math.sin(theta) + (yp - yc) * math.cos(theta)
    return xr, yr

def coord_in_out(set:str,x,y,angle:float):

    if set == '1_bay_line':
        x_out = x + 53.0
        y_out = y - 7.5
        x_in  = x_out
        y_in  = y_out
        x_out_aux=x_out-10
        y_out_aux=y_out
        x_in_aux=x_in-10
        y_in_aux=y_in
    elif set == '2_bay_line_opposite':
        x_in  = x - 53.84
        y_in  = y + 37.38
        x_out = x + 55.5
        y_out = y + 20
        x_in_aux=x_in+10
        y_in_aux=y_in
        x_out_aux=x_out+10
        y_out_aux=y_out
    elif set == '2_bay_line_same':
        x_in  = x + 53.0
        y_in  = y - 25.5
        x_out = x + 53.0
        y_out = y - 7.5
        x_out_aux=x_out+10
        y_out_aux=y_out
        x_in_aux=x_in-10
        y_in_aux=y_in
    # Aplicar rotación a x_in, y_in, x_out, y_out

    x_in_r,  y_in_r  = rotate_point(x, y, x_in,  y_in,  angle)
    x_out_r, y_out_r = rotate_point(x, y, x_out, y_out, angle)
    x_in_aux_r, y_in_aux_r = rotate_point(x, y, x_in_aux, y_in_aux, angle)
    x_out_aux_r, y_out_aux_r = rotate_point(x, y, x_out_aux, y_out_aux, angle)
    return x_in_r, y_in_r, x_out_r, y_out_r, x_in_aux_r, y_in_aux_r, x_out_aux_r, y_out_aux_r

def path_file(type:str):
    if type=='1_bay_line':
        file="assets/SETs/set_1s_1d.dxf"
        bloque='set_1s_1d'
    elif type=='2_bay_line_opposite':
        file="assets/SETs/set_2s_2d.dxf"
        bloque='set_2s_2d'
    elif type=='2_bay_line_same':
        file="assets/SETs/set_2s_1d.dxf"
        bloque='set_2s_1d'

    return file,bloque