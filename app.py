import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from folium.plugins import MarkerCluster

# Configuración de la página
st.set_page_config(page_title="PuntoRojo - Gestión de Totalizadores", layout="wide")

st.title("🔴 PuntoRojo: Inteligencia de Pérdidas")
st.markdown("### Distrito Nacional & Zona Este")

# --- FUNCIÓN DE CARGA ROBUSTA ---
def load_data(files):
    data_dict = {}
    for file in files:
        name = file.name.lower()
        # Leer el archivo
        df = pd.read_csv(file)
        
        # NORMALIZACIÓN DE COLUMNAS: Quitar espacios, puntos y pasar a MAYÚSCULAS
        df.columns = [str(col).strip().upper().replace(" ", "_") for col in df.columns]
        
        if "balance_ct" in name or "lectura" in name:
            data_dict['balance'] = df
        elif "bdg" in name:
            data_dict['bdg'] = df
        elif "relación" in name or "relacion" in name:
            data_dict['relacion'] = df
            
    return data_dict

# --- SIDEBAR ---
with st.sidebar:
    st.header("Configuración de Datos")
    uploaded_files = st.file_uploader(
        "Sube los archivos CSV (Balance, BDG, Relación)", 
        type=['csv'], 
        accept_multiple_files=True
    )
    st.info("💡 Consejo: Asegúrate de que el archivo de pérdidas contenga la columna 'TOTALIZADOR' y 'PERDIDA_PORC'.")

if uploaded_files:
    dfs = load_data(uploaded_files)
    
    # 1. VALIDACIÓN DE ARCHIVOS CRÍTICOS
    if 'balance' in dfs and 'bdg' in dfs:
        balance = dfs['balance']
        bdg = dfs['bdg']
        
        # Columnas clave normalizadas
        ID_COL = 'TOTALIZADOR'
        PERDIDA_COL = 'PERDIDA_PORC'
        
        if ID_COL in balance.columns and ID_COL in bdg.columns:
            # 2. CRUCE DE DATOS (Merge)
            # Traemos coordenadas y datos técnicos de la BDG
            cols_bdg = [c for c in [ID_COL, 'LATITUD', 'LONGITUD', 'CAPACIDAD_KVA', 'DIRECCION'] if c in bdg.columns]
            
            main_df = pd.merge(balance, bdg[cols_bdg], on=ID_COL, how='left')

            # Convertir pérdida a número por seguridad
            if PERDIDA_COL in main_df.columns:
                main_df[PERDIDA_COL] = pd.to_numeric(main_df[PERDIDA_COL], errors='coerce').fillna(0)
            
            # Ordenar por pérdida para el TOP 10
            main_df = main_df.sort_values(by=PERDIDA_COL, ascending=False)

            # --- VISTA: TOP 10 Y MAPA ---
            st.subheader("⚠️ Análisis de Puntos Críticos")
            col_tabla, col_mapa = st.columns([1, 1.5])
            
            with col_tabla:
                st.write("**Top 10 Mayores Pérdidas**")
                # Mostramos columnas que existen en tus archivos
                cols_mostrar = [c for c in [ID_COL, 'CIRCUITO', PERDIDA_COL] if c in main_df.columns]
                st.dataframe(main_df[cols_mostrar].head(10), use_container_width=True, hide_index=True)

            with col_mapa:
                # Mapa centrado en Santo Domingo (Distrito Nacional)
                m = folium.Map(location=[18.475, -69.93], zoom_start=12, tiles="cartodbpositron")
                marker_cluster = MarkerCluster().add_to(m)
                
                # Filtrar los que tienen coordenadas
                geo_df = main_df.dropna(subset=['LATITUD', 'LONGITUD'])
                
                for _, row in geo_df.iterrows():
                    # Color del punto según la gravedad
                    val_p = row[PERDIDA_COL]
                    p_color = "red" if val_p > 40 else "orange" if val_p > 20 else "green"
                    
                    folium.CircleMarker(
                        location=[row['LATITUD'], row['LONGITUD']],
                        radius=7,
                        color=p_color,
                        fill=True,
                        popup=f"Totalizador: {row[ID_COL]}<br>Pérdida: {val_p}%"
                    ).add_to(marker_cluster)
                
                st_folium(m, width="100%", height=400)

            # --- BUSCADOR Y DETALLE DE SUMINISTROS ---
            st.divider()
            st.subheader("🔍 Buscador de Suministros Asociados")
            
            selected_id = st.selectbox("Escribe o selecciona un ID de Totalizador:", [""] + list(main_df[ID_COL].unique()))
            
            if selected_id:
                # Datos del totalizador seleccionado
                info = main_df[main_df[ID_COL] == selected_id].iloc[0]
                
                met1, met2, met3 = st.columns(3)
                met1.metric("Pérdida", f"{info[PERDIDA_COL]}%")
                met2.metric("Circuito", info.get('CIRCUITO', 'N/A'))
                met3.write(f"**Ubicación:** {info.get('DIRECCION', 'No disponible en BDG')}")
                
                # Buscar suministros en el archivo 'Relación'
                if 'relacion' in dfs:
                    rel = dfs['relacion']
                    if ID_COL in rel.columns:
                        hijos = rel[rel[ID_COL] == selected_id]
                        st.write(f"### Suministros vinculados ({len(hijos)})")
                        st.dataframe(hijos, use_container_width=True)
                        
                        # Insight de Naval Ravikant para la toma de decisiones
                        if info[PERDIDA_COL] > 40:
                            st.error(f"**Recomendación Atlas:** Con un {info[PERDIDA_COL]}% de pérdida, el apalancamiento está en la inspección técnica inmediata. No pierdas tiempo en análisis manuales; este punto es una anomalía clara.")
                    else:
                        st.warning(f"El archivo de Relación no tiene la columna '{ID_COL}'.")
                else:
                    st.info("Sube el archivo 'Relación' para ver los NICs de este totalizador.")
        else:
            st.error(f"Error: No se encontró la columna '{ID_COL}' en los archivos subidos.")
    else:
        st.info("Esperando archivos... Asegúrate de subir el 'Balance' y la 'BDG'.")
else:
    st.write("Favor subir los archivos CSV en la barra lateral para procesar el balance.")
