import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from folium.plugins import MarkerCluster
import io

st.set_page_config(page_title="PuntoRojo - Gestión de Totalizadores", layout="wide")
st.title("🔴 PuntoRojo: Inteligencia de Pérdidas")

def clean_and_load(file):
    """Limpia archivos que tienen encabezados de reporte antes de la tabla."""
    raw_data = file.getvalue().decode('utf-8')
    lines = raw_data.splitlines()
    
    # Buscamos la línea donde realmente empiezan los datos (ej. donde esté 'ITEM' o 'TOTALIZADOR')
    start_line = 0
    for i, line in enumerate(lines[:20]): # Escaneamos las primeras 20 filas
        if "ITEM" in line.upper() or "TOTALIZADOR" in line.upper() or "NIC" in line.upper():
            start_line = i
            break
            
    df = pd.read_csv(io.StringIO("\n".join(lines[start_line:])))
    df.columns = [str(col).strip().upper().replace(" ", "_") for col in df.columns]
    return df

# --- PROCESAMIENTO ---
with st.sidebar:
    st.header("Carga de Datos")
    uploaded_files = st.file_uploader("Sube los archivos CSV", type=['csv'], accept_multiple_files=True)

if uploaded_files:
    data = {}
    for f in uploaded_files:
        name = f.name.lower()
        df_temp = clean_and_load(f)
        
        if "bdg" in name: data['bdg'] = df_temp
        elif "relación" in name or "relacion" in name: data['relacion'] = df_temp
        else: data['balance'] = df_temp # Por defecto el balance

    if 'balance' in data and 'bdg' in data:
        # Identificación flexible de columnas
        # En tus archivos el ID es 'TOTALIZADOR' o 'MEDIDOR'
        id_col = next((c for c in data['balance'].columns if c in ['TOTALIZADOR', 'MEDIDOR', 'ID']), None)
        id_bdg = next((c for c in data['bdg'].columns if c in ['TOTALIZADOR', 'CONTADOR', 'MEDIDOR']), None)
        
        if id_col and id_bdg:
            # Unimos con la BDG para coordenadas
            main_df = pd.merge(data['balance'], data['bdg'], left_on=id_col, right_on=id_bdg, how='left')
            
            # Ranking y Mapa
            col_t, col_m = st.columns([1, 1.5])
            
            with col_t:
                st.subheader("Top Pérdidas")
                st.dataframe(main_df.head(10), use_container_width=True)

            with col_m:
                # Mapa centrado en Distrito Nacional
                m = folium.Map(location=[18.47, -69.93], zoom_start=12)
                cluster = MarkerCluster().add_to(m)
                
                # Usamos los nombres exactos de tu BDG: 'LATITUD' y 'LONGITUD'
                if 'LATITUD' in main_df.columns and 'LONGITUD' in main_df.columns:
                    for _, row in main_df.dropna(subset=['LATITUD', 'LONGITUD']).iterrows():
                        folium.Marker(
                            location=[row['LATITUD'], row['LONGITUD']],
                            popup=f"ID: {row[id_col]}"
                        ).add_to(cluster)
                st_folium(m, width="100%", height=450)
        else:
            st.error("No se encontró una columna de enlace (TOTALIZADOR/MEDIDOR) en los archivos.")
