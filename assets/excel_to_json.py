# -*- coding: utf-8 -*-
"""
Script: excel_to_json.py
Convierte assets/DB_PLATFORM.xlsx -> assets/db_platform.json una sola vez.
Luego, la app usará únicamente el JSON.
"""
import os, json
from typing import Dict, Any
import pandas as pd

EXCEL = './DB_PLATFORM.xlsx'
JSON  = './db_platform.json'

if not os.path.exists(EXCEL):
    raise FileNotFoundError(f"No existe el Excel: {EXCEL}")

xl = pd.ExcelFile(EXCEL, engine='openpyxl')
wtg = pd.read_excel(xl, sheet_name='WTG')
power = pd.read_excel(xl, sheet_name='POWER MW')
blade = pd.read_excel(xl, sheet_name='DIAMETER_BLADE')
transform = pd.read_excel(xl, sheet_name='TRANSFORM')
platform = pd.read_excel(xl, sheet_name='PLATFORM')

# Compatibilidad modelo-torre (X)
tower_cols = [c for c in wtg.columns if isinstance(c, (int, float))]
tower_map = {c: str(wtg.loc[0, c]) for c in tower_cols}
model_compat = {}
for _, row in wtg.iterrows():
    model = row.get('Unnamed: 1')
    if not isinstance(model, str) or model == 'WTG Model':
        continue
    comp = []
    for c in tower_cols:
        val = str(row.get(c)).strip().lower()
        if val in ('x', 'x '):
            comp.append(tower_map[c])
    model_compat[model] = sorted(set(comp))

# Potencias
model_powers: Dict[str, Any] = {}
for _, r in power.iterrows():
    model = r.get('Unnamed: 1')
    if not isinstance(model, str) or model == 'WTG Model':
        continue
    p = r.get('Unnamed: 2'); q = r.get('Unnamed: 3'); s = r.get('Unnamed: 4')
    if pd.isna(p):
        continue
    try: p_val = float(p)
    except Exception: continue
    p_mw = p_val/1000.0 if p_val > 100 else p_val
    entry = {"power_mw": round(p_mw, 3), "power_raw": p_val}
    if not pd.isna(q): entry["q_var"] = float(q)
    if not pd.isna(s): entry["s_mva"] = float(s)
    model_powers.setdefault(model, []).append(entry)

# Diámetro rotor
model_blade = {}
for _, r in blade.iterrows():
    model = r.get('Unnamed: 1')
    if not isinstance(model, str) or model == 'WTG Model':
        continue
    d = r.get('Unnamed: 2')
    if pd.isna(d): continue
    try: model_blade[model] = float(d)
    except Exception: pass

# Transformador
model_transform = {}
for _, r in transform.iterrows():
    model = r.get('Unnamed: 1')
    if not isinstance(model, str) or model == 'WTG Model':
        continue
    d = {}
    nll50 = r.get('frequency 50hz'); scl50 = r.get('Unnamed: 3')
    if not (pd.isna(nll50) and pd.isna(scl50)):
        d['50hz'] = {}
        if not pd.isna(nll50): d['50hz']['nll_kw'] = float(nll50)
        if not pd.isna(scl50): d['50hz']['scl_kw'] = float(scl50)
    nll60 = r.get('Frecquency 60hz'); scl60 = r.get('Unnamed: 5')
    if not (pd.isna(nll60) and pd.isna(scl60)):
        d['60hz'] = {}
        if not pd.isna(nll60): d['60hz']['nll_kw'] = float(nll60)
        if not pd.isna(scl60): d['60hz']['scl_kw'] = float(scl60)
    kva = r.get('Powe Transformer (kVA)')
    if not pd.isna(kva): d['transformer_kva'] = float(kva)
    if d: model_transform[model] = d

# Plataforma torre
col_dict = {
    'tower_code': 'Unnamed: 1',
    'road_pad': ['ROAD PAD','Unnamed: 4','Unnamed: 5','Unnamed: 6'],
    'crane_boom_pad': ['CRANE BOOM PAD','Unnamed: 8','Unnamed: 9','Unnamed: 10'],
    'blade_pad': ['BLADES PAD','Unnamed: 12','Unnamed: 13','Unnamed: 14'],
    'road_extension': ['ROAD EXTENSION','Unnamed: 16','Unnamed: 17','Unnamed: 18'],
    'crane_pad_1': ['CRANE PAD 1','Unnamed: 20','Unnamed: 21','Unnamed: 22'],
    'crane_pad_2': ['CRANE PAD 2','Unnamed: 24','Unnamed: 25','Unnamed: 26'],
    'pre1': ['Preassembly 1','Unnamed: 28','Unnamed: 29'],
    'pre2': ['Preassembly 2','Unnamed: 31','Unnamed: 32'],
    'pre3': ['Preassembly 3','Unnamed: 34','Unnamed: 35'],
    'pre4': ['Preassembly 4','Unnamed: 37','Unnamed: 38'],
    'pre5': ['Preassembly 5','Unnamed: 40','Unnamed: 41'],
    'pre6': ['Preassembly 6','Unnamed: 43','Unnamed: 44'],
    'entry_x': 'entry',
    'entry_y': 'Unnamed: 47',
    'out_x': 'out',
    'out_y': 'Unnamed: 49',
    'wide_road': 'Unnamed: 2',
    'diameter': 'Diameter'
}

def _read_pad(row, keys):
    vals = [row.get(keys[0]), row.get(keys[1]), row.get(keys[2]), row.get(keys[3])]
    if any(not pd.isna(v) for v in vals):
        out = []
        for v in vals:
            try: out.append(float(v))
            except Exception: out.append(0.0)
        return tuple(out)
    return None

def _read_pre(row, keys):
    vals = [row.get(keys[0]), row.get(keys[1]), row.get(keys[2])]
    if any(not pd.isna(v) for v in vals):
        out = []
        for v in vals:
            try: out.append(float(v))
            except Exception: out.append(0.0)
        return tuple(out)
    return (0.0, 0.0, 0.0)

platform_db = {}
for _, r in platform.iterrows():
    tower = r.get(col_dict['tower_code'])
    if not isinstance(tower, str):
        continue
    if not tower.startswith(('TS','TC','TCS')):
        continue
    entry_x = r.get(col_dict['entry_x']); entry_y = r.get(col_dict['entry_y'])
    out_x = r.get(col_dict['out_x']);     out_y = r.get(col_dict['out_y'])
    try:
        entry = (float(entry_x), float(entry_y)) if not (pd.isna(entry_x) or pd.isna(entry_y)) else (0.0, 0.0)
    except Exception:
        entry = (0.0, 0.0)
    try:
        outp = (float(out_x), float(out_y)) if not (pd.isna(out_x) or pd.isna(out_y)) else (0.0, 0.0)
    except Exception:
        outp = (0.0, 0.0)
    pads = {}
    for key in ['road_pad','crane_boom_pad','blade_pad','road_extension','crane_pad_1','crane_pad_2']:
        pad = _read_pad(r, col_dict[key])
        if pad is not None:
            pads[key] = pad
    preassembly = {
        'preassembly_1': _read_pre(r, col_dict['pre1']),
        'preassembly_2': _read_pre(r, col_dict['pre2']),
        'preassembly_3': _read_pre(r, col_dict['pre3']),
        'preassembly_4': _read_pre(r, col_dict['pre4']),
        'preassembly_5': _read_pre(r, col_dict['pre5']),
        'preassembly_6': _read_pre(r, col_dict['pre6'])
    }
    wide_road_m = r.get(col_dict['wide_road'])
    try:
        wide_road_m = float(wide_road_m) if wide_road_m is not None and str(wide_road_m) != '' and not pd.isna(wide_road_m) else None
    except Exception:
        wide_road_m = None
    diameter_m = r.get(col_dict['diameter'])
    try:
        diameter_m = float(diameter_m) if diameter_m is not None and str(diameter_m) != '' and not pd.isna(diameter_m) else None
    except Exception:
        diameter_m = None
    platform_db[tower] = {
        'entry_point': entry,
        'exit_point': outp,
        'pads': pads,
        'preassembly': preassembly,
        'wide_road_m': wide_road_m,
        'platform_diameter_m': diameter_m
    }

# Construir DB final y guardar
db: Dict[str, Any] = {
    'models': sorted(list(model_compat.keys())),
    'compatibility': model_compat,
    'power': model_powers,
    'blade_diameter_m': model_blade,
    'transform': model_transform,
    'tower_platform': platform_db,
}

os.makedirs(os.path.dirname(JSON), exist_ok=True)
with open(JSON, 'w', encoding='utf-8') as f:
    json.dump(db, f, ensure_ascii=False, indent=2)
print(f"Creado JSON: {JSON}")
