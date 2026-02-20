from bisect import bisect_right

def get_factor_penalizacion_bins7(slope_value: float) -> float:
    """
    7 factores y 6 cortes configurables en 'st.session_state["slope_bins_7"]'.
    Reglas:
      - s == 0  -> idx 0
      - s  > 0  -> idx = bisect_right(cortes, s), acotado a 1..6
    """
    s = abs(float(slope_value))

    try:
        import streamlit as st
        factors = st.session_state.get("factor_penalizacion", [1, 2, 3, 4, 5, 6, 7])
        bins    = st.session_state.get("slope_bins_7",        [0, 3, 6, 9, 12, 15])
    except Exception:
        # Fallback si corres fuera de Streamlit
        factors = [1, 2, 3, 4, 5, 6, 7]
        bins    = [0, 3, 6, 9, 12, 15]

    # Sanitización por si el usuario cambió tamaños accidentalmente
    if len(factors) != 7:
        factors = (factors + [factors[-1]] * 7)[:7]
    if len(bins) != 6:
        bins = [0, 3, 6, 9, 12, 15]

    if s == 0.0:
        idx = 0
    else:
        idx = bisect_right(bins, s)      # 1..6 si cae dentro / >6 si supera el último corte
        idx = min(max(idx, 1), 6)        # asegurar 1..6 para s>0

    return float(factors[idx])
s=
print(get_factor_penalizacion_bins7(s))