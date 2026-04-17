import streamlit as st
import pandas as pd
from data_utils import obtener_historial_jugador, buscar_stats_equipo_en_archivos
from scout_agent import scout_app, llm
import plotly.express as px
from data_utils import obtener_lista_equipos, obtener_jugadores_equipo, obtener_stats_jugador, crear_pdf_scouting, crear_pdf_equipo


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
st.title("🏀 Asistente de Scouting Inteligente - Liga Sierra de Cádiz")

# --- MENÚ LATERAL ---
modo = st.sidebar.radio("Selecciona el tipo de análisis:", ["👤 Análisis de Jugador", "🛡️ Scouting de Rival"])

# ==========================================
# MODO 1: JUGADOR INDIVIDUAL
# ==========================================
if modo == "👤 Análisis de Jugador":
    st.header("Análisis Histórico de Jugador")

    # --- NUEVA ESTRUCTURA DE PESTAÑAS ---
    tab_directorio, tab_busqueda = st.tabs(["📋 Explorador por Equipos", "🔍 Búsqueda Manual"])

    nombre_jugador = None

    with tab_directorio:
        col1, col2 = st.columns(2)
        with col1:
            lista_equipos = obtener_lista_equipos()
            equipo_sel = st.selectbox("Selecciona Equipo:", ["-"] + lista_equipos)

        with col2:
            if equipo_sel != "-":
                lista_jugadores = obtener_jugadores_equipo(equipo_sel)
                jugador_sel = st.selectbox("Selecciona Jugador:", ["-"] + lista_jugadores)
                if jugador_sel != "-":
                    # Extraemos el nombre quitando el dorsal (ej: "10 - NOMBRE" -> "NOMBRE")
                    nombre_jugador = jugador_sel.split(" - ")[1]


    with tab_busqueda:
        nombre_input = st.text_input("Introduce Apellidos, Nombre (ej: CORNEJO SANTALLA, HUGO):", key="input_manual")
        if nombre_input:
            nombre_jugador = nombre_input

    # --- LÓGICA DE GENERACIÓN DE INFORME ---
    if nombre_jugador:
        if st.button(f"Generar Informe de jugador", type="primary"):
            # Usamos la función de DB para el historial
            datos_historial = obtener_stats_jugador(nombre_jugador)
            historial_df = pd.DataFrame(datos_historial)

            if not historial_df.empty:
                st.markdown(f"### 📈 Evolución de {nombre_jugador.upper()} en la temporada")

                # Limpieza y conversión
                historial_df['PTS'] = pd.to_numeric(historial_df['PTS'], errors='coerce').fillna(0)
                historial_df['Valoracion'] = pd.to_numeric(historial_df['Valoracion'], errors='coerce').fillna(0)
                historial_df['Num_Jornada'] = historial_df['Partido_Origen'].str.extract(r'_j(\d+)_').astype(float)
                historial_df = historial_df.sort_values(by='Num_Jornada')

                historial_df['Etiqueta_X'] = historial_df['Num_Jornada'].apply(
                    lambda x: f"Jornada {int(x)}" if pd.notna(x) else "Otro"
                )

                # Gráfica Plotly
                fig = px.line(
                    historial_df,
                    x='Etiqueta_X',
                    y=['PTS', 'Valoracion'],
                    markers=True,
                    title="Puntos y Valoración por Partido",
                    labels={'value': 'Estadística', 'Etiqueta_X': 'Jornada', 'variable': 'Métrica'}
                )

                fig.for_each_trace(lambda t: t.update(
                    name=t.name.replace("Valoracion", "VAL"),
                    hovertemplate="<b>%{x}</b><br>%{y} %{data.name}<extra></extra>"
                ))

                fig.update_xaxes(categoryorder='array', categoryarray=historial_df['Etiqueta_X'])
                st.plotly_chart(fig, use_container_width=True)

                # Análisis de IA
                with st.spinner("La IA está analizando la temporada..."):
                    inputs = {"nombre_jugador": nombre_jugador}
                    config = {"configurable": {"thread_id": "1"}}
                    resultado = scout_app.invoke(inputs, config)

                    st.success("¡Informe generado!")
                    st.markdown("### 📋 Informe Técnico")
                    st.markdown(resultado["analisis_tactico"])

                    st.divider()
                    st.subheader("📥 Exportar Informe")

                    # Generamos los bytes del PDF
                    pdf_bytes = crear_pdf_scouting(nombre_jugador, resultado["analisis_tactico"], fig)

                    st.download_button(
                        label="Descargar Informe en PDF",
                        data=pdf_bytes,
                        file_name=f"Scouting_{nombre_jugador.replace(' ', '_')}.pdf",
                        mime="application/pdf",
                        icon="📄"
                    )

                    with st.expander("📊 Ver estadísticas numéricas extraídas"):
                        st.dataframe(historial_df)
            else:
                st.error(
                    f"No se han encontrado datos para: {nombre_jugador}. Recuerda que SQLite requiere mayúsculas exactas para la Ñ.")

# ==========================================
# MODO 2: EQUIPO RIVAL
# ==========================================
elif modo == "🛡️ Scouting de Rival":
    st.header("Plan de Partido: Próximo Rival")

    # 1. Sacamos la lista de equipos usando la función que ya creamos en data_utils
    lista_equipos = obtener_lista_equipos()

    # 2. Cambiamos la caja de texto libre por un menú desplegable
    nombre_equipo = st.selectbox("Selecciona el equipo rival:", ["Seleccionar..."] + lista_equipos)

    if st.button("Generar Plan de Partido"):
        # 3. Comprobamos que el usuario no haya dejado puesto "Seleccionar..."
        if nombre_equipo != "Seleccionar...":
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

                    # Prompt para Gemini/Groq
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

                    st.divider()
                    st.subheader("📥 Exportar Plan de Partido")

                    # Llamamos a nuestra nueva función
                    pdf_bytes_equipo = crear_pdf_equipo(nombre_equipo, respuesta.content, resumen)

                    st.download_button(
                        label="Descargar Plan en PDF",
                        data=pdf_bytes_equipo,
                        file_name=f"Plan_Partido_{nombre_equipo.replace(' ', '_')}.pdf",
                        mime="application/pdf",
                        icon="📄"
                    )
        else:
            st.warning("Por favor, selecciona un equipo de la lista.")