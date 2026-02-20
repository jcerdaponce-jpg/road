import os, sys, subprocess
import multiprocessing as mp
from time import perf_counter

# ======= 1) FUNCIÓN DE CARGA CPU (SUSTITUYE POR TU CÓMPUTO REAL SI QUIERES) =======
def tarea_pesada(n: int) -> int:
    """
    Sustituye este bucle por tu cómputo real (p.ej. precálculo de snap, rutas, buffers, etc.).
    O déjalo tal cual si solo quieres "calentar" CPU para probar paralelismo.
    """
    total = 0
    # ⚠️ Ajusta el número de iteraciones si se te hace muy lento:
    for _ in range(8_000_000):
        total += n * n
    return total

def usar_todos_los_nucleos(precompute: bool = False):
    """
    Ejecuta 'tarea_pesada' en paralelo (un proceso por núcleo) si precompute=True.
    Devuelve la lista de resultados o None si no se precalcula.
    """
    if not precompute:
        print("[Launcher] Precálculo desactivado (PRECOMPUTE_CORES != 1).")
        return None

    # Contexto con 'spawn' para máxima compatibilidad (Windows-friendly)
    ctx = mp.get_context("spawn")
    cpu = ctx.cpu_count()
    print(f"[Launcher] Usando {cpu} núcleos para precálculo...")

    t0 = perf_counter()
    # chunksize=1 está bien para pocas tareas; sube si mapeas miles de elementos
    with ctx.Pool(processes=cpu) as pool:
        resultados = pool.map(tarea_pesada, range(cpu), chunksize=1)
    t1 = perf_counter()

    print(f"[Launcher] Precálculo paralelo OK en {t1 - t0:.2f}s.")
    return resultados

# ======= 2) MAIN: CONFIG STREAMLIT + (OPCIONAL) PRECÁLCULO + EJECUTAR APP =======
def main():
    # --- Config de Streamlit (poner ANTES de ejecutar) ---
    os.environ["STREAMLIT_SERVER_MAX_UPLOAD_SIZE_MB"] = "1600"
    os.environ["STREAMLIT_SERVER_MAX_MESSAGE_SIZE_MB"] = "1600"
    os.environ["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"

    # --- ¿Ejecutar o no el precálculo en todos los núcleos? ---
    # Actívalo exportando PRECOMPUTE_CORES=1 (o en Windows: set PRECOMPUTE_CORES=1)
    precompute_flag = os.getenv("PRECOMPUTE_CORES", "0") == "1"
    _ = usar_todos_los_nucleos(precompute=precompute_flag)

    # --- Lanzar Streamlit ---
    cmd = [sys.executable, "-m", "streamlit", "run", "app_V15.py"]
    print(f"[Launcher] Ejecutando: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)

if __name__ == "__main__":
    # Requisito para Windows/pyinstaller y para 'spawn'
    mp.freeze_support()
    try:
        mp.set_start_method("spawn", force=False)
    except RuntimeError:
        # Ya estaba establecido en este proceso
        pass
    main()




'''import os, subprocess, sys

import matplotlib
matplotlib.use("TkAgg")



# Opción 1: variable de entorno
os.environ["STREAMLIT_SERVER_MAX_UPLOAD_SIZE"] = "1600"

#subprocess.run([sys.executable, "-m", "streamlit", "run", "prueba_streamlit.py"], check=True)
subprocess.run([sys.executable, "-m", "streamlit", "run", "app_V15.py"], check=True)'''

