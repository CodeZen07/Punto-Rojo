"""
Gestión de Pérdidas Eléctricas | Distrito Nacional
Balance CT | Balance Central | Relación | BDG
"""

import random
import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium

# ─────────────────────────────────────────────────────────
# CONFIGURACIÓN
# ─────────────────────────────────────────────────────────
st.set_page_config(
    page_title="PuntoRojo – Pérdidas Eléctricas",
    page_icon="🔴",
    layout="wide",
)


# ─────────────────────────────────────────────────────────
# FUNCIONES DE CARGA
# ─────────────────────────────────────────────────────────

def leer_balance_ct(xls):
    """
    Detecta la fila con 'ITEM' en Balance CT y lee la tabla de clientes.
    Retorna (metadata_dict, dataframe_clientes).
    """
    raw = pd.read_excel(xls, sheet_name="Balance CT", header=None, dtype=str)
    meta = {}
    header_row = None

    for i, row in raw.iterrows():
        vals = row.fillna("").astype(str).tolist()

        # Extraer metadata de filas decorativas
        for j, v in enumerate(vals):
            v_up = v.strip().upper()
            if ("TOTALIZADOR:" in v_up or "TALIZADOR:" in v_up) and "TOTALIZADOR" not in meta:
                meta["TOTALIZADOR"] = vals[j + 2] if j + 2 < len(vals) else vals[j + 1] if j + 1 < len(vals) else ""
            if "SECTOR:" in v_up and "SECTOR" not in meta:
                meta["SECTOR"] = vals[j + 2] if j + 2 < len(vals) else ""
            if v_up == "CIRCUITO" and "CIRCUITO" not in meta:
                meta["CIRCUITO"] = vals[j + 1] if j + 1 < len(vals) else ""
            if "DIRECCI" in v_up and ":" in v and "DIRECCION" not in meta:
                meta["DIRECCION"] = vals[j + 2] if j + 2 < len(vals) else ""

        # Detectar fila de encabezado real
        if "ITEM" in [v.strip().upper() for v in vals]:
            header_row = i
            break

    if header_row is None:
        return meta, None

    df = pd.read_excel(xls, sheet_name="Balance CT", header=header_row)

    # Renombrar columnas a nombres estándar
    rename = {}
    for col in df.columns:
        c = str(col).strip().upper()
        if c == "ITEM":                        rename[col] = "ITEM"
        elif c == "NOMBRE":                    rename[col] = "NOMBRE"
        elif c == "NIC":                       rename[col] = "NIC"
        elif c == "NIS":                       rename[col] = "NIS"
        elif c == "MEDIDOR":                   rename[col] = "MEDIDOR"
        elif c == "MODULO":                    rename[col] = "MODULO"
        elif c == "LECTURA 1":                 rename[col] = "LECTURA_1"
        elif "LECTURA" in c and "2" in c:      rename[col] = "LECTURA_2"
        elif c in ("DIF.", "DIF"):             rename[col] = "DIFERENCIA"
        elif "CLIENTES" in c:                  rename[col] = "CLIENTES_BC"
        elif "PROM" in c and "CONS" in c:      rename[col] = "PROM_CONSUMO"
        elif "ULT" in c and "CF" in c:         rename[col] = "ULT_CF"
    df = df.rename(columns=rename)

    # Solo filas con ITEM numérico
    df = df[pd.to_numeric(df.get("ITEM", pd.Series(dtype=str)), errors="coerce").notna()]
    df = df.reset_index(drop=True)
    return meta, df


def leer_balance_central(xls):
    """
    Hoja 'Balance Central' — columnas reales del archivo:
    NIS, Totalizador, Medidor, Clientes, Compra, Facturación,
    Pérdida, %Pérdida, Estado actual, Circuito, Sector, Dirección
    """
    if "Balance Central" not in xls.sheet_names:
        return None
    df = pd.read_excel(xls, sheet_name="Balance Central")
    df.columns = [str(c).strip() for c in df.columns]

    rename = {}
    for col in df.columns:
        c = col.strip().upper().replace(" ", "_")
        if c == "NIS":                         rename[col] = "NIS"
        elif c == "TOTALIZADOR":               rename[col] = "TOTALIZADOR"
        elif c == "MEDIDOR":                   rename[col] = "MEDIDOR"
        elif c == "CLIENTES":                  rename[col] = "CLIENTES"
        elif c == "COMPRA":                    rename[col] = "COMPRA_KWH"
        elif "FACTUR" in c:                    rename[col] = "FACTURACION_KWH"
        elif c in ("PÉRDIDA", "PERDIDA"):      rename[col] = "PERDIDA_KWH"
        elif "%PÉRDIDA" in c or "%PERDIDA" in c: rename[col] = "PCT_PERDIDA"
        elif "ESTADO_ACTUAL" in c:             rename[col] = "ESTADO"
        elif c == "CIRCUITO":                  rename[col] = "CIRCUITO"
        elif c == "SECTOR":                    rename[col] = "SECTOR"
        elif "DIRECCI" in c:                   rename[col] = "DIRECCION"
        elif c in ("TECNOLOGÍA", "TECNOLOGIA"): rename[col] = "TECNOLOGIA"
        elif c == "KVA":                       rename[col] = "KVA"
    df = df.rename(columns=rename)
    df = df.dropna(how="all").reset_index(drop=True)
    return df


def leer_relacion(xls):
    """
    Hoja 'Relación' — columnas reales:
    Medidor, Tipo, Totalizador, NIS, NIC, Consumo,
    Compra, Facturación, Pérdidas, % Pérdidas, Circuito
    """
    if "Relación" not in xls.sheet_names:
        return None
    df = pd.read_excel(xls, sheet_name="Relación")
    df.columns = [str(c).strip() for c in df.columns]

    rename = {}
    for col in df.columns:
        c = col.strip().upper().replace(" ", "_").replace(".", "")
        if c == "MEDIDOR":                     rename[col] = "MEDIDOR"
        elif c == "TIPO":                      rename[col] = "TIPO"
        elif c == "TOTALIZADOR":               rename[col] = "TOTALIZADOR"
        elif c == "NIS":                       rename[col] = "NIS"
        elif c == "NIC":                       rename[col] = "NIC"
        elif c == "CONSUMO":                   rename[col] = "CONSUMO_KWH"
        elif c == "COMPRA":                    rename[col] = "COMPRA_KWH"
        elif "FACTUR" in c:                    rename[col] = "FACTURACION_KWH"
        elif c in ("PÉRDIDAS", "PERDIDAS"):    rename[col] = "PERDIDAS_KWH"
        elif "%" in c and "PERD" in c:         rename[col] = "PCT_PERDIDAS"
        elif c == "CIRCUITO":                  rename[col] = "CIRCUITO"
        elif "LUMINARIA" in c:                 rename[col] = "LUMINARIAS"
    df = df.rename(columns=rename)
    df = df.dropna(how="all").reset_index(drop=True)
    return df


def leer_bdg(xls):
    """Hoja BDG — sin coordenadas GPS en este archivo."""
    bdg_sheet = next((s for s in xls.sheet_names if "bdg" in s.lower()), None)
    if not bdg_sheet:
        return None
    df = pd.read_excel(xls, sheet_name=bdg_sheet)
    df.columns = [str(c).strip() for c in df.columns]
    df = df.dropna(how="all").reset_index(drop=True)
    return df


# ─────────────────────────────────────────────────────────
# SEMÁFORO
# ─────────────────────────────────────────────────────────

def semaforo_color(pct):
    pct = abs(pct)
    if pct > 30:    return "red"
    elif pct >= 15: return "orange"
    else:           return "green"

def semaforo_emoji(pct):
    pct = abs(pct)
    if pct > 30:    return "🔴 Alta (>30%)"
    elif pct >= 15: return "🟠 Media (15-30%)"
    else:           return "🟢 Baja (<15%)"


# ─────────────────────────────────────────────────────────
# UI — CABECERA Y CARGA
# ─────────────────────────────────────────────────────────

st.title("🔴 PuntoRojo — Pérdidas Eléctricas | Distrito Nacional")

uploaded = st.file_uploader(
    "📂 Sube el archivo Excel (Balance de Totalizadores)",
    type=["xlsx"],
)

if not uploaded:
    st.info("Sube el archivo Excel para comenzar.")
    st.stop()

xls = pd.ExcelFile(uploaded)

with st.spinner("Procesando hojas del archivo..."):
    meta_ct, df_ct = leer_balance_ct(xls)
    df_bc          = leer_balance_central(xls)
    df_rel         = leer_relacion(xls)
    df_bdg         = leer_bdg(xls)

# Resumen de carga
partes = []
if df_ct  is not None: partes.append(f"✅ Balance CT ({len(df_ct)} clientes)")
if df_bc  is not None: partes.append(f"✅ Balance Central ({len(df_bc)} totalizadores)")
if df_rel is not None: partes.append(f"✅ Relación ({len(df_rel)} registros)")
if df_bdg is not None: partes.append(f"✅ BDG ({len(df_bdg):,} suministros)")
st.success("  |  ".join(partes))


# ─────────────────────────────────────────────────────────
# TABS
# ─────────────────────────────────────────────────────────

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📋 Balance CT",
    "📊 Top 10 Pérdidas",
    "🗺️ Mapa",
    "🔗 Relación Padre-Hijo",
    "🔍 BDG / Explorador",
])


# ══════════════════════════════════════════════
# TAB 1 — BALANCE CT
# ══════════════════════════════════════════════
with tab1:
    st.subheader("📋 Balance CT — Detalle del Totalizador")

    if df_ct is None:
        st.error("No se pudo leer la hoja 'Balance CT'.")
    else:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Totalizador", meta_ct.get("TOTALIZADOR", "N/D"))
        c2.metric("Sector",      meta_ct.get("SECTOR",      "N/D"))
        c3.metric("Circuito",    meta_ct.get("CIRCUITO",    "N/D"))
        c4.metric("Total Clientes", len(df_ct))
        st.divider()

        buscar = st.text_input("🔍 Buscar cliente por nombre o NIC")
        df_show = df_ct.copy()
        if buscar:
            mask = df_show.apply(
                lambda col: col.astype(str).str.contains(buscar, case=False, na=False)
            ).any(axis=1)
            df_show = df_show[mask]

        cols_ct = [c for c in ["ITEM","NOMBRE","NIC","NIS","MEDIDOR",
                                "LECTURA_1","LECTURA_2","DIFERENCIA","CLIENTES_BC"]
                   if c in df_show.columns]
        st.dataframe(df_show[cols_ct], use_container_width=True, height=450)

        if "DIFERENCIA" in df_ct.columns:
            total = pd.to_numeric(df_ct["DIFERENCIA"], errors="coerce").sum()
            st.metric("Suma total de diferencias (kWh)", f"{total:,.3f}")

        csv = df_show.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Descargar como CSV", csv,
                           file_name="balance_ct.csv", mime="text/csv")


# ══════════════════════════════════════════════
# TAB 2 — TOP 10 PÉRDIDAS
# ══════════════════════════════════════════════
with tab2:
    st.subheader("📊 Top 10 — Totalizadores con Mayor % de Pérdida")

    if df_bc is None:
        st.error("No se encontró la hoja 'Balance Central'.")
    elif "PCT_PERDIDA" not in df_bc.columns:
        st.error(f"Columna '%%Pérdida' no encontrada. Columnas disponibles: {list(df_bc.columns)}")
    else:
        df_work = df_bc.copy()
        df_work["PCT_PERDIDA"] = pd.to_numeric(df_work["PCT_PERDIDA"], errors="coerce")
        df_work["PCT_ABS"]     = df_work["PCT_PERDIDA"].abs()

        # Filtro sector
        if "SECTOR" in df_work.columns:
            sectores   = ["Todos"] + sorted(df_work["SECTOR"].dropna().unique().tolist())
            sector_sel = st.selectbox("Filtrar por Sector", sectores)
            if sector_sel != "Todos":
                df_work = df_work[df_work["SECTOR"] == sector_sel]

        top10 = (df_work
                 .dropna(subset=["PCT_PERDIDA"])
                 .sort_values("PCT_ABS", ascending=False)
                 .head(10)
                 .reset_index(drop=True))
        top10["Semáforo"] = top10["PCT_PERDIDA"].apply(semaforo_emoji)

        cols_top = [c for c in ["TOTALIZADOR","SECTOR","CIRCUITO","CLIENTES",
                                 "COMPRA_KWH","FACTURACION_KWH","PERDIDA_KWH",
                                 "PCT_PERDIDA","ESTADO","Semáforo"]
                    if c in top10.columns]
        st.dataframe(top10[cols_top], use_container_width=True, height=420)

        if "TOTALIZADOR" in top10.columns:
            chart = top10[["TOTALIZADOR","PCT_ABS"]].set_index("TOTALIZADOR")
            chart.columns = ["% Pérdida (abs)"]
            st.bar_chart(chart)

        st.divider()
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Total Totalizadores",    len(df_bc))
        k2.metric("Pérdida Promedio",       f"{df_work['PCT_PERDIDA'].mean():.2f}%")
        k3.metric("Peor Pérdida",           f"{df_work['PCT_ABS'].max():.2f}%")
        k4.metric("Totalizadores >30%",     int((df_work["PCT_ABS"] > 30).sum()))


# ══════════════════════════════════════════════
# TAB 3 — MAPA SEMÁFORO
# ══════════════════════════════════════════════
with tab3:
    st.subheader("🗺️ Mapa de Semáforo — Distrito Nacional")
    st.caption("🔴 >30%  |  🟠 15-30%  |  🟢 <15%  — Posición por circuito (el BDG no contiene coordenadas GPS)")

    # Coordenadas aproximadas por circuito del DN
    CIRCUITO_COORDS = {
        "TIM203":(18.4750,-69.9120), "TIM204":(18.4760,-69.9110),
        "TIM205":(18.4770,-69.9130), "TIM201":(18.4720,-69.9200),
        "TIM202":(18.4730,-69.9190), "CNP804":(18.4800,-69.9350),
        "CNP803":(18.4810,-69.9340), "CNP802":(18.4820,-69.9360),
        "CNP806":(18.4830,-69.9370), "CNP809":(18.4840,-69.9380),
        "DESP01":(18.4700,-69.9050), "DESP02":(18.4710,-69.9040),
        "DESP03":(18.4690,-69.9060), "DESP06":(18.4680,-69.9070),
        "DESP08":(18.4670,-69.9080), "DESP09":(18.4660,-69.9090),
        "CAPO04":(18.4900,-69.9150), "CAPO06":(18.4910,-69.9140),
        "RCL076":(18.4650,-69.9400), "RCL080":(18.4640,-69.9410),
        "VIME05":(18.5100,-69.9500), "VIME06":(18.5110,-69.9490),
        "INVI03":(18.5200,-69.9600), "LM3805":(18.5300,-69.9700),
        "LM3807":(18.5310,-69.9710), "LM3808":(18.5320,-69.9720),
        "LM3802":(18.5330,-69.9730), "EBRI02":(18.4600,-69.9800),
        "EBRI03":(18.4610,-69.9810), "EBRI12":(18.4620,-69.9820),
    }

    if df_bc is None:
        st.warning("Se necesita la hoja 'Balance Central' para el mapa.")
    else:
        df_map = df_bc.copy()
        df_map["PCT_PERDIDA"] = pd.to_numeric(df_map.get("PCT_PERDIDA"), errors="coerce").fillna(0)
        df_map["PCT_ABS"]     = df_map["PCT_PERDIDA"].abs()

        m = folium.Map(location=[18.48, -69.93], zoom_start=13, tiles="CartoDB positron")

        legend = """<div style="position:fixed;bottom:30px;left:30px;z-index:9999;
            background:white;padding:12px;border-radius:8px;border:1px solid #ccc;font-size:13px;">
            🔴 &gt;30% pérdida<br>🟠 15–30%<br>🟢 &lt;15%</div>"""
        m.get_root().html.add_child(folium.Element(legend))

        plotted, sin_coord = 0, 0
        for _, row in df_map.iterrows():
            circ   = str(row.get("CIRCUITO", "")).strip().upper()
            coords = CIRCUITO_COORDS.get(circ)
            if not coords:
                sin_coord += 1
                continue

            pct  = row["PCT_ABS"]
            lat  = coords[0] + random.uniform(-0.0015, 0.0015)
            lon  = coords[1] + random.uniform(-0.0015, 0.0015)

            popup = f"""
            <b>Totalizador:</b> {row.get('TOTALIZADOR','N/D')}<br>
            <b>Circuito:</b> {circ}<br>
            <b>Sector:</b> {row.get('SECTOR','')}<br>
            <b>Compra:</b> {row.get('COMPRA_KWH','')} kWh<br>
            <b>Facturación:</b> {row.get('FACTURACION_KWH','')} kWh<br>
            <b>% Pérdida:</b> {row['PCT_PERDIDA']:.2f}%
            """
            folium.CircleMarker(
                location=[lat, lon], radius=9,
                color=semaforo_color(pct), fill=True,
                fill_color=semaforo_color(pct), fill_opacity=0.85,
                popup=folium.Popup(popup, max_width=300),
                tooltip=f"{row.get('TOTALIZADOR','?')} | {row['PCT_PERDIDA']:.1f}%",
            ).add_to(m)
            plotted += 1

        i1, i2 = st.columns(2)
        i1.info(f"**{plotted}** totalizadores graficados")
        if sin_coord:
            i2.warning(f"**{sin_coord}** sin coordenadas de circuito")

        st_folium(m, width="100%", height=580)
        st.caption("💡 Para geolocalización exacta agrega columnas LATITUD y LONGITUD al archivo BDG.")


# ══════════════════════════════════════════════
# TAB 4 — RELACIÓN PADRE-HIJO
# ══════════════════════════════════════════════
with tab4:
    st.subheader("🔗 Relación Padre (Totalizador) → Hijos (Suministros / NICs)")

    if df_rel is None:
        st.error("No se encontró la hoja 'Relación'.")
    elif "TOTALIZADOR" not in df_rel.columns:
        st.error(f"No se encontró columna 'Totalizador'. Disponibles: {list(df_rel.columns)}")
    else:
        buscar_tot = st.text_input("🔍 Buscar Totalizador", placeholder="Código o nombre...")
        tots = sorted(df_rel["TOTALIZADOR"].dropna().astype(str).unique().tolist())
        tots_f = [t for t in tots if buscar_tot.upper() in t.upper()] if buscar_tot else tots

        if not tots_f:
            st.warning("Sin coincidencias.")
        else:
            tot_sel = st.selectbox(f"Selecciona Totalizador ({len(tots_f)} encontrados)", tots_f)
            registros = df_rel[df_rel["TOTALIZADOR"].astype(str) == str(tot_sel)]

            if "TIPO" in registros.columns:
                padre = registros[registros["TIPO"].str.strip().str.upper() == "TOTALIZADOR"]
                hijos = registros[registros["TIPO"].str.strip().str.upper() == "CLIENTE"]
            else:
                padre, hijos = pd.DataFrame(), registros

            st.markdown(f"### Totalizador: `{tot_sel}`")
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Suministros", len(hijos))

            if not padre.empty:
                def get_num(df, col):
                    return pd.to_numeric(df[col].iloc[0], errors="coerce") if col in df.columns else None
                cp = get_num(padre, "COMPRA_KWH")
                fp = get_num(padre, "FACTURACION_KWH")
                pp = get_num(padre, "PERDIDAS_KWH")
                if cp is not None: k2.metric("Compra (kWh)",       f"{cp:,.2f}")
                if fp is not None: k3.metric("Facturación (kWh)",  f"{fp:,.2f}")
                if pp is not None: k4.metric("Pérdida (kWh)",      f"{pp:,.2f}")

            cols_h = [c for c in ["NIC","NIS","MEDIDOR","CONSUMO_KWH",
                                   "LUMINARIAS","CIRCUITO"] if c in hijos.columns]
            st.dataframe(hijos[cols_h].reset_index(drop=True),
                         use_container_width=True, height=400)

            csv_h = hijos.to_csv(index=False).encode("utf-8")
            st.download_button("⬇️ Descargar como CSV", csv_h,
                               file_name=f"suministros_{tot_sel}.csv", mime="text/csv")


# ══════════════════════════════════════════════
# TAB 5 — BDG / EXPLORADOR
# ══════════════════════════════════════════════
with tab5:
    st.subheader("🔍 BDG — Base de Datos General / Explorador de Pestañas")

    sheet_sel = st.selectbox("Selecciona pestaña", xls.sheet_names)
    try:
        if sheet_sel == "Balance CT":
            df_exp = df_ct
        elif sheet_sel == "Balance Central":
            df_exp = df_bc
        elif sheet_sel == "Relación":
            df_exp = df_rel
        else:
            df_exp = pd.read_excel(xls, sheet_name=sheet_sel)
    except Exception as e:
        st.error(f"Error al leer: {e}")
        df_exp = None

    if df_exp is not None:
        st.caption(f"Filas: {len(df_exp):,}  |  Columnas: {len(df_exp.columns)}")
        filtro = st.text_input("🔍 Filtrar por texto", key="filtro_exp")
        if filtro:
            mask = df_exp.apply(
                lambda col: col.astype(str).str.contains(filtro, case=False, na=False)
            ).any(axis=1)
            df_exp = df_exp[mask]
            st.info(f"{len(df_exp):,} filas coinciden")

        st.dataframe(df_exp, use_container_width=True, height=520)
        st.download_button(
            f"⬇️ Descargar '{sheet_sel}' como CSV",
            df_exp.to_csv(index=False).encode("utf-8"),
            file_name=f"{sheet_sel.replace(' ','_')}.csv",
            mime="text/csv",
        )

# ─────────────────────────────────────────────────────────
st.divider()
st.caption("🔴 PuntoRojo v3.0  ·  Pérdidas Eléctricas  ·  Distrito Nacional")
