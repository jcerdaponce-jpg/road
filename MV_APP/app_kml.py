

# --- 4) KML
with st.sidebar.expander("KML", expanded=False):
    kml_up = st.file_uploader("Subir KML", type=["kml"])
    if kml_up is not None:
        try:
            import geopandas as gpd
            gdf = gpd.read_file(kml_up)
            if gdf.crs is not None:
                gdf = gdf.to_crs(epsg=4326)
            data = json.loads(gdf.to_json())
            st.session_state.other_fc_list.append(data)
            st.success("KML convertido y añadido a la sesión.")
        except Exception as e:
            st.error("Para KML necesitas geopandas/fiona. " + str(e))