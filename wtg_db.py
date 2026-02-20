# -*- coding: utf-8 -*-
"""
Módulo: wtg_db (JSON-only)

Gestiona la base de datos en JSON: carga, guardado y edición.
Estructura esperada del JSON (resumen):
{
  "models": ["N149/5.X", ...],
  "compatibility": { "N149/5.X": ["TS84", ...], ... },
  "power": { "N149/5.X": [ {"power_mw": 5.7, "q_var": 2761.0, "s_mva": 6333.49}, ... ] },
  "blade_diameter_m": { "N149/5.X": 149.1, ... },
  "foundation_diameter_m": { "N149/5.X": 16.2, ... },
  "transform": { "N149/5.X": { "50hz": {"nll_kw": 2900.0, "scl_kw": 70000.0}, "60hz": {...}, "transformer_kva": 6350.0 } },
  "tower_platform": { "TS108-05": { "entry_point": [x,y], "exit_point": [x,y],
                      "pads": {"road_pad": [x1,y1,x2,y2], ...},
                      "preassembly": {"preassembly_1": [xc,yc,r], ...},
                      "wide_road_m": 12.0, "platform_diameter_m": 60.0 } }
}
"""
from typing import Dict, List, Any, Optional
import json, os

DEFAULT_JSON = 'assets/db_platform.json'

# ---------------------------
# Carga / guardado
# ---------------------------
def load_db(json_path: Optional[str] = None) -> Dict[str, Any]:
    json_path = json_path or DEFAULT_JSON
    if not os.path.exists(json_path):
        raise FileNotFoundError(f"No existe el JSON: {json_path}")
    with open(json_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_db(db: Dict[str, Any], json_path: Optional[str] = None) -> str:
    json_path = json_path or DEFAULT_JSON
    os.makedirs(os.path.dirname(json_path), exist_ok=True)
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(db, f, ensure_ascii=False, indent=2)
    return json_path

# ---------------------------
# Lecturas helper
# ---------------------------
def get_models(db: Dict[str, Any]) -> List[str]:
    return db.get('models', [])

def get_compatible_towers(db: Dict[str, Any], model: Optional[str]) -> List[str]:
    if not model:
        return []
    return db.get('compatibility', {}).get(model, [])

def get_power_variants(db: Dict[str, Any], model: Optional[str]) -> List[Dict[str, Any]]:
    if not model:
        return []
    return db.get('power', {}).get(model, [])

def get_blade_diameter(db: Dict[str, Any], model: Optional[str]) -> Optional[float]:
    if not model:
        return None
    return db.get('blade_diameter_m', {}).get(model)

def get_foundation_diameter(db: Dict[str, Any], model: Optional[str]) -> Optional[float]:
    if not model:
        return None
    return db.get('foundation_diameter_m', {}).get(model)

def get_platform(db: Dict[str, Any], tower: Optional[str]) -> Optional[Dict[str, Any]]:
    if not tower:
        return None
    return db.get('tower_platform', {}).get(tower)

# ---------------------------
# Edición
# ---------------------------
def model_exists(db: Dict[str, Any], model_name: str, case_insensitive: bool = True) -> bool:
    if not isinstance(model_name, str):
        return False
    name = model_name.strip()
    models = db.get('models', []) or []
    if case_insensitive:
        names = [str(m).strip().lower() for m in models]
        return name.lower() in names
    return name in models

def add_model(db: Dict[str, Any], model_name: str,
              compatible_towers: List[str],
              power_variants: List[Dict[str, Any]],
              blade_diameter_m: float,
              foundation_diameter_m: Optional[float] = None,
              transform_info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if not isinstance(model_name, str) or not model_name.strip():
        raise ValueError('model_name inválido')
    m = model_name.strip()
    models = set(db.get('models', []))
    models.add(m)
    db['models'] = sorted(models)
    db.setdefault('compatibility', {})[m] = sorted(set(compatible_towers or []))
    clean_vars: List[Dict[str, Any]] = []
    for v in (power_variants or []):
        try: p = float(v.get('power_mw'))
        except Exception: continue
        e = {'power_mw': round(p, 3)}
        if v.get('q_var') is not None:
            try: e['q_var'] = float(v['q_var'])
            except Exception: pass
        if v.get('s_mva') is not None:
            try: e['s_mva'] = float(v['s_mva'])
            except Exception: pass
        clean_vars.append(e)
    db.setdefault('power', {})[m] = clean_vars
    try:
        db.setdefault('blade_diameter_m', {})[m] = float(blade_diameter_m)
    except Exception: pass
    if foundation_diameter_m is not None:
        try: db.setdefault('foundation_diameter_m', {})[m] = float(foundation_diameter_m)
        except Exception: pass
    if transform_info:
        out: Dict[str, Any] = {}
        if '50hz' in transform_info:
            out['50hz'] = {}
            for k in ('nll_kw','scl_kw'):
                if transform_info['50hz'].get(k) is not None:
                    out['50hz'][k] = float(transform_info['50hz'][k])
        if '60hz' in transform_info:
            out['60hz'] = {}
            for k in ('nll_kw','scl_kw'):
                if transform_info['60hz'].get(k) is not None:
                    out['60hz'][k] = float(transform_info['60hz'][k])
        if transform_info.get('transformer_kva') is not None:
            out['transformer_kva'] = float(transform_info['transformer_kva'])
        db.setdefault('transform', {})[m] = out
    return db

def set_platform_for_tower(db: Dict[str, Any], tower_code: str, platform: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(tower_code, str) or not tower_code.strip():
        raise ValueError('tower_code inválido')
    t = tower_code.strip()
    tp = db.setdefault('tower_platform', {})
    entry = tuple(platform.get('entry_point', (0.0, 0.0)))
    exitp = tuple(platform.get('exit_point', (0.0, 0.0)))
    pads = platform.get('pads', {}) or {}
    preassembly = platform.get('preassembly', {}) or {}
    wide_road_m = platform.get('wide_road_m')
    platform_diameter_m = platform.get('platform_diameter_m')
    out: Dict[str, Any] = {
        'entry_point': (float(entry[0]), float(entry[1])) if len(entry) >= 2 else (0.0, 0.0),
        'exit_point': (float(exitp[0]), float(exitp[1])) if len(exitp) >= 2 else (0.0, 0.0),
        'pads': {k: tuple(v) for k, v in pads.items()},
        'preassembly': preassembly,
    }
    if wide_road_m is not None:
        try: out['wide_road_m'] = float(wide_road_m)
        except Exception: pass
    if platform_diameter_m is not None:
        try: out['platform_diameter_m'] = float(platform_diameter_m)
        except Exception: pass
    tp[t] = out
    return db
