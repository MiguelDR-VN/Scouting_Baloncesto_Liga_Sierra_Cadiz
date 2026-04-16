import os
import sqlite3
import pandas as pd
import re
from fpdf import FPDF
import io

def normalizar_texto(texto):
    if not isinstance(texto, str): return ""
    # 1. Pasamos a minúsculas en Python (que sí sabe que Ñ minúscula es ñ)
    texto = texto.lower().strip()
    # 2. Quitamos tildes Y convertimos la ñ en n
    tabla = str.maketrans("áéíóúüñ", "aeiouun")
    texto = texto.translate(tabla)
    # 3. Quitamos comas y símbolos
    texto = re.sub(r'[^a-z0-9\s]', ' ', texto)
    return " ".join(texto.split())


def limpiar_nombres_columnas(df):
    """Renombra las columnas repetidas (A/I) para que la IA las entienda."""
    # Primero quitamos espacios en blanco de los nombres de columnas
    df.columns = [str(c).strip() for c in df.columns]

    # Mapear los nombres
    mapeo = {
        'A/I': 'T2_anotados_intentados',
        '%': 'T2_porcentaje',
        'A/I.1': 'T3_anotados_intentados',
        '%.1': 'T3_porcentaje',
        'A/I.2': 'TL_anotados_intentados',
        '%.2': 'TL_porcentaje',
        'DEF': 'Rebotes_Defensivos',
        'OF': 'Rebotes_Ofensivos',
        'Tot.': 'Rebotes_Totales',
        'AST': 'Asistencias',
        'REC': 'Robos',
        'PER': 'Perdidas',
        'FC': 'Faltas_Cometidas',
        'FR': 'Faltas_Recibidas',
        'VAL': 'Valoracion',
        'PTS': 'PTS'
    }
    return df.rename(columns=mapeo)


def obtener_stats_jugador(nombre_jugador):
    try:
        import sqlite3
        import pandas as pd

        # Python limpia lo que escribe el usuario: "periañez" -> "perianez"
        nombre_limpio = normalizar_texto(nombre_jugador)
        palabras = nombre_limpio.split()

        conexion = sqlite3.connect("scouting.db")

        # Buscamos cada palabra limpia en la columna limpia
        condiciones = " AND ".join([f"Nombre_Normalizado LIKE '%{p}%'" for p in palabras])
        query = f"SELECT * FROM estadisticas WHERE {condiciones}"

        df = pd.read_sql(query, conexion)
        conexion.close()
        return df.to_dict(orient='records')
    except Exception as e:
        return []


def buscar_stats_equipo_en_archivos(nombre_equipo, carpeta_data="data/"):
    """Escanea los archivos buscando la tabla correcta de un equipo, evitando títulos generales."""
    archivos = [f for f in os.listdir(carpeta_data) if f.endswith(('.xlsx', '.xls'))]
    todas_las_stats = []
    nombre_busqueda = normalizar_texto(nombre_equipo)

    for archivo in archivos:
        path = os.path.join(carpeta_data, archivo)
        try:
            df_raw = pd.read_excel(path, header=None)

            # 1. Buscamos todas las filas que sean la cabecera de una tabla estadística
            filas_cabecera = []
            for idx, row in df_raw.iterrows():
                # Normalizamos la fila para buscar la palabra "nombre"
                row_norm = [normalizar_texto(str(x)) for x in row.values]
                if "nombre" in row_norm:
                    filas_cabecera.append(idx)

            # 2. Comprobamos a qué equipo pertenece cada cabecera
            for fila_idx in filas_cabecera:
                equipo_correcto = False

                # Miramos hasta 3 filas por encima de "Nombre" para ver el nombre del equipo
                for offset in range(1, 4):
                    if fila_idx - offset >= 0:
                        fila_arriba = [normalizar_texto(str(x)) for x in df_raw.iloc[fila_idx - offset].values]

                        for celda in fila_arriba:
                            # Comprobamos si está nuestro equipo y EXCLUIMOS la fila del título (que tiene "vs")
                            if nombre_busqueda in celda and "vs" not in celda:
                                equipo_correcto = True
                                break
                    if equipo_correcto:
                        break

                # 3. Si es la tabla de nuestro equipo, la extraemos
                if equipo_correcto:
                    df = pd.read_excel(path, header=fila_idx)
                    df.columns = [str(c).strip() for c in df.columns]

                    if "TOTALES" in df['Nombre'].values:
                        idx_totales = df[df['Nombre'] == "TOTALES"].index[0]
                        df = df.iloc[:idx_totales]

                    df = df.dropna(subset=['Nombre'])

                    # Llamamos a la función de limpieza
                    from data_utils import limpiar_nombres_columnas
                    df = limpiar_nombres_columnas(df)
                    df['Partido_Origen'] = archivo
                    todas_las_stats.append(df)

                    # Ya encontramos al equipo en este partido, saltamos al siguiente archivo
                    break

        except Exception as e:
            print(f"Error procesando {archivo}: {e}")

    if not todas_las_stats:
        return None

    return pd.concat(todas_las_stats, ignore_index=True)


def obtener_historial_jugador(nombre_jugador):
    """
    Saca todo el historial de un jugador en 0.1 segundos desde SQLite.
    Sustituye al antiguo bucle que leía los Excels uno a uno.
    """
    try:
        import sqlite3
        import pandas as pd

        conexion = sqlite3.connect("scouting.db")
        # Buscamos al jugador en la base de datos (ignorando mayúsculas)
        query = f"SELECT * FROM estadisticas WHERE lower(Nombre) LIKE lower('%{nombre_jugador}%')"

        df = pd.read_sql(query, conexion)
        conexion.close()

        # Devolvemos el historial listo para usar
        return df.to_dict(orient='records')

    except Exception as e:
        print(f"Error al leer la base de datos en obtener_historial_jugador: {e}")
        return []


def obtener_lista_equipos():
    """Devuelve la lista de equipos únicos ordenados."""
    conexion = sqlite3.connect("scouting.db")
    query = "SELECT DISTINCT Equipo FROM estadisticas ORDER BY Equipo"
    df = pd.read_sql(query, conexion)
    conexion.close()
    return df['Equipo'].tolist()


def obtener_jugadores_equipo(equipo):
    try:
        import sqlite3
        import pandas as pd

        conexion = sqlite3.connect("scouting.db")
        # Traemos todos los registros de ese equipo
        query = f"SELECT Dorsal, Nombre FROM estadisticas WHERE Equipo = '{equipo}'"
        df = pd.read_sql(query, conexion)
        conexion.close()

        if df.empty:
            return []

        # --- LA MAGIA PARA UNIFICAR DORSALES ---
        # 1. Contamos cuántas veces ha usado cada dorsal cada jugador
        conteos = df.groupby(['Nombre', 'Dorsal']).size().reset_index(name='veces_usado')

        # 2. Ordenamos para que el dorsal más usado quede arriba de todo
        conteos = conteos.sort_values(by=['Nombre', 'veces_usado'], ascending=[True, False])

        # 3. Truco maestro: Nos quedamos solo con la primera fila de cada jugador
        # (que corresponde al dorsal que más ha usado) y descartamos el resto
        df_final = conteos.drop_duplicates(subset=['Nombre'], keep='first')
        # ---------------------------------------

        # 4. Limpiamos y ordenamos por dorsal para que el menú quede bonito
        df_final['Dorsal'] = pd.to_numeric(df_final['Dorsal'], errors='coerce').fillna(0).astype(int)
        df_final = df_final.sort_values(by='Dorsal')

        # 5. Creamos la lista final
        lista = []
        for _, row in df_final.iterrows():
            lista.append(f"{row['Dorsal']} - {row['Nombre']}")

        return lista

    except Exception as e:
        print(f"Error en obtener_jugadores_equipo: {e}")
        return []



def crear_pdf_scouting(nombre_jugador, analisis_ia, fig_plotly):
    pdf = FPDF()
    pdf.add_page()

    # --- Encabezado ---
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, f"INFORME DE SCOUTING: {nombre_jugador.upper()}", ln=True, align="C")
    pdf.ln(10)

    # --- LA NUEVA MAGIA DEL COLOR TOTAL ---
    # 1. Obligamos a la gráfica a usar un tema luminoso y textos oscuros
    fig_plotly.update_layout(
        template="plotly_white",  # Tema de fondo blanco y cuadrícula sutil
        paper_bgcolor="white",  # Fondo exterior blanco
        plot_bgcolor="white",  # Fondo interior blanco
        font=dict(color="black")  # Letras negras para que se lean en el PDF
    )

    # 2. ---> BLOQUE CLAVE: ASIGNAR COLORES A CADA LÍNEA <---
    # Elegimos colores intensos y estándar para imprimir (Azul y Rojo)
    colores_impresion = ['#1f77b4', '#d62728']  # Hex: Azul y Rojo

    # Iteramos por las líneas (traces) de la gráfica y les asignamos el color
    for i, trace in enumerate(fig_plotly.data):
        color_indice = i % len(colores_impresion)  # Para alternar si hubiera más de 2 líneas
        trace.update(line=dict(color=colores_impresion[color_indice]))
    # -----------------------------------------------------

    # 3. scale=2 para Alta Resolución (HD)
    img_bytes = fig_plotly.to_image(format="png", width=800, height=450, scale=2)
    img_buffer = io.BytesIO(img_bytes)

    # Insertamos la imagen en el PDF
    pdf.image(img_buffer, x=10, y=pdf.get_y(), w=190)
    pdf.ln(100)  # Saltamos espacio

    # --- Análisis de la IA ---
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, "Analisis Tactico de la IA:", ln=True)
    pdf.set_font("Arial", "", 11)

    texto_limpio = analisis_ia.replace("**", "").replace("- ", "* ")
    texto_limpio = texto_limpio.encode('latin-1', 'replace').decode('latin-1')

    pdf.multi_cell(0, 8, texto_limpio)

    # --- Pie de página ---
    pdf.set_y(-20)
    pdf.set_font("Arial", "I", 8)
    pdf.cell(0, 10, "Generado por Scouting AI - Liga Sierra de Cadiz", align="C")

    return bytes(pdf.output())



def crear_pdf_equipo(nombre_equipo, analisis_ia, df_top5):
    """Genera el PDF para el scouting del equipo rival."""
    pdf = FPDF()
    pdf.add_page()

    # --- Encabezado ---
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, f"PLAN DE PARTIDO: {nombre_equipo.upper()}", ln=True, align="C")
    pdf.ln(5)

    # --- Análisis de la IA ---
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, "Pizarra Tactica:", ln=True)
    pdf.set_font("Arial", "", 11)

    # Limpiamos Markdown para que FPDF lo lea bien
    texto_limpio = analisis_ia.replace("**", "").replace("- ", "* ")
    # Evitamos errores de caracteres raros o tildes al convertir
    texto_limpio = texto_limpio.encode('latin-1', 'replace').decode('latin-1')

    pdf.multi_cell(0, 8, texto_limpio)
    pdf.ln(10)

    # --- Tabla del Top 5 Amenazas ---
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, "Top 5 Amenazas (Medias Temporada):", ln=True)
    pdf.set_font("Arial", "B", 10)

    # Cabeceras de la tabla (con fondo gris)
    pdf.set_fill_color(220, 220, 220)
    pdf.cell(90, 10, "Jugador", border=1, fill=True)
    pdf.cell(30, 10, "PTS", border=1, fill=True, align="C")
    pdf.cell(30, 10, "VAL", border=1, fill=True, align="C")
    pdf.ln()

    # Filas de los jugadores
    pdf.set_font("Arial", "", 10)
    for index, row in df_top5.iterrows():
        # index es el Nombre porque agrupamos por Nombre en Pandas
        nombre_jugador = str(index).encode('latin-1', 'replace').decode('latin-1')
        pts = f"{row['PTS']:.1f}"
        val = f"{row['Valoracion']:.1f}"

        pdf.cell(90, 10, nombre_jugador, border=1)
        pdf.cell(30, 10, pts, border=1, align="C")
        pdf.cell(30, 10, val, border=1, align="C")
        pdf.ln()

    # --- Pie de página ---
    pdf.set_y(-20)
    pdf.set_font("Arial", "I", 8)
    pdf.cell(0, 10, "Generado por Scouting AI - Liga Sierra de Cadiz", align="C")

    # Retornamos los bytes puros (la solución que aplicamos antes para Streamlit)
    return bytes(pdf.output())