# -*- coding: utf-8 -*-

import os, json, glob, datetime

from dataclasses import dataclass, field, asdict
import pandas as pd
import math
from excel_report import  crear_excel_4_hojas_vertical_desde_rutas
from unir_dxf import unir_dxf_en_un_archivo
from math import hypot
from ezdxf.math import bulge_to_arc, arc_angle_span_rad, Vec2
from ezdxf.path import make_path

from typing import Any, Dict, List, Optional, Tuple
import plotly.express as px
from streamlit_folium import st_folium
import base64

from funcion_auxiliares_a import *
from external_functions import *



from MV_APP.MV_CABLE import main_set_medium_voltage


from DEM_FILE import dem_file

# 1) Intentar desde session/config/env:
raster_path = dem_file(required=False)

from PLOT_OHL import plot_ohl
from folium.plugins import Draw, MeasureControl, LocateControl, Geocoder, MarkerCluster
HAS_PYPROJ=True; HAS_EZDXF=True; HAS_PANDAS=True
try:
    from pyproj import CRS, Transformer
except Exception:
    HAS_PYPROJ=False
try:
    import ezdxf
except Exception:
    HAS_EZDXF=False
try:
    import pandas as pd
except Exception:
    HAS_PANDAS=False
WTG_DB_AVAILABLE=True
try:
    from wtg_db import (load_db, save_db, get_models, get_compatible_towers, get_power_variants, get_blade_diameter, get_foundation_diameter, get_platform, set_platform_for_tower)
except Exception:
    WTG_DB_AVAILABLE=False

#=================================================
#FOMATS


# --- CSS para igualar altura con selectbox ---
st.markdown("""
    <style>
    .big-box {
        border: 1px solid rgba(49,51,63,0.2);
        padding: 10px;
        border-radius: 4px;
        height: 48px;
        display: flex;
        align-items: center;
        font-size: 16px;
    }
    </style>
""", unsafe_allow_html=True)


st.markdown("""
<style>
/* Fuerza que todas las columnas alineen arriba */
div[data-testid="column"] {
    display: flex;
    flex-direction: column;
    justify-content: flex-start;
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<style>



:root {
    /* Colores corporativos Nordex */
    --nordex-blue: #135091;
    --nordex-blue-dark: #00508F;

    /* Texto */
    --text-dark: #333;
    --text-light: #555;

    /* Fondo general */
    --background-light: #f8f9fc;
}

/* Aplicar fuente global */
html, body, [class*="css"] {
    font-family: 'Montserrat', sans-serif;
}



.main_title {
    text-align: left;
    font-size: 35px;
    font-weight: 300;
    color: #135091 !important;
    font-family: 'Montserrat' !important;
   
}
.sub_title {
    text-align: left;
    font-size: 35px;
    font-weight: 300;
    color: #135091 !important;
    font-family: 'Monserrat' !important;

}
.sub_sub_title {
    text-align: left;
    font-size: 15px;
    font-weight: 150;
    color: #135091 !important;
    font-family: 'Monserrat' !important;

}
</style>
""", unsafe_allow_html=True)
##========================================================

if "power_wtg" not in st.session_state:
    st.session_state["power_wtg"] = 0.1
if "todos_sets" not in st.session_state:
    st.session_state["todos_sets"]=[]
if 'set_ids' not in st.session_state:
    st.session_state["set_ids"]=[]
if 'conexiones' not in st.session_state:
    st.session_state["conexiones"]=[]
if 'set_central_value' not in st.session_state:
    st.session_state["set_central_value"]=[]
if 'total_trafo' not in st.session_state:
    st.session_state["total_trafo"]=[]
if 'total_shelter' not in st.session_state:
    st.session_state["total_shelter"]=[]
if 'bay_line_ohl' not in st.session_state:
    st.session_state['bay_line_ohl']=[]

st.session_state['max_mv_current']=2500





@dataclass
class WTG:
    id: str
    utm_x: float
    utm_y: float
    power: Optional[float] = None

    def coord_wtg(self) -> Tuple[float, float]:
        return (self.utm_x, self.utm_y)

    def resume_wtg(self) -> dict:
        return {
            "wtg": self.id,
            "UTM_X": self.utm_x,
            "UTM_Y": self.utm_y,
            "power": self.power
        }


def get_ip_location():
    try:
        r = requests.get("http://ip-api.com/json/").json()
        return r.get("lat"), r.get("lon")
    except:
        return None, None



def load_icon_data_uri(icon_bytes: bytes, filename_hint: str = "./assets/WTG_PICTURE.png") -> str:
    """Convierte icono a data-URI base64 (admite .ico/.png/.jpg)."""
    mime = "image/x-icon"
    ext = os.path.splitext(filename_hint.lower())[1]
    if ext in [".png"]:
        mime = "image/png"
    elif ext in [".jpg", ".jpeg"]:
        mime = "image/jpeg"
    b64 = base64.b64encode(icon_bytes).decode("ascii")
    return f"data:{mime};base64,{b64}"

def load_json_safe(path: str):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        st.error(f"No se encontró el archivo: {path}")
    except json.JSONDecodeError as e:
        st.error(f"JSON inválido ({path}): {e}")
    return None

def latest_file(pattern: str):
    files = sorted(glob.glob(pattern))
    return files[-1] if files else None

def normalize_s_mva(raw):
    """Si s_mva > 100, asumimos kVA y lo pasamos a MVA."""
    if raw is None: return None
    return (raw/1000.0) if (float(raw) > 100.0) else float(raw)
def utm_to_wgs84(huso:int, hemisferio:str, easting:float, northing:float):
    from pyproj import CRS, Transformer
    south = hemisferio.lower().startswith('s')
    crs_utm = CRS.from_dict({'proj':'utm','zone':int(huso),'south':south})
    crs_wgs = CRS.from_epsg(4326)
    tf = Transformer.from_crs(crs_utm, crs_wgs, always_xy=True)
    lon, lat = tf.transform(easting, northing)
    return lon, lat

def make_transformer_from_epsg(epsg_src:int):
    if not HAS_PYPROJ: return None
    from pyproj import CRS, Transformer
    crs_src = CRS.from_epsg(int(epsg_src)); crs_wgs = CRS.from_epsg(4326)
    return Transformer.from_crs(crs_src, crs_wgs, always_xy=True)

def make_transformer_from_utm(huso:int, hemisferio:str, datum:str='WGS84'):
    if not HAS_PYPROJ: return None
    from pyproj import CRS, Transformer
    south = hemisferio.lower().startswith('s'); huso=int(huso)
    if datum.upper()=='ETRS89':
        if (28<=huso<=38) and not south:
            epsg_src=25800+huso; crs_src=CRS.from_epsg(epsg_src)
        else:
            crs_src=CRS.from_dict({'proj':'utm','zone':huso,'south':south,'datum':'WGS84'})
    else:
        crs_src=CRS.from_dict({'proj':'utm','zone':huso,'south':south,'datum':'WGS84'})
    crs_wgs=CRS.from_epsg(4326)
    return Transformer.from_crs(crs_src, crs_wgs, always_xy=True)

def transform_xy(transformer,x,y):
    if transformer is None: return None
    lon,lat=transformer.transform(x,y); return lon,lat

def get_current_utm_epsg():
    try:
        huso=int(st.session_state.get('ui_huso')) if st.session_state.get('ui_huso') else None
    except Exception:
        huso=None
    hemi=st.session_state.get('ui_hemisferio') or 'Norte'
    if huso and 1<=huso<=60:
        return (32700+huso) if str(hemi).lower().startswith('s') else (32600+huso)
    return 32613

def get_tf_wgs84_to_utm():
    if not HAS_PYPROJ: return None, get_current_utm_epsg()
    from pyproj import Transformer
    epsg_dest=get_current_utm_epsg()
    try:
        tf=Transformer.from_crs('EPSG:4326', f'EPSG:{epsg_dest}', always_xy=True); return tf, epsg_dest
    except Exception:
        return None, epsg_dest

def _coords_to_utm_list(coords, tf):
    out=[]
    for lng,lat in coords:
        x,y=tf.transform(float(lng), float(lat)); out.append([x,y])
    return out

def _geom_to_utm(geom, tf):
    if not geom or 'type' not in geom: return geom
    gtype=geom['type']
    if gtype=='Point':
        lng,lat=geom['coordinates']; x,y=tf.transform(float(lng), float(lat)); return {'type':'Point','coordinates':[x,y]}
    elif gtype=='LineString':
        return {'type':'LineString','coordinates':_coords_to_utm_list(geom['coordinates'], tf)}
    elif gtype=='Polygon':
        rings=[]
        for ring in geom['coordinates']: rings.append(_coords_to_utm_list(ring, tf))
        return {'type':'Polygon','coordinates':rings}
    return geom

def fc_to_utm(fc_wgs):
    tf, epsg=get_tf_wgs84_to_utm()
    if tf is None: return None, epsg
    feats=[]
    for feat in fc_wgs.get('features',[]):
        geom=feat.get('geometry'); props=(feat.get('properties') or {}).copy(); props['utm_epsg']=epsg
        feats.append({'type':'Feature','properties':props,'geometry':_geom_to_utm(geom, tf)})
    return {'type':'FeatureCollection','features':feats,'meta':{'crs':f'EPSG:{epsg}'}}, epsg

def save_camino_and_register(fc, folder):
    out_wgs_a, out_utm_a = save_fc_dual(fc, folder, 'camino')
    init = st.session_state; init.setdefault('paths', {})
    init['paths']['camino_wgs_geojson'] = out_wgs_a
    if out_utm_a:
        init['paths']['camino_utm_geojson'] = out_utm_a
    return out_wgs_a, out_utm_a


def save_restricciones_and_register(fc, folder):
    out_wgs_b, out_utm_b = save_fc_dual(fc, folder, 'restricciones')

    # Acceso al session_state
    state = st.session_state
    state.setdefault("paths", {})

    # Registrar rutas internas
    state["paths"]["restricciones_wgs_geojson"] = out_wgs_b

    if out_utm_b:
        state["paths"]["restricciones_utm_geojson"] = out_utm_b
        # ruta principal = UTM si existe
        state["restricciones_path"] = out_utm_b
    else:
        # Si no hay UTM, usar WGS
        state["restricciones_path"] = out_wgs_b

    return out_wgs_b, out_utm_b


def save_ruad_survey_and_register(fc, folder):
    out_wgs_c, out_utm_c = save_fc_dual(fc, folder, 'ruad_survey')
    init = st.session_state; init.setdefault('paths', {})
    init['paths']['ruad_survey_wgs_geojson'] = out_wgs_c
    if out_utm_c:
        init['paths']['ruad_survey_utm_geojson'] = out_utm_c
    return out_wgs_c, out_utm_c

def save_grid_on_and_register(fc, folder):
    out_wgs_d, out_utm_d = save_fc_dual(fc, folder, 'grid_on')
    init = st.session_state
    init.setdefault('paths', {})
    init['paths']['grid_on_wgs_geojson'] = out_wgs_d
    if out_utm_d:
        init['paths']['grid_on_wgs_geojson'] = out_utm_d
    return out_wgs_d, out_utm_d







def save_fc_dual(fc_wgs, folder, prefix):
    ts=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    out_wgs=os.path.join(folder, f'{prefix}_{ts}.geojson')
    with open(out_wgs,'w',encoding='utf-8') as f: json.dump(fc_wgs,f,ensure_ascii=False,indent=2)
    fc_utm, epsg = fc_to_utm(fc_wgs); out_utm=None
    if fc_utm is not None:
        out_utm=os.path.join(folder, f'{prefix}_{ts}_utm{epsg}.geojson')
        with open(out_utm,'w',encoding='utf-8') as f: json.dump(fc_utm,f,ensure_ascii=False,indent=2)

    return out_wgs, out_utm
def dxf_to_geojson(dxf_path: str, transformer):
    if not HAS_EZDXF:
        raise RuntimeError("ezdxf no está instalado. Ejecuta: pip install ezdxf")
    doc = ezdxf.readfile(dxf_path)
    msp = doc.modelspace()
    features = []
    def add_feature(geometry, props=None):
        features.append({"type": "Feature", "properties": props or {}, "geometry": geometry})
    # LINE
    for e in msp.query("LINE"):
        p1 = transform_xy(transformer, e.dxf.start.x, e.dxf.start.y)
        p2 = transform_xy(transformer, e.dxf.end.x, e.dxf.end.y)
        if p1 and p2:
            add_feature({"type": "LineString", "coordinates": [list(p1), list(p2)]},
                        {"layer": e.dxf.layer, "type": "LINE", "closed": False})
    # LWPOLYLINE
    for e in msp.query("LWPOLYLINE"):
        pts = [transform_xy(transformer, p[0], p[1]) for p in e.get_points()]
        pts = [p for p in pts if p]
        if not pts:
            continue
        if e.closed and len(pts) >= 3:
            add_feature({"type": "Polygon", "coordinates": [[list(p) for p in pts] + [list(pts[0])]]},
                        {"layer": e.dxf.layer, "type": "LWPOLYLINE", "closed": True})
        else:
            add_feature({"type": "LineString", "coordinates": [[p[0], p[1]] for p in pts]},
                        {"layer": e.dxf.layer, "type": "LWPOLYLINE", "closed": False})
    # POLYLINE
    for e in msp.query("POLYLINE"):
        pts = []
        try:
            for v in e.vertices:
                p = transform_xy(transformer, v.dxf.location.x, v.dxf.location.y)
                if p:
                    pts.append(p)
        except Exception:
            pts = []
        if not pts:
            continue
        closed = bool(e.is_closed)
        if closed and len(pts) >= 3:
            add_feature({"type": "Polygon", "coordinates": [[list(p) for p in pts] + [list(pts[0])]]},
                        {"layer": e.dxf.layer, "type": "POLYLINE", "closed": True})
        else:
            add_feature({"type": "LineString", "coordinates": [[p[0], p[1]] for p in pts]},
                        {"layer": e.dxf.layer, "type": "POLYLINE", "closed": False})
    # HATCH simplificado
    for e in msp.query("HATCH"):
        try:
            for path in e.paths:
                pts = []
                for edge in path.edges:
                    if edge.TYPE == "LineEdge":
                        p1 = transform_xy(transformer, edge.start[0], edge.start[1])
                        p2 = transform_xy(transformer, edge.end[0], edge.end[1])
                        if p1 and p2:
                            if not pts:
                                pts.append(p1)
                            pts.append(p2)
                if len(pts) >= 3:
                    add_feature({"type": "Polygon", "coordinates": [[list(p) for p in pts] + [list(pts[0])]]},
                                {"layer": e.dxf.layer, "type": "HATCH", "closed": True})
        except Exception:
            pass
    return {"type": "FeatureCollection", "features": features}

def get_platform_fallback(db: dict, torre: str):
    """Devuelve la plataforma de forma robusta:
    - Si existe db['towers'][torre]['platform'], úsalo.
    - Si existe db['tower_platform'][torre'], úsalo tal cual.
    """
    if not isinstance(db, dict) or not torre:
        return None
    # 1) Estructura tipo: {"towers": {"TC120N": {"platform": {...}}}}
    plat = (db.get('towers', {}).get(torre, {}) or {}).get('platform')
    if plat:
        return plat
    # 2) Estructura tipo: {"tower_platform": {"TC120N": {...}}}
    plat = db.get('tower_platform', {}).get(torre)
    if plat:
        return plat
    return None

# ===== DWG -> DXF =====
def convert_dwg_to_dxf_oda(dwg_path: str, out_dir: str, out_version: str = "ACAD2018", oda_exec_path: str = None) -> str:
    oda_cmd = oda_exec_path if oda_exec_path else shutil.which("ODAFileConverter")
    if not oda_cmd:
        raise RuntimeError("No se encuentra ODAFileConverter. Instálalo o provee la ruta en el campo correspondiente.")
    with tempfile.TemporaryDirectory() as src_dir, tempfile.TemporaryDirectory() as tgt_dir:
        src_dwg = os.path.join(src_dir, os.path.basename(dwg_path))
        shutil.copy2(dwg_path, src_dwg)
        cmd = [oda_cmd, src_dir, tgt_dir, "*.dwg", out_version, "0", "0", "DXF"]
        subprocess.run(cmd, check=True)
        out_dxf = os.path.join(tgt_dir, os.path.splitext(os.path.basename(dwg_path))[0] + ".dxf")
        if not os.path.exists(out_dxf):
            raise RuntimeError("Conversión ODA falló: no se generó DXF.")
        final_dxf = os.path.join(out_dir, os.path.basename(out_dxf))
        shutil.copy2(out_dxf, final_dxf)
        return final_dxf
def convert_dwg_to_dxf_libredwg(dwg_path: str, out_dir: str, dxf_version: str = "r2013") -> str:
    dwg2dxf = shutil.which("dwg2dxf")
    if not dwg2dxf:
        raise RuntimeError("No se encuentra 'dwg2dxf' (LibreDWG) en PATH.")
    out_dxf = os.path.join(out_dir, os.path.splitext(os.path.basename(dwg_path))[0] + ".dxf")
    cmd = [dwg2dxf, "--as", dxf_version, "-y", "-o", out_dxf, dwg_path]
    subprocess.run(cmd, check=True)
    if not os.path.exists(out_dxf):
        raise RuntimeError("Conversión LibreDWG falló: no se generó DXF.")
    return out_dxf





def save_raster_and_register(uploaded_file, raster_folder):

    ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    session_id = st.session_state.get('session_id', 'no_session')
    name, ext = os.path.splitext(uploaded_file.name)
    safe_name = re.sub(r'[^a-zA-Z0-9._-]+', '-', name).strip('-').lower()

    # Nombre final: original + session_id + timestamp
    out_filename = f"{safe_name}_{session_id}{ext}"
    out_path = os.path.join(raster_folder, out_filename)

    # Guardar archivo
    with open(out_path, 'wb') as f:
        f.write(uploaded_file.read())

    # Registrar en session_state
    st.session_state.setdefault('paths', {})
    st.session_state['paths']['raster_file'] = out_path


    return out_path


# === Utilidades simples ===
def utm_zone_from_lon(lon: float) -> int:
    """Calcula HUSO UTM (1..60) a partir de la longitud en grados."""
    # UTM: zone = floor((lon + 180) / 6) + 1
    import math
    z = int(math.floor((lon + 180.0) / 6.0) + 1)
    return max(1, min(60, z))

def wgs84_utm_label(zone: int, hemi: str) -> str:
    """Etiqueta legible del sistema: 'WGS84 UTM Z13 Norte/Sur'."""
    hemi_norm = 'Norte' if str(hemi).lower().startswith('n') else 'Sur'
    return f"WGS84 UTM Z{int(zone)} {hemi_norm}"

def hemisferio_from_lat(lat: float) -> str:
    """Hemisferio estimado: Norte si lat>=0, Sur si lat<0."""
    return 'Norte' if lat >= 0 else 'Sur'



# =============================================================================
# Icono data-URI
# =============================================================================


# --- UI ---


st.set_page_config(
    page_icon='assets/ndx_logo.png',
    layout='wide',
    page_title='Nx Layout Designer'
)

col1,col2 = st.columns([1,1])
with col1:
    st.image("assets/ndx_logo.png", width=350)
    st.markdown("<div style='height:5px;'></div>", unsafe_allow_html=True)
    st.markdown(
        "<h2 class='main_title'>Nx Layout Designer</h2>",
        unsafe_allow_html=True
    )




st.markdown("<div style='height:40px;'></div>", unsafe_allow_html=True)

SALIDAS_DIR='salidas'
ASSETS_DIR='assets'
os.makedirs(SALIDAS_DIR, exist_ok=True)
os.makedirs(ASSETS_DIR, exist_ok=True)








init=st.session_state
for k,v in {'cad_fc_list':[], 'other_fc_list':[], 'excel_points':[], 'excel_point_labels':[], 'layers_restr':set(), 'layers_cam':set(), 'niveles_tension':{}}.items():
    init.setdefault(k,v)
init.setdefault('proj_name','_sin_nombre_'); init.setdefault('session_id', datetime.datetime.now().strftime('%Y%m%d_%H%M%S'))
slug=re.sub(r'[^a-zA-Z0-9]+','-', (init.get('proj_name') or '_sin_nombre_').strip()).strip('-').lower()
seed=f"{slug}-{init.get('session_id','')}"; proj_hash=hashlib.sha1(seed.encode('utf-8')).hexdigest()[:8]
init.setdefault('project_id', f"{slug}-{proj_hash}"); init.setdefault('map_center',[0,0]); init.setdefault('map_zoom',3)

st.sidebar.markdown( "<h2 class='main_title'>Proyecto</h2>", unsafe_allow_html=True)

init['proj_name']=st.sidebar.text_input( "Nombre Proyecto",value=init.get('proj_name','_sin_nombre_'), key='proj_name_input') or init['proj_name']
slug=re.sub(r'[^a-zA-Z0-9]+','-', init['proj_name'].strip()).strip('-').lower(); seed=f"{slug}-{init.get('session_id','')}"; proj_hash=hashlib.sha1(seed.encode('utf-8')).hexdigest()[:8]
init['project_id']=f"{slug}-{proj_hash}"
st.sidebar.caption(f"Session ID: {init['session_id']}"); st.sidebar.caption(f"Project ID: {init['project_id']}")
init.setdefault('paths', {})
session_id_=init['session_id']




#from coordenadas_huso_expander import render_coordenadas_huso_sidebar

#render_coordenadas_huso_sidebar(    init=st.session_state,    HAS_PYPROJ=HAS_PYPROJ,    utm_zone_from_lon=utm_zone_from_lon,    utm_to_wgs84=utm_to_wgs84,    make_transformer_from_epsg=make_transformer_from_epsg,)




with st.sidebar.expander('Coordenadas / HUSO (para centrar el mapa)', expanded=False):
    coord_mode = st.radio('Modo de entrada', [ "UTM (HUSO)","Lat/Lon (WGS84)"], index=0, key='ui_center_mode')

    if coord_mode == "Lat/Lon (WGS84)":
        # Entrada directa en grados decimales
        lat = st.number_input('Latitud', value=float(init['map_center'][0]), format='%.6f', key='ui_lat_wgs')
        lon = st.number_input('Longitud', value=float(init['map_center'][1]), format='%.6f', key='ui_lon_wgs')
        zoom = st.slider('Zoom', 2, 18, value=int(init['map_zoom']), key='ui_zoom_wgs')

        # Info de referencia (no cambia CRS, solo ayuda visual)
        huso_est = utm_zone_from_lon(lon)

        hemi_est = hemisferio_from_lat(lat)
        st.caption(f"HUSO estimado: **{huso_est}**, Hemisferio estimado: **{hemi_est}** · Sistema: **{wgs84_utm_label(huso_est, hemi_est)}**")

        # ✅ Botón para centrar el mapa también en este modo
        if st.button('Aplicar centro al mapa', type='primary', key='btn_apply_center_wgs'):
            init['map_center'] = [lat, lon]
            init['map_zoom'] = int(zoom)
            init['map_huso'] = huso_est
            init['map_hemisferio'] = hemi_est
            init['map_datum'] = 'WGS84'

            st.rerun()

    else:
        # Modo UTM WGS84 explícito: HUSO + Hemisferio (sin EPSG)
        # Por defecto, tomamos el HUSO estimado desde la longitud actual y hemisferio desde la latitud actual:
        huso_center = st.number_input(
            'HUSO UTM (1–60)', min_value=1, max_value=60,
            value=int(utm_zone_from_lon(float(init['map_center'][1]))),
            step=1, key='ui_huso'
        )
        hemisferio_center = st.selectbox('Hemisferio', ["Norte", "Sur"],
                                         index=0 if hemisferio_from_lat(float(init['map_center'][0])) == 'Norte' else 1,
                                         key='ui_hemisferio')
        zoom = st.slider('Zoom', 2, 18, value=int(init['map_zoom']), key='ui_zoom_utm')

        # Si tienes pyproj, permitimos convertir E/N reales a WGS84
        use_en = HAS_PYPROJ and st.checkbox('Usar Easting/Northing (pyproj)', value=False, key='ui_use_en')

        if use_en:
            easting_c  = st.number_input('Easting (m)',  value=500000.0, step=1.0, key='ui_easting')
            northing_c = st.number_input('Northing (m)', value=4730000.0, step=1.0, key='ui_northing')
            try:
                lon, lat = utm_to_wgs84(huso_center, hemisferio_center, easting_c, northing_c)
                st.success(f"Centro convertido: lat={lat:.6f}, lon={lon:.6f} · Sistema: {wgs84_utm_label(huso_center, hemisferio_center)}")
            except Exception as e:
                st.error(f"UTM→WGS84 falló: {e}")
                # Fallback simple: meridiano central del HUSO + latitud actual (aprox)
                lon = -183 + 6 * int(huso_center)
                lat = float(init['map_center'][0])
                st.info('Usando meridiano central del HUSO como fallback por error en la conversión.')
        else:
            # Aproximación: meridiano central del HUSO y latitud que indiques
            lon = -183 + 6 * int(huso_center)  # λ0 = 6·Z − 183
            lat = st.number_input('Latitud aproximada', value=float(init['map_center'][0]),
                                  format='%.6f', key='ui_lat_utm')
            st.info(f'Usando meridiano central del HUSO {huso_center} como longitud. Sistema: {wgs84_utm_label(huso_center, hemisferio_center)}')


        # ✅ Botón para aplicar el centro en modo UTM
        if st.button('Aplicar centro al mapa', type='primary', key='btn_apply_center_utm'):
            init['map_center'] = [lat, lon]
            init['map_zoom'] = int(zoom)
            # Si te interesa guardar el sistema actual, puedes añadir:
            init['map_crs'] = wgs84_utm_label(huso_center, hemisferio_center)
            init['map_huso'] = huso_center
            init['map_hemisferio'] = hemisferio_center
            init['map_datum'] = 'WGS84'
            init['data_project']={
                'project_name': init.get('proj_name'),
                'session_id':init.get('session_id'),
                'project_id': init.get('project_id'),
                'huso':init.get('map_huso'),
                'hemisferio':hemisferio_center}
            base_cfg = os.path.join('salidas',
                                    st.session_state.get('proj_name', '_sin_nombre_'),
                                    st.session_state.get('project_id', 'pid'),
                                    'config')
            os.makedirs(base_cfg, exist_ok=True)
            cfg_path = os.path.join(base_cfg, 'data.json')

            with open(cfg_path, 'w', encoding='utf-8') as f:
                json.dump(init['data_project'], f, ensure_ascii=False, indent=2)

            st.rerun()


#with st.sidebar.expander('Niveles de tensión', expanded=False):
            #   mt_kv = st.number_input('Media tensión (kV)', min_value=1.0, step=0.1,
            #               value=float(init.get('niveles_tension', {}).get('media_tension_kv', 34.5)),
    #               key='ui_mt_kv')
    #at_kv = st.number_input('Alta tensión (kV)', min_value=35.0, step=1.0,
            #                       value=float(init.get('niveles_tension', {}).get('alta_tension_kv', 220.0)),
    #               key='ui_at_kv')

    #epsg_utm = get_current_utm_epsg()
    #huso_val = int(str(epsg_utm)[-2:]) if (32601 <= epsg_utm <= 32760) else None
    #hemi_val = 'Sur' if 32701 <= epsg_utm <= 32760 else 'Norte'


    # 1) APLICAR: guarda niveles + timestamp dentro del diccionario
    #if st.button('Aplicar niveles de tensión', type='primary', key='btn_apply_tension'):
        #   ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')  # <-- crea un timestamp
        #init['niveles_tension'] = {
            #   'media_tension_kv': float(mt_kv),
            #'alta_tension_kv': float(at_kv),
            #'utm_epsg': int(epsg_utm),
            #'huso': huso_val,
            #'hemisferio': hemi_val,
            #'proj_name': init.get('proj_name'),
            #'project_id': init.get('project_id'),
            #'session_id': init.get('session_id'),
            #'timestamp': ts  # <-- lo guardas aquí
        #}

        #nt = init['niveles_tension']
        #base = os.path.join('salidas', init.get('proj_name', '_sin_nombre_'),
        #                   init.get('project_id', 'pid'), 'config')
        #os.makedirs(base, exist_ok=True)

        # Nombre de archivo con session_id y timestamp del diccionario
        #fpath_a = os.path.join(base, f"niveles_tension_{init.get('session_id')}.json")
        #with open(fpath_a, 'w', encoding='utf-8') as f:
        #   json.dump(nt, f, ensure_ascii=False, indent=2)

        #init.setdefault('paths', {})
        #init['paths']['niveles_tension_json'] = fpath_a

        #st.success('Niveles de tensión aplicados y guardados.')
        #st.info(f'Archivo guardado: {fpath_a}')




import os
import tempfile

from osgeo import gdal
from folium.raster_layers import ImageOverlay

from localtileserver import TileClient, get_folium_tile_layer
import folium




def add_raster_overlay_to_map(m,raster_path: str, layer_name: str = "DEM (overlay)", opacity: float = 0.75,
                              max_png_pixels: int = 4096,  # controla tamaño final del PNG
                              cache_mb: int = 512):
    """
    Reproyecta un DEM (cualquiera) a EPSG:4326 y lo añade como overlay al mapa Folium.
    Optimizado para rasters grandes: usa WarpedVRT + downsample a PNG de tamaño controlado.
    """

    if not raster_path or not os.path.exists(raster_path):
        return False, "Raster no encontrado."

    try:
        # 1) Ajustes GDAL para rendimiento/estabilidad
        gdal.UseExceptions()  # Para capturar errores como excepciones
        gdal.SetConfigOption("GDAL_CACHEMAX", str(cache_mb))       # MB de caché
        gdal.SetConfigOption("GDAL_NUM_THREADS", "ALL_CPUS")       # Multihilo donde aplique
        gdal.SetConfigOption("CPL_LOG_ERRORS", "YES")              # Log de errores (opcional)

        tmpdir = tempfile.mkdtemp()
        warped_vrt = os.path.join(tmpdir, "dem_wgs84.vrt")         # reproyectado, pero como VRT
        png_out = os.path.join(tmpdir, "dem_wgs84.png")

        # 2) Reproyección a VRT (ligero). Evita crear un TIF enorme.
        warp_opts = gdal.WarpOptions(
            dstSRS="EPSG:4326",
            resampleAlg="bilinear",
            multithread=True,
            errorThreshold=0.125  # tolerancia por defecto de gdalwarp
        )

        # Formato VRT para que sea "virtual"
        ds_vrt = gdal.Warp(warped_vrt, raster_path, options=warp_opts, format="VRT")
        if ds_vrt is None:
            return False, "GDAL.Warp (VRT) falló: no se pudo reproyectar el DEM a EPSG:4326."

        # 3) Sacamos dimensiones del VRT reproyectado para decidir el downsample
        width = ds_vrt.RasterXSize
        height = ds_vrt.RasterYSize

        # Calcula nueva resolución destino controlando lado mayor
        if max(width, height) > max_png_pixels:
            if width >= height:
                out_w = max_png_pixels
                out_h = int(height * (max_png_pixels / float(width)))
            else:
                out_h = max_png_pixels
                out_w = int(width * (max_png_pixels / float(height)))
        else:
            out_w, out_h = width, height

        # 4) Convertir a PNG (downsampleado). Suficiente para overlay en Folium.
        translate_opts = gdal.TranslateOptions(
            format="PNG",
            width=out_w,
            height=out_h
        )
        ds_png = gdal.Translate(png_out, ds_vrt, options=translate_opts)

        if ds_png is None or not os.path.exists(png_out):
            return False, "GDAL.Translate falló: no se pudo convertir DEM reproyectado a PNG."

        # 5) Bounds (EPSG:4326) del VRT reproyectado
        gt = ds_vrt.GetGeoTransform()
        # gt: [minx, px_w, 0, maxy, 0, px_h]
        min_lon = gt[0]
        max_lat = gt[3]
        px_w = gt[1]
        px_h = gt[5]  # casi siempre negativo
        max_lon = min_lon + width * px_w
        min_lat = max_lat + height * px_h  # si px_h < 0, resta

        overlay = ImageOverlay(
            name=layer_name,
            image=png_out,
            bounds=[[min_lat, min_lon], [max_lat, max_lon]],
            opacity=opacity,
            interactive=True,
            cross_origin=False,
            zindex=4
        )
        overlay.add_to(m)
        return True, f"Overlay añadido (PNG {out_w}×{out_h}). Fuente reproyectada vía VRT: {warped_vrt}"

    except Exception as e:
        # Mensaje claro de error
        return False, f"Fallo añadiendo overlay: {type(e).__name__}: {e}"



m = folium.Map(
    location=init['map_center'],
    zoom_start=init['map_zoom'],
    tiles='Esri.WorldImagery',
    control_scale=True
)


# Reinyectar overlay raster si existe en session_state
#ro = st.session_state.get("raster_overlay")
#if ro:
#   ok, msg = add_raster_overlay_to_map(
#       m,
#       ro["path"],
#       layer_name=ro.get("layer_name", "DEM (overlay)"),
#       opacity=ro.get("opacity", 0.75)
#   )
#   if not ok:
#       st.warning(f"Overlay raster no cargado: {msg}")

MeasureControl(position='topleft').add_to(m)
LocateControl(auto_start=False, **{'setView':False,'flyTo':False,'keepCurrentZoom':True}).add_to(m)
Geocoder(collapsed=True, position='topleft').add_to(m)
Draw(export=False, position='topleft', draw_options={'polyline':True,'polygon':{'allowIntersection':False,'showArea':True},'rectangle':True,'circle':False,'circlemarker':False,'marker':True}, edit_options={'poly':{'allowIntersection':False}}).add_to(m)

st.sidebar.markdown('## Cargar datos')
TMP_DIR=os.path.join(SALIDAS_DIR,'_tmp')
os.makedirs(TMP_DIR, exist_ok=True)

proy_dir=os.path.join(SALIDAS_DIR, init['proj_name'])
restr_dir=os.path.join(proy_dir,'restricciones')
cam_dir=os.path.join(proy_dir,'caminos')
ruad_dir=os.path.join(proy_dir,'ruad_survey')
gridon_dir=os.path.join(proy_dir,'grid_on')
puntos_dir=os.path.join(proy_dir,'puntos')
JSON_FILES=os.path.join(proy_dir,'JSON_FILES')
RASTER_DIR = os.path.join(SALIDAS_DIR, init['proj_name'], 'RASTER_FILE')
DXF_FILES=os.path.join(proy_dir,'DXF_FILES')
EXCEL_FILES=os.path.join(proy_dir,'EXCEL_FILES')
for d in (proy_dir, restr_dir, cam_dir, ruad_dir, gridon_dir,puntos_dir,JSON_FILES,RASTER_DIR,
          DXF_FILES,EXCEL_FILES): os.makedirs(d, exist_ok=True)



# --- [3] Sidebar desplegable para cargar el archivo raster DEM ---

with st.sidebar.expander('Raster DEM', expanded=False):
    st.caption("Sube tu raster (DEM) y lo guardamos en /RASTER_DIR del proyecto.")

    # Subir archivo raster
    raster_file = st.file_uploader(
        'Subir raster DEM',
        type=['tif', 'tiff', 'asc', 'img', 'vrt', 'png', 'jpg', 'jpeg'],
        key='ui_raster_file'
    )

    # Botón para guardar el raster

    if st.button('Guardar Raster', key='btn_save_raster'):
        if raster_file is None:
            st.warning('Primero selecciona un archivo raster.')
        else:
            try:
                saved_path = save_raster_and_register(raster_file, RASTER_DIR)
                st.success(f'Raster guardado: {saved_path}')



                # === NUEVO: persistir en config.json del proyecto ===
                base_cfg = os.path.join('salidas',
                                        st.session_state.get('proj_name', '_sin_nombre_'),
                                        st.session_state.get('project_id', 'pid'),
                                        'config')
                os.makedirs(base_cfg, exist_ok=True)
                cfg_path = os.path.join(base_cfg, 'config.json')

                # Cargar (si existe), actualizar 'raster_file' y guardar
                data = {}
                if os.path.exists(cfg_path):
                    try:
                        with open(cfg_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                    except Exception:
                        data = {}
                data['raster_file'] = str(saved_path)

                with open(cfg_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                # ================================================
                client = TileClient(os.path.abspath(saved_path))
                nasadem_layer = get_folium_tile_layer(
                    client,
                    name="DEM (NASADEM/GeoTIFF)",
                    overlay=True,  # para que aparezca como overlay con checkbox
                    show=True,
                    opacity=0.6
                )

                # 3) Añadir la capa al mapa
                m.add_child(nasadem_layer)

                # 4) Añadir control de capas (si no lo tenías)
                folium.LayerControl(collapsed=False).add_to(m)

                #ok, msg = add_raster_overlay_to_map(m, saved_path, layer_name="DEM (overlay)", opacity=0.75)
                #if ok:
                 #   st.info(msg)
                #else:
                 #   st.warning(msg)

            except Exception as e:
                st.error(f'Error guardando raster: {e}')

    # Mostrar ruta registrada (si existe)
    #raster_path_reg = st.session_state.get('paths', {}).get('raster_file')
    #if raster_path_reg:
     #   st.info(f'Raster actual: {raster_path_reg}')
    #ruta_raste = raster_path_reg  # alias local si lo necesitas

    #if st.button('Guardar Raster', key='btn_save_raster'):
    #   if raster_file is None:
    #       st.warning('Primero selecciona un archivo raster.')
    #   else:
    #       try:
    #           saved_path = save_raster_and_register(raster_file, RASTER_DIR)
    #           st.success(f'Raster guardado: {saved_path}')

    #       except Exception as e:
    #           st.error(f'Error guardando raster: {e}')

    # Mostrar ruta registrada (si existe)
    #raster_path_reg = st.session_state.get('paths', {}).get('raster_file')
    #if raster_path_reg:
    #   st.info(f'Raster actual: {raster_path_reg}')

    # ruta_raste=raster_path_reg



default_huso = init.get('map_huso', 13)
default_hemi = init.get('map_hemisferio', 'Norte')
default_datum = init.get('map_datum', 'WGS84')

with st.sidebar.expander('Excel/CSV (puntos)', expanded=False):
    excel_file=st.file_uploader('Subir Excel/CSV', type=['xlsx','xls','csv'], key='ui_pts_file')
    if excel_file is not None:
        if not HAS_PANDAS:
            st.error('Instala pandas: pip install pandas openpyxl xlrd')
        else:
            try:
                fname=excel_file.name.lower()
                if fname.endswith('.xlsx'): df_points=pd.read_excel(excel_file, engine='openpyxl')
                elif fname.endswith('.xls'):
                    try: df_points=pd.read_excel(excel_file, engine='xlrd')
                    except Exception: st.error('Para .xls instala xlrd: pip install xlrd'); df_points=None
                else:
                    sep=st.text_input('Separador CSV', value=',', key='ui_pts_sep'); df_points=pd.read_csv(excel_file, sep=sep)
                if df_points is None or df_points.empty: st.warning('El archivo está vacío o no se pudo leer.')
                else:
                    st.success(f'Archivo cargado ({len(df_points)} filas, {len(df_points.columns)} columnas)')
                    with st.sidebar.expander('Vista previa (10 filas)'): st.write(df_points.head(10))
                    cols=list(df_points.columns)
                    name_col = st.selectbox('Columna nombre/id (opcional)', ['(ninguna)'] + cols, index=0,
                                            key='ui_pts_namecol')
                    x_col=st.selectbox('Columna X/Easting o Longitud', cols, key='ui_pts_xcol')
                    y_col=st.selectbox('Columna Y/Northing o Latitud', cols, key='ui_pts_ycol')

                    map_huso = init.get('map_huso')

                    map_hemi = init.get('map_hemisferio')
                    map_datum = init.get('map_datum', 'WGS84')

                    # Determinar índice inicial del radio
                    if map_huso:  # significa que el usuario centró en UTM
                        idx_coordmode = 1  # UTM
                    else:
                        idx_coordmode = 0  # WGS84

                    coord_mode_pts=st.radio('CRS de los puntos', ['Lat/Lon (WGS84)','UTM (HUSO)','EPSG'], index=idx_coordmode, key='ui_pts_coordmode')
                    transformer_pts=None
                    if coord_mode_pts=='UTM (HUSO)':
                        if HAS_PYPROJ:

                            huso_pts = st.number_input(
                                'HUSO',
                                min_value=1,
                                max_value=60,
                                value=int(default_huso),
                                step=1,
                                key='ui_pts_huso'
                            )

                            hemisferio_pts = st.selectbox(
                                'Hemisferio',
                                ['Norte', 'Sur'],
                                index=0 if default_hemi == 'Norte' else 1,
                                key='ui_pts_hemisferio'
                            )

                            datum_pts = st.selectbox(
                                'Datum',
                                ['ETRS89', 'WGS84'],
                                index=1 if default_datum == 'WGS84' else 0,
                                key='ui_pts_datum'
                            )

                            if datum_pts=='ETRS89' and (not (28<=int(huso_pts)<=38) or hemisferio_pts=='Sur'):
                                st.error('ETRS89 sólo Europa husos 28–38 Norte. Para HUSO 13 usa WGS84 (EPSG:32613) o cambia a HUSO 30 (EPSG:25830).'); transformer_pts=None
                            else:
                                transformer_pts=make_transformer_from_utm(int(huso_pts), hemisferio_pts, datum_pts)
                        else:
                            st.error('pyproj requerido para UTM. Instala: pip install pyproj')
                    elif coord_mode_pts=='EPSG':
                        if HAS_PYPROJ:
                            epsg_pts=st.number_input('EPSG origen', value=32613, step=1, key='ui_pts_epsg'); transformer_pts=make_transformer_from_epsg(int(epsg_pts))
                        else:
                            st.error('pyproj requerido para EPSG. Instala: pip install pyproj')
                    use_icon_excel=st.checkbox('Usar icono WTG_PICTURE.png', value=False, key='ui_pts_iconchk')
                    default_icon_path=os.path.join(ASSETS_DIR,'WTG_PICTURE.png')
                    icon_path_text=st.text_input('Ruta del icono', value=default_icon_path, key='ui_pts_iconpath')
                    icon_upload=st.file_uploader('O subir icono', type=['ico','png','jpg','jpeg'], key='ui_pts_iconupload')
                    icon_size_px=st.number_input('Tamaño icono (px)', min_value=10, max_value=20, value=20, key='ui_pts_iconsize')
                    if st.button('Añadir puntos al mapa', key='btn_excel_add'):
                        names=df_points[name_col] if name_col!='(ninguna)' else pd.Series(['']*len(df_points))
                        x_vals=pd.to_numeric(df_points[x_col], errors='coerce'); y_vals=pd.to_numeric(df_points[y_col], errors='coerce')
                        if coord_mode_pts!='Lat/Lon (WGS84)' and transformer_pts is None:
                            st.error('CRS seleccionado requiere pyproj válido. Ajusta HUSO/Datum o usa EPSG.')
                        else:

                            # === CACHEAR ICONO SOLO UNA VEZ ===
                            if "excel_icon_cache" not in st.session_state:
                                st.session_state["excel_icon_cache"] = {}

                            # KEY = icono + tamaño
                            icon_key = f"{icon_path_text}_{icon_size_px}"

                            if icon_key in st.session_state["excel_icon_cache"]:
                                icon_uri = st.session_state["excel_icon_cache"][icon_key]
                            else:
                                icon_uri = None
                                if use_icon_excel:
                                    try:
                                        if icon_upload is not None:
                                            icon_uri = load_icon_data_uri(icon_upload.read(),
                                                                          filename_hint=icon_upload.name)
                                        elif os.path.exists(icon_path_text):
                                            with open(icon_path_text, 'rb') as f:
                                                icon_uri = load_icon_data_uri(f.read(), filename_hint=os.path.basename(
                                                    icon_path_text))
                                        st.session_state["excel_icon_cache"][icon_key] = icon_uri
                                    except Exception as e:
                                        st.warning(f"No se pudo cargar icono: {e}")

                            added=discarded=0; labels=[]
                            for i,(vx,vy,nm) in enumerate(zip(x_vals,y_vals,names)):
                                if pd.isna(vx) or pd.isna(vy): discarded+=1; continue
                                try:
                                    if coord_mode_pts=='Lat/Lon (WGS84)': lon_pt,lat_pt=float(vx),float(vy)
                                    else: lon_pt,lat_pt=transform_xy(transformer_pts, float(vx), float(vy))
                                    label=f"excel fila {i}"+(f" — {nm}" if str(nm) else '')
                                    init['excel_points'].append({'lat':lat_pt,'lon':lon_pt,'popup':str(nm) if str(nm) else '', 'icon_uri':icon_uri,'icon_size':int(icon_size_px),'label':label})
                                    labels.append(label); added+=1
                                except Exception: discarded+=1
                            existing=set(init.get('excel_point_labels',[])); init.setdefault('excel_point_labels',[]).extend([lbl for lbl in labels if lbl not in existing])
                            st.success(f'{added} puntos añadidos a la sesión.')
                            if discarded: st.warning(f'{discarded} filas descartadas (valores no numéricos o CRS no válido).')
                    if st.button('Guardar JSON (id, lat, lon + UTM)', key='btn_save_minjson'):
                        def save_coords_json_minimal(points_list, folder, prefix):
                            from pyproj import Transformer
                            ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
                            out_path = os.path.join(folder, f'{prefix}_{ts}.json')
                            try:
                                huso = int(st.session_state.get('ui_huso')) if st.session_state.get(
                                    'ui_huso') else None
                            except Exception:
                                huso = None
                            hemi = st.session_state.get('ui_hemisferio') or 'Norte'
                            if huso and 1 <= huso <= 60:
                                epsg_dest = (32700 + huso) if str(hemi).lower().startswith('s') else (32600 + huso)
                            else:
                                epsg_dest = 32613
                            transformer_utm = None
                            if HAS_PYPROJ:
                                try:
                                    transformer_utm = Transformer.from_crs('EPSG:4326', f'EPSG:{epsg_dest}',
                                                                           always_xy=True)
                                except Exception:
                                    transformer_utm = None
                            items = []
                            st.session_state['wtgs'] = []
                            for p in points_list:
                                pid = p.get('popup') or p.get('label') or None
                                lon = p.get('lon')
                                lat = p.get('lat')
                                utm_x = utm_y = None
                                if transformer_utm is not None and lon is not None and lat is not None:
                                    try:
                                        utm_x, utm_y = transformer_utm.transform(float(lon), float(lat))
                                    except Exception:
                                        utm_x, utm_y = None, None
                                items.append({'id': pid, 'lat': lat, 'lon': lon, 'utm_x': utm_x, 'utm_y': utm_y})
                                st.session_state['wtgs'].append(WTG(id=pid,utm_x=utm_x,utm_y=utm_y))#llenado de la clases
                            with open(out_path, 'w', encoding='utf-8') as f:
                                json.dump(items, f, ensure_ascii=False, indent=2)

                            return out_path


                        outj_min = save_coords_json_minimal(init['excel_points'], puntos_dir, 'coords_min_excel')
                        st.success(f'Guardado: {outj_min}')
                        init['paths']['coords_min_json'] = outj_min

            except Exception as e:
                st.error(f'Error leyendo Excel/CSV: {e}')


default_huso = init.get('map_huso', 13)
default_hemi = init.get('map_hemisferio', 'Norte')
default_datum = init.get('map_datum', 'WGS84')

with st.sidebar.expander("AutoCAD (DWG/DXF)", expanded=False):
    fmt_cad = st.selectbox("Formato CAD", ["DXF", "DWG"], index=0, key='ui_cad_fmt')
    out_dxf = None
    cad_file_dw = cad_file_dx = None
    if fmt_cad == "DWG":
        conv_method = st.radio("Conversión DWG→DXF", ["ODA File Converter", "LibreDWG (dwg2dxf)"], index=0, key='ui_cad_conv')
        if conv_method == "ODA File Converter":
            oda_exec = st.text_input("Ruta ODAFileConverter (opcional)", value="", key='ui_cad_odaexec')
            dxf_out_version_oda = st.selectbox("Versión DXF (ODA)", ["ACAD2000","ACAD2004","ACAD2007","ACAD2010","ACAD2013","ACAD2018"], index=5, key='ui_cad_oda_ver')
        else:
            dxf_out_version_libredwg = st.selectbox("Versión DXF (LibreDWG)", ["r12","r14","r2000","r2004","r2007","r2010","r2013"], index=6, key='ui_cad_libredwg_ver')
        cad_file_dw = st.file_uploader("Subir DWG", type=["dwg"], key='ui_cad_dwgfile')
    else:
        cad_file_dx = st.file_uploader("Subir DXF", type=["dxf"], key='ui_cad_dxffile')

    st.markdown("**CRS CAD → WGS84**")
    transformer_cad_local = None

    idx_crs_mode_cad = 0 if init.get('map_huso') else 1
    crs_mode_local = st.radio(
        "Definir CRS",
        ["UTM (HUSO + Hemisferio + Datum)","EPSG"],
        index=idx_crs_mode_cad,
        key='ui_cad_crsmode'
    )



    if HAS_PYPROJ:
        if crs_mode_local == "EPSG":
            # Si el mapa ya estaba en UTM (default_huso), proponemos su EPSG correspondiente
            # Norte: 32600 + huso | Sur: 32700 + huso. Si no hay info, usa 32613.
            if init.get('map_huso'):
                epsg_sugerido = (32700 + int(default_huso)) if str(default_hemi).lower().startswith('s') else (
                            32600 + int(default_huso))
            else:
                epsg_sugerido = 32613

            epsg_src_local = st.number_input(
                "EPSG (p.ej. 25830 / 32613)",
                value=int(epsg_sugerido),
                step=1,
                key='ui_cad_epsg'
            )
            try:
                transformer_cad_local = make_transformer_from_epsg(int(epsg_src_local))
            except Exception as e:
                st.error(f"EPSG inválido: {e}")
                transformer_cad_local = None

        else:
            # UTM con defaults tomados de init (o fallback 13 / Norte / WGS84)
            huso_src_local = st.number_input(
                "HUSO",
                min_value=1, max_value=60,
                value=int(default_huso),
                step=1,
                key='ui_cad_huso'
            )

            hemisferio_src_local = st.selectbox(
                "Hemisferio",
                ["Norte", "Sur"],
                index=0 if default_hemi == "Norte" else 1,
                key='ui_cad_hemisferio'
            )

            datum_src_local = st.selectbox(
                "Datum",
                ["ETRS89", "WGS84"],
                index=1 if default_datum == "WGS84" else 0,
                key='ui_cad_datum'
            )

            if datum_src_local == "ETRS89" and (not (28 <= int(huso_src_local) <= 38) or hemisferio_src_local == "Sur"):
                st.error("ETRS89 sólo aplica a husos 28–38 Norte. Usa WGS84 o ajusta HUSO.")
                transformer_cad_local = None
            else:
                transformer_cad_local = make_transformer_from_utm(
                    int(huso_src_local), hemisferio_src_local, datum=datum_src_local
                )
    else:
        st.error("pyproj requerido para transformar CRS (EPSG/UTM→WGS84).")

    if st.button("Añadir CAD al mapa", key='btn_cad_add'):
        try:
            if fmt_cad == "DWG" and cad_file_dw is not None:
                tmp_dwg = os.path.join(TMP_DIR, cad_file_dw.name)
                with open(tmp_dwg, 'wb') as f:
                    f.write(cad_file_dw.read())
                if transformer_cad_local is None:
                    st.error("Configura un CRS válido antes de convertir/añadir.")
                else:
                    # Convertir a DXF
                    try:
                        if 'conv_method' in locals() and conv_method == "ODA File Converter":
                            out_dxf = convert_dwg_to_dxf_oda(tmp_dwg, TMP_DIR, dxf_out_version_oda, oda_exec_path=oda_exec or None)
                        else:
                            out_dxf = convert_dwg_to_dxf_libredwg(tmp_dwg, TMP_DIR, dxf_out_version_libredwg)
                    except Exception as e:
                        st.error(f"Conversión DWG→DXF falló: {e}")
                        out_dxf = None
            elif fmt_cad == "DXF" and cad_file_dx is not None:
                out_dxf = os.path.join(TMP_DIR, cad_file_dx.name)
                with open(out_dxf, 'wb') as f:
                    f.write(cad_file_dx.read())
            else:
                st.warning("Sube un archivo CAD.")

            if out_dxf and transformer_cad_local is not None:
                if not HAS_EZDXF:
                    st.error("ezdxf no está instalado. Ejecuta: pip install ezdxf")
                else:
                    fc_dxf = dxf_to_geojson(out_dxf, transformer_cad_local)
                    feats = fc_dxf.get('features', [])
                    # Actualiza sets de capas útiles
                    for feat in feats:
                        gtype = (feat.get('geometry', {}) or {}).get('type')
                        layer = (feat.get('properties', {}) or {}).get('layer', 'sin_capa')
                        if gtype in ("LineString", "Polygon"):
                            init['layers_restr'].add(layer)
                        if gtype == "LineString":
                            init['layers_cam'].add(layer)
                    init['cad_fc_list'].append(fc_dxf)
                    st.success(f"CAD añadido: {len(feats)} entidades (DXF: {os.path.basename(out_dxf)}).")
                    if len(feats) == 0:
                        st.info("El DXF se procesó pero no contenía entidades convertibles (LINE/LWPOLYLINE/POLYLINE/HATCH).")
        except Exception as e:
            st.error(f"Error procesando CAD: {e}")


# Pintar mapa
for fc in init['cad_fc_list']: folium.GeoJson(fc, name='Plano CAD', style_function=lambda x:{'color':'#ff9900','weight':2,'fillOpacity':0.2}).add_to(m)
for fc in init['other_fc_list']: folium.GeoJson(fc, name='Capa').add_to(m)
if init['excel_points']:
    mc=MarkerCluster(name='Puntos (Excel)').add_to(m)
    for p in init['excel_points']:
        kwargs={}
        if p.get('icon_uri'): kwargs['icon']=folium.CustomIcon(icon_image=p['icon_uri'], icon_size=(p['icon_size'], p['icon_size']))
        folium.Marker([p['lat'], p['lon']], popup=p.get('popup',''), **kwargs).add_to(mc)
folium.LayerControl().add_to(m)








#st.markdown("<div class='sub_title'>MAP</div>", unsafe_allow_html=True)





st_data=st_folium(m, width=1700, height=1000 ,returned_objects=['all_drawings'])
st.markdown( '#### Current drawings')
features=st_data.get('all_drawings') or []
st.write(f'Total: **{len(features)}** elementos')
if features: st.json({'type':'FeatureCollection','features':features})

st.markdown('#### Selección y guardado')
colR,colC,colS=st.columns(3)
layers_restr_sorted=sorted(list(init['layers_restr'])); layers_cam_sorted=sorted(list(init['layers_cam']))

def filter_fc_by_layers(fc_list, layers, tipo, allowed_geom=("LineString","Polygon")):
    layers_set=set(layers or [])
    feats=[]
    for fc in fc_list:
        for feat in fc.get('features',[]):
            props=(feat.get('properties',{}) or {})
            layer=props.get('layer','sin_capa'); gtype=(feat.get('geometry',{}) or {}).get('type')
            if layer in layers_set and gtype in allowed_geom:
                feats.append({'type':'Feature','properties':{**props,'tipo':tipo,'source':'dxf'},'geometry':feat['geometry']})
    return {'type':'FeatureCollection','features':feats}



with colR:
    st.markdown('##### Restricciones')
    sel_layers_restr=st.multiselect('Capas del DXF (líneas o polígonos)', layers_restr_sorted, key='ui_restr_layers')
    include_drawn_restr=st.checkbox('Incluir dibujos (LineString/Polygon)', value=True, key='ui_restr_incl_drawn')
    if st.button('Guardar restricciones', key='btn_save_restr'):
        feats_out=[]
        fc_restr_layers=filter_fc_by_layers(init['cad_fc_list'], sel_layers_restr, 'restriccion', ('LineString','Polygon'))
        feats_out.extend(fc_restr_layers['features'])
        if include_drawn_restr:
            for feat in features:
                gtype=(feat.get('geometry',{}) or {}).get('type')
                if gtype in ('LineString','Polygon'):
                    feats_out.append({'type':'Feature','properties':{'tipo':'restriccion','source':'drawn'},'geometry':feat['geometry']})
        if feats_out:
            out_wgs,out_utm=save_restricciones_and_register({'type':'FeatureCollection','features':feats_out}, restr_dir)
            st.success(f'Guardado WGS84: {out_wgs}')
            if out_utm: st.info(f'Guardado UTM: {out_utm}')
        else: st.warning('No hay elementos para restricciones.')

with colC:
    st.markdown('##### Caminos')
    sel_layers_cam=st.multiselect('Capas del DXF (solo líneas)', layers_cam_sorted, key='ui_cam_layers')
    include_drawn_cam=st.checkbox('Incluir dibujos (LineString)', value=True, key='ui_cam_incl_drawn')
    if st.button('Guardar camino', key='btn_save_cam'):
        feats_out=[]
        fc_cam_layers=filter_fc_by_layers(init['cad_fc_list'], sel_layers_cam, 'camino', ('LineString',))
        feats_out.extend(fc_cam_layers['features'])
        if include_drawn_cam:
            for feat in features:
                if (feat.get('geometry',{}) or {}).get('type')=='LineString':
                    feats_out.append({'type':'Feature','properties':{'tipo':'camino','source':'drawn'},'geometry':feat['geometry']})
        if feats_out:
            out_wgs,out_utm=save_camino_and_register({'type':'FeatureCollection','features':feats_out}, cam_dir)
            st.success(f'Guardado WGS84: {out_wgs}')
            if out_utm: st.info(f'Guardado UTM: {out_utm}')
        else: st.warning('No hay polilíneas para camino.')

with colS:
    st.markdown('#### Access Point (puntos)')
    excel_labels=init['excel_point_labels']
    sel_excel_ruad=st.multiselect('Puntos (Excel) a incluir', excel_labels, key='ui_ruad_labels')
    include_drawn_points=st.checkbox('Incluir puntos dibujados', value=True, key='ui_ruad_incl_drawn')
    if st.button('Guardar Road Survey', key='btn_save_ruad'):
        points=[]
        if include_drawn_points:
            for feat in features:
                if (feat.get('geometry',{}) or {}).get('type')=='Point': points.append({'type':'Feature','properties':{'tipo':'ruad_survey','source':'drawn'},'geometry':feat['geometry']})
        label_set=set(sel_excel_ruad or [])
        for p in init['excel_points']:
            if p.get('label') in label_set: points.append({'type':'Feature','properties':{'tipo':'ruad_survey','source':'excel'},'geometry':{'type':'Point','coordinates':[p['lon'], p['lat']]}})

        if points:

            ruad_coords = []
            for f in points:
                geom = f.get('geometry', {}) or {}
                if geom.get('type') == 'Point':
                    lon, lat = geom.get('coordinates', [None, None])
                    if lon is not None and lat is not None:
                        ruad_coords.append((lon, lat))
            st.session_state['ruad_coords'] = ruad_coords
            out_wgs,out_utm=save_ruad_survey_and_register({'type':'FeatureCollection','features':points}, ruad_dir)
            st.success(f'Guardado WGS84: {out_wgs}')
            if out_utm: st.info(f'Guardado UTM: {out_utm}')
        else: st.warning('No hay puntos seleccionados para ruad_survey.')


MV_list = [33.0, 34.5]
HV_list = [110.0, 220.0, 235.0]
default_mv = st.session_state.get("medium_voltage", 33.0)
default_hv = st.session_state.get("high_voltage", 220.0)
idx_1 = MV_list.index(default_mv) if default_mv in MV_list else 0
idx_2 = HV_list.index(default_hv) if default_hv in HV_list else 0
with st.sidebar.expander('Niveles de tensión', expanded=False):
    st.selectbox(
        "Medium Voltage Level (kV)",
        options=MV_list,
        key="medium_voltage",
        index=idx_1,
        help="Medium voltage"
    )
    st.selectbox(
        "High Voltage Level (kV)",
        options=HV_list,
        key="high_voltage",
        index=idx_2,
        help="Medium voltage"
    )
               # mt_kv = st.number_input('Media tensión (kV)', min_value=1.0, step=0.1,
                #     value=float(init.get('niveles_tension', {}).get('media_tension_kv', 34.5)),
    #               key='ui_mt_kv')
    #at_kv = st.number_input('Alta tensión (kV)', min_value=35.0, step=1.0,
            #                       value=float(init.get('niveles_tension', {}).get('alta_tension_kv', 220.0)),
    #               key='ui_at_kv')






# DB JSON

st.sidebar.markdown('### Base de Datos (JSON)'); default_json=os.path.join('assets','db_platform.json'); json_path=st.sidebar.text_input('Ruta JSON', value=default_json, key='json_path')
if st.sidebar.button('Cargar DB JSON', key='btn_db_load'):
    if not WTG_DB_AVAILABLE: st.sidebar.error("El módulo 'wtg_db' no está disponible.")
    else:
        try: st.session_state.db=load_db(json_path=json_path); st.sidebar.success('DB cargada.')
        except Exception as e: st.sidebar.error(f'No se pudo cargar la DB: {e}')

st.sidebar.markdown('### WTG (modelo / torre / frecuencia)')
if WTG_DB_AVAILABLE and 'db' in st.session_state and st.session_state.db:
    db=st.session_state.db; modelos=get_models(db); modelo=st.sidebar.selectbox('Modelo', modelos, key='wtg_model') if modelos else None
    torres=get_compatible_towers(db, modelo) if modelo else []; torre=st.sidebar.selectbox('Torre (compatibles)', torres, key='wtg_torre') if torres else None
    freq_label=st.sidebar.selectbox('Frecuencia',["50 Hz","60 Hz"], index=0, key='wtg_freq'); freq_key='50hz' if freq_label.startswith('50') else '60hz'
    variantes=get_power_variants(db, modelo) if modelo else []; idx_default=max(range(len(variantes)), key=lambda i: variantes[i].get('power_mw',0)) if variantes else 0
    etiquetas=[f"{v.get('power_mw','?')} MW — Q={v.get('q_var','-')} — S={v.get('s_mva','-')}" for v in variantes]
    ix_var=st.sidebar.selectbox('Variante de potencia', list(range(len(etiquetas))) if etiquetas else [], format_func=lambda i: etiquetas[i] if i<len(etiquetas) else '', index=idx_default, key='wtg_var') if etiquetas else None
    variante=variantes[ix_var] if (variantes and ix_var is not None) else None
    diam_blade=get_blade_diameter(db, modelo) if modelo else None; foundation_diameter=get_foundation_diameter(db, modelo) if modelo else None
    transf_all=db.get('transform',{}).get(modelo,{}) if modelo else {}; transf=transf_all.get(freq_key,{}) if isinstance(transf_all,dict) else {}; plat = get_platform_fallback(db, torre) if torre else None
    if st.sidebar.button('Aplicar configuración WTG', key='btn_apply_wtg'):
        tension={}or {}
        st.session_state.wtg_config={'proj_name':init.get('proj_name'),'project_id':init.get('project_id'),'session_id':init.get('session_id'),'wtg_model':modelo,'tower_type':torre,'frequency':freq_key,'power_variant':variante,'diameter_blade_m':diam_blade,'foundation_diameter_m':foundation_diameter,'transform':transf,'platform':plat,'niveles_tension':tension}; st.sidebar.success('Configuración WTG aplicada.')
else:
    if not WTG_DB_AVAILABLE: st.sidebar.info("El módulo 'wtg_db' no está disponible.")
    else: st.sidebar.info('Carga primero la DB JSON.')

if st.session_state.get('wtg_config'):
    cfg=st.session_state['wtg_config']; modelo=cfg.get('wtg_model'); torre=cfg.get('tower_type'); freq=cfg.get('frequency'); variante=cfg.get('power_variant') or {}; diam_blade=cfg.get('diameter_blade_m'); foundation_diameter=cfg.get('foundation_diameter_m'); transf=cfg.get('transform') or {}; plat=cfg.get('platform') or {}; tension=cfg.get('niveles_tension') or {}
    colA,colB=st.columns(2)
    with colA:
        st.write('**Modelo**', modelo); st.write('**Torre**', torre); st.write('**Frecuencia**', '50 Hz' if freq=='50hz' else '60 Hz'); st.write('**Potencia**'); st.json(variante or {'power_mw':None}); st.write('**Transformador**'); st.json(transf or {'nll_kw':None,'scl_kw':None})
        st.write('**Niveles de tensión (kV)**'); st.json({'media':st.session_state.get("medium_voltage", 33.0),'alta':st.session_state.get("high_voltage", 220.0),'utm_epsg':tension.get('utm_epsg'),'huso':tension.get('huso'),'hemisferio':tension.get('hemisferio')})
    with colB:
        st.write("**Blade diameter (m)**", diam_blade)
        st.write("**Fundación (diámetro m, por modelo)**", foundation_diameter)
        st.write("**Wide road (m)**", (plat or {}).get('wide_road_m'))
        st.write("**Diámetro plataforma (m)**", (plat or {}).get('platform_diameter_m'))
        st.write("**entry_exit**")
        st.json({"entry_point": (plat or {}).get('entry_point'), "exit_point": (plat or {}).get('exit_point')})

        st.write("**Pads** (rectángulos [x1,y1,x2,y2])")
        st.json((plat or {}).get('pads', {}))
        st.write("**Preassembly** (puntos [x,y,z])")
        st.json((plat or {}).get('preassembly', {}))

    if st.button('Guardar configuración WTG (JSON)', key='btn_save_wtgjson'):
        ts=datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        base=os.path.join('salidas',init.get('proj_name','_sin_nombre_'), init.get('project_id','pid'), 'config')
        os.makedirs(base, exist_ok=True)
        fname=os.path.join(base, f"wtg_cfg_{init.get('proj_name','_sin_nombre_')}_{init.get('project_id','pid')}_{ts}.json")
        cfg_to_save=dict(cfg)
        cfg_to_save['utm_epsg_at_save']=get_current_utm_epsg()

        st.session_state['power_wtg'] = cfg_to_save['power_variant']['s_mva']

        with open(fname,'w',encoding='utf-8') as f:
            json.dump(cfg_to_save,f,ensure_ascii=False,indent=2)
        try:
            file_path_a=init['paths']['coords_min_json']
        except Exception as e:
            st.error(f"FALTAN LISTA DE WTGS__{e}")
            st.stop()  # No continuamos si no hay json_b

        dxf_file_a  = f"{DXF_FILES}/blade_diameter.dxf"
        from b_cad_restriction_blade import main_blade
        main_blade(file_path_a, diam_blade, dxf_file_a)
        st.success(f'Configuración guardada: {fname}')

        init['paths']['utm_epsg_at_save'] = fname

else: st.info('Carga la DB JSON y aplica la configuración WTG desde el sidebar.')





def json_(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data

def json_list(lista):
    list_tuple=[]
    for i in lista:
        list_tuple.append((i['id'], i['utm_x'], i['utm_y']))
    return list_tuple


def load_inputs_from_init(init):
    paths = init.get('paths', {}) or {}

    #path_nt    = paths.get('niveles_tension_json',None)

    path_coord = paths.get('coords_min_json',None)
    path_grid  = paths.get('grid_on_wgs_geojson',None)
    path_road  = paths.get('camino_utm_geojson',None)
    path_restricciones= paths.get('restricciones_utm_geojson',None)
    path_road_survey = paths.get('ruad_survey_utm_geojson',None)
    path_wtg  = paths.get('utm_epsg_at_save',None)
    return path_coord, path_grid, path_road, path_restricciones, path_road_survey, path_wtg


def lista_MV_json():
    file_set = "./RESULTADOS/SET calculadas. Criterio 10.5km 1 SETs, opción 1.xlsx"
    file_perdidas = "./RESULTADOS/Pérdidas_Totales_opcion1_1_SETs.xlsx"
    file_resultados = "./RESULTADOS/resultados_circuitos_opcion1_1_SETs.xlsx"

    df_set = pd.read_excel(file_set, engine="openpyxl")
    df_perd = pd.read_excel(file_perdidas, engine="openpyxl")
    df_res = pd.read_excel(file_resultados, engine="openpyxl")

    row_set = df_set.iloc[0]
    row_res = df_res.iloc[0]
    row_loss = df_perd.iloc[0]
    cols_set = df_set.columns.tolist()
    cols_resul = df_res.columns.tolist()
    cols_loss = df_perd.columns.tolist()
    col_x = cols_set[0]
    col_y = cols_set[1]
    col_set_power = cols_set[3]
    col_wtg_num = cols_set[2]
    col_main_tx = cols_set[5]
    col_mv_bus = cols_set[4]

    col_circuit_3 = cols_resul[0]
    col_circuit_2 = cols_resul[1]
    col_len_120 = cols_resul[4]
    col_len_300 = cols_resul[5]
    col_len_630 = cols_resul[6]
    col_earthing = cols_loss[9]
    col_loss_kw = cols_loss[1]
    col_loss_pct = cols_loss[2]

    record_list = {
        "Simulation SET": {
            "x": float(row_set[col_x]) if col_x in df_set.columns else None,
            "y": float(row_set[col_y]) if col_y in df_set.columns else None,
            "SET Power": round(float(row_set[col_set_power]), 3) if col_set_power in df_set.columns else None,
            "WIND Turbine Number": int(row_set[col_wtg_num]) if col_wtg_num in df_set.columns else None,
            "MAIN TRANSFORMER": str(row_set[col_main_tx]) if col_main_tx in df_set.columns else None,
            "MV Busbar Number": int(row_set[col_mv_bus]) if col_mv_bus in df_set.columns else None,
        },
        "MV_COLLECTOR": {
            "3 wtg circuit number": int(row_res[col_circuit_3]) if col_circuit_3 in df_res.columns else None,
            "2 wtg circuit number": int(row_res[col_circuit_2]) if col_circuit_2 in df_res.columns else None,
            "120mm2 Cable Length[km]": round(float(row_res[col_len_120]), 3) if col_len_120 in df_res.columns else None,
            "300mm2 Cable Length[km]": round(float(row_res[col_len_300]), 3) if col_len_300 in df_res.columns else None,
            "630mm2 Cable Length[km]": round(float(row_res[col_len_630]), 3) if col_len_630 in df_res.columns else None,
            "Earthing wire conductor[km]": round(float(row_loss[col_earthing]) / 3.0,
                                                 3) if col_earthing in df_perd.columns else None,
            "Losses [kW]": round(float(row_loss[col_loss_kw]), 3) if col_loss_kw in df_perd.columns else None,
            "Percent Losses[%]": round(float(row_loss[col_loss_pct]),
                                       3)  if col_loss_pct in df_perd.columns else None,
        }
    }
    return record_list


def resolve_raster_path(init):
    from pathlib import Path
    import os

    # 1) Ruta guardada en sesión
    raster_path = (init.get('paths', {}) or {}).get('raster_file')
    if raster_path and os.path.exists(raster_path):
        return str(Path(raster_path).resolve())

    # 2) Intentar localizar el último .tif en la carpeta del proyecto actual
    raster_dir = Path('salidas') / init['proj_name'] / 'RASTER_FILE'
    raster_dir.mkdir(parents=True, exist_ok=True)
    # reutiliza tu util 'latest_file'
    latest = latest_file(str(raster_dir / '*.tif'))
    if latest and os.path.exists(latest):
        return str(Path(latest).resolve())

    # 3) Fallback: dem_file()
    try:
        rp = dem_file()
        if rp and os.path.exists(rp):
            return str(Path(rp).resolve())
    except Exception:
        pass

    return None  # si nada funciona, devuelves None

#list_project={'Project':
                    #  {"name":init['proj_name_input'],
    #  "session_id": init['project_id'],
    #                   "WTG MODEL":json_b['wtg_model'],
    #                 "Tower Model":json_b['tower_type'],
    #                  "POWER TURBINE[MW]":json_b['power_variant']['power_mw'],
    #                  "POWER TURBINE[MVA]": json_b['power_variant']['s_mva']
    #      }
    #}


# El botón devuelve True solo cuando se hace clic



def sumar_cantidades_materiales(material: dict):

    total_relleno = 0.0
    total_excavacion = 0.0


    for wtg, info in material.items():
        minimo = info.get("minimo", {})
        total_excavacion += float(minimo.get("volumen excavacion", 0.0) or 0.0)
        total_relleno += float(minimo.get("volumen relleno", 0.0) or 0.0)

    return {    "total_relleno": round(total_relleno,3),
            "total_excavacion": round(total_excavacion,3),

        }


def length_lwpolyline(pline) -> float:
    """
    Longitud exacta de una LWPOLYLINE, considerando bulge (arcos) entre vértices consecutivos.
    Nota: LWPOLYLINE es planar; la z va como 'elevation'. Trabajamos en XY.  [1](https://ezdxf.readthedocs.io/en/stable/dxfentities/lwpolyline.html)
    """
    # Obtener puntos como (x, y, bulge)
    with pline.points("xyb") as pts:
        points = list(pts)  # [(x, y, bulge), ...]

    n = len(points)
    if n < 2:
        return 0.0

    total = 0.0

    # Segmentar del i -> i+1
    for i in range(n - 1):
        x1, y1, b = points[i]
        x2, y2, _ = points[i + 1]

        if abs(b) < 1e-12:
            total += hypot(x2 - x1, y2 - y1)
        else:
            start = Vec2(x1, y1)
            end   = Vec2(x2, y2)
            # bulge_to_arc: devuelve (midpoint, radius, start_angle, end_angle) en radianes
            _, radius, a1, a2 = bulge_to_arc(b, start,end)  # [2](https://github.com/mozman/ezdxf/discussions/826)[3](https://stackoverflow.com/questions/75364107/ezdxf-bulge-to-arc-conversion)
            ang_span = arc_angle_span_rad(a1, a2)            # [4](https://ezdxf.readthedocs.io/en/stable/math/core.html)
            total += abs(ang_span) * radius

    # Si está cerrada, el bulge del último vértice aplica al tramo último->primero  [1](https://ezdxf.readthedocs.io/en/stable/dxfentities/lwpolyline.html)
    if pline.closed and n >= 2:
        x1, y1, b = points[-1]
        x2, y2, _ = points[0]
        if abs(b) < 1e-12:
            total += hypot(x2 - x1, y2 - y1)
        else:
            start = Vec2(x1, y1)
            end   = Vec2(x2, y2)
            _, radius, a1, a2 = bulge_to_arc(b, start, end)  # [2](https://github.com/mozman/ezdxf/discussions/826)[3](https://stackoverflow.com/questions/75364107/ezdxf-bulge-to-arc-conversion)
            ang_span = arc_angle_span_rad(a1, a2)            # [4](https://ezdxf.readthedocs.io/en/stable/math/core.html)
            total += abs(ang_span) * radius

    return total


def length_polyline(entity, tol=0.01) -> float:
    """
    Longitud de una POLYLINE clásica.
    Se convierte a Path y se aplanan las curvas para aproximar la longitud.  [5](https://ezdxf.readthedocs.io/en/stable/path.html)
    """
    path = make_path(entity)  # Path con líneas y Bézier/aprox. de arcos  [5](https://ezdxf.readthedocs.io/en/stable/path.html)
    verts = list(path.flattening(tol))  # discretiza curvas en segmentos lineales
    if len(verts) < 2:
        return 0.0
    return sum(hypot(verts[i+1].x - verts[i].x, verts[i+1].y - verts[i].y) for i in range(len(verts) - 1))


def sumar_longitudes_polilineas(dxf_path: str, capas_incluir=None) -> dict:
    """
    Suma las longitudes de todas las polilíneas del DXF (modelspace).
    Retorna:
      {
        'total_m': float,
        'por_capa': {layer_name: float, ...},
        'detalles': [(handle, layer, tipo, longitud), ...]
      }

    'capas_incluir' puede ser una lista de nombres de capa para filtrar.
    """
    doc = ezdxf.readfile(dxf_path)
    msp = doc.modelspace()

    detalles = []
    por_capa = {}
    total = 0.0

    # Consultar ambas: LWPOLYLINE y POLYLINE
    for e in msp.query("LWPOLYLINE POLYLINE"):
        layer = e.dxf.layer
        if capas_incluir and layer not in capas_incluir:
            continue

        if e.dxftype() == "LWPOLYLINE":
            L = length_lwpolyline(e)  # exacto con bulge  [1](https://ezdxf.readthedocs.io/en/stable/dxfentities/lwpolyline.html)
        else:  # "POLYLINE"
            L = length_polyline(e)    # aproximado por Path  [5](https://ezdxf.readthedocs.io/en/stable/path.html)

        total += L
        por_capa[layer] = por_capa.get(layer, 0.0) + L
        detalles.append((e.dxf.handle, layer, e.dxftype(), L))

    return {"total_m": total, "por_capa": por_capa, "detalles": detalles}

def longitud_total_geojson(feature_collection: Dict[str, Any]) -> Dict[str, float]:
    """
    Calcula la longitud total de todas las geometrías LineString dentro de un FeatureCollection.
    Asume coordenadas en metros (p. ej., UTM EPSG:32613).

    Retorna:
      {"metros": float, "km": float}
    """
    if feature_collection.get("type") != "FeatureCollection":
        raise ValueError("Se esperaba type='FeatureCollection'.")

    total_m = 0.0
    for feat in feature_collection.get("features", []):
        geom = feat.get("geometry", {})
        if geom.get("type") != "LineString":
            continue
        coords = geom.get("coordinates", [])
        # Sumar distancias entre puntos consecutivos
        for i in range(len(coords) - 1):
            x1, y1 = coords[i][0], coords[i][1]
            x2, y2 = coords[i+1][0], coords[i+1][1]
            total_m += math.hypot(x2 - x1, y2 - y1)

    return {"metros": total_m, "km": total_m / 1000.0}


st.markdown("<div style='height:40px;'></div>", unsafe_allow_html=True)
st.markdown('### Roads')
c1, c2 ,c3,c4,c5,c6= st.columns(6)
with c1:
    st.number_input(
        "Excavation price (€/m³)",
        key="excavation_price",
        min_value=0.0,
        value=st.session_state.get("excavation_price", 5.0),  # valor por defecto
        step=0.5,
        help="Precio unitario de excavación"
    )
with c2:
    st.number_input(
        "Fill price (€/m³)",
        key="fill_price",
        min_value=0.0,
        value=st.session_state.get("fill_price", 5.0),         # valor por defecto
        step=0.5,
        help="Precio unitario de relleno"
    )
with c3:
    st.number_input(
        "Mesh spacing",
        key="mesh_spacing",
        min_value=10.0,
        value=st.session_state.get("mesh_spacing", 30.0),  # valor por defecto
        step=10.0,
        help="Mesh spacing")
with c4:
    opciones_width = [3.0, 4.0, 5.0, 6.0, 7.0]   # la lista que quieras

    st.selectbox(
        "Road width (m)",
        options=opciones_width,
        key="road_width",
        index=opciones_width.index(
            st.session_state.get("road_width", 6.0)
        ),
        help="Road width"
    )
st.session_state.setdefault("excavation_price", 5.0)
st.session_state.setdefault("fill_price", 5.0)
st.session_state.setdefault("road_width", 6.0)
st.session_state.setdefault("mesh_spacing", 30)
# Defaults coherentes

st.session_state.setdefault("factor_penalizacion", [1, 2, 3, 4, 5, 6, 7])
st.session_state.setdefault("slope_bins_7",        [0, 3, 6, 9, 12, 15])
# 👉 Crear columnas para limitar ancho (ej. 40% – 60%)
left, right = st.columns([0.4, 0.8])
with left:   # ← el expander queda SOLO en esta columna angosta
    with st.expander("⚙️ Penalización por pendiente (editar lista)", expanded=False):

        fp_str = st.text_input(
            "factor_penalizacion (JSON, largo = 7)",
            value=json.dumps(st.session_state["factor_penalizacion"]),
            help="Ej.: [1, 2, 3, 4, 5, 6, 7]"
        )

        bins_str = st.text_input(
            "slope_bins_7 (JSON, 6 cortes, ascendente, en %)",
            value=json.dumps(st.session_state["slope_bins_7"]),
            help="Ej.: [0, 3, 6, 9, 12, 15]"
        )

        ok = True
        msgs = []

        # Validación factores
        try:
            parsed_f = json.loads(fp_str)
            if not (isinstance(parsed_f, list) and len(parsed_f) == 7):
                raise ValueError("factor_penalizacion debe tener exactamente 7 valores.")
            st.session_state["factor_penalizacion"] = [float(x) for x in parsed_f]
        except Exception as e:
            ok = False; msgs.append(f"factores: {e}")

        # Validación cortes
        try:
            parsed_b = json.loads(bins_str)
            if not (isinstance(parsed_b, list) and len(parsed_b) == 6):
                raise ValueError("slope_bins_7 debe tener 6 cortes (definen 7 tramos).")
            if any(parsed_b[i] >= parsed_b[i+1] for i in range(len(parsed_b)-1)):
                raise ValueError("slope_bins_7 debe estar ascendente.")
            st.session_state["slope_bins_7"] = [float(x) for x in parsed_b]
        except Exception as e:
            ok = False; msgs.append(f"bins: {e}")

        if ok:
            st.success("Penalización y cortes guardados.")
        else:
            st.error("Config inválida:\n- " + "\n- ".join(msgs))

# El botón devuelve True solo cuando se hace clic
if st.button("ROAD"):
    base_cfg = os.path.join('salidas',
                            st.session_state.get('proj_name', '_sin_nombre_'),
                            st.session_state.get('project_id', 'pid'),
                            'config')
    path_data=f'{base_cfg}/data.json'
    path_coord, path_grid, path_road, path_restricciones, path_road_survey, path_wtg = load_inputs_from_init(init)


    raster_path = resolve_raster_path(st.session_state)
    if not raster_path:
        st.error("No se encontró un DEM para este proyecto. Sube/Guarda el raster en 'Raster DEM' o verifica /salidas/<proyecto>/RASTER_FILE.")
        st.stop()
    from pathlib import Path

    raster_path = str(Path(raster_path).resolve())
    st.session_state.setdefault('paths', {})
    st.session_state['paths']['raster_file'] = raster_path
    st.info(f"[DEM] Usando: {raster_path}")

    from ROAD_SCRIPT import road_script_main

    path_coord, path_grid, path_road, path_restricciones, path_road_survey, path_wtg = load_inputs_from_init(init)


    try:
        json_b = json_(path_wtg)
    except Exception as e:
        st.error(f"FALTA CARGAR BASE DE DATOS WTG__{e}")
        st.stop()  # No continuamos si no hay json_b


    list_project = {'Project':
                        {"name": init['proj_name'],
                         "project_id": init['project_id'],
                         "WTG MODEL": json_b['wtg_model'],
                         "Tower Model": json_b['tower_type'],
                         "POWER TURBINE[MW]": json_b['power_variant']['power_mw'],
                         "POWER TURBINE[MVA]": round(json_b['power_variant']['s_mva'],2)
                         }
                    }


    largo_camino = abs(json_b['platform']['entry_point'][0] - json_b['platform']['exit_point'][0])
    try:
        with open(path_road, "r", encoding="utf-8") as f:
            data_road_existing = json.load(f)
        camino_existente = round(longitud_total_geojson(data_road_existing)['km'], 3)
    except:
        camino_existente=0


    lista_material = road_script_main(path_data, path_wtg, path_grid, path_road_survey, path_restricciones, path_road, path_coord, raster_path,JSON_FILES,DXF_FILES,path_road)

    wtgs = st.session_state.get('wtgs', [])
    wtg_number=len(wtgs) ###cambiar por el largo de turbinas....
    h=sumar_cantidades_materiales(lista_material)
    dxf_road_ruta = f"{DXF_FILES}/rutas_optimas.dxf"
    res = round(sumar_longitudes_polilineas(dxf_road_ruta)['total_m'] / 1000, 3)
    total_road = res + round(wtg_number * largo_camino / 1000, 3)
    lista_record = {'Total Relleno Plataforma[m3]': round(h['total_relleno'],3),
            'Total Excavacion Plataforma[m3]':round(h['total_excavacion'],3),
            'Total Camino[km]':total_road,
            'Total Camino Existente [km]':camino_existente}

    lista_final = {**list_project, **lista_record}

    with open(f"./salidas/{json_b['proj_name']}/JSON_FILES/HV_ROAD_RESULTS.json", "w", encoding="utf-8") as f:
            json.dump(lista_final, f, ensure_ascii=False, indent=2)
    st.success("¡Acción realizada con éxito!")












else:
        st.write("Esperando a que presiones el botón...")



def ensure_layers(doc, layer_names):
    for name in layer_names:
        if name not in doc.layers:
            doc.layers.add(name=name, color=30,lineweight=25, linetype="CONTINUOUS")

def geojson_a_dxf_ezdxf(geojson_path: str, dxf_path: str, capa: str = "camino_existente"):
    with open(geojson_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    doc = ezdxf.new("R2000")
    doc.units = ezdxf.units.M  # metros (coherente con UTM)
    ensure_layers(doc, ["0", capa, "Platform", "Ruta_Ajustada", "Rutas"])

    msp = doc.modelspace()

    for feat in data.get("features", []):
        props = feat.get("properties", {}) or {}
        geom = feat.get("geometry", {}) or {}

        if geom.get("type") == "LineString" and props.get("tipo") == "camino":
            try:
                coords = [(float(x), float(y)) for x, y in geom.get("coordinates", [])]
            except Exception as e:
                               # Log mínimo y sigue con la siguiente feature
                print(f"Advertencia: coordenadas inválidas en feature {props!r}: {e}")
                continue

            if coords:
                msp.add_lwpolyline(coords, dxfattribs={"layer": capa})

    doc.saveas(dxf_path)

st.markdown("<div style='height:40px;'></div>", unsafe_allow_html=True)
st.markdown('### Cluster Substation')

Back_up_list_power=[0.05,0.1,0.15,0.2]
s1, s2, s3 = st.columns(3)
default_back_up = st.session_state.get("back_up_power", 0.05)
default_cluster_set_number = st.session_state.get("cluster_set_number", 3)
valor_power = st.session_state["power_wtg"]

wtgs = st.session_state.get('wtgs', [])
for wtg in wtgs:
    wtg.power=valor_power
total_power_WF=round(len(wtgs)*valor_power/1000,2)
st.session_state["total_power_wf"]=total_power_WF

idx_3 = Back_up_list_power.index(default_back_up) if default_back_up in Back_up_list_power else 0

with s1:

    st.markdown('WF Power [MVA]')
    st.markdown(f"<div class='big-box'><b>{total_power_WF:.2f} MVA</b> &nbsp; </div>",unsafe_allow_html=True)
    col_1a, col_2a = st.columns([1, 1])  # ajusta proporciones a gusto
    with col_1a:
        st.selectbox(
         "Back-Up Power Back Up (%)",
         options=Back_up_list_power,
         key="back_up_power",
         index=idx_3,
         help="Back Up Power (%)",
         format_func=lambda x: f"{x * 100:.0f} %"
        )
    with col_2a:

        power_total = st.session_state["total_power_wf"]
        back_up = st.session_state["back_up_power"]  # <-- porcentaje seleccionado

        resultado = power_total * back_up

        st.markdown('POWER [MVA]')

        st.markdown(f"<div class='big-box'><b>{resultado:.2f} MVA</b> &nbsp; </div>",unsafe_allow_html=True)

    st.selectbox(
         "Cluster Set Number",
         options=[1, 2, 3, 4, 5],
         index=2,  # valor inicial = 1
         key="cluster_set_number"
     )

with s2:
    default_huso = init.get('map_huso', 13)
    default_hemi = init.get('map_hemisferio', 'Norte')
    default_datum = init.get('map_datum', 'WGS84')
    st.markdown("##### Grid_on – Selección de punto")

    modo = st.radio(
        "Forma de seleccionar el punto grid_on:",
        ["Elegir en el mapa", "Ingresar coordenadas manualmente"],
        index=0,
        key="ui_modo_gridon"
    )

    grid_point_wgs = None   # (lon, lat) en WGS84

    # --------------------------------------------------
    # 1) SELECCIÓN DESDE MAPA (POINT dibujado)
    # --------------------------------------------------
    if modo == "Elegir en el mapa":
        ruad_set = set(st.session_state.get("ruad_coords", []))
        drawn_candidates = []

        for feat in features:
            geom = feat.get("geometry", {})
            if geom.get("type") == "Point":
                lon, lat = geom.get("coordinates", [None, None])
                if (lon, lat) not in ruad_set:
                    drawn_candidates.append((lon, lat))

        if not drawn_candidates:
            st.warning("No hay puntos dibujados disponibles.")
        else:
            fmt = lambda i: f"#{i+1} → ({drawn_candidates[i][1]:.6f}, {drawn_candidates[i][0]:.6f})"
            idx = st.selectbox(
                "Selecciona un punto del mapa",
                options=list(range(len(drawn_candidates))),
                format_func=fmt,
                key="ui_gridon_drawn_select"
            )
            grid_point_wgs = drawn_candidates[idx]

    # --------------------------------------------------
    # 2) INGRESO MANUAL DE COORDENADAS
    # --------------------------------------------------
    else:
        tipo_manual = st.radio(
            "Tipo de coordenadas",
            ["WGS84 (Lat/Lon)", "UTM (HUSO actual)"],
            index=0,
            key="ui_gridon_manual_tipo"
        )

        # -------------------- WGS84 --------------------
        if tipo_manual == "WGS84 (Lat/Lon)":
            lat = st.number_input("Latitud", format="%.6f", key="ui_gridon_lat_wgs")
            lon = st.number_input("Longitud", format="%.6f", key="ui_gridon_lon_wgs")
            grid_point_wgs = (lon, lat)

        # -------------------- UTM ----------------------
        else:
            huso = init.get("map_huso", default_huso)
            hemisferio = init.get("map_hemisferio", default_hemi)

            st.caption(f"Huso actual: **{huso}**, Hemisferio: **{hemisferio}**")

            easting = st.number_input("Easting (m)", format="%.2f", key="ui_gridon_easting")
            northing = st.number_input("Northing (m)", format="%.2f", key="ui_gridon_northing")

            try:
                lon, lat = utm_to_wgs84(huso, hemisferio, easting, northing)
                grid_point_wgs = (lon, lat)
                st.success(f"Convertido a WGS84: lat={lat:.6f}, lon={lon:.6f}")
            except Exception as e:
                st.error(f"Conversión UTM → WGS84 falló: {e}")

    # Prepara los datos del mapa para usarlos en s5
    map_data = None
    if grid_point_wgs:
        map_data = {"lat": [grid_point_wgs[1]], "lon": [grid_point_wgs[0]]}

    # --------------------------------------------------
    # BOTÓN DE GUARDADO
    # --------------------------------------------------
    if st.button("Guardar grid_on", key="btn_save_grid_new"):
        if not grid_point_wgs:
            st.warning("No hay punto seleccionado.")
        else:
            lon, lat = grid_point_wgs

            feature = {
                "type": "Feature",
                "properties": {"tipo": "grid_on", "source": modo},
                "geometry": {"type": "Point", "coordinates": [lon, lat]}
            }

            fc_grid = {"type": "FeatureCollection", "features": [feature]}

            out_wgs, out_utm = save_grid_on_and_register(fc_grid, gridon_dir)

            st.success(f"Guardado grid_on WGS84: {out_wgs}")
            if out_utm:
                st.info(f"Guardado grid_on UTM: {out_utm}")

            st.session_state["grid_on_coords"] = [(lon, lat)]

# =======================
# Columna s5: render mapa
# =======================

#=================================================
# PREPARAR DATOS DEL MAPA (debe estar ANTES del with s5)
# =====================================================
map_data = None
if grid_point_wgs:
    map_data = pd.DataFrame({
        "lat": [grid_point_wgs[1]],
        "lon": [grid_point_wgs[0]],
    })

# =====================================================
#        COLUMNA S5: VISTA PREVIA DEL PUNTO
# =====================================================
with s3:
    st.markdown("##### Vista previa del punto")
    map_placeholder = st.empty()

    if map_data is not None:
        import pydeck as pdk

        view_state = pdk.ViewState(
            latitude=map_data["lat"][0],
            longitude=map_data["lon"][0],
            zoom=8,
            pitch=0,
            bearing=0
        )

        layer = pdk.Layer(
            "ScatterplotLayer",
            data=map_data,  # ← ahora es un DataFrame
            get_position=["lon", "lat"],
            get_color=[255, 0, 0],  # punto rojo
            get_radius=100  # tamaño del punto
        )

        mapa = pdk.Deck(
            layers=[layer],
            initial_view_state=view_state,
            map_style=None  # sin Mapbox
        )

        map_placeholder.pydeck_chart(mapa, height=250)

    else:
        st.info("Selecciona o ingresa un punto para visualizarlo aquí.")

def convertir_sets_a_latlon(todos, epsg_utm=32719):   # cambia a 32613 si es tu HUSO
    transformer = Transformer.from_crs(f"EPSG:{epsg_utm}", "EPSG:4326", always_xy=True)
    puntos = []
    for s in todos:
        lon, lat = transformer.transform(s.utm_x, s.utm_y)
        puntos.append({
            "id": s.id,
            "lat": lat,
            "lon": lon
        })
    return puntos


@dataclass
class Connection:
    origen: Any
    destino: Any
    orientacion_origen: Optional[str] = None
    orientacion_destino: Optional[str] = None
    power: float=0.0
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)




# =========================
# Estado inicial
# =========================
if "ui_ready" not in st.session_state:
    st.session_state["ui_ready"] = False
if "conexiones" not in st.session_state:
    st.session_state["conexiones"] = []
path_coord, path_grid, path_road, path_restricciones, path_road_survey, path_wtg = load_inputs_from_init(init)
if st.button("Cluster SET"):
    # --- CARGAS BASE ---
    path_coord, path_grid, path_road, path_restricciones, path_road_survey, path_wtg = load_inputs_from_init(init)

    json_b = json_(path_wtg)
    POWER_WTG = round(json_b['power_variant']['s_mva'], 3)
    list_wtg = json_list(json_(path_coord))
    wtg_number = len(list_wtg)
    cluster_number = st.session_state["cluster_set_number"]

    Resumen_MV, SETS_coord = main_set_medium_voltage(
        cluster_number, POWER_WTG, st.session_state["medium_voltage"], list_wtg, 1
    )




    # --- Clase SET (como la tienes) ---
    class SET:
        def __init__(self, id, WTGs, utm_x, utm_y, POWER):
            self.id = id
            self.WTGs = WTGs
            self.power_set = round((WTGs) * POWER, 1)
            self.utm_x = utm_x
            self.utm_y = utm_y
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


    def list_MV_1(resumen_MV,SETS_coord):
        SET1=SET('SET_1',resumen_MV['resumen_sets'][0]['WTGs'], SETS_coord[0][0], SETS_coord[0][1], POWER_WTG)
        return [SET1]

    def list_MV_2(resumen_MV,SETS_coord):
        SET1=SET('SET_1',resumen_MV['resumen_sets'][0]['WTGs'], SETS_coord[0][0], SETS_coord[0][1], POWER_WTG)
        SET2 = SET('SET_2', resumen_MV['resumen_sets'][1]['WTGs'], SETS_coord[1][0], SETS_coord[1][1], POWER_WTG)
        return [SET1,SET2]

    def list_MV_3(resumen_MV, SETS_coord):
        # Ojo con el orden de índices (conservé el tuyo)

        SET2 = SET('SET_2', resumen_MV['resumen_sets'][0]['WTGs'], SETS_coord[0][0], SETS_coord[0][1], POWER_WTG)
        SET3 = SET('SET_3', resumen_MV['resumen_sets'][1]['WTGs'], SETS_coord[1][0], SETS_coord[1][1], POWER_WTG)
        SET1 = SET('SET_1', resumen_MV['resumen_sets'][2]['WTGs'], SETS_coord[2][0], SETS_coord[2][1], POWER_WTG)
        return [SET1, SET2, SET3]
    def list_MV_4(resumen_MV, SETS_coord):
        # Ojo con el orden de índices (conservé el tuyo)
        SET1 = SET('SET_1', resumen_MV['resumen_sets'][0]['WTGs'], SETS_coord[0][0], SETS_coord[0][1], POWER_WTG)
        SET3 = SET('SET_3', resumen_MV['resumen_sets'][1]['WTGs'], SETS_coord[1][0], SETS_coord[1][1], POWER_WTG)
        SET4 = SET('SET_4', resumen_MV['resumen_sets'][2]['WTGs'], SETS_coord[2][0], SETS_coord[2][1], POWER_WTG)
        SET2 = SET('SET_2', resumen_MV['resumen_sets'][3]['WTGs'], SETS_coord[3][0], SETS_coord[3][1], POWER_WTG)

        return [SET1, SET2, SET3,SET4]



    def list_MV_5(resumen_MV, SETS_coord):
        # Ojo con el orden de índices (conservé el tuyo)
        SET5 = SET('SET_5', resumen_MV['resumen_sets'][0]['WTGs'], SETS_coord[0][0], SETS_coord[0][1], POWER_WTG)
        SET1 = SET('SET_1', resumen_MV['resumen_sets'][1]['WTGs'], SETS_coord[1][0], SETS_coord[1][1], POWER_WTG)
        SET3 = SET('SET_3', resumen_MV['resumen_sets'][2]['WTGs'], SETS_coord[2][0], SETS_coord[2][1], POWER_WTG)
        SET4 = SET('SET_4', resumen_MV['resumen_sets'][3]['WTGs'], SETS_coord[3][0], SETS_coord[3][1], POWER_WTG)
        SET2 = SET('SET_2', resumen_MV['resumen_sets'][4]['WTGs'], SETS_coord[4][0], SETS_coord[4][1], POWER_WTG)
        return [SET1, SET2, SET3, SET4,SET5]

    formula_texto=f'list_MV_{st.session_state["cluster_set_number"]}(Resumen_MV, SETS_coord)'
    sets=eval(formula_texto)

    cords_xy = [(s.utm_x, s.utm_y) for s in sets]
    st.session_state["Total_power"] = sum([(s.power_set) for s in sets])
    print(st.session_state["Total_power"] ,'potencia_total')
    # --- Reubicar clusters (robusto si faltan rutas) ---
    ruta_1 = f'{DXF_FILES}/blade_diameter.dxf'
    ruta_3 = f'{DXF_FILES}/rutas_optimas.dxf'
    from reubicar_cluster import reubicar_cluster
    print(cords_xy,ruta_1,path_restricciones,ruta_3,path_road)
    sets_reubicado = reubicar_cluster(cords_xy, ruta_1, path_restricciones, ruta_3, path_road)

    for i, (x, y) in enumerate(sets_reubicado):
        sets[i].utm_x = round(x, 2)
        sets[i].utm_y = round(y, 2)

    # --- GRID opcional, seguro ---
    GRID_SET = None
    try:
        if os.path.exists(path_grid):
            with open(path_grid, "r", encoding="utf-8") as f:
                data_grid = json.load(f)
            features = data_grid.get("features", [])
            if features:
                coords = features[0]["geometry"]["coordinates"]
                if isinstance(coords, (list, tuple)) and len(coords) >= 2:
                    GRID_SET = SET("grid_on", 0, coords[0], coords[1], 0)
    except Exception as e:
        print(f"[WARN] No se pudo cargar grid → se omite ({e})")

    todos = sets + ([GRID_SET] if GRID_SET else [])



    # --- Lat/Lon para mapa ---
    set_list = convertir_sets_a_latlon(todos, epsg_utm=get_current_utm_epsg())

    if isinstance(set_list, list):
        df = pd.DataFrame(set_list)


    # =========================
    # PERSISTIR para que la UI NO DESAPAREZCA
    # =========================
    st.session_state["ui_ready"] = True
    st.session_state["df_records"] = df.to_dict("records")      # para rehidratar mapa
    st.session_state["todos_sets"] = todos                      # puedes guardar objetos SET
    st.session_state["set_ids"] = df["id"].tolist()             # <-- FIX al bug de iterar DataFrame
    st.session_state["sets_por_id"] = {s.id: s for s in todos}
    st.session_state["orientaciones"] = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    st.session_state["tipos_subestacion"] = ["1_bay_line", "2_bay_line_opposite", "2_bay_line_same"]

# =========================
# UI PERSISTENTE (sólo si ya se ejecutó Cluster SET)
# =========================
if st.session_state["ui_ready"]:
    df = pd.DataFrame(st.session_state["df_records"])
    todos = st.session_state["todos_sets"]
    set_ids = st.session_state["set_ids"]
    ORIENTACIONES = st.session_state["orientaciones"]
    TIPOS_SUBESTACION = st.session_state["tipos_subestacion"]

    # --- Mapa (rehidratado) ---
    fig = px.scatter_mapbox(
        df, lat="lat", lon="lon",
        hover_name="id", zoom=8,
        size=[8] * len(df), size_max=10
    )
    fig.update_layout(
        mapbox_style="open-street-map",
        height=350,
        margin={"r": 50, "t": 50, "l": 50, "b": 50}
    )
    st.plotly_chart(fig, width="stretch")

    st.subheader("Modo de conexión de subestaciones")

    # --- Modo ---
    col_m1, col_m2 = st.columns(2)
    with col_m1:
        modo = st.selectbox(
            "Seleccione el modo:",
            ["Centralized", "Decentralized"],
            key="modo"
        )



    conexiones_obj: List[Connection] = []

    # =========================
    # MODO CENTRALIZADO
    # =========================
    if modo == "Centralized":
        with col_m2:
            set_central = st.selectbox(
                "SET central:",
                set_ids,
                key="set_central"
            )
        st.session_state["set_central_value"] = set_central

        otros = [sid for sid in set_ids if sid != set_central]

        sets_por_id = st.session_state["sets_por_id"]
        set_obj = sets_por_id[set_central]


        coords_otros = {}

        for sid in otros:
            obj = sets_por_id[sid]  # este es el objeto SET
            coords = (obj.utm_x, obj.utm_y)
            coords_otros[sid] = coords

        #st.write("Coordenadas:", set_obj.id)
        #st.write("Coordenadas:", coords_otros)

        st.markdown("###### Centralized set configurations")
        if not otros:
            st.info("No hay otras SETs para conectar a la central.")
        else:
            for i, remoto in enumerate(otros, start=1):
                st.markdown(f"**Conexión {i}: {remoto} → {set_central}**")
                c_a_1, c_a_2, c_a_3, c_a_4 = st.columns([1, 1, 1, 1])

                with c_a_1:
                    st.caption(f"SET remota: {remoto}")
                with c_a_2:
                    ori_rem = st.selectbox(
                        "Orientación (remota)",
                        ORIENTACIONES,
                        key=f"ori_{str(remoto)}_to_{str(set_central)}_rem"
                    )

                with c_a_3:
                    st.caption(f"SET central: {set_central}")
                with c_a_4:
                    ori_cen = st.selectbox(
                        "Orientación (central)",
                        ORIENTACIONES,
                        key=f"ori_{str(remoto)}_to_{str(set_central)}_cen"
                    )

                conexiones_obj.append(
                    Connection(
                        origen=remoto,
                        destino=set_central,
                        orientacion_origen=ori_rem,
                        orientacion_destino=ori_cen,
                        power=sets_por_id[remoto].power_set




                    )
                )

    # =========================
    # MODO DESCENTRALIZADO
    # =========================
    else:
        st.markdown("### Decentralized set Configurations")
        # Regla: número de conexiones = len(set_ids) - 1 (al menos 1)
        n_conexiones = max(len(set_ids) - 1, 1)

        for i in range(n_conexiones):
            st.markdown(f"**Conexión {i+1}**")
            col_in, col_ori_in, col_out, col_ori_out = st.columns(4)

            with col_in:
                entrada = st.selectbox(
                    f"Entrada {i+1}",
                    set_ids,
                    key=f"entrada_{i}"
                )
            with col_ori_in:
                orient_in = st.selectbox(
                    f"Orient. entrada {i+1}",
                    ORIENTACIONES,
                    key=f"orient_in_{i}"
                )
            with col_out:
                salida = st.selectbox(
                    f"Salida {i+1}",
                    set_ids,
                    key=f"salida_{i}"
                )
            with col_ori_out:
                orient_out = st.selectbox(
                    f"Orient. salida {i+1}",
                    ORIENTACIONES,
                    key=f"orient_out_{i}"
                )

            if entrada == salida:
                st.warning(f"Conexión {i+1}: entrada y salida no deben ser la misma SET.")



            conexiones_obj.append(
                Connection(
                    origen=entrada,
                    destino=salida,
                    orientacion_origen=orient_in,
                    orientacion_destino=orient_out,
                    power=default_back_up*st.session_state["Total_power"]


                )
            )

    # =========================
    # Tipos de subestación por SET (visible en ambos modos)
    # =========================
    st.markdown("### CLUSTER SET ")
    st.session_state.setdefault("tipos_por_set", {})
    tipos_por_set: Dict[str, str] = {}
    conexiones_dict = [c.to_dict() for c in conexiones_obj]
    st.session_state['conexiones']=conexiones_dict
    sets_sss=st.session_state["todos_sets"]

    resumenes = [s.resume() for s in sets_sss]
    MV_voltage_set=st.session_state.get("medium_voltage", 33.0)
    current=st.session_state['max_mv_current']
    max_power_building=math.sqrt(3)*MV_voltage_set*current/1000
    modo = st.session_state.get('modo')
    tipos_por_set_local = dict(st.session_state["tipos_por_set"])


    a_10,a_11 ,a_12 ,a_13,a_14,a_15 = st.columns(6)
    temporal_power=0
    total_tf_power=0
    total_shelter_buil=0
    for i in set_ids:

        temporal_power +=round(get_power_of_set(resumenes, i) / 1000, 2)

    for sid in set_ids:
        if modo == 'Centralized':
            if st.session_state["set_central_value"]==sid:
                Power_transfer=round(temporal_power-round(get_power_of_set(resumenes, sid) / 1000, 2),2)
            else:
                Power_transfer=round(get_power_of_set(resumenes, sid) / 1000, 2)
            Total_power = round(get_power_of_set(resumenes, sid) / 1000, 2)
            tf_number = math.ceil(Power_transfer/ 300)
            shelter_number=math.ceil(Total_power/max_power_building)

        else:
            Power_transfer = round(st.session_state['total_power_wf'] * st.session_state['back_up_power'],2)
            Total_power = round(get_power_of_set(resumenes, sid) / 1000, 2)
            tf_number = math.ceil(Power_transfer / 300)
            shelter_number = math.ceil(Total_power / max_power_building)
        total_tf_power+=tf_number
        total_shelter_buil+=shelter_number
        st.session_state["total_trafo"]=total_tf_power
        st.session_state["total_shelter"] = total_shelter_buil

        with a_10:
            f" {sid}"
            st.markdown(f"<div class='big-box'><b>Cluster {sid}</b> &nbsp; </div>", unsafe_allow_html=True)
        with a_11:
            # Rellena valor por defecto si ya había uno guardado
            default_tipo = tipos_por_set_local.get(str(sid), TIPOS_SUBESTACION[0] if TIPOS_SUBESTACION else "")
            tipo = st.selectbox(
                label=f"Tipo SET {sid}",
                options=TIPOS_SUBESTACION,
                index=(TIPOS_SUBESTACION.index(default_tipo) if default_tipo in TIPOS_SUBESTACION else 0),
                key=f"tipo_set_{sid}"
            )
            tipos_por_set_local[str(sid)] = tipo  # actualiza el local

        with a_12:
            f"Power WF Connected SET [MVA]"
            st.markdown(f"<div class='big-box'><b>{Total_power} </b> &nbsp; </div>", unsafe_allow_html=True)
        with a_13:
            f"Power Transfer [MVA]"
            st.markdown(f"<div class='big-box'><b>{Power_transfer} </b> &nbsp; </div>", unsafe_allow_html=True)

        with a_14:
            f"Main Transformer"
            st.markdown(f"<div class='big-box'><b>{tf_number} </b> &nbsp; </div>", unsafe_allow_html=True)

        with a_15:
            f"Shelter_building"
            st.markdown(f"<div class='big-box'><b>{shelter_number} </b> &nbsp; </div>", unsafe_allow_html=True)
    st.session_state["tipos_por_set"] = tipos_por_set_local

    st.write('configuration_set_ok')
st.markdown("<div style='height:40px;'></div>", unsafe_allow_html=True)
st.markdown('### MV Collector System')
st.markdown('##### .....currently under development')

st.markdown("<div style='height:40px;'></div>", unsafe_allow_html=True)
if st.button("MV Collector System"):
    drop_opts = [0.01, 0.02, 0.03, 0.04, 0.05]  # 1% a 5%
    losses_current = [0.005, 0.01, 0.015, 0.02, 0.025, 0.03]  # 1% a 5%
    a_c_10, a_c_11, a_c_12, a_c_13 = st.columns(4)
    with a_c_10:
        st.markdown('MV Voltage [kV]')
        st.markdown(f"<div class='big-box'><b>{default_mv:.2f} kV</b> &nbsp; </div>", unsafe_allow_html=True)
    with a_c_11:
        st.number_input(
                'Thermal Resistance m²·K/W',
                key="thermal_resistance",
                min_value=0.0,
                value=1.5,  # valor por defecto
                step=0.25,
                help="Thermal Resistance"
            )
    with a_c_12:
        st.selectbox(
                "Drop Voltage (%)",
                options=drop_opts,
                key="drop_voltage",
                index=2,  # 0.04 -> 4%
                help="drop voltage (%)",
                format_func=lambda x: f"{x * 100:.0f} %"
            )
    with a_c_13:
        st.selectbox(
                "Losses nominal current (%)",
                options=losses_current,
                key="losses_nominal_current",
                index=2,  # 0.04 -> 4%
                help="losses nominal current (%)",
                format_func=lambda x: f"{x * 100:.2f} %"
            )

    try:

        tipos_por_set: Dict[str, str] = {}
        conexiones_dict = [c.to_dict() for c in conexiones_obj]
        sets_sss = st.session_state["todos_sets"]
        resumenes = [s.resume() for s in sets_sss]
        MV_voltage_set = st.session_state.get("medium_voltage", 33.0)
        current = st.session_state['max_mv_current']
        max_power_building = math.sqrt(3) * MV_voltage_set * current / 1000

        modo = st.session_state.get('modo')

        j = 0
        for i in st.session_state['set_ids']:
            if modo == 'Centralized':
                Total_power = round(get_power_of_set(resumenes, i) / 1000, 2)
                Power_transfer = Total_power
                tf_number = math.ceil(Power_transfer / 300)
                shelter_number = math.ceil(Total_power / max_power_building)
                number_wtgs = get_turbines_sets(resumenes, i)

            else:
                Power_transfer = round(st.session_state['total_power_wf'] * st.session_state['back_up_power'], 2)
                Total_power = round(get_power_of_set(resumenes, i) / 1000, 2)
                tf_number = math.ceil(Power_transfer / 300)
                shelter_number = math.ceil(Total_power / max_power_building)
                number_wtgs = get_turbines_sets(resumenes, i)

            col_in, col_ori_in, col_out, col_ori_out = st.columns(4)

            with col_in:
                f'Substation {j + 1}'
                st.markdown(f"<div class='big-box'><b>{i}</b> &nbsp; </div>", unsafe_allow_html=True)
            with col_ori_in:
                f"Power WF Connected SET [MVA]"
                st.markdown(f"<div class='big-box'><b>{Total_power}</b> &nbsp; </div>", unsafe_allow_html=True)
            with col_out:
                "WTGS Connected"
                st.markdown(f"<div class='big-box'><b> {number_wtgs}</b> &nbsp; </div>", unsafe_allow_html=True)
            with col_ori_out:
                "Shelter Number"
                st.markdown(f"<div class='big-box'><b> {shelter_number}</b> &nbsp; </div>", unsafe_allow_html=True)
            j += 1


        st.success('Pending...........................')

    except:
        st.write('Waiting..........')

st.markdown("<div style='height:40px;'></div>", unsafe_allow_html=True)
st.markdown('### Overhead line')

from ohl_functions import *
conexiones = st.session_state['conexiones']

high_voltage=st.session_state.get("high_voltage", 220.0)
j=1
total_bay_line=0
for i in conexiones:
    col_1_hv,col_2_hv,col_3_hv,col_4_hv,col_5_hv=st.columns(5)
    with col_1_hv:
        'Initial Substation'
        st.markdown(f"<div class='big-box'><b>{i['origen']}</b> &nbsp; </div>", unsafe_allow_html=True)
    with col_2_hv:
        'Final Substation'
        st.markdown(f"<div class='big-box'><b>{i['destino']}</b> &nbsp; </div>", unsafe_allow_html=True)
    with col_3_hv:
        'High Level Voltage[kV]'
        st.markdown(f"<div class='big-box'><b>{high_voltage}</b> &nbsp; </div>", unsafe_allow_html=True)
    with col_4_hv:
        'Power Transfer[MVA]'
        st.markdown(f"<div class='big-box'><b>{round(i['power']/1000,2)}</b> &nbsp; </div>", unsafe_allow_html=True)
    with col_5_hv:
        'Total circuits'
        circuit=math.ceil(power_range(high_voltage,i['power']/1000))
        st.markdown(f"<div class='big-box'><b>{circuit}</b> &nbsp; </div>", unsafe_allow_html=True)
    total_bay_line+=circuit*2
    j+=1
st.session_state['bay_line_ohl']=total_bay_line
st.markdown("<div style='height:40px;'></div>", unsafe_allow_html=True)

if st.button('HV_OHL'):

    tipos_por_set= st.session_state["tipos_por_set"]
    print(tipos_por_set)
    from HV_OHL import main_ohl_main
    path_coord, path_grid, path_road, path_restricciones, path_road_survey, path_wtg = load_inputs_from_init(init)
    ohl_list, ohl_list_files, ohl_coordenadas = main_ohl_main(raster_path, st.session_state["restricciones_path"],
                                                              conexiones, tipos_por_set, st.session_state['todos_sets'],
                                                              DXF_FILES)
    #####ohl cordenadas es para poder determinar los nvertices y determinar las cantidades de torres.

    path_ohl = f"{JSON_FILES}/HV_OHL_RESULTS.json"
    with open(path_ohl, "w", encoding="utf-8") as f:
        json.dump(ohl_list, f, ensure_ascii=False, indent=2)
    path_ohl_coord = f"{JSON_FILES}/coord_ohl.json"
    with open(path_ohl_coord, "w", encoding="utf-8") as f:
        json.dump(ohl_coordenadas, f, ensure_ascii=False, indent=2)
    print(ohl_list_files)
    st.session_state['ohl_list_files'] = ohl_list_files
    st.success('Success!!!')

else:
    st.info("Pulsa **Cluster SET** para ejecutar y mostrar las opciones.")










        

st.markdown("<div style='height:40px;'></div>", unsafe_allow_html=True)
st.markdown('### Post processing')



if st.button("Post"):
    print(st.session_state["bay_line_ohl"],'bahias')
    sets=st.session_state.get('todos_sets')
    sets_por_id = {s.id: s for s in sets}
    excel_path = crear_excel_4_hojas_vertical_desde_rutas(json2_path=f"{JSON_FILES}/HV_OHL_RESULTS.json",json3_path=f"{JSON_FILES}/HV_ROAD_RESULTS.json",
                                                          output_xlsx=f"{EXCEL_FILES}/REPORT_CIVIL.xlsx",
                                                          columnas=("Campo", "Valor")
                                                          )

    rutas = []
    for i in sets_por_id:
        path_a=f'{DXF_FILES}/{i}.dxf'
        rutas.append(path_a)
    list_files=st.session_state.get('ohl_list_files')
    for i in list_files:
        path_b=f'{DXF_FILES}/{i}'
        rutas.append(path_b)


    path_coord, path_grid, path_road, path_restricciones, path_road_survey, path_wtg = load_inputs_from_init(
        init)
    #path_road='salidas/cabeza_mar/caminos/camino_20260206_004518_utm32719.geojson'
    geojson_a_dxf_ezdxf(path_road,f'{DXF_FILES}/camino_existente.dxf',capa="camino_existente")

    from buffer_polilinea import buffer_caminos_dxf

    ancho_camino_1 = st.session_state["road_width"]
    path_buffer= f"{DXF_FILES}/rutas_optimas.dxf"
    path_buffer_out=f"{DXF_FILES}/rutas_optimas_buffer.dxf"
    buffer_caminos_dxf(ruta_dxf=path_buffer,ancho_camino=ancho_camino_1,  salida_dxf=path_buffer_out)

    rutas.append(f"{DXF_FILES}/PLATFORM.dxf")
    rutas.append(f"{DXF_FILES}/rutas_optimas_buffer.dxf")
    rutas.append(f"{DXF_FILES}/camino_existente.dxf")
    out = unir_dxf_en_un_archivo(
        rutas_dxf=rutas,
        salida_dxf=f"{EXCEL_FILES}/PLANO_PROJ.dxf"
    )
    print(EXCEL_FILES)
    


    print("DXF unificado:", out)

    st.success('Success!!!')
    #crear_excel_reporte_auto

else:
        st.write("Esperando a que presiones el botón...")


