import os
import pandas as pd
import unicodedata


def normalizar_texto(texto):
    """Quita acentos, pone en minúsculas y limpia espacios."""
    if not isinstance(texto, str):
        texto = str(texto)
    # Normaliza caracteres (p.e. 'á' -> 'a')
    texto_normalizado = "".join(
        c for c in unicodedata.normalize('NFD', texto)
        if unicodedata.category(c) != 'Mn'
    )
    return texto_normalizado.lower().strip()


def limpiar_nombres_columnas(df):
    """Renombra las columnas repetidas (A/I) para que la IA las entienda."""
    # Primero quitamos espacios en blanco de los nombres de columnas
    df.columns = [str(c).strip() for c in df.columns]

    # Mapeo de nombres para evitar los .1, .2 que pone Pandas
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




def obtener_stats_jugador(nombre_buscado, path_excel):
    """Función para el scouting individual (usada en /scout/{jugador})"""
    try:
        df_raw = pd.read_excel(path_excel, header=None)
        # Buscamos la fila donde está la cabecera "Nombre"
        indices = df_raw[df_raw.iloc[:, 1] == "Nombre"].index.tolist()

        full_stats = []
        for idx in indices:
            df = pd.read_excel(path_excel, header=idx)
            df.columns = [str(c).strip() for c in df.columns]

            if "TOTALES" in df['Nombre'].values:
                idx_totales = df[df['Nombre'] == "TOTALES"].index[0]
                df = df.iloc[:idx_totales]

            df = df.dropna(subset=['Nombre'])
            df = limpiar_nombres_columnas(df)
            full_stats.append(df)

        if not full_stats: return []

        df_final = pd.concat(full_stats, ignore_index=True)
        nombre_norm = normalizar_texto(nombre_buscado)
        # Filtramos usando texto normalizado
        resultado = df_final[df_final['Nombre'].apply(normalizar_texto).str.contains(nombre_norm, na=False)]
        return resultado.to_dict(orient='records')
    except Exception as e:
        print(f"Error en obtener_stats_jugador: {e}")
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

                    # Llamamos a tu función de limpieza
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



def obtener_historial_jugador(nombre_buscado, carpeta_data="data/"):
    """Busca a un jugador en TODOS los archivos y junta sus estadísticas históricas."""
    archivos = [f for f in os.listdir(carpeta_data) if f.endswith(('.xlsx', '.xls'))]
    historial_completo = []

    for archivo in archivos:
        path = os.path.join(carpeta_data, archivo)
        # Reutilizamos tu función que busca en un solo archivo
        stats_partido = obtener_stats_jugador(nombre_buscado, path)

        if stats_partido:
            # stats_partido es una lista. Le añadimos el nombre del archivo para saber de qué partido es
            for stat in stats_partido:
                stat['Partido_Origen'] = archivo
                historial_completo.append(stat)

    return historial_completo