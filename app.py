import streamlit as st
import pandas as pd
import hashlib
from datetime import datetime, date, timedelta
import calendar
from supabase import create_client, Client

# ── CONSTANTES ─────────────────────────────────────────────────
MESES_PT   = ["","Janeiro","Fevereiro","Março","Abril","Maio","Junho",
               "Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"]
MESES_ABBR = ["","Jan","Fev","Mar","Abr","Mai","Jun",
               "Jul","Ago","Set","Out","Nov","Dez"]
STATUS_OPTS  = ["Em Aberto","Pago","Vencido"]
STATUS_COR   = {"Em Aberto":"#854d0e","Pago":"#166534","Vencido":"#991b1b"}
PESO_LABEL   = {1:"⚡ Essencial",2:"💳 Financeiro",3:"📦 Não Essencial"}

# ── PAGE CONFIG ────────────────────────────────────────────────
st.set_page_config(page_title="Dashboard Financeiro",page_icon="💰",
                   layout="wide",initial_sidebar_state="expanded")

st.markdown("""
<style>
  html,body,[class*="css"],[class*="st-"]{font-family:Arial,sans-serif!important;font-size:12px!important}
  h1{font-family:Arial,sans-serif!important;font-size:20px!important;font-weight:bold!important}
  h2,h3{font-family:Arial,sans-serif!important;font-size:16px!important;font-weight:bold!important}
  .stTabs [data-baseweb="tab"]{font-family:Arial,sans-serif!important;font-size:12px!important}
  .stMetric label{font-size:11px!important}
  .stMetric [data-testid="metric-container"] div{font-size:14px!important;font-weight:bold!important}
  .bloco-semana{background:#0F172A;border-left:3px solid #2563EB;
    padding:6px 12px;margin:6px 0;border-radius:0 4px 4px 0;
    font-size:13px;font-weight:bold;color:#93C5FD}
  .col-header{background:#1E293B;padding:5px 8px;font-size:11px;
    font-weight:bold;color:#94A3B8;border-radius:4px;text-align:center}
  div[data-testid="column"]{padding:2px 4px!important}
</style>""",unsafe_allow_html=True)

# ── SUPABASE ───────────────────────────────────────────────────
@st.cache_resource
def get_sb() -> Client:
    return create_client(st.secrets["SUPABASE_URL"],st.secrets["SUPABASE_KEY"])

def _hash(pw:str)->str: return hashlib.sha256(pw.encode()).hexdigest()

# ── HELPERS DE DATA ────────────────────────────────────────────
def week_range(ref:date|None=None):
    if ref is None: ref=date.today()
    start=ref-timedelta(days=(ref.weekday()+1)%7)
    return start,start+timedelta(days=6)

def weeks_of_month(year:int,month:int)->list:
    first=date(year,month,1)
    last=date(year,month,calendar.monthrange(year,month)[1])
    weeks,cur,n=[],first,1
    while cur<=last:
        s,e=week_range(cur)
        weeks.append({"num":n,"start":max(s,first),"end":min(e,last),
            "label":f"Semana {n}  ({max(s,first).strftime('%d/%m')} – {min(e,last).strftime('%d/%m')})"})
        cur=e+timedelta(days=1); n+=1
    return weeks

def month_range(year:int,month:int):
    last=calendar.monthrange(year,month)[1]
    return f"{year}-{month:02d}-01",f"{year}-{month:02d}-{last:02d}"

def ym(d:date)->str: return f"{d.year}-{d.month:02d}"

# ── CRUD: USUÁRIOS ─────────────────────────────────────────────
def sb_get_user(u:str):
    r=get_sb().table("users").select("*").eq("username",u).execute()
    return r.data[0] if r.data else None

def sb_update_password(u:str,pw:str):
    get_sb().table("users").update({"password_hash":_hash(pw)}).eq("username",u).execute()

# ── CRUD: LANÇAMENTOS ──────────────────────────────────────────
def sb_get_lanc(u:str,year:int,month:int)->list:
    s,e=month_range(year,month)
    r=get_sb().table("lancamentos").select("*").eq("username",u)\
        .gte("data",s).lte("data",e).order("data").execute()
    return r.data or []

def sb_get_lanc_semana(u:str,ini:date,fim:date)->list:
    r=get_sb().table("lancamentos").select("*").eq("username",u)\
        .gte("data",ini.isoformat()).lte("data",fim.isoformat()).order("data").execute()
    return r.data or []

def sb_add_lanc(u:str,dt:date,desc:str,val:float,peso:int,status:str,juros:float,obs:str):
    get_sb().table("lancamentos").insert({
        "id":int(datetime.now().timestamp()*1000),"username":u,
        "data":dt.isoformat(),"descricao":desc,"valor":val,
        "peso":peso,"status":status,"juros_multa":juros,"obs":obs
    }).execute()

def sb_update_lanc(row_id:int,**kwargs):
    get_sb().table("lancamentos").update(kwargs).eq("id",row_id).execute()

def sb_delete_lanc(row_id:int):
    get_sb().table("lancamentos").delete().eq("id",row_id).execute()

def sb_delete_mes(u:str,year:int,month:int):
    s,e=month_range(year,month)
    sb=get_sb()
    sb.table("lancamentos").delete().eq("username",u).gte("data",s).lte("data",e).execute()
    sb.table("depositos").delete().eq("username",u).gte("data",s).lte("data",e).execute()

# ── CRUD: DEPÓSITOS ────────────────────────────────────────────
def sb_get_dep(u:str,year:int,month:int)->list:
    s,e=month_range(year,month)
    r=get_sb().table("depositos").select("*").eq("username",u)\
        .gte("data",s).lte("data",e).order("data").execute()
    return r.data or []

def sb_get_dep_semana(u:str,ini:date,fim:date)->list:
    r=get_sb().table("depositos").select("*").eq("username",u)\
        .gte("data",ini.isoformat()).lte("data",fim.isoformat()).execute()
    return r.data or []

def sb_add_dep(u:str,dt:date,val:float,desc:str):
    get_sb().table("depositos").insert({
        "id":int(datetime.now().timestamp()*1000),"username":u,
        "data":dt.isoformat(),"valor":val,"descricao":desc
    }).execute()

def sb_delete_dep(row_id:int):
    get_sb().table("depositos").delete().eq("id",row_id).execute()

# ── CRUD: METAS ────────────────────────────────────────────────
def sb_get_meta(u:str,am:str)->dict:
    r=get_sb().table("metas").select("*").eq("username",u).eq("ano_mes",am).execute()
    return r.data[0] if r.data else {"meta":0.0,"guardado":0.0}

def sb_get_metas_ano(u:str,year:int)->list:
    r=get_sb().table("metas").select("*").eq("username",u)\
        .like("ano_mes",f"{year}%").execute()
    return r.data or []

def sb_upsert_meta(u:str,am:str,meta=None,add:float=0.0):
    curr=sb_get_meta(u,am)
    get_sb().table("metas").upsert({
        "username":u,"ano_mes":am,
        "meta":meta if meta is not None else curr.get("meta",0.0),
        "guardado":curr.get("guardado",0.0)+add
    },on_conflict="username,ano_mes").execute()

# ── MOTOR DE DECISÃO ───────────────────────────────────────────
def motor_decisao(lancamentos:list,saldo:float):
    df=pd.DataFrame(lancamentos)
    if df.empty: return [],saldo,[]
    abertos=df[df["status"]!="Pago"].copy()
    if abertos.empty: return [],saldo,[]
    sugestoes,alertas,saldo_rest=[],[],saldo
    for peso,icone in [(1,"⚡"),(2,"💳"),(3,"📦")]:
        g=abertos[abertos["peso"]==peso].copy()
        if g.empty: continue
        if peso==1:
            total=g["valor"].astype(float).sum()
            if total>saldo_rest:
                alertas.append(f"🚨 **ALERTA DE CRISE** — Essenciais: R$ {total:,.2f} | Disponível: R$ {saldo_rest:,.2f} | Déficit: R$ {total-saldo_rest:,.2f}")
            for _,r in g.iterrows():
                sugestoes.append({"Peso":f"{icone} Peso 1","Descrição":r["descricao"],
                    "Valor":f"R$ {float(r['valor']):,.2f}","Recomendação":"Pagar PRIMEIRO"})
                saldo_rest-=float(r["valor"])
        elif peso==2:
            g["custo"]=g.apply(lambda r:float(r["valor"])*(float(r.get("juros_multa")or 0)/100),axis=1)
            g=g.sort_values("custo",ascending=False)
            for _,r in g.iterrows():
                ca=r["custo"]
                sugestoes.append({"Peso":f"{icone} Peso 2","Descrição":r["descricao"],
                    "Valor":f"R$ {float(r['valor']):,.2f}",
                    "Recomendação":f"Custo de atraso: R$ {ca:,.2f}/mês" if ca>0 else "Sem juros — após Peso 1"})
                saldo_rest-=float(r["valor"])
        else:
            for _,r in g.iterrows():
                sugestoes.append({"Peso":f"{icone} Peso 3","Descrição":r["descricao"],
                    "Valor":f"R$ {float(r['valor']):,.2f}","Recomendação":"Só se sobrar saldo"})
    return sugestoes,saldo_rest,alertas

# ── LOGIN ──────────────────────────────────────────────────────
def page_login():
    st.markdown("<h1 style='text-align:center'>💰 Dashboard Financeiro</h1>",unsafe_allow_html=True)
    st.markdown("<p style='text-align:center;color:gray'>Controle semanal · Metas · Priorização Inteligente</p>",unsafe_allow_html=True)
    st.divider()
    _,col,_=st.columns([1,1.2,1])
    with col:
        with st.form("login"):
            user=st.text_input("Usuário")
            pw=st.text_input("Senha",type="password")
            ok=st.form_submit_button("Entrar",use_container_width=True,type="primary")
        if ok:
            row=sb_get_user(user)
            if row and row["password_hash"]==_hash(pw):
                st.session_state.update(logged_in=True,username=user)
                st.rerun()
            else:
                st.error("Usuário ou senha incorretos.")

# ── SIDEBAR COM RELATÓRIO SEMANAL ──────────────────────────────
def render_sidebar()->str:
    u=st.session_state["username"]
    hoje=date.today()
    ini,fim=week_range(hoje)
    with st.sidebar:
        st.markdown(f"### 👋 {u}")
        st.divider()
        PAGES={"📊 Dashboard":"dashboard","📅 Lançamentos":"lancamentos",
               "💵 Depósitos":"depositos","🎯 Metas":"metas","⚙️ Configurações":"config"}
        page=st.radio("Navegação",list(PAGES.keys()),label_visibility="collapsed")
        st.divider()
        # ── Relatório semanal ──
        st.markdown("**📋 Semana Atual**")
        st.caption(f"{ini.strftime('%d/%m')} – {fim.strftime('%d/%m/%Y')}")
        try:
            lanc_s=sb_get_lanc_semana(u,ini,fim)
            dep_s=sb_get_dep_semana(u,ini,fim)
            rec=sum(float(d["valor"]) for d in dep_s)
            pago=sum(float(l["valor"]) for l in lanc_s if l["status"]=="Pago")
            aberto=sum(float(l["valor"]) for l in lanc_s if l["status"]!="Pago")
            saldo=rec-pago
            c1,c2=st.columns(2)
            c1.metric("Entradas",f"R$ {rec:,.2f}")
            c2.metric("Pago",f"R$ {pago:,.2f}")
            cor="🟢" if saldo>=0 else "🔴"
            st.metric(f"{cor} Saldo",f"R$ {saldo:,.2f}")
            if aberto>0:
                st.caption(f"⏳ Pendente: R$ {aberto:,.2f}")
        except:
            st.caption("Sem dados.")
        st.divider()
        if st.button("🚪 Sair",use_container_width=True):
            st.session_state.clear(); st.rerun()
    return PAGES[page]

# ── HELPER: CONFIRMAÇÃO DUPLA DE EXCLUSÃO ─────────────────────
def btn_delete(key:str,label:str="🗑️")->bool:
    st.session_state.setdefault("confirm_del",set())
    if key in st.session_state["confirm_del"]:
        c1,c2=st.columns(2)
        if c1.button("✅ Sim",key=f"yes_{key}",type="primary"):
            st.session_state["confirm_del"].discard(key)
            return True
        if c2.button("❌ Não",key=f"no_{key}"):
            st.session_state["confirm_del"].discard(key)
            st.rerun()
    else:
        if st.button(label,key=f"del_{key}"):
            st.session_state["confirm_del"].add(key)
            st.rerun()
    return False

# ── PÁGINA: DASHBOARD ──────────────────────────────────────────
def page_dashboard(u:str):
    hoje=date.today()
    am=ym(hoje)
    ini,fim=week_range(hoje)
    st.title("📊 Dashboard Financeiro")
    st.caption(f"Hoje: {hoje.strftime('%d/%m/%Y')} — semana fecha no sábado às 23:59")
    st.divider()

    lanc_mes=sb_get_lanc(u,hoje.year,hoje.month)
    dep_mes=sb_get_dep(u,hoje.year,hoje.month)
    total_rec=sum(float(d["valor"]) for d in dep_mes)
    total_pago=sum(float(l["valor"]) for l in lanc_mes if l["status"]=="Pago")
    total_aberto=sum(float(l["valor"]) for l in lanc_mes if l["status"]!="Pago")
    total_vencido=sum(float(l["valor"]) for l in lanc_mes if l["status"]=="Vencido")
    saldo=total_rec-total_pago

    c1,c2,c3,c4,c5=st.columns(5)
    c1.metric("💰 Depósitos do Mês",f"R$ {total_rec:,.2f}")
    c2.metric("✅ Pago",f"R$ {total_pago:,.2f}")
    c3.metric("🟡 Em Aberto",f"R$ {total_aberto:,.2f}")
    c4.metric("🔴 Vencido",f"R$ {total_vencido:,.2f}")
    c5.metric("💵 Saldo Disponível",f"R$ {saldo:,.2f}")
    st.divider()

    # Progresso meta mensal
    meta_info=sb_get_meta(u,am)
    meta_val=float(meta_info.get("meta",0))
    guard_val=float(meta_info.get("guardado",0))
    st.subheader("🎯 Meta de Reserva — Mês Atual")
    if meta_val>0:
        p=min(guard_val/meta_val,1.0)
        st.progress(p,text=f"R$ {guard_val:,.2f} / R$ {meta_val:,.2f}  •  {p*100:.1f}%")
    else:
        st.info("Defina a meta mensal na aba 🎯 Metas.")

    # Progresso anual
    metas_ano=sb_get_metas_ano(u,hoje.year)
    total_ano=sum(float(m.get("guardado",0)) for m in metas_ano)
    meta_ano=sum(float(m.get("meta",0)) for m in metas_ano)
    st.subheader(f"📈 Reserva Acumulada — {hoje.year}")
    if meta_ano>0:
        pa=min(total_ano/meta_ano,1.0)
        st.progress(pa,text=f"R$ {total_ano:,.2f} guardados  •  {pa*100:.1f}%")
    else:
        st.info("Configure metas mensais para ver o acumulado anual.")
    st.divider()

    # Motor de decisão semana atual
    lanc_sem=sb_get_lanc_semana(u,ini,fim)
    dep_sem=sb_get_dep_semana(u,ini,fim)
    rec_sem=sum(float(d["valor"]) for d in dep_sem)
    st.subheader(f"🤖 Motor de Decisão — Semana {ini.strftime('%d/%m')} a {fim.strftime('%d/%m')}")
    if lanc_sem:
        sugs,saldo_pos,alertas=motor_decisao(lanc_sem,rec_sem)
        for a in alertas: st.error(a)
        if sugs:
            st.dataframe(pd.DataFrame(sugs),use_container_width=True,hide_index=True)
            if saldo_pos<0:
                st.warning(f"⚠️ Déficit estimado: R$ {abs(saldo_pos):,.2f}")
            else:
                st.success(f"✅ Saldo após pagamentos: R$ {saldo_pos:,.2f}")
    else:
        st.info("Nenhum lançamento na semana atual.")

# ── PÁGINA: LANÇAMENTOS (layout novo) ─────────────────────────
def page_lancamentos(u:str):
    hoje=date.today()
    st.title("📅 Lançamentos (Custos)")

    # ── Top metrics ────────────────────────────────────────────
    # Calcula totais do mês selecionado (começa no atual)
    mes_sel=st.session_state.get("lanc_mes",hoje.month)
    ano_sel=st.session_state.get("lanc_ano",hoje.year)

    # ── Tabs de meses ──────────────────────────────────────────
    tabs=st.tabs([MESES_ABBR[m] for m in range(1,13)])
    for idx,tab in enumerate(tabs):
        m=idx+1
        with tab:
            st.session_state["lanc_mes"]=m
            st.session_state["lanc_ano"]=hoje.year
            _render_mes_lancamentos(u,hoje.year,m,hoje)

def _render_mes_lancamentos(u:str,ano:int,mes:int,hoje:date):
    lanc=sb_get_lanc(u,ano,mes)
    dep=sb_get_dep(u,ano,mes)
    total_rec=sum(float(d["valor"]) for d in dep)
    total_lanc=sum(float(l["valor"]) for l in lanc)
    n_pago=sum(1 for l in lanc if l["status"]=="Pago")
    n_aberto=sum(1 for l in lanc if l["status"]=="Em Aberto")
    n_vencido=sum(1 for l in lanc if l["status"]=="Vencido")

    c1,c2,c3,c4,c5=st.columns(5)
    c1.metric("💰 Saldo Total Depósitos",f"R$ {total_rec:,.2f}")
    c2.metric("📋 Total Lançamentos",f"R$ {total_lanc:,.2f}")
    c3.metric("🟢 Pagos",str(n_pago))
    c4.metric("🟡 Em Aberto",str(n_aberto))
    c5.metric("🔴 Vencidos",str(n_vencido))
    st.divider()

    # ── Formulário de adição ───────────────────────────────────
    with st.expander("➕ Novo Lançamento"):
        with st.form(f"f_lanc_{mes}",clear_on_submit=True):
            c1,c2=st.columns(2)
            dt=c1.date_input("Vencimento",value=date(ano,mes,1) if date(ano,mes,1)>hoje else hoje)
            desc=c2.text_input("Descrição")
            c3,c4,c5=st.columns(3)
            val=c3.number_input("Valor (R$)",min_value=0.0,value=0.0,step=100.0,format="%.2f")
            peso=c4.selectbox("Categoria",[1,2,3],format_func=lambda p:PESO_LABEL[p])
            status=c5.selectbox("Situação",STATUS_OPTS)
            c6,c7=st.columns(2)
            juros=c6.number_input("Juros/Multa (% a.m.)",min_value=0.0,step=0.1,format="%.1f")
            obs=c7.text_input("Observação")
            if st.form_submit_button("Adicionar",use_container_width=True,type="primary"):
                if desc and val>0:
                    sb_add_lanc(u,dt,desc,val,peso,status,juros,obs)
                    st.success("Lançamento adicionado!")
                    st.rerun()
                else:
                    st.warning("Preencha Descrição e Valor.")

    if not lanc:
        st.info(f"Nenhum lançamento em {MESES_PT[mes]}.")
        return

    # ── Cabeçalho da tabela ────────────────────────────────────
    df=pd.DataFrame(lanc)
    df["data_d"]=pd.to_datetime(df["data"]).dt.date
    ini_sem,fim_sem=week_range(hoje)

    hcols=st.columns([1.5,2,3,1.8,1.5,2,0.6,0.6])
    headers=["Semana","Categoria","Descrição","Valor","Situação","Obs","",""]
    for hc,ht in zip(hcols,headers):
        hc.markdown(f"<div class='col-header'>{ht}</div>",unsafe_allow_html=True)

    # ── Linhas por semana ──────────────────────────────────────
    for semana in weeks_of_month(ano,mes):
        s,e=semana["start"],semana["end"]
        df_s=df[(df["data_d"]>=s)&(df["data_d"]<=e)]
        if df_s.empty: continue
        tot=df_s["valor"].astype(float).sum()
        pag=df_s[df_s["status"]=="Pago"]["valor"].astype(float).sum()
        destaque="🔵" if s<=hoje<=e else ""
        st.markdown(
            f"<div class='bloco-semana'>{destaque} {semana['label']} &nbsp;|&nbsp; "
            f"{len(df_s)} lançamento(s) &nbsp;|&nbsp; Total: R$ {tot:,.2f} &nbsp;|&nbsp; Pago: R$ {pag:,.2f}</div>",
            unsafe_allow_html=True)

        for _,row in df_s.iterrows():
            rid=int(row["id"])
            c1,c2,c3,c4,c5,c6,c7,c8=st.columns([1.5,2,3,1.8,1.5,2,0.6,0.6])
            c1.write(pd.Timestamp(row["data"]).strftime("%d/%m"))
            c2.write(PESO_LABEL.get(row["peso"],"—"))
            c3.write(row["descricao"])
            c4.write(f"R$ {float(row['valor']):,.2f}")
            idx_st=STATUS_OPTS.index(row["status"]) if row["status"] in STATUS_OPTS else 0
            novo_st=c5.selectbox("",STATUS_OPTS,index=idx_st,
                key=f"st_{rid}",label_visibility="collapsed")
            novo_obs=c6.text_input("",value=row.get("obs","")or"",
                key=f"obs_{rid}",label_visibility="collapsed")
            # Edit save
            if novo_st!=row["status"] or novo_obs!=(row.get("obs","")or""):
                sb_update_lanc(rid,status=novo_st,obs=novo_obs)
                st.rerun()
            # Delete com confirmação dupla
            with c7:
                if btn_delete(f"lanc_{rid}"):
                    sb_delete_lanc(rid); st.rerun()

# ── PÁGINA: DEPÓSITOS ──────────────────────────────────────────
def page_depositos(u:str):
    hoje=date.today()
    st.title("💵 Depósitos (Receitas)")
    tabs=st.tabs([MESES_ABBR[m] for m in range(1,13)])
    for idx,tab in enumerate(tabs):
        m=idx+1
        with tab:
            _render_mes_depositos(u,hoje.year,m,hoje)

def _render_mes_depositos(u:str,ano:int,mes:int,hoje:date):
    dep=sb_get_dep(u,ano,mes)
    total=sum(float(d["valor"]) for d in dep)
    st.metric(f"💰 Total de Receitas — {MESES_PT[mes]}",f"R$ {total:,.2f}")

    with st.expander("➕ Novo Depósito"):
        with st.form(f"f_dep_{mes}",clear_on_submit=True):
            c1,c2=st.columns(2)
            dt=c1.date_input("Data",value=hoje if mes==hoje.month else date(ano,mes,1))
            val=c2.number_input("Valor (R$)",min_value=0.0,value=0.0,step=100.0,format="%.2f")
            desc=st.text_input("Descrição / Histórico")
            if st.form_submit_button("Adicionar Depósito",use_container_width=True,type="primary"):
                if val>0:
                    sb_add_dep(u,dt,val,desc); st.success("Depósito registrado!"); st.rerun()
                else:
                    st.warning("Informe um valor maior que zero.")

    if not dep:
        st.info(f"Nenhum depósito em {MESES_PT[mes]}."); return

    df=pd.DataFrame(dep)
    df["data_d"]=pd.to_datetime(df["data"]).dt.date
    df=df.sort_values("data_d")
    hcols=st.columns([2,5,2.5,0.8])
    for hc,ht in zip(hcols,["Data","Descrição","Valor",""]):
        hc.markdown(f"<div class='col-header'>{ht}</div>",unsafe_allow_html=True)
    for _,row in df.iterrows():
        rid=int(row["id"])
        c1,c2,c3,c4=st.columns([2,5,2.5,0.8])
        c1.write(row["data_d"].strftime("%d/%m/%Y"))
        c2.write(row.get("descricao")or"—")
        c3.write(f"R$ {float(row['valor']):,.2f}")
        with c4:
            if btn_delete(f"dep_{rid}"):
                sb_delete_dep(rid); st.rerun()

# ── PÁGINA: METAS ──────────────────────────────────────────────
def page_metas(u:str):
    hoje=date.today()
    am=ym(hoje)
    st.title("🎯 Metas de Economia")
    st.subheader(f"Meta de {MESES_PT[hoje.month]} / {hoje.year}")

    info=sb_get_meta(u,am)
    meta_val=float(info.get("meta",0))
    guard_val=float(info.get("guardado",0))

    c1,c2,c3=st.columns(3)
    nova_meta=c1.number_input("Meta (R$)",value=meta_val,min_value=0.0,step=100.0,format="%.2f")
    add_val=c2.number_input("Valor a Guardar (R$)",value=0.0,min_value=0.0,step=100.0,format="%.2f")
    b1,b2=c3.columns(2)
    if b1.button("💾 Salvar",use_container_width=True):
        sb_upsert_meta(u,am,meta=nova_meta); st.success("Meta salva!"); st.rerun()
    if b2.button("✅ Guardar",use_container_width=True):
        if add_val>0:
            sb_upsert_meta(u,am,add=add_val)
            st.success(f"R$ {add_val:,.2f} adicionado!"); st.rerun()

    if nova_meta>0:
        p=min(guard_val/nova_meta,1.0)
        st.progress(p,text=f"R$ {guard_val:,.2f} / R$ {nova_meta:,.2f}  •  {p*100:.1f}%")

    st.divider()
    st.subheader(f"📊 Progresso por Mês — {hoje.year}")
    metas={"".join(m["ano_mes"].split("-")[1:]):m for m in sb_get_metas_ano(u,hoje.year)}
    cols=st.columns(4)
    total_ano=meta_ano=0.0
    for i,m in enumerate(range(1,13)):
        key=f"{m:02d}"
        inf=metas.get(key,{"meta":0.0,"guardado":0.0})
        mv,gv=float(inf.get("meta",0)),float(inf.get("guardado",0))
        total_ano+=gv; meta_ano+=mv
        with cols[i%4]:
            if mv>0:
                st.metric(MESES_ABBR[m],f"R$ {gv:,.2f}",f"de R$ {mv:,.2f}")
                st.progress(min(gv/mv,1.0))
            else:
                st.metric(MESES_ABBR[m],"Sem meta","")
    st.divider()
    st.subheader(f"🏆 Total guardado em {hoje.year}: R$ {total_ano:,.2f}")
    if meta_ano>0:
        st.progress(min(total_ano/meta_ano,1.0),
            text=f"{min(total_ano/meta_ano,1.0)*100:.1f}%  (R$ {total_ano:,.2f} / R$ {meta_ano:,.2f})")

# ── PÁGINA: CONFIGURAÇÕES ──────────────────────────────────────
def page_config(u:str):
    hoje=date.today()
    st.title("⚙️ Configurações")
    st.subheader("🔐 Alterar Senha")
    with st.form("f_pw"):
        pw_atual=st.text_input("Senha Atual",type="password")
        pw_nova=st.text_input("Nova Senha",type="password")
        pw_conf=st.text_input("Confirmar Nova Senha",type="password")
        if st.form_submit_button("Alterar Senha",type="primary"):
            row=sb_get_user(u)
            if row and row["password_hash"]==_hash(pw_atual):
                if pw_nova==pw_conf and pw_nova:
                    sb_update_password(u,pw_nova); st.success("Senha alterada!")
                else: st.error("As senhas não coincidem ou estão vazias.")
            else: st.error("Senha atual incorreta.")

    st.divider()
    st.subheader("🗑️ Zona de Perigo")
    with st.expander("Apagar todos os dados do mês atual"):
        st.warning(f"Remove TODOS os lançamentos e depósitos de {MESES_PT[hoje.month]}/{hoje.year}. Irreversível.")
        confirmado=st.checkbox("Entendo que esta ação não pode ser desfeita")
        if confirmado:
            if btn_delete("del_mes_atual","🗑️ Confirmar Exclusão"):
                sb_delete_mes(u,hoje.year,hoje.month)
                st.success("Dados do mês apagados."); st.rerun()

# ── MAIN ───────────────────────────────────────────────────────
def main():
    st.session_state.setdefault("logged_in",False)
    if not st.session_state["logged_in"]:
        page_login()
        return
    routed=render_sidebar()
    u=st.session_state["username"]
    if   routed=="dashboard":    page_dashboard(u)
    elif routed=="lancamentos":  page_lancamentos(u)
    elif routed=="depositos":    page_depositos(u)
    elif routed=="metas":        page_metas(u)
    else:                        page_config(u)

if __name__=="__main__":
    main()
