import os
import pandas as pd
import sqlite3
import difflib
from data_utils import limpiar_nombres_columnas, normalizar_texto

import difflib


def unificar_nombres_equipo(df):
    """Detecta nombres mal escritos pero es capaz de distinguir entre hermanos."""
    equipos = df['Equipo'].dropna().unique()

    def nombres_compatibles(nombre_corto, nombre_largo):
        palabras_corto = nombre_corto.split()
        palabras_largo = nombre_largo.split()

        # Cada palabra del nombre corto DEBE encajar en alguna del nombre largo
        for p_corto in palabras_corto:
            encaja = False
            for p_largo in palabras_largo:
                # Comprobamos si es la misma palabra, si es una abreviatura (ej: migue -> miguel)
                # o si es un error tipográfico mínimo (>85% similitud)
                if p_largo.startswith(p_corto) or p_corto.startswith(p_largo):
                    encaja = True
                    break
                elif difflib.SequenceMatcher(None, p_corto, p_largo).ratio() > 0.85:
                    encaja = True
                    break

            # Si una sola palabra del nombre corto no encaja (ej: 'alvaro' contra 'daniel'), fallamos.
            if not encaja:
                return False
        return True

    for equipo in equipos:
        mask_eq = df['Equipo'] == equipo
        nombres_equipo = df[mask_eq]['Nombre'].dropna().unique()

        # Ordenamos del más largo al más corto
        nombres_equipo = sorted(nombres_equipo, key=len, reverse=True)

        for i, nombre_maestro in enumerate(nombres_equipo):
            norm_maestro = normalizar_texto(nombre_maestro)

            for nombre_variante in nombres_equipo[i + 1:]:
                norm_variante = normalizar_texto(nombre_variante)

                # Usamos nuestra nueva lógica estricta
                if nombres_compatibles(norm_variante, norm_maestro):
                    filas_a_cambiar = mask_eq & (df['Nombre'] == nombre_variante)
                    df.loc[filas_a_cambiar, 'Nombre'] = nombre_maestro
                    df.loc[filas_a_cambiar, 'Nombre_Normalizado'] = norm_maestro

    return df


def procesar_excel_para_db(path_excel, nombre_archivo):
    try:
        df_raw = pd.read_excel(path_excel, header=None)
        indices = df_raw[df_raw.iloc[:, 1] == "Nombre"].index.tolist()
        tablas_equipos = []

        for idx in indices:
            nombre_equipo_crudo = str(df_raw.iloc[idx - 2, 0])
            if nombre_equipo_crudo == "nan" or nombre_equipo_crudo.strip() == "":
                nombre_equipo_crudo = str(df_raw.iloc[idx - 1, 0])

            nombre_equipo = nombre_equipo_crudo.replace("Equipo Local:", "").replace("Equipo Visitante:", "").strip()

            df = pd.read_excel(path_excel, header=idx)
            df.columns = [str(c).strip() for c in df.columns]

            if "TOTALES" in df['Nombre'].values:
                idx_totales = df[df['Nombre'] == "TOTALES"].index[0]
                df = df.iloc[:idx_totales]

            df = df.dropna(subset=['Nombre'])
            df = limpiar_nombres_columnas(df)

            df['Equipo'] = nombre_equipo
            df['Partido_Origen'] = nombre_archivo
            tablas_equipos.append(df)

        if not tablas_equipos:
            return None

        return pd.concat(tablas_equipos, ignore_index=True)

    except Exception as e:
        print(f"Error procesando el Excel {nombre_archivo}: {e}")
        return None


def crear_base_de_datos(carpeta_data="data/", db_name="scouting.db"):
    print("Iniciando la migración a SQLite...")

    if os.path.exists(db_name):
        try:
            os.remove(db_name)
            print("Archivo viejo eliminado. Creando base de datos limpia...")
        except PermissionError:
            print(f"❌ ERROR: No se pudo borrar {db_name}. Cierra Streamlit o DB Browser.")
            return

    conexion = sqlite3.connect(db_name)
    archivos = [f for f in os.listdir(carpeta_data) if f.endswith(('.xlsx', '.xls'))]
    todos_los_datos = []

    for archivo in archivos:
        ruta = os.path.join(carpeta_data, archivo)
        df_partido = procesar_excel_para_db(ruta, archivo)
        if df_partido is not None:
            todos_los_datos.append(df_partido)
            print(f"✅ Leído: {archivo} (Equipos: {df_partido['Equipo'].unique()})")

    if todos_los_datos:
        # 1. Unimos todo en un solo DataFrame
        df_final = pd.concat(todos_los_datos, ignore_index=True)

        # 2. UNIFICAMOS COLUMNA DORSAL (Súper importante)
        posibles_nombres_dorsal = ['Num.', 'Num', 'Nº', 'No.', 'DORSAL', 'Dorsal', '#']
        for col in posibles_nombres_dorsal:
            if col in df_final.columns:
                df_final.rename(columns={col: 'Dorsal'}, inplace=True)
                print(f"ℹ️ Renombrada columna '{col}' a 'Dorsal'")
                break

        # Si después de intentar renombrar no existe, la creamos vacía para que no pete la SQL
        if 'Dorsal' not in df_final.columns:
            print("⚠️ Advertencia: No se encontró columna de Dorsal. Creando columna vacía.")
            df_final['Dorsal'] = 0

        #Convertimos todos los dorsales a int
        df_final['Dorsal'] = df_final['Dorsal'].astype(int)

        # 3. Limpiamos nombres y creamos columna normalizada para búsqueda
        df_final['Nombre'] = df_final['Nombre'].astype(str).str.strip()
        df_final['Nombre_Normalizado'] = df_final['Nombre'].apply(normalizar_texto)

        print("🧹 Limpiando y unificando nombres duplicados o mal escritos...")
        df_final = unificar_nombres_equipo(df_final)

        # 4. Volcamos a la base de datos (UNA SOLA VEZ)
        df_final.to_sql('estadisticas', conexion, if_exists='replace', index=False)
        print("\n🏆 ¡Base de datos creada con éxito en scouting.db!")
    else:
        print("\n❌ No se encontraron datos válidos.")

    conexion.close()


if __name__ == "__main__":
    crear_base_de_datos()