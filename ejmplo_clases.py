from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

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

def set_type(set:str,x,y):
    if set=='1_bay_line':
        x_out=x+53.0
        y_out=y-7.5
        x_in=0.0
        y_in=0.0
    elif set=='2_bay_line_opposite':
        x_in=x-53.84
        y_in=y-37.38
        x_out=x+55.5
        y_out=y+20
    elif set=='2_bay_line_same':
        x_in = x + 53.0
        y_in = y - 25.5
        x_out = x + 53.0
        y_out = y + -7.5
    return x_in, y_in, x_out, y_out

@dataclass
class Connection:
    origen: Any
    destino: Any
    orientacion_origen: Optional[str] = None
    orientacion_destino: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)



@dataclass
class EndpointInfo:
    set_id: Any              # ID o nombre de la SET
    utm_x: float = 0.0       # coordenada UTM X real
    utm_y: float = 0.0       # coordenada UTM Y real
    ohl_x_in: float = 0.0       # coordenada OHL desplazada
    ohl_y_in: float = 0.0       # coordenada OHL desplazada
    ohl_x_out: float = 0.0  # coordenada OHL desplazada
    ohl_y_out: float = 0.0  # coordenada OHL desplazada
    orientacion: float=0.0
    set_type: Optional[str] = None


class SET:
    def __init__(self, id, WTGs, utm_x, utm_y, POWER):
        self.id = id
        self.WTGs = WTGs
        self.power_set = round(float((WTGs) * POWER), 1)
        self.utm_x = float(utm_x)
        self.utm_y = float(utm_y)

    def coord_set(self):
        return (self.utm_x, self.utm_y)

    def resume(self):
        return {
            "SET": self.id,
            "N_WTGs": self.WTGs,
            "Power_SET": self.power_set,
            "UTM_X": self.utm_x,
            "UTM_Y": self.utm_y,
            "WTGs": self.WTGs,
        }
tipo='decentralized'


uno=SET('SET_1',10,10,2,7)
dos=SET('SET_2',25,10,45,7)
tres=SET('SET_3',35,10,45,7)

total_power=uno.power_set+dos.power_set+tres.power_set

conect_uno=Connection(origen=uno.id,destino=dos.id,orientacion_origen='N',orientacion_destino='W')
conect_dos=Connection(origen=tres.id,destino=dos.id,orientacion_origen='N',orientacion_destino='W')
print(type(uno.coord_set()))
x_in,y_in,x_out,y_out=set_type('1_bay_line',uno.utm_x,uno.utm_y)
print(x_in,y_in,x_out,y_out)
