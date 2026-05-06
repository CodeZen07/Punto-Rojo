import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from folium.plugins import MarkerCluster

# Configuración de la página
st.set_page_config(page_title="PuntoRojo - Gestión de Totalizadores", layout="wide")

st.title("🔴 PuntoRojo: Inteligencia de Pérdidas")

# --- FUNCIÓN DE ESCANEO FLEXIBLE ---
def find_column(df, variants):
    """Busca una columna entre varias variantes posibles."""
    cols = [c.strip().upper() for c in df.columns]
    for variant in variants:
        v_up = variant.upper()
        if v_up in cols:
            # Retorna el nombre original de la columna en el DF
            idx = cols.index(v_up)
            return df.columns[idx]
    return None

def load_data(files):
    data_dict = {}
    for file in files:
        name = file.name.lower()
        # El archivo 'Balance CT' suele tener basura en las primeras filas
        if "balance_ct" in name or "balance ct" in name:
            df = pd.read_csv(file, skiprows=2) # Saltamos los encabezados de adorno
        else:
            df = pd.read_csv(file)
        
        # Normalización básica para identificación de archivo
        if "bdg" in name: data_dict['bdg'] = df
        elif "relación" in name or "relacion" in name: data_dict['relacion'] = df
        elif "balance" in name or "lectura" in name: data_dict['balance'] = df
            
    return data_dict

# --- SIDEBAR ---
with st.sidebar:
    st.header("Carga de Datos")
    uploaded_files = st.file_uploader("Sube tus CSV", type=['csv'], accept_multiple_files=True)

if uploaded_files:
    dfs = load_data(uploaded_files)
    
    if 'balance' in dfs and 'bdg' in dfs:
        balance = dfs['balance']
        bdg = dfs['bdg']
        
        # BUSCAR COLUMNAS REALES (Evita el error de ID_TRAFO)
        id_col_bal = find_column(balance, ['TOTALIZADOR', 'MEDIDOR', 'NIS', 'ID'])
        id_col_bdg = find_column(bdg, ['TOTALIZADOR', 'CONTADOR', 'MEDIDOR', 'NIC'])
        perdida_col = find_column(balance, ['%PÉRDIDA', '%PERDIDA', 'PERDIDA_PORC', '%', 'PÉRDIDAS'])
        
        if id_col_bal and id_col_bdg:
            # Preparar BDG para el cruce
            cols_geo = [id_col_bdg, 'LATITUD', 'LONGITUD', 'DIRECCION', 'SECTOR']
            existentes_geo = [c for c in cols_geo if c in bdg.columns]
            
            # Unir datos
            main_df = pd.merge(
                balance, 
                bdg[existentes_geo], 
                left_on=id_col_bal, 
                right_on=id_col_bdg, 
                how='left'
            )

            # Limpiar datos de pérdida
            if perdida_col:
                main_df['VALOR_PERDIDA'] = pd.to_numeric(main_df[perdida_col], errors='coerce').fillna(0)
                main_df = main_df.sort_values(by='VALOR_PERDIDA', ascending=False)
            
            # --- INTERFAZ ---
            st.subheader("⚠️ Análisis Operativo")
            col_t, col_m = st.columns([1, 1.5])
            
            with col_t:
                st.write("**Ranking de Pérdidas**")
                display_cols = [c for c in [id_col_bal, 'CIRCUITO', perdida_col] if c in main_df.columns]
                st.dataframe(main_df[display_cols].head(10), use_container_width=True, hide_index=True)

            with col_m:
                m = folium.Map(location=[18.47, -69.93], zoom_start=12, tiles="cartodbpositron")
                cluster = MarkerCluster().add_to(m)
                
                # Mapa
                if 'LATITUD' in main_df.columns and 'LONGITUD' in main_df.columns:
                    for _, row in main_df.dropna(subset=['LATITUD', 'LONGITUD']).iterrows():
                        folium.CircleMarker(
                            location=[row['LATITUD'], row['LONGITUD']],
                            radius=6,
                            color="red" if row.get('VALOR_PERDIDA', 0) > 30 else "green",
                            fill=True,
                            popup=f"ID: {row[id_col_bal]}"
                        ).add_to(cluster)
                st_folium(m, width="100%", height=400)

            # --- BUSCADOR ---
            st.divider()
            selected = st.selectbox("Seleccionar Totalizador para ver Suministros:", [""] + list(main_df[id_col_bal].unique()))
            
            if selected and 'relacion' in dfs:
                rel = dfs['relacion']
                id_rel = find_column(rel, ['TOTALIZADOR', 'MEDIDOR', 'ID'])
                if id_rel:
                    hijos = rel[rel[id_rel].astype(str) == str(selected)]
                    st.write(f"Suministros asociados al Totalizador {selected}:")
                    st.dataframe(hijos, use_container_width=True)
        else:
            st.error("No se pudo vincular los archivos. Asegúrate de que ambos tengan una columna de 'Totalizador' o 'Medidor'.")
    else:
        st.info("Sube los archivos para procesar.")
