import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from folium.plugins import HeatMap, MarkerCluster

# Configuración de la página
st.set_page_config(page_title="PuntoRojo - Gestión de Totalizadores", layout="wide")

st.title("🔴 PuntoRojo: Inteligencia de Pérdidas")
st.markdown("### Distrito Nacional & Zona Este")

# --- FUNCIÓN PARA CARGAR Y LIMPIAR NOMBRES DE COLUMNAS ---
def load_data(files):
    data_dict = {}
    for file in files:
        name = file.name.lower()
        # Leemos el CSV
        df = pd.read_csv(file)
        # Limpiamos los nombres de las columnas (quitamos espacios y pasamos a mayúsculas)
        df.columns = [str(col).strip().upper() for col in df.columns]
        
        if "balance ct" in name:
            data_dict['balance'] = df
        elif "bdg" in name:
            data_dict['bdg'] = df
        elif "relación" in name or "relacion" in name:
            data_dict['relacion'] = df
    return data_dict

# --- CARGA DE ARCHIVOS EN SIDEBAR ---
with st.sidebar:
    st.header("Configuración de Datos")
    uploaded_files = st.file_uploader(
        "Sube los archivos CSV", 
        type=['csv'], 
        accept_multiple_files=True
    )
    st.info("Asegúrate de subir: Balance CT, BDG y Relación.")

if uploaded_files:
    dfs = load_data(uploaded_files)
    
    # Verificación de archivos clave
    if 'balance' in dfs and 'bdg' in dfs:
        balance = dfs['balance']
        bdg = dfs['bdg']
        
        # --- LÓGICA DE UNIÓN DINÁMICA ---
        # En tus archivos, la columna común es 'TOTALIZADOR'
        col_union = 'TOTALIZADOR'
        
        if col_union in balance.columns and col_union in bdg.columns:
            # Seleccionamos solo las columnas necesarias de BDG para no saturar
            columnas_bdg = [col_union, 'LATITUD', 'LONGITUD', 'CAPACIDAD_KVA', 'DIRECCION']
            # Filtramos solo las que existan en el archivo de BDG
            columnas_existentes = [c for c in columnas_bdg if c in bdg.columns]
            
            main_df = pd.merge(
                balance, 
                bdg[columnas_existentes], 
                on=col_union, 
                how='left'
            )

            # Convertir pérdida a numérico por si viene como texto
            if 'PERDIDA_PORC' in main_df.columns:
                main_df['PERDIDA_PORC'] = pd.to_numeric(main_df['PERDIDA_PORC'], errors='coerce').fillna(0)
            
            main_df = main_df.sort_values(by='PERDIDA_PORC', ascending=False)

            # --- VISUALIZACIÓN: TOP 10 ---
            st.subheader("⚠️ Top 10 Totalizadores con Mayor Pérdida")
            top_10 = main_df.head(10)
            
            cols = st.columns([1.2, 2])
            with cols[0]:
                st.dataframe(
                    top_10[[col_union, 'CIRCUITO', 'PERDIDA_PORC']], 
                    use_container_width=True,
                    hide_index=True
                )

            # --- VISUALIZACIÓN: MAPA ---
            with cols[1]:
                # Centrado en Distrito Nacional
                m = folium.Map(location=[18.48, -69.93], zoom_start=12, tiles="cartodbpositron")
                marker_cluster = MarkerCluster().add_to(m)
                
                # Solo graficamos los que tienen coordenadas
                geo_df = main_df.dropna(subset=['LATITUD', 'LONGITUD'])
                
                for _, row in geo_df.iterrows():
                    p_color = "red" if row['PERDIDA_PORC'] > 40 else "orange" if row['PERDIDA_PORC'] > 20 else "green"
                    folium.CircleMarker(
                        location=[row['LATITUD'], row['LONGITUD']],
                        radius=7,
                        color=p_color,
                        fill=True,
                        popup=f"ID: {row[col_union]}<br>Pérdida: {row['PERDIDA_PORC']}%"
                    ).add_to(marker_cluster)
                
                st_folium(m, width="100%", height=400)

            # --- BUSCADOR DE SUMINISTROS ---
            st.divider()
            st.subheader("🔍 Detalle de Suministros Asociados")
            
            selected_id = st.selectbox("Busca un ID de Totalizador:", [""] + list(main_df[col_union].unique()))
            
            if selected_id:
                # Mostrar info del totalizador
                info = main_df[main_df[col_union] == selected_id].iloc[0]
                st.info(f"**Circuito:** {info.get('CIRCUITO', 'N/A')} | **Pérdida:** {info['PERDIDA_PORC']}%")
                
                if 'relacion' in dfs:
                    rel = dfs['relacion']
                    # En 'relacion' la columna también es TOTALIZADOR
                    asociados = rel[rel['TOTALIZADOR'] == selected_id]
                    st.write(f"Suministros encontrados: {len(asociados)}")
                    st.dataframe(asociados, use_container_width=True)
                else:
                    st.warning("Sube el archivo de 'Relación' para ver los suministros de este totalizador.")
        else:
            st.error(f"No se encontró la columna '{col_union}' en los archivos. Verifica los encabezados.")
    else:
        st.info("Esperando archivos... Sube al menos 'Balance CT' y 'BDG'.")
else:
    st.info("👋 Bienvenida/o. Sube los archivos en la barra lateral para comenzar el análisis.")
