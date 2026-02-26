import streamlit as st
import pandas as pd
import folium
from folium.plugins import HeatMap
import numpy as np

# Función para generar datos de ejemplo
def generate_sample_data():
    infra_data = {
        'ID_Trafo': [1, 2, 3],
        'Sector': ['Gazcue', 'Ensanche Luperón', 'San Isidro'],
        'Latitud': [18.4691, 18.4868, 18.4507],
        'Longitud': [-69.9303, -69.9283, -69.9085],
        'Capacidad_kVA': [100, 150, 200],
        'kWh_Entregado': [2000, 2500, 3000]
    }
    
    com_data = {
        'ID_Trafo': [1, 2, 3],
        'kWh_Facturado': [1000, 1200, 1500],
        'Clientes_Directos': [50, 60, 70],
        'Recaudacion_DOP': [50000, 70000, 90000]
    }
    
    return pd.DataFrame(infra_data), pd.DataFrame(com_data)

# Configuración de la página
st.title("PuntoRojo - Detección de Pérdidas de Energía")
st.write("Sube tus archivos para detectar y priorizar intervenciones por pérdida de energía.")

# Carga de archivos
uploaded_file = st.file_uploader("Sube un archivo Excel o CSV", type=['xlsx', 'csv'], accept_multiple_files=True)

if uploaded_file is not None:
    # Cargar datos desde archivos
    for file in uploaded_file:
        if file.name.endswith('.csv'):
            data = pd.read_csv(file)
        elif file.name.endswith('.xlsx'):
            data = pd.read_excel(file)

        # Procesar los datos aquí
        st.write(data.head())   # Muestra las primeras filas de los datos subidos

# Generar datos de ejemplo si no hay archivos subidos
if not uploaded_file:
    infra_data, com_data = generate_sample_data()
    st.write("Datos de ejemplo generados.")
    st.write(infra_data)
    st.write(com_data)

# Procesar datos
if uploaded_file:
    # Aquí implementamos la lógica de cruce de datos
    # Unir las tablas de infraestructura y comercial
    merged_data = pd.merge(infra_data, com_data, on='ID_Trafo')
    merged_data['Pérdida'] = merged_data['kWh_Entregado'] - merged_data['kWh_Facturado']
    merged_data['Pérdida (%)'] = (merged_data['Pérdida'] / merged_data['kWh_Entregado']) * 100
    
    # Filtrar zonas de intervención
    zonas_intervencion = merged_data[(merged_data['Pérdida (%)'] > 45) | 
                                      (merged_data['Pérdida'] > 500) | 
                                      (merged_data['Clientes_Directos'] > 50)]
    
    # Mapa
    st.subheader("Mapa de Pérdidas de Energía")
    m = folium.Map(location=[18.4675, -69.9312], zoom_start=12)
    
    # HeatMap
    heat_data = [[row['Latitud'], row['Longitud']] for index, row in merged_data.iterrows()]
    HeatMap(heat_data).add_to(m)
    
    for _, row in merged_data.iterrows():
        folium.Marker([row['Latitud'], row['Longitud']],
                      popup=f"% Pérdida: {row['Pérdida (%)']:.2f}%, $ Perdido: {row['Pérdida']}, Clientes: {row['Clientes_Directos']}").add_to(m)
    
    st_folium(m, width=700, height=500)

    # Sugerencias operativas
    st.subheader("Sugerencias Operativas")
    for _, row in zonas_intervencion.iterrows():
        if row['Pérdida (%)'] > 45:
            st.write(f"En {row['Sector']}, la pérdida es técnica por sobrecarga; se sugiere aumento de capacidad de transformador.")
        else:
            st.write(f"En {row['Sector']}, la pérdida es no técnica; se sugiere operativo de normalización nocturno y blindaje de red.")

# Crear tabla de ruta crítica
if not zonas_intervencion.empty:
    st.subheader("Ruta Crítica")
    st.write(zonas_intervencion[['Sector', 'ID_Trafo', 'Pérdida', 'Pérdida (%)']])
