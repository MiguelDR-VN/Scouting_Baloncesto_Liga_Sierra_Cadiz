from fastapi import FastAPI
from data_utils import buscar_stats_equipo_en_archivos # <--- AQUÍ EL IMPORT
from scout_agent import scout_app # Tu LangGraph de antes
import pandas as pd

app = FastAPI()


@app.get("/jugador/{nombre}")
async def get_scout_report(nombre: str):
    # Lanzamos el flujo de LangGraph
    inputs = {"nombre_jugador": nombre}
    config = {"configurable": {"thread_id": "1"}}

    resultado = scout_app.invoke(inputs, config)

    return {
        "jugador": nombre,
        "informe": resultado["analisis_tactico"]
    }


@app.get("/rival/{nombre_equipo}")
async def get_rival_report(nombre_equipo: str):
    df_rival = buscar_stats_equipo_en_archivos(nombre_equipo)

    if df_rival is None:
        return {"error": f"No hay datos de {nombre_equipo}"}

    # Convertimos a número. 'errors=coerce' convierte los errores (como un "-") en NaN (vacío)
    df_rival['PTS'] = pd.to_numeric(df_rival['PTS'], errors='coerce')
    df_rival['Valoracion'] = pd.to_numeric(df_rival['Valoracion'], errors='coerce')

    resumen = df_rival.groupby('Nombre').agg({
        'PTS': 'mean',
        'Valoracion': 'mean'
    }).sort_values(by='Valoracion', ascending=False).head(5)

    from scout_agent import llm
    prompt = f"Scouting para el equipo {nombre_equipo}: {resumen.to_string()}"
    respuesta = llm.invoke(prompt)

    return {"equipo": nombre_equipo, "scouting": respuesta.content}