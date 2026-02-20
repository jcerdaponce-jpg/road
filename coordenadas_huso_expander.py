
# -*- coding: utf-8 -*-
"""
Módulo: coordenadas_huso_expander.py

Renderiza el expander "Coordenadas / HUSO (para centrar el mapa)" de Streamlit,
listo para incluirlo en cualquier app. Soporta tres modos: Lat/Lon (WGS84),
UTM (HUSO) y EPSG directo. Sincroniza centro/zoom y CRS del proyecto.

Uso:
    from coordenadas_huso_expander import render_coordenadas_huso_sidebar
    render_coordenadas_huso_sidebar(
        init=st.session_state,
        HAS_PYPROJ=HAS_PYPROJ,
        utm_zone_from_lon=utm_zone_from_lon,
        utm_to_wgs84=utm_to_wgs84,
        make_transformer_from_epsg=make_transformer_from_epsg,
    )
"""

import streamlit as st


def render_coordenadas_huso_sidebar(
    *,
    init: dict,
    HAS_PYPROJ: bool,
    utm_zone_from_lon,
    utm_to_wgs84,
    make_transformer_from_epsg,
):
    """Renderiza el expander de 'Coordenadas / HUSO (para centrar el mapa)'."""

    # --- Utilidades locales de robustez (solo para este expander) ---
    def _to_float(v, default):
        try:
            return float(v)
        except Exception:
            return float(default)

    def _safe_zone_from_lon(lon_val, default_zone=13):
        try:
            return int(utm_zone_from_lon(float(lon_val)))
        except Exception:
            return int(default_zone)

    def _is_utm_epsg(epsg: int) -> bool:
        return (32601 <= epsg <= 32660) or (32701 <= epsg <= 32760)

    def _utm_from_epsg(epsg: int):
        """Devuelve (huso, hemisferio) desde un EPSG UTM."""
        if 32601 <= epsg <= 32660:
            return int(str(epsg)[-2:]), 'Norte'
        if 32701 <= epsg <= 32760:
            return int(str(epsg)[-2:]), 'Sur'
        return None, None

    # --- Estado actual como base ---
    lat_actual  = _to_float(init.get('map_center', [0.0, 0.0])[0], 0.0)
    lon_actual  = _to_float(init.get('map_center', [0.0, 0.0])[1], 0.0)
    zoom_actual = int(init.get('map_zoom', 4))

    with st.sidebar.expander('Coordenadas / HUSO (para centrar el mapa)', expanded=False):
        # --- Selección de modo ---
        coord_mode = st.radio(
            'Modo de entrada',
            ["Lat/Lon (WGS84)", "UTM (HUSO)", "EPSG directo"],
            index=0,
            key='ui_center_mode'
        )

        # Variables a aplicar
        lat, lon, zoom = lat_actual, lon_actual, zoom_actual
        epsg_activo = None
        huso_center = None
        hemisferio_center = None

        # ========== 1) LAT/LON (WGS84) ==========
        if coord_mode == "Lat/Lon (WGS84)":
            lat  = st.number_input('Latitud',  value=lat_actual, format='%.6f', key='ui_lat_wgs')
            lon  = st.number_input('Longitud', value=lon_actual, format='%.6f', key='ui_lon_wgs')
            zoom = st.slider('Zoom', 2, 18, value=zoom_actual, key='ui_zoom_wgs')

            huso_estimado = _safe_zone_from_lon(lon, default_zone=13)
            st.caption(f"HUSO estimado a partir de la longitud: **{huso_estimado}**")

            fijar_crs_auto = st.checkbox(
                "Fijar CRS del proyecto desde este centro (UTM auto según Lon/Lat)",
                value=True,
                key='ui_fix_crs_from_wgs84'
            )
            if fijar_crs_auto:
                hemisferio_center = 'Norte' if float(lat) >= 0.0 else 'Sur'
                epsg_activo = (32600 + huso_estimado) if hemisferio_center == 'Norte' else (32700 + huso_estimado)

        # ========== 2) UTM (HUSO) ==========
        elif coord_mode == "UTM (HUSO)":
            huso_center = st.number_input(
                'HUSO UTM (1–60)', min_value=1, max_value=60,
                value=_safe_zone_from_lon(lon_actual, default_zone=13),
                step=1, key='ui_huso'
            )
            hemisferio_center = st.selectbox('Hemisferio', ["Norte", "Sur"], index=0, key='ui_hemisferio')
            zoom = st.slider('Zoom', 2, 18, value=zoom_actual, key='ui_zoom_utm')

            epsg_activo = (32600 + int(huso_center)) if hemisferio_center == "Norte" else (32700 + int(huso_center))
            st.caption(f"EPSG activo (UTM): **{epsg_activo}**")

            en_checked = st.checkbox('Introducir Easting/Northing (pyproj)', value=False, key='ui_use_en')
            if HAS_PYPROJ and en_checked:
                easting_c  = st.number_input('Easting (m)',  value=500000.0, step=1.0, key='ui_easting')
                northing_c = st.number_input('Northing (m)', value=4730000.0, step=1.0, key='ui_northing')
                try:
                    lon, lat = utm_to_wgs84(huso_center, hemisferio_center, float(easting_c), float(northing_c))
                    st.success(f"Centro: lat={lat:.6f}, lon={lon:.6f}")
                    if not (166021.0 <= float(easting_c) <= 833979.0):
                        st.info("⚠ Easting fuera del rango típico UTM (166 021–833 979 m).")
                    if not (0.0 <= float(northing_c) <= 10_000_000.0):
                        st.info("⚠ Northing fuera del rango típico UTM (0–10 000 000 m).")
                except Exception as e:
                    st.error(f"UTM→WGS84 falló: {e}")
                    lon = -183 + 6 * int(huso_center)   # Fallback: meridiano central
                    lat = lat_actual
            elif en_checked and not HAS_PYPROJ:
                st.error("pyproj no está disponible. Instala 'pyproj' o desmarca Easting/Northing.")
            else:
                lon = -183 + 6 * int(huso_center)      # Sin EN: meridiano central
                lat = st.number_input('Latitud aproximada', value=lat_actual, format='%.6f', key='ui_lat_utm')
                st.info('Usando meridiano central del HUSO como longitud.')

        # ========== 3) EPSG DIRECTO ==========
        else:
            epsg_input = st.number_input('EPSG del proyecto (ej.: 4326, 3857, 32617, 32719)',
                                         min_value=2000, max_value=70000, value=4326, step=1,
                                         key='ui_epsg_direct')
            zoom = st.slider('Zoom', 2, 18, value=zoom_actual, key='ui_zoom_epsg')
            epsg_activo = int(epsg_input)

            if _is_utm_epsg(epsg_activo):
                huso_center, hemisferio_center = _utm_from_epsg(epsg_activo)
                st.caption(f"Detectado UTM — HUSO **{huso_center}** Hemisferio **{hemisferio_center}**")
                en_checked = st.checkbox('Introducir Easting/Northing (pyproj) con este EPSG', value=False, key='ui_use_en_epsg')
                if HAS_PYPROJ and en_checked:
                    easting_c  = st.number_input('Easting (m)',  value=500000.0, step=1.0, key='ui_easting_epsg')
                    northing_c = st.number_input('Northing (m)', value=4730000.0, step=1.0, key='ui_northing_epsg')
                    try:
                        tf = make_transformer_from_epsg(epsg_activo)
                        if tf is None:
                            raise RuntimeError("Transformer no disponible.")
                        lon, lat = tf.transform(float(easting_c), float(northing_c))
                        st.success(f"Centro: lat={lat:.6f}, lon={lon:.6f}")
                    except Exception as e:
                        st.error(f"Transformación EPSG→WGS84 falló: {e}")
                        lon, lat = lon_actual, lat_actual
                elif en_checked and not HAS_PYPROJ:
                    st.error("pyproj no está disponible. Instala 'pyproj' o desmarca Easting/Northing.")
                else:
                    st.info("Ingresa un centro aproximado en WGS84 para posicionar el mapa.")
                    lat = st.number_input('Latitud (WGS84)',  value=lat_actual, format='%.6f', key='ui_lat_epsg_hint')
                    lon = st.number_input('Longitud (WGS84)', value=lon_actual, format='%.6f', key='ui_lon_epsg_hint')
            else:
                st.caption("EPSG no UTM. El centro se aplicará con Lat/Lon indicados:")
                lat = st.number_input('Latitud (WGS84)',  value=lat_actual, format='%.6f', key='ui_lat_epsg')
                lon = st.number_input('Longitud (WGS84)', value=lon_actual, format='%.6f', key='ui_lon_epsg')

        # --- Opcional: fijar como default del proyecto ---
        fix_default = st.checkbox(
            "Establecer este centro/CRS como valor por defecto del proyecto",
            value=False, key='ui_fix_default_center'
        )

        # --- Aplicar cambios ---
        if st.button('Aplicar centro al mapa', type='primary', key='btn_apply_center'):
            # Centro y zoom
            init['map_center'] = [lat, lon]
            init['map_zoom']   = zoom

            # Persistencia del CRS según el modo
            if coord_mode == "Lat/Lon (WGS84)":
                if epsg_activo is not None:
                    st.session_state['ui_epsg_utm_active'] = int(epsg_activo)
                    st.session_state['ui_huso'] = _safe_zone_from_lon(lon, default_zone=13)
                    st.session_state['ui_hemisferio'] = 'Norte' if float(lat) >= 0 else 'Sur'

            elif coord_mode == "UTM (HUSO)":
                if epsg_activo is not None:
                    st.session_state['ui_epsg_utm_active'] = int(epsg_activo)
                    st.session_state['ui_huso'] = int(huso_center)
                    st.session_state['ui_hemisferio'] = hemisferio_center

            else:  # EPSG directo
                if epsg_activo is not None:
                    st.session_state['ui_epsg_active'] = int(epsg_activo)
                    if _is_utm_epsg(epsg_activo):
                        h, hemi = _utm_from_epsg(epsg_activo)
                        if h is not None:
                            st.session_state['ui_huso'] = int(h)
                        if hemi is not None:
                            st.session_state['ui_hemisferio'] = hemi

            # Guardar como default del proyecto (opcional)
            if fix_default:
                st.session_state['ui_default_center'] = [lat, lon]
                st.session_state['ui_default_zoom']   = zoom
                st.session_state['ui_default_epsg']   = (
                    int(epsg_activo) if epsg_activo is not None
                    else int(st.session_state.get('ui_epsg_utm_active', 32613))
                )

            st.rerun()
