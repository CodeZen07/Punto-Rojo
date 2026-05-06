"""
PuntoRojo - Gestión de Pérdidas Eléctricas | Distrito Nacional
Ingeniero de Datos: app reestructurada con limpieza dinámica de encabezados,
fuzzy matching de columnas, semáforo visual y relación padre-hijo.
"""

import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import numpy as np
from difflib import get_close_matches
import re

# ──────────────────────────────────────────────
# CONFIGURACIÓN DE PÁGINA
# ──────────────────────────────────────────────
st.set_page_config(
    page_title="PuntoRojo – Pérdidas Eléctricas",
    page_icon="🔴",
    layout="wide",
)

st.title("🔴 PuntoRojo — Gestión de Pérdidas Eléctricas | Distrito Nacional")
st.caption("Sube el archivo Balance de Totalizadores para comenzar el análisis.")

# ──────────────────────────────────────────────
# HELPERS: FUZZY COLUMN FINDER
# ──────────────────────────────────────────────

COLUMN_ALIASES = {
    "TOTALIZADOR": ["totalizador", "talizador", "totalizadores", "id_trafo", "trafo", "transformador"],
    "NIC":         ["nic", "n_ic", "num_nic"],
    "NIS":         ["nis", "n_is", "num_nis"],
    "NOMBRE":      ["nombre", "name", "cliente", "titular"],
    "ESTADO":      ["estado", "situacion", "status", "estado_suministro"],
    "COMPRA":      ["compra", "kwh_entregado", "kwh compra", "kwh_compra", "energia_compra"],
    "FACTURACION": ["facturacion", "facturado", "kwh_facturado", "kwh facturado", "facturacion"],
    "PERDIDA":     ["perdida", "pérdida", "diff", "diferencia"],
    "PCT_PERDIDA": ["%perdida", "% perdida", "% pérdida", "%pérdida", "pct_perdida",
                    "porcentaje_perdida", "perdida%", "%", "pctperdida", "%_perdida"],
    "LATITUD":     ["latitud", "lat", "latitude", "y"],
    "LONGITUD":    ["longitud", "lon", "lng", "longitude", "x"],
    "CIRCUITO":    ["circuito", "circuit"],
    "SECTOR":      ["sector", "barrio", "zona"],
    "TIPO":        ["tipo", "type", "tipo_suministro"],
}


def _normalize(s: str) -> str:
    """Quita tildes, espacios extra y convierte a minúsculas."""
    s = str(s).lower().strip()
    replacements = {"á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "ü": "u", "ñ": "n"}
    for k, v in replacements.items():
        s = s.replace(k, v)
    s = re.sub(r"[^a-z0-9_%]", "", s)
    return s


def find_column(df: pd.DataFrame, canonical: str) -> str | None:
    """
    Busca la columna real en df que mejor coincide con el nombre canónico.
    Retorna el nombre real de la columna o None.
    """
    aliases = COLUMN_ALIASES.get(canonical, [canonical.lower()])
    normalized_aliases = [_normalize(a) for a in aliases]
    col_map = {_normalize(c): c for c in df.columns}

    for alias in normalized_aliases:
        if alias in col_map:
            return col_map[alias]

    # Fuzzy fallback
    candidates = list(col_map.keys())
    for alias in normalized_aliases:
        matches = get_close_matches(alias, candidates, n=1, cutoff=0.75)
        if matches:
            return col_map[matches[0]]
    return None


def safe_col(df: pd.DataFrame, canonical: str, default=None):
    """Retorna la Serie de la columna encontrada o una Serie de default."""
    col = find_column(df, canonical)
    if col:
        return df[col]
    if default is not None:
        return pd.Series([default] * len(df), index=df.index)
    return None


# ──────────────────────────────────────────────
# LIMPIEZA DINÁMICA DE ENCABEZADOS (Balance CT)
# ──────────────────────────────────────────────

def load_balance_ct(xls: pd.ExcelFile) -> pd.DataFrame | None:
    """
    Escanea la hoja 'Balance CT' fila por fila hasta encontrar 'ITEM' o 'TOTALIZADOR'
    y usa esa fila como encabezado real.
    """
    try:
        raw = pd.read_excel(xls, sheet_name="Balance CT", header=None, dtype=str)
    except Exception:
        return None

    header_row = None
    for i, row in raw.iterrows():
        row_upper = row.astype(str).str.upper().str.strip()
        if row_upper.isin(["ITEM", "TOTALIZADOR"]).any():
            header_row = i
            break

    if header_row is None:
        return None

    df = pd.read_excel(xls, sheet_name="Balance CT", header=header_row, dtype=str)
    df.columns = [str(c).strip().upper() for c in df.columns]
    # Eliminar filas donde la columna ITEM es NaN o no numérica
    item_col = find_column(df, "NIC") or (df.columns[0] if len(df.columns) > 0 else None)
    if item_col:
        df = df[df[item_col].notna() & (df[item_col] != "NAN")]
    df = df.reset_index(drop=True)
    return df


def load_sheet_clean(xls: pd.ExcelFile, sheet_name: str) -> pd.DataFrame | None:
    """Carga una hoja y normaliza columnas a MAYÚSCULAS."""
    try:
        df = pd.read_excel(xls, sheet_name=sheet_name, dtype=str)
        df.columns = [str(c).strip().upper() for c in df.columns]
        df = df.dropna(how="all").reset_index(drop=True)
        return df
    except Exception:
        return None


# ──────────────────────────────────────────────
# SEMÁFORO: color por % pérdida
# ──────────────────────────────────────────────

def traffic_light_color(pct: float) -> str:
    if pct > 30:
        return "red"
    elif pct >= 15:
        return "orange"
    else:
        return "green"


def traffic_light_label(pct: float) -> str:
    if pct > 30:
        return "🔴 Alta (>30%)"
    elif pct >= 15:
        return "🟠 Media (15–30%)"
    else:
        return "🟢 Baja (<15%)"


# ──────────────────────────────────────────────
# CARGA DE ARCHIVO
# ──────────────────────────────────────────────

uploaded_file = st.file_uploader(
    "📂 Sube el archivo Excel (Balance de Totalizadores)",
    type=["xlsx"],
)

if not uploaded_file:
    st.info("⬆️ Sube el archivo Excel para comenzar. El sistema detectará automáticamente los encabezados.")
    st.stop()

xls = pd.ExcelFile(uploaded_file)
available_sheets = xls.sheet_names

st.success(f"Archivo cargado. Pestañas encontradas: `{'`, `'.join(available_sheets)}`")

# ──────────────────────────────────────────────
# CARGA DE PESTAÑAS
# ──────────────────────────────────────────────

df_balance_ct      = load_balance_ct(xls)
df_balance_central = load_sheet_clean(xls, "Balance Central") if "Balance Central" in available_sheets else None
df_relacion        = load_sheet_clean(xls, "Relación")        if "Relación" in available_sheets        else None
df_bdg             = load_sheet_clean(xls, next((s for s in available_sheets if "bdg" in s.lower()), ""))

# ──────────────────────────────────────────────
# TABS PRINCIPALES
# ──────────────────────────────────────────────

tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Top 10 Pérdidas",
    "🗺️ Mapa Semáforo",
    "🔗 Relación Padre-Hijo",
    "🔍 Explorador de Datos",
])

# ══════════════════════════════════════════════
# TAB 1 – TOP 10 PÉRDIDAS
# ══════════════════════════════════════════════
with tab1:
    st.subheader("📊 Top 10 Totalizadores con Mayor % de Pérdida")

    # Preferir Balance Central (tiene %Pérdida limpio)
    df_top = df_balance_central if df_balance_central is not None else df_balance_ct

    if df_top is None:
        st.warning("No se encontró ninguna hoja de balance con datos.")
    else:
        pct_col  = find_column(df_top, "PCT_PERDIDA")
        tот_col  = find_column(df_top, "TOTALIZADOR")
        comp_col = find_column(df_top, "COMPRA")
        fact_col = find_column(df_top, "FACTURACION")
        perd_col = find_column(df_top, "PERDIDA")
        circ_col = find_column(df_top, "CIRCUITO")
        sect_col = find_column(df_top, "SECTOR")

        if pct_col is None:
            st.error("No se encontró la columna de % Pérdida. Revisa el archivo.")
        else:
            df_top = df_top.copy()
            df_top["_PCT"] = pd.to_numeric(df_top[pct_col], errors="coerce")

            cols_show = {}
            if tот_col:  cols_show["Totalizador"] = tот_col
            if sect_col: cols_show["Sector"]      = sect_col
            if circ_col: cols_show["Circuito"]    = circ_col
            if comp_col: cols_show["Compra (kWh)"]   = comp_col
            if fact_col: cols_show["Facturación (kWh)"] = fact_col
            if perd_col: cols_show["Pérdida (kWh)"]  = perd_col
            cols_show["% Pérdida"] = pct_col

            ranking = (
                df_top
                .dropna(subset=["_PCT"])
                .sort_values("_PCT", ascending=False)
                .head(10)
                .rename(columns={v: k for k, v in cols_show.items()})
            )

            display_cols = [c for c in cols_show.keys() if c in ranking.columns]
            ranking["Semáforo"] = ranking["% Pérdida"].apply(
                lambda x: traffic_light_label(float(x)) if pd.notna(x) else ""
            )
            display_cols.append("Semáforo")

            st.dataframe(
                ranking[display_cols].reset_index(drop=True),
                use_container_width=True,
                height=420,
            )

            # Mini chart
            if tот_col:
                chart_data = ranking[["Totalizador", "% Pérdida"]].copy()
                chart_data["% Pérdida"] = pd.to_numeric(chart_data["% Pérdida"], errors="coerce")
                st.bar_chart(chart_data.set_index("Totalizador"))

# ══════════════════════════════════════════════
# TAB 2 – MAPA SEMÁFORO
# ══════════════════════════════════════════════
with tab2:
    st.subheader("🗺️ Mapa de Semáforo de Pérdidas — Distrito Nacional")
    st.caption("🔴 >30% pérdida | 🟠 15-30% | 🟢 <15%")

    if df_bdg is None:
        st.warning("No se encontró la pestaña BDG. El mapa requiere coordenadas LATITUD/LONGITUD de esa pestaña.")
    elif df_balance_central is None:
        st.warning("No se encontró la hoja 'Balance Central' para cruzar % de pérdida.")
    else:
        lat_col  = find_column(df_bdg, "LATITUD")
        lon_col  = find_column(df_bdg, "LONGITUD")
        nis_col_bdg = find_column(df_bdg, "NIS")

        if not lat_col or not lon_col:
            st.warning(
                f"No se encontraron columnas LATITUD/LONGITUD en la pestaña BDG. "
                f"Columnas disponibles: {list(df_bdg.columns[:20])}"
            )
        else:
            # Cruzar BDG con Balance Central por NIS
            nis_col_bc  = find_column(df_balance_central, "NIS")
            pct_col_bc  = find_column(df_balance_central, "PCT_PERDIDA")
            tot_col_bc  = find_column(df_balance_central, "TOTALIZADOR")
            nom_col_bdg = find_column(df_bdg, "NOMBRE")

            df_bdg_geo = df_bdg.copy()
            df_bdg_geo["_LAT"] = pd.to_numeric(df_bdg_geo[lat_col], errors="coerce")
            df_bdg_geo["_LON"] = pd.to_numeric(df_bdg_geo[lon_col], errors="coerce")
            df_bdg_geo = df_bdg_geo.dropna(subset=["_LAT", "_LON"])

            if nis_col_bdg and nis_col_bc and pct_col_bc:
                df_bc_slim = df_balance_central[[nis_col_bc, pct_col_bc] +
                                                ([tot_col_bc] if tot_col_bc else [])].copy()
                df_bc_slim[nis_col_bc] = df_bc_slim[nis_col_bc].astype(str).str.strip()
                df_bdg_geo[nis_col_bdg] = df_bdg_geo[nis_col_bdg].astype(str).str.strip()

                df_map = df_bdg_geo.merge(
                    df_bc_slim,
                    left_on=nis_col_bdg,
                    right_on=nis_col_bc,
                    how="left",
                )
                df_map["_PCT"] = pd.to_numeric(df_map[pct_col_bc], errors="coerce").fillna(0)
            else:
                df_map = df_bdg_geo.copy()
                df_map["_PCT"] = 0.0

            # Construir mapa Folium
            m = folium.Map(location=[18.48, -69.93], zoom_start=13, tiles="CartoDB positron")

            plotted = 0
            for _, row in df_map.iterrows():
                lat, lon, pct = row["_LAT"], row["_LON"], row["_PCT"]
                color = traffic_light_color(abs(pct))
                label = traffic_light_label(abs(pct))
                tot_name = row.get(tot_col_bc, row.get(nis_col_bdg, "N/D")) if tot_col_bc else "N/D"
                nom = row[nom_col_bdg] if nom_col_bdg else ""

                popup_html = f"""
                <b>Totalizador:</b> {tot_name}<br>
                <b>NIS:</b> {row.get(nis_col_bdg, '')}<br>
                <b>Nombre:</b> {nom}<br>
                <b>% Pérdida:</b> {pct:.1f}%<br>
                <b>Estado:</b> {label}
                """
                folium.CircleMarker(
                    location=[lat, lon],
                    radius=8,
                    color=color,
                    fill=True,
                    fill_color=color,
                    fill_opacity=0.8,
                    popup=folium.Popup(popup_html, max_width=280),
                    tooltip=f"{tot_name} | {pct:.1f}%",
                ).add_to(m)
                plotted += 1

            st.info(f"Mostrando **{plotted}** puntos en el mapa.")
            st_folium(m, width="100%", height=560)

# ══════════════════════════════════════════════
# TAB 3 – RELACIÓN PADRE-HIJO
# ══════════════════════════════════════════════
with tab3:
    st.subheader("🔗 Relación Padre (Totalizador) → Hijo (Suministros / NICs)")

    if df_relacion is None:
        st.warning("No se encontró la pestaña 'Relación' en el archivo.")
    else:
        tot_col_rel  = find_column(df_relacion, "TOTALIZADOR")
        nic_col_rel  = find_column(df_relacion, "NIC")
        nis_col_rel  = find_column(df_relacion, "NIS")
        tipo_col_rel = find_column(df_relacion, "TIPO")

        if not tot_col_rel:
            st.error(
                f"No se encontró la columna 'Totalizador' en la pestaña Relación. "
                f"Columnas: {list(df_relacion.columns[:15])}"
            )
        else:
            # Buscador de totalizadores
            totalizadores = sorted(
                df_relacion[tot_col_rel].dropna().astype(str).unique().tolist()
            )

            search_text = st.text_input("🔍 Buscar Totalizador", placeholder="Escribe el nombre o código...")
            if search_text:
                totalizadores_filtrados = [t for t in totalizadores if search_text.upper() in t.upper()]
            else:
                totalizadores_filtrados = totalizadores

            if not totalizadores_filtrados:
                st.warning("Ningún totalizador coincide con la búsqueda.")
            else:
                selected = st.selectbox("Selecciona un Totalizador", totalizadores_filtrados)

                if selected:
                    hijos = df_relacion[
                        df_relacion[tot_col_rel].astype(str) == str(selected)
                    ].copy()

                    # Separar totalizador padre de clientes
                    if tipo_col_rel:
                        hijos_clientes = hijos[
                            hijos[tipo_col_rel].str.upper().str.strip() == "CLIENTE"
                        ]
                        fila_padre = hijos[
                            hijos[tipo_col_rel].str.upper().str.strip() == "TOTALIZADOR"
                        ]
                    else:
                        hijos_clientes = hijos
                        fila_padre = pd.DataFrame()

                    st.markdown(f"### Totalizador: `{selected}`")
                    col1, col2 = st.columns(2)

                    with col1:
                        st.metric("Total suministros asociados", len(hijos_clientes))

                    with col2:
                        compra_col_rel = find_column(df_relacion, "COMPRA")
                        fact_col_rel   = find_column(df_relacion, "FACTURACION")
                        if not fila_padre.empty and compra_col_rel:
                            compra_val = pd.to_numeric(
                                fila_padre[compra_col_rel].iloc[0], errors="coerce"
                            )
                            st.metric("Compra totalizador (kWh)", f"{compra_val:.2f}" if pd.notna(compra_val) else "N/D")

                    # Tabla de hijos
                    cols_hijo = {}
                    if nic_col_rel:  cols_hijo["NIC"]    = nic_col_rel
                    if nis_col_rel:  cols_hijo["NIS"]    = nis_col_rel
                    if tipo_col_rel: cols_hijo["Tipo"]   = tipo_col_rel

                    # Agregar columnas adicionales de consumo si existen
                    for canon in ["COMPRA", "FACTURACION", "PERDIDA", "PCT_PERDIDA", "CIRCUITO"]:
                        c = find_column(df_relacion, canon)
                        if c and c not in cols_hijo.values():
                            cols_hijo[canon.replace("_", " ").title()] = c

                    rename_map = {v: k for k, v in cols_hijo.items()}
                    display_df = hijos_clientes.rename(columns=rename_map)
                    display_cols = [k for k in cols_hijo.keys() if k in display_df.columns]

                    if display_cols:
                        st.dataframe(display_df[display_cols].reset_index(drop=True),
                                     use_container_width=True, height=400)
                    else:
                        st.dataframe(hijos_clientes.reset_index(drop=True),
                                     use_container_width=True, height=400)

                    # Download CSV
                    csv = hijos_clientes.to_csv(index=False).encode("utf-8")
                    st.download_button(
                        "⬇️ Descargar suministros como CSV",
                        csv,
                        file_name=f"suministros_{selected}.csv",
                        mime="text/csv",
                    )

# ══════════════════════════════════════════════
# TAB 4 – EXPLORADOR DE DATOS
# ══════════════════════════════════════════════
with tab4:
    st.subheader("🔍 Explorador de Datos Crudos")

    sheet_sel = st.selectbox("Selecciona una pestaña para explorar", available_sheets)
    if sheet_sel:
        df_exp = load_sheet_clean(xls, sheet_sel)
        if df_exp is None and sheet_sel == "Balance CT":
            df_exp = load_balance_ct(xls)

        if df_exp is not None:
            st.caption(f"Filas: {len(df_exp)} | Columnas: {len(df_exp.columns)}")

            search_exp = st.text_input("Filtrar filas (buscar texto en cualquier columna)", key="exp_search")
            if search_exp:
                mask = df_exp.apply(
                    lambda col: col.astype(str).str.contains(search_exp, case=False, na=False)
                ).any(axis=1)
                df_exp = df_exp[mask]

            st.dataframe(df_exp, use_container_width=True, height=500)

            csv_exp = df_exp.to_csv(index=False).encode("utf-8")
            st.download_button(
                f"⬇️ Descargar '{sheet_sel}' como CSV",
                csv_exp,
                file_name=f"{sheet_sel.replace(' ', '_')}.csv",
                mime="text/csv",
            )
        else:
            st.error("No se pudo cargar la pestaña seleccionada.")

# ──────────────────────────────────────────────
# FOOTER
# ──────────────────────────────────────────────
st.divider()
st.caption("PuntoRojo v2.0 · Gestión de Pérdidas Eléctricas · Distrito Nacional · EDEESTE")
