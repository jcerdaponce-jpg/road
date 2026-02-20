
import json
import networkx as nx

# Factor genérico que ya usabas
factor_camino_2 = 1

def mst_function(path_json_conexiones, start_node="road_survey",
                 outfile="JSON_FILES/e_mst.json", algoritmo_mst="kruskal"):

    """
    Construye el MST sobre terminales (WTG/SET/ACCESO) usando costos de camino más corto
    en el grafo de CAMINOS, y lo enraíza en `start_node` para ordenar los ramales.

    Parámetros:
      path_json_conexiones : str -> JSON con lista de conexiones (origen/destino/x/y/ruta_ponderada/distancia)
      start_node           : str -> nodo de inicio (acceso), por defecto "road survey"
      outfile              : str -> ruta de salida JSON
      algoritmo_mst        : str -> "prim" o "kruskal" (resultado debe ser el mismo)

    Retorna:
      str -> ruta del archivo JSON generado
    """
    # 1) Leer conexiones (aristas del grafo de CAMINOS)
    with open(path_json_conexiones, "r", encoding="utf-8") as f:
        conexiones = json.load(f)

    G = nx.Graph()
    pos = {}

    # 2) Construcción del grafo base de CAMINOS con tus reglas de ponderación
    for conexion in conexiones:
        origen = conexion["origen"]["nombre"]
        destino = conexion["destino"]["nombre"]
        distancia_ponderada = conexion["ruta_ponderada"]

        # Penalización fuerte entre camino_ - camino_ si supera umbral
        if origen.startswith("camino_") and destino.startswith("camino_"):
            if distancia_ponderada < 1500:
                peso = distancia_ponderada * 0.1
            else:
                peso = distancia_ponderada * 500000
        else:
            peso = distancia_ponderada * factor_camino_2

        G.add_edge(origen, destino, weight=peso)

        # Guardar coordenadas (último valor prevalece si se repite el nodo)
        pos[origen] = (conexion["origen"]["x"], conexion["origen"]["y"])
        pos[destino] = (conexion["destino"]["x"], conexion["destino"]["y"])

    # 3) Terminales: si quieres excluir nodos camino_ del conjunto de terminales, filtra aquí.
    #    Ahora usamos todos, como en tu código original:
    nodos_principales = list(G.nodes)

    # 4) Grafo reducido entre terminales con peso = costo del camino más corto en G
    G_reducido = nx.Graph()
    for i in range(len(nodos_principales)):
        for j in range(i + 1, len(nodos_principales)):
            u = nodos_principales[i]
            v = nodos_principales[j]
            try:
                ruta = nx.shortest_path(G, u, v, weight="weight")
                costo = sum(G[a][b]["weight"] for a, b in zip(ruta[:-1], ruta[1:]))
                G_reducido.add_edge(u, v, weight=costo)
            except nx.NetworkXNoPath:
                # Si no hay camino factible, se omite
                continue

    if G_reducido.number_of_edges() == 0:
        raise RuntimeError("El grafo reducido no tiene aristas; revisa conectividad/costos.")

    # 5) MST (independiente del nodo de inicio para el óptimo global)
    mst = nx.minimum_spanning_tree(G_reducido, algorithm=algoritmo_mst)

    # 6) Enraizar/ordenar desde el acceso "road survey"
    if start_node not in mst.nodes:
        # Si el nombre exacto no coincide, ayuda de diagnóstico:
        candidatos = [n for n in mst.nodes if "road" in n.lower() or "survey" in n.lower()]
        sugerencia = f" Candidatos encontrados: {candidatos}" if candidatos else ""
        raise ValueError(f"El nodo inicial '{start_node}' no está en el MST.{sugerencia}")

    aristas_ordenadas = list(nx.bfs_edges(mst, source=start_node))

    # 7) Expandir cada arista del MST a su ruta real sobre el grafo de CAMINOS G
    mst_rutas_json = []
    for u, v in aristas_ordenadas:
        try:
            ruta = nx.shortest_path(G, u, v, weight="weight")
            for a, b in zip(ruta[:-1], ruta[1:]):
                # Buscar la distancia REAL original si viene en el JSON de entrada
                distancia_real = next(
                    (d["distancia"] for d in conexiones if
                     (d["origen"]["nombre"] == a and d["destino"]["nombre"] == b) or
                     (d["origen"]["nombre"] == b and d["destino"]["nombre"] == a)),
                    None
                )
                # Agregamos cada segmento de la ruta real
                mst_rutas_json.append({
                    "origen":  {"nombre": a, "x": pos[a][0], "y": pos[a][1]},
                    "destino": {"nombre": b, "x": pos[b][0], "y": pos[b][1]},
                    "distancia_real": distancia_real,
                    "costo_ponderado": G[a][b]["weight"]
                })
        except nx.NetworkXNoPath:
            # Desconectado por restricciones: lo saltamos
            continue

    # 8) Exportar
    with open(outfile, "w", encoding="utf-8") as f:
        json.dump(mst_rutas_json, f, indent=2, ensure_ascii=False)

    return outfile




