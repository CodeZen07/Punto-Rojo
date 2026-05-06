import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from folium.plugins import HeatMap, MarkerCluster

# Configuración de la página
st.set_page_config(page_title="PuntoRojo - Gestión de Totalizadores", layout="wide")

st.title("🔴 PuntoRojo: Inteligencia de Pérdidas - Fase de Prueba")
st.markdown("### Distrito Nacional & Zona Este")

# --- FUNCIONES DE PROCESAMIENTO ---
def load_data(files):
    data_dict = {}
    for file in files:
        # Identificar archivo por nombre (según los que me pasaste)
        name = file.name.lower()
        df = pd.read_csv(file)
        
        if "balance ct" in name:
            data_dict['balance'] = df
        elif "bdg" in name:
            data_dict['bdg'] = df
        elif "relación" in name or "relacion" in name:
            data_dict['relacion'] = df
    return data_dict

# --- CARGA DE ARCHIVOS ---
with st.sidebar:
    st.header("Carga de Datos")
    uploaded_files = st.file_uploader(
        "Sube los archivos (Balance CT, BDG, Relación)", 
        type=['csv'], 
        accept_multiple_files=True
    )

if uploaded_files:
    dfs = load_data(uploaded_files)
    
    # Verificar que tengamos los archivos mínimos para operar
    if 'balance' in dfs and 'bdg' in dfs:
        balance = dfs['balance']
        bdg = dfs['bdg']
        
        # 1. CRUCE DE DATOS (Merge)
        # Unimos el Balance con la BDG para obtener coordenadas y datos técnicos
        # Usamos 'TOTALIZADOR' o el ID que vincule ambos
        main_df = pd.merge(
            balance, 
            bdg[['TOTALIZADOR', 'LATITUD', 'LONGITUD', 'CAPACIDAD_KVA', 'DIRECCION']], 
            on='TOTALIZADOR', 
            how='left'
        )
        
        # Limpieza rápida: Asegurar que las pérdidas sean numéricas
        main_df['PERDIDA_PORC'] = pd.to_numeric(main_df['PERDIDA_PORC'], errors='coerce')
        main_df = main_df.sort_values(by='PERDIDA_PORC', ascending=False)

        # --- SECCIÓN: TOP 10 PÉRDIDAS ---
        st.subheader("⚠️ Top 10 Totalizadores Críticos")
        top_10 = main_df.head(10)
        
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.dataframe(
                top_10[['TOTALIZADOR', 'CIRCUITO', 'PERDIDA_PORC', 'CONSUMO_TOTALIZADOR']],
                use_container_width=True
            )

        # --- SECCIÓN: MAPA INTERACTIVO ---
        with col2:
            st.write("Ubicación de Puntos Críticos")
            # Centrado en Santo Domingo / Distrito Nacional
            m = folium.Map(location=[18.47, -69.91], zoom_start=13, tiles="cartodbpositron")
            
            # Cluster para no saturar el mapa
            marker_cluster = MarkerCluster().add_to(m)
            
            for _, row in main_df.dropna(subset=['LATITUD', 'LONGITUD']).iterrows():
                # Color según severidad
                color = "red" if row['PERDIDA_PORC'] > 40 else "orange" if row['PERDIDA_PORC'] > 20 else "green"
                
                folium.CircleMarker(
                    location=[row['LATITUD'], row['LONGITUD']],
                    radius=8,
                    color=color,
                    fill=True,
                    fill_color=color,
                    popup=f"Totalizador: {row['TOTALIZADOR']}<br>Pérdida: {row['PERDIDA_PORC']}%<br>Circuito: {row['CIRCUITO']}"
                ).add_to(marker_cluster)
            
            st_folium(m, width=None, height=400)

        # --- SECCIÓN: BÚSQUEDA Y SUMINISTROS ASOCIADOS ---
        st.divider()
        st.subheader("🔍 Buscador de Suministros por Totalizador")
        
        search_id = st.selectbox("Selecciona o busca un Totalizador:", [""] + list(main_df['TOTALIZADOR'].unique()))
        
        if search_id and 'relacion' in dfs:
            rel = dfs['relacion']
            # Filtrar suministros asociados
            suministros = rel[rel['TOTALIZADOR'] == search_id]
            
            c1, c2, c3 = st.columns(3)
            info_totalizador = main_df[main_df['TOTALIZADOR'] == search_id].iloc[0]
            
            c1.metric("Pérdida Actual", f"{info_totalizador['PERDIDA_PORC']}%")
            c2.metric("Suministros Conectados", len(suministros))
            c3.write(f"**Ubicación:** {info_totalizador['DIRECCION']}")
            
            st.write("### Suministros Asociados (NICs)")
            st.table(suministros[['NIC', 'NOMBRE_CLIENTE', 'TARIFA', 'ESTADO']])
            
            # Insight Operativo
            if info_totalizador['PERDIDA_PORC'] > 50:
                st.error("💡 **Insight:** Este punto requiere blindaje de red inmediato. La pérdida supera el 50%, lo que sugiere fraude masivo o derivaciones directas.")
            elif info_totalizador['PERDIDA_PORC'] > 25:
                st.warning("💡 **Insight:** Se recomienda operativo de normalización nocturno para detectar anomalías no técnicas.")

    else:
        st.info("Por favor, sube los archivos de 'Balance CT', 'BDG' y 'Relación' para activar el análisis.")

else:
    st.warning("Esperando archivos CSV para iniciar el balance...")
