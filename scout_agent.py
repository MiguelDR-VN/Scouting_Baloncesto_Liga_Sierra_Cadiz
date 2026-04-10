import os
from dotenv import load_dotenv
from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
from langchain_google_genai import ChatGoogleGenerativeAI
from data_utils import obtener_stats_jugador
from langchain_groq import ChatGroq
from data_utils import obtener_historial_jugador

load_dotenv()

# LLM de Llama
llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    temperature=0,
    api_key=os.getenv("GROQ_API_KEY")
)



#llm = ChatGoogleGenerativeAI(
 #   model="models/gemini-2.5-flash",
  #  temperature=0.5,
   # api_key=os.getenv("GEMINI_API_KEY")
#)

# 1. Definimos el "Estado" del agente (qué info lleva encima)
class AgentState(TypedDict):
    nombre_jugador: str
    datos_crudos: dict
    analisis_tactico: str


# 2. Nodo 1: El Buscador (saca los datos)
def buscador_datos_node(state: AgentState):
    print(f"--- BUSCANDO HISTORIAL GLOBAL DE {state['nombre_jugador'].upper()} ---")

    # Escanea toda la carpeta
    datos_globales = obtener_historial_jugador(state['nombre_jugador'])

    return {"datos_crudos": datos_globales}


# 3. Nodo 2: El Analista (Usa Gemini para razonar)
def analista_gemini_node(state: AgentState):
    if not state['datos_crudos']:
        return {"analisis_tactico": "No se encontraron datos de este jugador en ningún partido."}

    # Cambiamos las instrucciones para un análisis global
    prompt = f"""
    Eres el Director Deportivo y analista principal de un equipo de baloncesto. 
    Aquí tienes el historial completo de estadísticas del jugador {state['nombre_jugador']} a lo largo de varios partidos esta temporada:

    {state['datos_crudos']}

    Analiza su rendimiento global en todos estos partidos y redacta un informe de scouting detallado.
    Tu informe debe contener:
    1. Perfil del jugador: ¿En qué destaca de forma consistente? (Ej: es un gran reboteador, tirador fiable, etc.)
    2. Puntos débiles: ¿Qué estadística le lastra partido tras partido?
    3. Evolución: ¿Es un jugador regular o sus números cambian mucho de un partido a otro?
    4. Plan de mejora: Un consejo táctico general enfocado a sus entrenamientos.
    """
    respuesta = llm.invoke(prompt)
    return {"analisis_tactico": respuesta.content}


# 4. Construcción del Grafo
workflow = StateGraph(AgentState)

workflow.add_node("buscador", buscador_datos_node)
workflow.add_node("analista", analista_gemini_node)

workflow.set_entry_point("buscador")
workflow.add_edge("buscador", "analista")
workflow.add_edge("analista", END)

# Compilamos el flujo
scout_app = workflow.compile()