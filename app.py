import streamlit as st
import pandas as pd
import hashlib
from datetime import datetime, date, timedelta
import calendar
from supabase import create_client, Client

# ─────────────────────────────────────────────
# CONFIGURAÇÃO DA PÁGINA
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Dashboard Financeiro",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────
# SUPABASE CLIENT
# ─────────────────────────────────────────────
@st.cache_resource
def get_sb() -> Client:
    return create_client(
        st.secrets["SUPABASE_URL"],
        st.secrets["SUPABASE_KEY"],
    )


def _hash(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()


# ─────────────────────────────────────────────
# HELPERS DE DATA / SEMANA
# ─────────────────────────────────────────────
def week_range(ref: date | None = None):
    if ref is None:
        ref = date.today()
    days_since_sun = (ref.weekday() + 1) % 7
    start = ref - timedelta(days=days_since_sun)
    return start, start + timedelta(days=6)


def weeks_of_month(year: int, month: int) -> list[dict]:
    first = date(year, month, 1)
    last  = date(year, month, calendar.monthrange(year, month)[1])
    weeks, current, n = [], first, 1
    while current <= last:
        s, e = week_range(current)
        weeks.append({
            "num":   n,
            "start": max(s, first),
            "end":   min(e, last),
            "label": f"Semana {n}  ({max(s,first).strftime('%d/%m')} – {min(e,last).strftime('%d/%m')})"
        })
        current = e + timedelta(days=1)
        n += 1
    return weeks


def ym(d: date) -> str:
    return f"{d.year}-{d.month:02d}"


# ─────────────────────────────────────────────
# OPERAÇÕES SUPABASE — USUÁRIOS
# ─────────────────────────────────────────────
def sb_get_user(username: str) -> dict | None:
    sb = get_sb()
    res = sb.table("users").select("*").eq("username", username).execute()
    return res.data[0] if res.data else None


def sb_create_user(username: str, password: str):
    get_sb().table("users").insert({
        "username":      username,
        "password_hash": _hash(password),
    }).execute()


def sb_update_password(username: str, new_pw: str):
    get_sb().table("users").update(
        {"password_hash": _hash(new_pw)}
    ).eq("username", username).execute()


# ─────────────────────────────────────────────
# OPERAÇÕES SUPABASE — LANÇAMENTOS
# ─────────────────────────────────────────────
def sb_get_lancamentos(username: str, year: int, month: int) -> list[dict]:
    prefix = f"{year}-{month:02d}"
    res = get_sb().table("lancamentos") \
        .select("*") \
        .eq("username", username) \
        .like("data", f"{prefix}%") \
        .order("data") \
        .execute()
    return res.data or []


def sb_add_lancamento(username: str, data_v: date, descricao: str, valor: float,
                       peso: int, status: str, juros: float):
    get_sb().table("lancamentos").insert({
        "id":          int(datetime.now().timestamp() * 1000),
        "username":    username,
        "data":        data_v.isoformat(),
        "descricao":   descricao,
        "valor":       valor,
        "peso":        peso,
        "status":      status,
        "juros_multa": juros,
    }).execute()


def sb_update_lancamento_status(row_id: int, status: str):
    get_sb().table("lancamentos").update(
        {"status": status}
    ).eq("id", row_id).execute()


def sb_delete_lancamento(row_id: int):
    get_sb().table("lancamentos").delete().eq("id", row_id).execute()


# ─────────────────────────────────────────────
# OPERAÇÕES SUPABASE — DEPÓSITOS
# ─────────────────────────────────────────────
def sb_get_depositos(username: str, year: int, month: int) -> list[dict]:
    prefix = f"{year}-{month:02d}"
    res = get_sb().table("depositos") \
        .select("*") \
        .eq("username", username) \
        .like("data", f"{prefix}%") \
        .order("data") \
        .execute()
    return res.data or []


def sb_add_deposito(username: str, data_d: date, valor: float, descricao: str):
    get_sb().table("depositos").insert({
        "id":        int(datetime.now().timestamp() * 1000),
        "username":  username,
        "data":      data_d.isoformat(),
        "valor":     valor,
        "descricao": descricao,
    }).execute()


def sb_delete_deposito(row_id: int):
    get_sb().table("depositos").delete().eq("id", row_id).execute()


# ─────────────────────────────────────────────
# OPERAÇÕES SUPABASE — METAS
# ─────────────────────────────────────────────
def sb_get_meta(username: str, ano_mes: str) -> dict:
    res = get_sb().table("metas") \
        .select("*") \
        .eq("username", username) \
        .eq("ano_mes", ano_mes) \
        .execute()
    return res.data[0] if res.data else {"meta": 0.0, "guardado": 0.0}


def sb_get_metas_ano(username: str, year: int) -> list[dict]:
    res = get_sb().table("metas") \
        .select("*") \
        .eq("username", username) \
        .like("ano_mes", f"{year}%") \
        .execute()
    return res.data or []


def sb_upsert_meta(username: str, ano_mes: str, meta: float | None = None,
                    guardado_add: float = 0.0):
    sb   = get_sb()
    curr = sb_get_meta(username, ano_mes)

    new_meta     = meta if meta is not None else curr.get("meta", 0.0)
    new_guardado = curr.get("guardado", 0.0) + guardado_add

    sb.table("metas").upsert({
        "username":  username,
        "ano_mes":   ano_mes,
        "meta":      new_meta,
        "guardado":  new_guardado,
    }, on_conflict="username,ano_mes").execute()


def sb_delete_mes(username: str, year: int, month: int):
    prefix = f"{year}-{month:02d}"
    sb = get_sb()
    sb.table("lancamentos").delete().eq("username", username).like("data", f"{prefix}%").execute()
    sb.table("depositos").delete().eq("username", username).like("data", f"{prefix}%").execute()


# ─────────────────────────────────────────────
# MOTOR DE DECISÃO
# ─────────────────────────────────────────────
def motor_decisao(lancamentos: list[dict], saldo: float):
    df = pd.DataFrame(lancamentos)
    if df.empty:
        return [], saldo, []

    abertos = df[df["status"] != "Pago"].copy()
    if abertos.empty:
        return [], saldo, []

    sugestoes, alertas = [], []
    saldo_rest = saldo

    for peso, icone in [(1, "⚡"), (2, "💳"), (3, "📦")]:
        grupo = abertos[abertos["peso"] == peso].copy()
        if grupo.empty:
            continue

        if peso == 1:
            total = grupo["valor"].sum()
            if total > saldo_rest:
                alertas.append(
                    f"🚨 **ALERTA DE CRISE** — Saldo insuficiente para as contas Essenciais!\n"
                    f"Necessário: **R$ {total:,.2f}** | Disponível: **R$ {saldo_rest:,.2f}** | "
                    f"Déficit: **R$ {(total - saldo_rest):,.2f}**"
                )
            for _, r in grupo.iterrows():
                sugestoes.append({
                    "Peso": f"{icone} Peso 1",
                    "Descrição": r["descricao"],
                    "Valor": r["valor"],
                    "Recomendação": "Pagar PRIMEIRO — sem juros, sem atraso"
                })
                saldo_rest -= r["valor"]

        elif peso == 2:
            grupo["custo_atraso"] = grupo.apply(
                lambda r: r["valor"] * (float(r.get("juros_multa") or 0) / 100), axis=1
            )
            grupo = grupo.sort_values("custo_atraso", ascending=False)
            for _, r in grupo.iterrows():
                ca = r["custo_atraso"]
                motivo = (
                    f"Maior custo de atraso: R$ {ca:,.2f}/mês"
                    if ca > 0 else "Sem juros informados — pagar após o Peso 1"
                )
                sugestoes.append({
                    "Peso": f"{icone} Peso 2",
                    "Descrição": r["descricao"],
                    "Valor": r["valor"],
                    "Recomendação": motivo
                })
                saldo_rest -= r["valor"]

        else:
            for _, r in grupo.iterrows():
                sugestoes.append({
                    "Peso": f"{icone} Peso 3",
                    "Descrição": r["descricao"],
                    "Valor": r["valor"],
                    "Recomendação": "Pagar somente se sobrar saldo"
                })

    return sugestoes, saldo_rest, alertas


# ─────────────────────────────────────────────
# LOGIN
# ─────────────────────────────────────────────
def page_login():
    st.markdown("<h1 style='text-align:center'>💰 Dashboard Financeiro</h1>", unsafe_allow_html=True)
    st.markdown(
        "<p style='text-align:center;color:gray'>Controle semanal · Metas · Priorização Inteligente</p>",
        unsafe_allow_html=True,
    )
    st.divider()

    _, col, _ = st.columns([1, 1.2, 1])
    with col:
        with st.form("login"):
            user = st.text_input("Usuário")
            pw   = st.text_input("Senha", type="password")
            ok   = st.form_submit_button("Entrar", use_container_width=True, type="primary")

        if ok:
            row = sb_get_user(user)
            if row and row["password_hash"] == _hash(pw):
                st.session_state.update(logged_in=True, username=user)
                st.rerun()
            else:
                st.error("Usuário ou senha incorretos.")

    st.caption("Primeiro acesso? Crie o usuário admin via SQL no Supabase — veja `supabase_setup.sql`.")


# ─────────────────────────────────────────────
# SIDEBAR + ROTEADOR
# ─────────────────────────────────────────────
PAGES = {
    "📊 Dashboard":     "dashboard",
    "📅 Lançamentos":   "lancamentos",
    "💵 Depósitos":     "depositos",
    "🎯 Metas":         "metas",
    "⚙️ Configurações": "config",
}


def main_app():
    with st.sidebar:
        st.markdown(f"### 👋 {st.session_state['username']}")
        st.divider()
        page = st.radio("Navegação", list(PAGES.keys()), label_visibility="collapsed")
        st.divider()
        if st.button("🚪 Sair", use_container_width=True):
            st.session_state.clear()
            st.rerun()

    routed = PAGES[page]
    u = st.session_state["username"]

    if   routed == "dashboard":    page_dashboard(u)
    elif routed == "lancamentos":  page_lancamentos(u)
    elif routed == "depositos":    page_depositos(u)
    elif routed == "metas":        page_metas(u)
    else:                          page_config(u)


# ─────────────────────────────────────────────
# PÁGINA: DASHBOARD
# ─────────────────────────────────────────────
def page_dashboard(u: str):
    hoje = date.today()
    am   = ym(hoje)

    st.title("📊 Dashboard Financeiro")
    st.caption(f"Hoje: {hoje.strftime('%d/%m/%Y')} — semana fecha no sábado às 23:59")
    st.divider()

    lanc_mes = sb_get_lancamentos(u, hoje.year, hoje.month)
    dep_mes  = sb_get_depositos(u, hoje.year, hoje.month)

    total_receita = sum(float(d["valor"]) for d in dep_mes)
    total_pago    = sum(float(l["valor"]) for l in lanc_mes if l["status"] == "Pago")
    total_aberto  = sum(float(l["valor"]) for l in lanc_mes if l["status"] != "Pago")
    saldo_disp    = total_receita - total_pago

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💰 Receitas do Mês",    f"R$ {total_receita:,.2f}")
    c2.metric("✅ Total Pago",          f"R$ {total_pago:,.2f}")
    c3.metric("📋 A Pagar (em aberto)", f"R$ {total_aberto:,.2f}")
    c4.metric("💵 Saldo Disponível",    f"R$ {saldo_disp:,.2f}")

    st.divider()

    # ── Progresso mensal ───────────────────────────────────────
    meta_info    = sb_get_meta(u, am)
    meta_mensal  = float(meta_info.get("meta",     0))
    guardado_mes = float(meta_info.get("guardado", 0))

    st.subheader("🎯 Meta de Reserva — Mês Atual")
    if meta_mensal > 0:
        prog = min(guardado_mes / meta_mensal, 1.0)
        st.progress(prog,
            text=f"R$ {guardado_mes:,.2f} de R$ {meta_mensal:,.2f}  •  {prog*100:.1f}%")
    else:
        st.info("Defina a meta mensal na aba **🎯 Metas**.")

    # ── Progresso anual ────────────────────────────────────────
    st.subheader(f"📈 Reserva Acumulada — {hoje.year}")
    metas_ano   = sb_get_metas_ano(u, hoje.year)
    total_anual = sum(float(m.get("guardado", 0)) for m in metas_ano)
    meta_anual  = sum(float(m.get("meta",     0)) for m in metas_ano)

    if meta_anual > 0:
        pa = min(total_anual / meta_anual, 1.0)
        st.progress(pa,
            text=f"R$ {total_anual:,.2f} guardados em {hoje.year}  •  {pa*100:.1f}% da meta anual")
    else:
        st.info("Configure metas mensais para ver o acumulado anual.")

    st.divider()

    # ── Semana atual ───────────────────────────────────────────
    ini, fim = week_range(hoje)
    st.subheader(f"📅 Semana Atual  ({ini.strftime('%d/%m')} – {fim.strftime('%d/%m')})")

    lanc_sem = [l for l in lanc_mes
                if ini.isoformat() <= l["data"] <= fim.isoformat()]
    dep_sem  = [d for d in dep_mes
                if ini.isoformat() <= d["data"] <= fim.isoformat()]

    rec_sem   = sum(float(d["valor"]) for d in dep_sem)
    pago_sem  = sum(float(l["valor"]) for l in lanc_sem if l["status"] == "Pago")
    saldo_sem = rec_sem - pago_sem

    cs1, cs2, cs3 = st.columns(3)
    cs1.metric("Entradas", f"R$ {rec_sem:,.2f}")
    cs2.metric("Pago",     f"R$ {pago_sem:,.2f}")
    cs3.metric("Saldo",    f"R$ {saldo_sem:,.2f}")

    # ── Motor de decisão ───────────────────────────────────────
    if lanc_sem:
        st.divider()
        st.subheader("🤖 Motor de Decisão — Sugestão de Pagamento")

        sugestoes, saldo_pos, alertas = motor_decisao(lanc_sem, rec_sem)

        for a in alertas:
            st.error(a)

        if sugestoes:
            df_s = pd.DataFrame(sugestoes)
            df_s["Valor"] = df_s["Valor"].apply(lambda v: f"R$ {float(v):,.2f}")
            st.dataframe(df_s, use_container_width=True, hide_index=True)

            if saldo_pos < 0:
                st.warning(f"⚠️ Déficit estimado após todos os pagamentos: **R$ {abs(saldo_pos):,.2f}**")
            else:
                st.success(f"✅ Saldo estimado após pagamentos: **R$ {saldo_pos:,.2f}**")
    else:
        st.info("Nenhum lançamento na semana atual. Adicione na aba **📅 Lançamentos**.")


# ─────────────────────────────────────────────
# PÁGINA: LANÇAMENTOS
# ─────────────────────────────────────────────
def page_lancamentos(u: str):
    hoje = date.today()
    st.title("📅 Lançamentos (Custos)")

    col1, col2 = st.columns(2)
    ano = col1.selectbox("Ano", range(hoje.year - 1, hoje.year + 2), index=1)
    mes = col2.selectbox("Mês", range(1, 13), index=hoje.month - 1,
                          format_func=lambda m: calendar.month_name[m])

    # ── Formulário ─────────────────────────────────────────────
    with st.expander("➕ Novo Lançamento"):
        with st.form("f_lanc", clear_on_submit=True):
            r1c1, r1c2 = st.columns(2)
            dt_v  = r1c1.date_input("Vencimento", value=hoje)
            desc  = r1c2.text_input("Descrição")

            r2c1, r2c2, r2c3 = st.columns(3)
            valor  = r2c1.number_input("Valor (R$)", min_value=0.0, step=0.01, format="%.2f")
            peso   = r2c2.selectbox("Peso", [1, 2, 3],
                        format_func=lambda p: {1:"1 — Essencial",2:"2 — Financeiro",3:"3 — Não Essencial"}[p])
            status = r2c3.selectbox("Status", ["Em Aberto", "Pago", "Atrasado"])

            juros = st.number_input("Juros / Multa (% a.m.)", min_value=0.0, step=0.1,
                                     help="Taxa mensal de juros em caso de atraso")

            if st.form_submit_button("Adicionar", use_container_width=True, type="primary"):
                if desc and valor > 0:
                    sb_add_lancamento(u, dt_v, desc, valor, peso, status, juros)
                    st.success("Lançamento adicionado!")
                    st.rerun()
                else:
                    st.warning("Preencha Descrição e Valor.")

    st.divider()

    # ── Tabela por semanas ─────────────────────────────────────
    lanc_mes = sb_get_lancamentos(u, ano, mes)
    if not lanc_mes:
        st.info("Nenhum lançamento neste período.")
        return

    df_mes = pd.DataFrame(lanc_mes)
    df_mes["data_d"] = pd.to_datetime(df_mes["data"]).dt.date

    STATUS_OPTS  = ["Em Aberto", "Pago", "Atrasado"]
    STATUS_EMOJI = {"Em Aberto": "🟡", "Pago": "🟢", "Atrasado": "🔴"}

    for semana in weeks_of_month(ano, mes):
        s, e = semana["start"], semana["end"]
        df_s = df_mes[(df_mes["data_d"] >= s) & (df_mes["data_d"] <= e)]
        if df_s.empty:
            continue

        tot = df_s["valor"].astype(float).sum()
        pag = df_s[df_s["status"] == "Pago"]["valor"].astype(float).sum()

        with st.expander(
            f"📆 {semana['label']}  —  Total: R$ {tot:,.2f}  |  Pago: R$ {pag:,.2f}",
            expanded=(s <= date.today() <= e)
        ):
            hdr = st.columns([1.5, 3.5, 2, 1.5, 2.5, 0.8])
            for h, t in zip(hdr, ["Data", "Descrição", "Valor", "Peso", "Status", ""]):
                h.markdown(f"**{t}**")
            st.divider()

            for _, row in df_s.iterrows():
                c1, c2, c3, c4, c5, c6 = st.columns([1.5, 3.5, 2, 1.5, 2.5, 0.8])
                c1.write(pd.Timestamp(row["data"]).strftime("%d/%m"))
                c2.write(row["descricao"])
                c3.write(f"R$ {float(row['valor']):,.2f}")
                c4.write({1:"⚡ P1", 2:"💳 P2", 3:"📦 P3"}[row["peso"]])

                idx = STATUS_OPTS.index(row["status"]) if row["status"] in STATUS_OPTS else 0
                novo_st = c5.selectbox(
                    "st", STATUS_OPTS, index=idx,
                    key=f"st_{row['id']}", label_visibility="collapsed",
                    format_func=lambda s: f"{STATUS_EMOJI[s]} {s}"
                )

                if c6.button("🗑️", key=f"del_{row['id']}"):
                    sb_delete_lancamento(int(row["id"]))
                    st.rerun()

                if novo_st != row["status"]:
                    sb_update_lancamento_status(int(row["id"]), novo_st)
                    st.rerun()


# ─────────────────────────────────────────────
# PÁGINA: DEPÓSITOS
# ─────────────────────────────────────────────
def page_depositos(u: str):
    hoje = date.today()
    st.title("💵 Depósitos (Receitas)")

    col1, col2 = st.columns(2)
    ano = col1.selectbox("Ano", range(hoje.year - 1, hoje.year + 2), index=1)
    mes = col2.selectbox("Mês", range(1, 13), index=hoje.month - 1,
                          format_func=lambda m: calendar.month_name[m])

    with st.expander("➕ Novo Depósito"):
        with st.form("f_dep", clear_on_submit=True):
            c1, c2 = st.columns(2)
            dt_d  = c1.date_input("Data do Depósito", value=hoje)
            valor = c2.number_input("Valor (R$)", min_value=0.0, step=0.01, format="%.2f")
            desc  = st.text_input("Descrição / Histórico")

            if st.form_submit_button("Adicionar Depósito", use_container_width=True, type="primary"):
                if valor > 0:
                    sb_add_deposito(u, dt_d, valor, desc)
                    st.success("Depósito registrado!")
                    st.rerun()
                else:
                    st.warning("Informe um valor maior que zero.")

    st.divider()

    depositos = sb_get_depositos(u, ano, mes)
    if not depositos:
        st.info("Nenhum depósito neste período.")
        return

    df = pd.DataFrame(depositos)
    df["data_d"] = pd.to_datetime(df["data"]).dt.date
    df = df.sort_values("data_d")

    total = df["valor"].astype(float).sum()
    st.metric("💰 Total de Receitas no Mês", f"R$ {total:,.2f}")
    st.divider()

    hdr = st.columns([2, 4, 2.5, 0.8])
    for h, t in zip(hdr, ["Data", "Descrição", "Valor", ""]):
        h.markdown(f"**{t}**")

    for _, row in df.iterrows():
        c1, c2, c3, c4 = st.columns([2, 4, 2.5, 0.8])
        c1.write(row["data_d"].strftime("%d/%m/%Y"))
        c2.write(row.get("descricao") or "—")
        c3.write(f"R$ {float(row['valor']):,.2f}")
        if c4.button("🗑️", key=f"del_d_{row['id']}"):
            sb_delete_deposito(int(row["id"]))
            st.rerun()


# ─────────────────────────────────────────────
# PÁGINA: METAS
# ─────────────────────────────────────────────
def page_metas(u: str):
    hoje = date.today()
    am   = ym(hoje)
    st.title("🎯 Metas de Economia")

    st.subheader(f"Meta de {calendar.month_name[hoje.month]} / {hoje.year}")

    info      = sb_get_meta(u, am)
    meta_val  = float(info.get("meta",     0))
    guard_val = float(info.get("guardado", 0))

    c1, c2, c3 = st.columns(3)
    nova_meta = c1.number_input("Meta (R$)",           value=meta_val,  min_value=0.0, step=10.0)
    add_val   = c2.number_input("Valor a Guardar (R$)", value=0.0,       min_value=0.0, step=10.0)

    b1, b2 = c3.columns(2)
    if b1.button("💾 Salvar Meta", use_container_width=True):
        sb_upsert_meta(u, am, meta=nova_meta)
        st.success("Meta atualizada!")
        st.rerun()

    if b2.button("✅ Guardar", use_container_width=True):
        if add_val > 0:
            sb_upsert_meta(u, am, guardado_add=add_val)
            st.success(f"R$ {add_val:,.2f} adicionado à reserva!")
            st.rerun()

    if nova_meta > 0:
        p = min(guard_val / nova_meta, 1.0)
        st.progress(p, text=f"R$ {guard_val:,.2f} / R$ {nova_meta:,.2f}  •  {p*100:.1f}%")

    st.divider()

    # ── Visão anual ────────────────────────────────────────────
    st.subheader(f"📊 Progresso por Mês — {hoje.year}")
    metas_ano = {m["ano_mes"]: m for m in sb_get_metas_ano(u, hoje.year)}

    cols = st.columns(4)
    total_ano = 0.0
    meta_ano  = 0.0
    for i, m in enumerate(range(1, 13)):
        key = f"{hoje.year}-{m:02d}"
        inf = metas_ano.get(key, {"meta": 0.0, "guardado": 0.0})
        mv  = float(inf.get("meta",     0))
        gv  = float(inf.get("guardado", 0))
        total_ano += gv
        meta_ano  += mv
        with cols[i % 4]:
            if mv > 0:
                p = min(gv / mv, 1.0)
                st.metric(calendar.month_abbr[m], f"R$ {gv:,.2f}", f"de R$ {mv:,.2f}")
                st.progress(p)
            else:
                st.metric(calendar.month_abbr[m], "Sem meta", "")

    st.divider()
    st.subheader(f"🏆 Total Guardado em {hoje.year}: R$ {total_ano:,.2f}")
    if meta_ano > 0:
        pa = min(total_ano / meta_ano, 1.0)
        st.progress(pa,
            text=f"{pa*100:.1f}% da meta anual  (R$ {total_ano:,.2f} / R$ {meta_ano:,.2f})")


# ─────────────────────────────────────────────
# PÁGINA: CONFIGURAÇÕES
# ─────────────────────────────────────────────
def page_config(u: str):
    hoje = date.today()
    st.title("⚙️ Configurações")

    st.subheader("🔐 Alterar Senha")
    with st.form("f_pw"):
        pw_atual   = st.text_input("Senha Atual",          type="password")
        pw_nova    = st.text_input("Nova Senha",            type="password")
        pw_confirm = st.text_input("Confirmar Nova Senha", type="password")

        if st.form_submit_button("Alterar Senha", type="primary"):
            row = sb_get_user(u)
            if row and row["password_hash"] == _hash(pw_atual):
                if pw_nova == pw_confirm and pw_nova:
                    sb_update_password(u, pw_nova)
                    st.success("Senha alterada com sucesso!")
                else:
                    st.error("As senhas nao coincidem ou estao vazias.")
            else:
                st.error("Senha atual incorreta.")

    st.divider()
    st.subheader("Sobre o Sistema")
    st.info("""
**Dashboard Financeiro Pessoal**

- **Corte semanal:** todo sabado as 23:59
- **Peso 1 Essencial:** maxima prioridade, pagar sem falta
- **Peso 2 Financeiro:** priorizado pelo maior custo de atraso (juros x valor)
- **Peso 3 Nao Essencial:** somente se sobrar saldo
- **Alerta de Crise:** disparado quando saldo nao cobre o Peso 1
- **Dados persistidos:** Supabase (PostgreSQL)
    """)

    st.divider()
    st.subheader("Zona de Perigo")
    with st.expander("Apagar todos os dados do mes atual"):
        am = ym(hoje)
        st.warning("Remove lancamentos e depositos do mes. Nao pode ser desfeito.")
        if st.button("Confirmar exclusao do mes atual", type="primary"):
            sb_delete_mes(u, hoje.year, hoje.month)
            st.success("Dados do mes apagados.")
            st.rerun()


# ENTRY POINT
def main():
    st.session_state.setdefault("logged_in", False)
    if not st.session_state["logged_in"]:
        page_login()
    else:
        main_app()


if __name__ == "__main__":
    main()
