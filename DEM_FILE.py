
# DEM_FILE.py
import os, json
from pathlib import Path

class RutaDEMNoDefinida(Exception):
    pass

def _get_from_streamlit():
    try:
        import streamlit as st
        return st.session_state.get("paths", {}).get("raster_file")
    except Exception:
        return None

def _get_from_env(var_name="RASTER_FILE"):
    return os.environ.get(var_name)

def _get_from_config(config_path):
    if not config_path: return None
    p = Path(config_path)
    if not p.exists(): return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data.get("raster_file")
    except Exception:
        return None

def dem_file(required: bool = False,
             default_path: str | None = None,
             env_var: str = "RASTER_FILE",
             config_path: str | None = None) -> str | None:
    """
    Devuelve la ruta del DEM o None si no puede resolverla.
    Si required=True, valida existencia y lanza error si no existe.
    """
    candidates = [
        _get_from_streamlit(),
        _get_from_env(env_var),
        _get_from_config(config_path),
        default_path,
    ]
    for val in candidates:
        if val:
            p = Path(val).expanduser().resolve()
            if required and not p.exists():
                raise FileNotFoundError(f"El DEM no existe: {p}")
            return str(p)
    # Si nada funciona:
    if required:
        raise RutaDEMNoDefinida(
            "DEM no configurado. Define 'RASTER_FILE' en el entorno, sube/guarda el raster en la app, o pasa 'default_path'."
        )
    return None  # <- Tolerante: al inicio devuelve None
