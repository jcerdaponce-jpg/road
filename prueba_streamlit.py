import streamlit as st
import streamlit as st

# ---------------------------
# Estado: mostrar UI o no
# ---------------------------
if "ui_ready" not in st.session_state:
    st.session_state["ui_ready"] = False

# (Opcional) Botón para reiniciar
def reset_ui():
    # Si prefieres no limpiar todo el estado, borra solo lo necesario
    for k in list(st.session_state.keys()):
        if k.startswith(("ori_", "entrada_", "salida_", "orient_in_", "orient_out_", "tipo_set_", "set_central")):
            st.session_state.pop(k, None)
    st.session_state["ui_ready"] = False

# ---------------------------
# Botón que habilita la UI
# ---------------------------
col_b1, col_b2 = st.columns([1, 1])
with col_b1:
    if st.button("Cluster SET"):
        st.session_state["ui_ready"] = True
with col_b2:
    st.button("Reiniciar configuración", on_click=reset_ui)

# ---------------------------
# Renderiza la UI sólo si se pulsó el botón
# ---------------------------
if st.session_state["ui_ready"]:

    # =========================
    # Datos base (puedes reemplazarlos por los reales; si ya los tienes, léelos de session_state)
    # =========================
    if "set_ids" not in st.session_state:
        st.session_state["set_ids"] = [1, 2, 3, 4]  # <-- Reemplaza por tus IDs reales
    set_ids = st.session_state["set_ids"]

    ORIENTACIONES = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    TIPOS_SUBESTACION = [
        "1_bay_line",
        "2_bay_line_opposite",
        "2_bay_line_same"
    ]

    st.title("Configuración de conexiones entre subestaciones")

    # =========================
    # Modo de operación
    # =========================
    col_m1, col_m2 = st.columns(2)

    with col_m1:
        modo = st.selectbox(
            "Seleccione el modo:",
            ["centralized", "decentralized"],
            key="modo"
        )

    # =========================
    # MODO CENTRALIZADO
    # =========================
    if modo == "centralized":
        with col_m2:
            set_central = st.selectbox(
                "SET central:",
                set_ids,
                key="set_central"
            )

        otros = [sid for sid in set_ids if sid != set_central]

        st.markdown("### Conexiones automáticas hacia la SET central")
        if not otros:
            st.info("No hay otras SETs para conectar a la central.")
        else:
            conexiones = []
            for i, remoto in enumerate(otros, start=1):
                st.markdown(f"**Conexión {i}: {remoto} → {set_central}**")
                c1, c2, c3, c4 = st.columns([1.2, 1, 1.2, 1])

                with c1:
                    st.caption(f"SET remota: {remoto}")
                with c2:
                    ori_rem = st.selectbox(
                        "Orientación (remota)",
                        ORIENTACIONES,
                        key=f"ori_{str(remoto)}_to_{str(set_central)}_rem"
                    )
                with c3:
                    st.caption(f"SET central: {set_central}")
                with c4:
                    ori_cen = st.selectbox(
                        "Orientación (central)",
                        ORIENTACIONES,
                        key=f"ori_{str(remoto)}_to_{str(set_central)}_cen"
                    )

                conexiones.append({
                    "origen": remoto,
                    "destino": set_central,
                    "orientacion_origen": ori_rem,
                    "orientacion_destino": ori_cen
                })

            st.markdown("#### Resumen de conexiones")
            #st.write(conexiones)

    # =========================
    # MODO DESCENTRALIZADO
    # =========================
    else:
        st.markdown("### Configuración de conexiones descentralizadas")
        # Regla pedida: número de conexiones = len(set_ids) - 1 (al menos 1)
        n_conexiones = max(len(set_ids) - 1, 1)

        conexiones = []
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

            conexiones.append({
                "conexion": i+1,
                "entrada": entrada,
                "salida": salida,
                "orientacion_entrada": orient_in,
                "orientacion_salida": orient_out
            })

        st.markdown("#### Resumen de conexiones")
        st.write(conexiones)

    # =========================
    # Tipos de subestación por SET (visible en ambos modos)
    # =========================
    st.markdown("### Tipo de subestación por cada SET")
    for sid in set_ids:
        st.selectbox(
            f"Tipo SET {sid}",
            TIPOS_SUBESTACION,
            key=f"tipo_set_{sid}"
        )

else:
    st.info("Pulsa **Cluster SET** para mostrar las opciones.")