import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
from datetime import date

st.set_page_config(page_title="Control DiDi", layout="wide")

DB = "control_diario.db"
CATEGORIAS = ["Bencina", "Lavado", "Mano de Obra", "Repuesto",
              "Peaje", "Comida", "Estacionamiento", "Otro"]

def conn():
    return sqlite3.connect(DB, check_same_thread=False)

def init_db():
    c = conn()
    try:
        cols = [r[1] for r in c.execute("PRAGMA table_info(periodos)").fetchall()]
        if cols and "comision" in cols:
            c.execute("DROP TABLE periodos")
            c.execute("DROP TABLE gastos")
    except Exception:
        pass
    c.execute("""CREATE TABLE IF NOT EXISTS periodos(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha_inicio TEXT NOT NULL, fecha_fin TEXT NOT NULL,
        ganancia REAL NOT NULL, km REAL NOT NULL)""")
    c.execute("""CREATE TABLE IF NOT EXISTS gastos(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        periodo_id INTEGER NOT NULL, tipo TEXT NOT NULL, monto REAL NOT NULL)""")
    c.commit()
    c.close()

init_db()

def fmt(n):
    return f"${n:,.0f}".replace(",", ".")

def cargar_periodos():
    c = conn()
    df = pd.read_sql_query("""SELECT p.*, COALESCE(SUM(g.monto),0) AS gastos
        FROM periodos p LEFT JOIN gastos g ON g.periodo_id = p.id
        GROUP BY p.id ORDER BY p.fecha_inicio DESC""", c)
    c.close()
    if not df.empty:
        df["ganancia_neta"] = df["ganancia"] - df["gastos"]
    return df

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
            c = conn()
            c.execute("INSERT INTO periodos VALUES(NULL,?,?,?,?)",
                      (fi.isoformat(), ff.isoformat(), ganancia, km))
            c.commit(); c.close()
            st.success(f"✅ Periodo guardado. Ganancia registrada: {fmt(ganancia)}")
            st.rerun()

# ============ NUEVO GASTO ============
elif opcion == "💸 Nuevo Gasto":
    st.header("Registrar gasto")
    df = cargar_periodos()
    if df.empty:
        st.warning("Primero registra un periodo.")
    else:
        opciones = {f"#{r.id} — {r.fecha_inicio} → {r.fecha_fin} — Ganancia: {fmt(r.ganancia)}": r.id for r in df.itertuples()}
        with st.form("f_gasto"):
            per = st.selectbox("Periodo", list(opciones.keys()))
            tipo = st.selectbox("Tipo de gasto", CATEGORIAS)
            monto = st.number_input("Monto ($)", min_value=0.0, step=100.0)
            guardar = st.form_submit_button("💾 Guardar Gasto")
            if guardar:
                c = conn()
                c.execute("INSERT INTO gastos VALUES(NULL,?,?,?)",
                          (opciones[per], tipo, monto))
                c.commit(); c.close()
                st.success(f"✅ {tipo} de {fmt(monto)} registrado")
                st.rerun()

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
                g = conn().execute(
                    "SELECT tipo, monto FROM gastos WHERE periodo_id=?",
                    (r.id,)).fetchall()
                if g:
                    st.write("**Desglose de gastos:**")
                    st.table(pd.DataFrame(g, columns=["Tipo", "Monto ($)"]))

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
            gastos = pd.read_sql_query("SELECT * FROM gastos", conn())
            g_f = gastos[gastos["periodo_id"].isin(df_f["id"])]
            if not g_f.empty:
                por_tipo = g_f.groupby("tipo")["monto"].sum().reset_index()
                fig = px.pie(por_tipo, values="monto", names="tipo",
                             title="¿En qué se va la plata?", hole=0.4)
                st.plotly_chart(fig)
            else:
                st.info("Sin gastos en este rango.")

# ============ EDITAR / BORRAR ============
elif opcion == "⚙️ Editar / Borrar":
    st.header("⚙️ Administrar periodos y gastos")
    df = cargar_periodos()
    if df.empty:
        st.info("Sin datos aún.")
    else:
        # --- PERIODOS ---
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
                        c = conn()
                        c.execute("UPDATE periodos SET fecha_inicio=?, fecha_fin=?, ganancia=?, km=? WHERE id=?",
                                  (fi_e.isoformat(), ff_e.isoformat(), gan_e, km_e, r.id))
                        c.commit(); c.close()
                        st.toast("✅ Periodo actualizado")
                        st.rerun()

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
                    if cc1.button("Sí, borrar", key=f"del_p_y_{r.id}", type="primary"):
                        c = conn()
                        c.execute("DELETE FROM gastos WHERE periodo_id=?", (r.id,))
                        c.execute("DELETE FROM periodos WHERE id=?", (r.id,))
                        c.commit(); c.close()
                        st.session_state[key_conf] = False
                        st.toast("✅ Periodo borrado")
                        st.rerun()
                    if cc2.button("Cancelar", key=f"del_p_n_{r.id}"):
                        st.session_state[key_conf] = False
                        st.rerun()

        # --- GASTOS ---
        st.divider()
        st.subheader("💸 Gastos")
        todos = pd.read_sql_query("""SELECT g.id, g.periodo_id, g.tipo, g.monto,
            p.fecha_inicio, p.fecha_fin FROM gastos g JOIN periodos p ON g.periodo_id = p.id
            ORDER BY g.id DESC""", conn())
        if todos.empty:
            st.info("No hay gastos registrados.")
        else:
            for gr in todos.itertuples():
                with st.expander(f"#{gr.id} — {gr.tipo}: {fmt(gr.monto)} (periodo #{gr.periodo_id})"):
                    with st.form(f"edit_g_{gr.id}"):
                        idx = CATEGORIAS.index(gr.tipo) if gr.tipo in CATEGORIAS else 0
                        tipo_e = st.selectbox("Tipo", CATEGORIAS, index=idx, key=f"t_e_{gr.id}")
                        monto_e = st.number_input("Monto ($)", value=float(gr.monto), min_value=0.0, step=100.0, key=f"m_e_{gr.id}")
                        if st.form_submit_button("💾 Guardar cambios"):
                            c = conn()
                            c.execute("UPDATE gastos SET tipo=?, monto=? WHERE id=?", (tipo_e, monto_e, gr.id))
                            c.commit(); c.close()
                            st.toast("✅ Gasto actualizado")
                            st.rerun()
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
                        if cc1.button("Sí, borrar", key=f"del_g_y_{gr.id}", type="primary"):
                            c = conn()
                            c.execute("DELETE FROM gastos WHERE id=?", (gr.id,))
                            c.commit(); c.close()
                            st.session_state[key_conf] = False
                            st.toast("✅ Gasto borrado")
                            st.rerun()
                        if cc2.button("Cancelar", key=f"del_g_n_{gr.id}"):
                            st.session_state[key_conf] = False
                            st.rerun()
                            