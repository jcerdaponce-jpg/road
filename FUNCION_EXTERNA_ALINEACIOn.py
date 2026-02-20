
import json
import math
from typing import Dict, List, Tuple
from collections import defaultdict

# -----------------------------
# Helpers de parsing / geometría
# -----------------------------
def _is_camino(name: str) -> bool:
    return name.startswith("camino_")

def _is_wtg_entry(name: str) -> bool:
    return name.startswith("wtg_") and name.endswith("_entry")

def _is_wtg_out(name: str) -> bool:
    return name.startswith("wtg_") and name.endswith("_out")

def _wtg_id_from(name: str) -> str:
    """
    Extrae el ID del patrón wtg_<ID>_entry|out.
    Soporta IDs con subrayados internos (p.ej. wtg_12_A_entry).
    """
    parts = name.split("_")
    return "_".join(parts[1:-1])  # todo menos 'wtg' y el sufijo 'entry'/'out'

def _build_name2xy(edges: List[Dict]) -> Dict[str, Tuple[float, float]]:
    """
    Crea un índice nombre -> (x, y) a partir de las aristas del MST final.
    """
    name2xy = {}
    for e in edges:
        for side in ("origen", "destino"):
            n = e[side]
            name2xy[n["nombre"]] = (n["x"], n["y"])
    return name2xy

def _angle_deg(vx: float, vy: float) -> float:
    """
    Heading del vector (vx, vy) en grados [0, 360).
    """
    ang = math.degrees(math.atan2(vy, vx))
    return (ang + 360.0) % 360.0

# -----------------------------
# 1) Vectores entry->out por WTG
# -----------------------------
def compute_wtg_vectors_from_edges(edges: List[Dict]) -> Dict[str, Dict]:
    """
    Devuelve, para cada WTG detectado en edges, el vector entry->out y su heading:
      {
        '<wtg_id>': {
           'entry': (xe, ye),
           'out': (xo, yo),
           'vector': (vx, vy),
           'heading_deg': <float>,
           'modulo': <float>
        }, ...
      }
    """
    name2xy = _build_name2xy(edges)
    result: Dict[str, Dict] = {}

    # Buscar todas las 'entry' y comprobar si existe su 'out' correspondiente
    for name in list(name2xy.keys()):
        if _is_wtg_entry(name):
            wid = _wtg_id_from(name)
            entry_name = f"wtg_{wid}_entry"
            out_name   = f"wtg_{wid}_out"
            if entry_name in name2xy and out_name in name2xy:
                (xe, ye) = name2xy[entry_name]
                (xo, yo) = name2xy[out_name]
                vx, vy = (xo - xe, yo - ye)
                result[wid] = {
                    "entry": (xe, ye),
                    "out": (xo, yo),
                    "vector": (vx, vy),
                    "heading_deg": round(_angle_deg(vx, vy), 3),
                    "modulo": (vx**2 + vy**2) ** 0.5
                }
    return result

# -----------------------------------------------------------
# 2) Turbinas cuyo ENTRY está conectado a algún 'camino_*'
# -----------------------------------------------------------
def wtg_entries_connected_to_camino(edges: List[Dict]):
    """
    Devuelve:
      - wtg_ids: lista ordenada de IDs de WTG cuyo *entry* conecta con un 'camino_*'
      - detalle: dict[wtg_id] -> lista de dicts con info del/los camino(s)
    """
    detalle = defaultdict(list)
    for idx, e in enumerate(edges):
        o = e["origen"]["nombre"]
        d = e["destino"]["nombre"]

        # camino_*  -> wtg_*_entry
        if _is_camino(o) and _is_wtg_entry(d):
            wid = _wtg_id_from(d)
            detalle[wid].append({
                "camino": o,
                "edge_index": idx,
                "sentido": "camino -> wtg_entry",
                "distancia_real": e.get("distancia_real"),
                "costo_ponderado": e.get("costo_ponderado"),
            })
        # wtg_*_entry -> camino_*
        elif _is_wtg_entry(o) and _is_camino(d):
            wid = _wtg_id_from(o)
            detalle[wid].append({
                "camino": d,
                "edge_index": idx,
                "sentido": "wtg_entry -> camino",
                "distancia_real": e.get("distancia_real"),
                "costo_ponderado": e.get("costo_ponderado"),
            })

    wtg_ids = sorted(detalle.keys(), key=lambda x: (len(x), x))
    return wtg_ids, dict(detalle)

# --------------------------------------------------------
# 3) Lista de turbinas interconectadas (WTG ↔ WTG)
# --------------------------------------------------------
def list_wtg_interconnections(edges: List[Dict], include_internal: bool = False):
    """
    Devuelve lista de pares (from_wtg, to_wtg, edge_index) para aristas del tipo:
      wtg_*_out  <->  wtg_*_entry
    Si include_internal=False (por defecto), excluye los pares (X -> X)
    """
    pairs = []
    for idx, e in enumerate(edges):
        o = e["origen"]["nombre"]
        d = e["destino"]["nombre"]
        if _is_wtg_out(o) and _is_wtg_entry(d):
            a, b = _wtg_id_from(o), _wtg_id_from(d)
            if include_internal or (a != b):
                pairs.append((a, b, idx))
        elif _is_wtg_out(d) and _is_wtg_entry(o):
            a, b = _wtg_id_from(d), _wtg_id_from(o)
            if include_internal or (a != b):
                pairs.append((a, b, idx))
    return pairs

# -----------------------------
# (Opcional) Cargar desde archivo
# ----------------------------

def load_edges(path: str) -> List[Dict]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

FOLDER_NAME_1=""
path_final = f".{FOLDER_NAME_1}/e_mst.json"
edges=load_edges(path_final)

# 1) Direcciones entry->out por turbina
wtg_vectors = compute_wtg_vectors_from_edges(edges)
print(wtg_vectors)

wtg_ids, detalle = wtg_entries_connected_to_camino(edges)
print("WTG con entry conectado a camino:", wtg_ids)
print("Detalle:", detalle)

# 3) Lista de turbinas interconectadas (entre distintas turbinas)
intercon = list_wtg_interconnections(edges, include_internal=False)
print("Interconexiones WTG (A -> B):", intercon)
