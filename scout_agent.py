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


"""# LLM de Google
llm = ChatGoogleGenerativeAI(
    model="models/gemini-2.5-flash",
    temperature=0.5,
    api_key=os.getenv("GEMINI_API_KEY")
)"""

# 1. Definimos el "Estado" del agente
class AgentState(TypedDict):
    nombre_jugador: str
    datos_crudos: list
    analisis_tactico: str


# 2. Nodo 1: El Buscador (consulta la BBDD)
def buscador_datos_node(state: AgentState):
    print(f"--- CONSULTANDO BBDD: HISTORIAL DE {state['nombre_jugador'].upper()} ---")

    # escanea el .db
    datos_db = obtener_historial_jugador(state['nombre_jugador'])

    return {"datos_crudos": datos_db}


# 3. Nodo 2: El Analista
def analista_gemini_node(state: AgentState):
    if not state['datos_crudos']:
        return {"analisis_tactico": f"No hay registros en la base de datos para {state['nombre_jugador']}."}

    # Convertimos a texto para el prompt
    prompt = f"""
    Eres el Director Deportivo. Analiza el historial de {state['nombre_jugador']} basado en estos datos de la base de datos:

    {state['datos_crudos']}

    Genera un informe profesional que incluya:
    1. Perfil Consistente: ¿Qué hace bien siempre?
    2. Puntos Críticos: ¿Qué falla en sus peores partidos?
    3. Análisis de Regularidad: ¿Sus estadísticas son estables o montaña rusa?
    4. Plan de Trabajo: Un consejo táctico para su próximo entrenamiento.
    5. ¿Cómo defenderlo?: Pautas para poder parar a ese jugador 
    """

    respuesta = llm.invoke(prompt)
    return {"analisis_tactico": respuesta.content}


# 4. Construcción del Grafo (Se mantiene igual, la estructura es sólida)
workflow = StateGraph(AgentState)

workflow.add_node("buscador", buscador_datos_node)
workflow.add_node("analista", analista_gemini_node)

workflow.set_entry_point("buscador")
workflow.add_edge("buscador", "analista")
workflow.add_edge("analista", END)

scout_app = workflow.compile()