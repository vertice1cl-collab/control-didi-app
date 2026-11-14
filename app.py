import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date
from supabase import create_client

st.set_page_config(page_title="Control DiDi", layout="wide")

SUPABASE_URL = "https://vsjpavghptbsdwzomieq.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZzanBhdmdocHRic2R3em9taWVxIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTQ2NzYyMDQsImV4cCI6MjExMDI1MjIwNH0.jp78w535sVdmkOXGOsXiArNdRNb1x34bxym3byuvIc4"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

CATEGORIAS = ["Bencina", "Lavado", "Mano de Obra", "Repuesto",
              "Peaje", "Comida", "Estacionamiento", "Otro"]

def fmt(n):
    try:
        return f"${float(n):,.0f}".replace(",", ".")
    except Exception:
        return f"${n}"

def cargar_periodos():
    try:
        res = supabase.table("periodos").select("*").order("fecha_inicio", desc=True).execute()
        if not res.data:
            return pd.DataFrame(columns=["id", "fecha_inicio", "fecha_fin", "ganancia", "km", "gastos", "ganancia_neta"])
        df = pd.DataFrame(res.data)
        res_g = supabase.table("gastos").select("periodo_id, monto").execute()
        if res_g.data:
            df_g = pd.DataFrame(res_g.data)
            sumas = df_g.groupby("periodo_id")["monto"].sum().reset_index()
            sumas.columns = ["id", "gastos"]
            df = df.merge(sumas, on="id", how="left")
            df["gastos"] = df["gastos"].fillna(0)
        else:
            df["gastos"] = 0.0
        df["ganancia_neta"] = df["ganancia"] - df["gastos"]
        return df
    except Exception as e:
        st.error(f"Error cargando periodos: {e}")
        return pd.DataFrame()

def cargar_gastos():
    try:
        res = supabase.table("gastos").select("*").order("id", desc=True).execute()
        if not res.data:
            return pd.DataFrame(columns=["id", "periodo_id", "tipo", "monto"])
        return pd.DataFrame(res.data)
    except Exception as e:
        st.error(f"Error cargando gastos: {e}")
        return pd.DataFrame()

# Test de conexión
try:
    supabase.table("periodos").select("id").limit(1).execute()
    st.sidebar.success("✅ Conectado a Supabase")
except Exception as e:
    st.sidebar.error(f"❌ Sin conexión: {e}")

st.sidebar.title("🚗 Control DiDi")
opcion = st.sidebar.radio("Menú", [
    "➕ Nuevo Periodo", "💸 Nuevo Gasto", "📋 Historial",
    "📅 Resumen Semanal", "📆 Resumen Mensual", "💰 Balance General",
    "⚙️ Editar / Borrar",
])

# ============ NUEVO PERIODO ============
if opcion == "➕ Nuevo Periodo":
    st.header("Registrar nuevo periodo")
    with st.form("f_periodo"):
        c1, c2 = st.columns(2)
        with c1:
            fi = st.date_input("Fecha inicio", value=date.today())
            ganancia = st.number_input("Ganancia neta del periodo ($)", min_value=0.0, step=100.0)
        with c2:
            ff = st.date_input("Fecha fin", value=date.today())
            km = st.number_input("Kilómetros recorridos", min_value=0.0, step=1.0)
        guardar = st.form_submit_button("💾 Guardar Periodo")
        if guardar:
            try:
                supabase.table("periodos").insert({
                    "fecha_inicio": fi.isoformat(),
                    "fecha_fin": ff.isoformat(),
                    "ganancia": float(ganancia),
                    "km": float(km),
                }).execute()
                st.success(f"✅ Periodo guardado. Ganancia: {fmt(ganancia)}")
                st.rerun()
            except Exception as e:
                st.error(f"Error al guardar: {e}")

# ============ NUEVO GASTO ============
elif opcion == "💸 Nuevo Gasto":
    st.header("Registrar gasto")
    df = cargar_periodos()
    if df.empty:
        st.warning("Primero registra un periodo.")
    else:
        opciones = {f"#{r.id} — {r.fecha_inicio} → {r.fecha_fin} — Ganancia: {fmt(r.ganancia)}": int(r.id) for r in df.itertuples()}
        with st.form("f_gasto"):
            per = st.selectbox("Periodo", list(opciones.keys()))
            tipo = st.selectbox("Tipo de gasto", CATEGORIAS)
            monto = st.number_input("Monto ($)", min_value=0.0, step=100.0)
            guardar = st.form_submit_button("💾 Guardar Gasto")
            if guardar:
                try:
                    supabase.table("gastos").insert({
                        "periodo_id": opciones[per],
                        "tipo": tipo,
                        "monto": float(monto),
                    }).execute()
                    st.success(f"✅ {tipo} de {fmt(monto)} registrado")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

# ============ HISTORIAL ============
elif opcion == "📋 Historial":
    st.header("Historial de periodos")
    df = cargar_periodos()
    if df.empty:
        st.info("Sin datos aún.")
    else:
        for r in df.itertuples():
            color = "🟢" if r.ganancia_neta >= 0 else "🔴"
            with st.expander(f"{color} #{r.id} — {r.fecha_inicio} al {r.fecha_fin} — Ganancia real: {fmt(r.ganancia_neta)}"):
                c1, c2 = st.columns(2)
                c1.write(f"**Ganancia del periodo:** {fmt(r.ganancia)}")
                c1.write(f"**Gastos:** {fmt(r.gastos)}")
                c1.write(f"**KM:** {r.km:,.0f}")
                c2.write(f"**Ganancia real (neta):** {fmt(r.ganancia_neta)}")
                try:
                    res = supabase.table("gastos").select("tipo, monto").eq("periodo_id", int(r.id)).execute()
                    if res.data:
                        st.write("**Desglose de gastos:**")
                        st.table(pd.DataFrame(res.data))
                except Exception:
                    pass

# ============ RESUMEN SEMANAL ============
elif opcion == "📅 Resumen Semanal":
    st.header("Resumen semanal")
    df = cargar_periodos()
    if df.empty:
        st.info("Sin datos.")
    else:
        df["fecha"] = pd.to_datetime(df["fecha_inicio"])
        df["semana"] = df["fecha"].dt.strftime("%Y-S%V")
        resumen = df.groupby("semana").agg(
            Periodos=("id", "count"),
            Ganancia=("ganancia", "sum"),
            Gastos=("gastos", "sum"),
            Ganancia_Neta=("ganancia_neta", "sum"),
            KM=("km", "sum"),
        ).reset_index()
        st.dataframe(resumen)
        fig = px.bar(resumen, x="semana", y="Ganancia_Neta", title="Ganancia neta por semana")
        st.plotly_chart(fig)

# ============ RESUMEN MENSUAL ============
elif opcion == "📆 Resumen Mensual":
    st.header("Resumen mensual")
    df = cargar_periodos()
    if df.empty:
        st.info("Sin datos.")
    else:
        df["fecha"] = pd.to_datetime(df["fecha_inicio"])
        df["mes"] = df["fecha"].dt.strftime("%Y-%m")
        resumen = df.groupby("mes").agg(
            Periodos=("id", "count"),
            Ganancia=("ganancia", "sum"),
            Gastos=("gastos", "sum"),
            Ganancia_Neta=("ganancia_neta", "sum"),
            KM=("km", "sum"),
        ).reset_index()
        st.dataframe(resumen)
        fig = px.bar(resumen, x="mes", y="Ganancia_Neta", title="Ganancia neta por mes")
        st.plotly_chart(fig)

# ============ BALANCE GENERAL ============
elif opcion == "💰 Balance General":
    st.header("Balance general")
    df = cargar_periodos()
    if df.empty:
        st.info("Sin datos.")
    else:
        df["fecha"] = pd.to_datetime(df["fecha_inicio"])
        c1, c2 = st.columns(2)
        with c1:
            fi = st.date_input("Desde", value=df["fecha"].min().date())
        with c2:
            ff = st.date_input("Hasta", value=df["fecha"].max().date())
        df_f = df[(df["fecha"] >= pd.Timestamp(fi)) & (df["fecha"] <= pd.Timestamp(ff))]

        if df_f.empty:
            st.warning("Sin datos en ese rango.")
        else:
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Periodos", len(df_f))
            m2.metric("Ganancia registrada", fmt(df_f["ganancia"].sum()))
            m3.metric("Gastos totales", fmt(df_f["gastos"].sum()))
            m4.metric("Ganancia neta real", fmt(df_f["ganancia_neta"].sum()))

            st.divider()
            st.subheader("Distribución de gastos por tipo")
            try:
                res = supabase.table("gastos").select("*").execute()
                if res.data:
                    gdf = pd.DataFrame(res.data)
                    g_f = gdf[gdf["periodo_id"].isin(df_f["id"])]
                    if not g_f.empty:
                        por_tipo = g_f.groupby("tipo")["monto"].sum().reset_index()
                        fig = px.pie(por_tipo, values="monto", names="tipo",
                                     title="¿En qué se va la plata?", hole=0.4)
                        st.plotly_chart(fig)
                    else:
                        st.info("Sin gastos en este rango.")
            except Exception as e:
                st.error(f"Error: {e}")

# ============ EDITAR / BORRAR ============
elif opcion == "⚙️ Editar / Borrar":
    st.header("⚙️ Administrar periodos y gastos")
    df = cargar_periodos()
    if df.empty:
        st.info("Sin datos aún.")
    else:
        st.subheader("📅 Periodos")
        for r in df.itertuples():
            with st.expander(f"#{r.id} — {r.fecha_inicio} al {r.fecha_fin} — Ganancia: {fmt(r.ganancia)} | Gastos: {fmt(r.gastos)}"):
                with st.form(f"edit_p_{r.id}"):
                    st.write("**Editar periodo**")
                    c1, c2 = st.columns(2)
                    with c1:
                        fi_e = st.date_input("Fecha inicio", value=pd.to_datetime(r.fecha_inicio).date(), key=f"fi_e_{r.id}")
                        gan_e = st.number_input("Ganancia del periodo ($)", value=float(r.ganancia), min_value=0.0, step=100.0, key=f"gan_e_{r.id}")
                    with c2:
                        ff_e = st.date_input("Fecha fin", value=pd.to_datetime(r.fecha_fin).date(), key=f"ff_e_{r.id}")
                        km_e = st.number_input("KM", value=float(r.km), min_value=0.0, step=1.0, key=f"km_e_{r.id}")
                    if st.form_submit_button("💾 Guardar cambios"):
                        try:
                            supabase.table("periodos").update({
                                "fecha_inicio": fi_e.isoformat(),
                                "fecha_fin": ff_e.isoformat(),
                                "ganancia": float(gan_e),
                                "km": float(km_e),
                            }).eq("id", int(r.id)).execute()
                            st.toast("✅ Periodo actualizado")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")

                key_conf = f"conf_del_p_{r.id}"
                if key_conf not in st.session_state:
                    st.session_state[key_conf] = False
                if not st.session_state[key_conf]:
                    if st.button(f"🗑️ Borrar periodo #{r.id}", key=f"del_p_{r.id}"):
                        st.session_state[key_conf] = True



                      
                        st.rerun()
                else:
                    st.warning("¿Seguro? Se borrarán también los gastos asociados.")
                    cc1, cc2 = st.columns(2)
                    if cc1.button("Sí, borrar", key=f"del_p_y_{r.id}"):
                        try:
                            supabase.table("periodos").delete().eq("id", int(r.id)).execute()
                            st.session_state[key_conf] = False
                            st.toast("✅ Periodo borrado")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")
                    if cc2.button("Cancelar", key=f"del_p_n_{r.id}"):
                        st.session_state[key_conf] = False
                        st.rerun()

        st.divider()
        st.subheader("💸 Gastos")
        gdf = cargar_gastos()
        if gdf.empty:
            st.info("No hay gastos registrados.")
        else:
            for gr in gdf.itertuples():
                with st.expander(f"#{gr.id} — {gr.tipo}: {fmt(gr.monto)} (periodo #{gr.periodo_id})"):
                    with st.form(f"edit_g_{gr.id}"):
                        idx = CATEGORIAS.index(gr.tipo) if gr.tipo in CATEGORIAS else 0
                        tipo_e = st.selectbox("Tipo", CATEGORIAS, index=idx, key=f"t_e_{gr.id}")
                        monto_e = st.number_input("Monto ($)", value=float(gr.monto), min_value=0.0, step=100.0, key=f"m_e_{gr.id}")
                        if st.form_submit_button("💾 Guardar cambios"):
                            try:
                                supabase.table("gastos").update({
                                    "tipo": tipo_e,
                                    "monto": float(monto_e),
                                }).eq("id", int(gr.id)).execute()
                                st.toast("✅ Gasto actualizado")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error: {e}")

                    key_conf = f"conf_del_g_{gr.id}"
                    if key_conf not in st.session_state:
                        st.session_state[key_conf] = False
                    if not st.session_state[key_conf]:
                        if st.button(f"🗑️ Borrar gasto #{gr.id}", key=f"del_g_{gr.id}"):
                            st.session_state[key_conf] = True
                            st.rerun()
                    else:
                        st.warning("¿Seguro que quieres borrar este gasto?")
                        cc1, cc2 = st.columns(2)
                        if cc1.button("Sí, borrar", key=f"del_g_y_{gr.id}"):
                            try:
                                supabase.table("gastos").delete().eq("id", int(gr.id)).execute()
                                st.session_state[key_conf] = False
                                st.toast("✅ Gasto borrado")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error: {e}")
                        if cc2.button("Cancelar", key=f"del_g_n_{gr.id}"):
                            st.session_state[key_conf] = False
                            st.rerun()
