import streamlit as st
import pandas as pd
from data_utils import obtener_historial_jugador, buscar_stats_equipo_en_archivos
from scout_agent import scout_app, llm


@st.cache_data(ttl=3600) # Guarda la memoria durante 1 hora
def obtener_datos_jugador_memoria(nombre):
    # Llama a LangGraph
    inputs = {"nombre_jugador": nombre}
    config = {"configurable": {"thread_id": "1"}}
    return scout_app.invoke(inputs, config)

@st.cache_data(ttl=3600)
def obtener_datos_rival_memoria(nombre_equipo):
    return buscar_stats_equipo_en_archivos(nombre_equipo)



# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Scouting AI", page_icon="🏀", layout="wide")

st.title("🏀 Asistente de Scouting Inteligente")
st.markdown("Deja que la IA prepare tu partido.")

# --- MENÚ LATERAL ---
modo = st.sidebar.radio("Selecciona el tipo de análisis:", ["👤 Análisis de Jugador", "🛡️ Scouting de Rival"])

st.sidebar.markdown("---")
st.sidebar.info("Desarrollado para automatizar la lectura de actas de la Liga de la Sierra de Cádiz.")

# ==========================================
# MODO 1: JUGADOR INDIVIDUAL
# ==========================================
if modo == "👤 Análisis de Jugador":
    st.header("Análisis Histórico de Jugador")
    nombre_jugador = st.text_input("Introduce apellidos, nombre del jugador (ej: Cornejo Santalla, Hugo):")

    if st.button("Generar Informe del Jugador"):
        if nombre_jugador:
            with st.spinner("Escaneando temporada y generando informe..."):
                # Llamamos a tu LangGraph
                inputs = {"nombre_jugador": nombre_jugador}
                config = {"configurable": {"thread_id": "1"}}
                resultado = scout_app.invoke(inputs, config)

                # --- MOSTRAR RESULTADOS ---
                st.success("¡Informe generado!")

                # Mostrar el texto de la IA (Streamlit lee Markdown automáticamente para que se vea bonito)
                st.markdown("### 📋 Informe Técnico")
                st.markdown(resultado["analisis_tactico"])

                # Mostrar los datos en bruto en una tabla desplegable
                datos_crudos = obtener_historial_jugador(nombre_jugador)
                if datos_crudos:
                    with st.expander("📊 Ver estadísticas numéricas extraídas"):
                        st.dataframe(pd.DataFrame(datos_crudos))
        else:
            st.warning("Por favor, introduce un nombre.")

# ==========================================
# MODO 2: EQUIPO RIVAL
# ==========================================
elif modo == "🛡️ Scouting de Rival":
    st.header("Plan de Partido: Próximo Rival")
    nombre_equipo = st.text_input("Introduce el nombre del equipo rival (ej. Olvera 2):")

    if st.button("Generar Plan de Partido"):
        if nombre_equipo:
            with st.spinner("Analizando al equipo rival..."):
                df_rival = buscar_stats_equipo_en_archivos(nombre_equipo)

                if df_rival is None or df_rival.empty:
                    st.error(f"No se han encontrado datos para el equipo: {nombre_equipo}")
                else:
                    # Limpieza de datos
                    df_rival['PTS'] = pd.to_numeric(df_rival['PTS'], errors='coerce')
                    df_rival['Valoracion'] = pd.to_numeric(df_rival['Valoracion'], errors='coerce')

                    # Sacamos el Top 5
                    resumen = df_rival.groupby('Nombre').agg({
                        'PTS': 'mean',
                        'Valoracion': 'mean'
                    }).sort_values(by='Valoracion', ascending=False).head(5)

                    # Prompt para Gemini
                    prompt = f"""
                    Actúa como el entrenador jefe. Jugamos contra {nombre_equipo}.
                    Aquí tienes el TOP 5 de sus mejores jugadores y sus medias (Puntos y Valoración):
                    {resumen.to_string()}

                    Escribe un informe estructurado con:
                    - **Amenazas Principales:** Quiénes son y cómo pararlos.
                    - **Perfil Ofensivo del Equipo:** Según los puntos, a qué juegan.
                    - **Clave del Partido:** Un consejo táctico motivador.
                    """

                    respuesta = llm.invoke(prompt)

                    # --- MOSTRAR RESULTADOS ---
                    st.success("¡Plan de partido listo!")

                    st.markdown("### 📋 Pizarra Táctica")
                    st.markdown(respuesta.content)

                    st.markdown("### 🔥 Top 5 Amenazas (Medias de la temporada)")
                    st.dataframe(resumen.style.highlight_max(axis=0, color='#ffcccc'))
        else:
            st.warning("Por favor, introduce un nombre de equipo.")