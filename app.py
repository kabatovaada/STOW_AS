import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
from io import BytesIO
import os, glob, base64, requests

st.set_page_config(page_title="STOW AS Report", page_icon="📦", layout="wide")

# ─── CSS ─────────────────────────────────────────────
st.markdown("""
<style>
    .block-container {padding-top: 1.5rem; padding-bottom: 1rem;}
    div[data-testid="stMetric"] {background: #161B22; border: 1px solid #30363D; border-radius: 8px; padding: 12px 16px;}
    div[data-testid="stMetric"] label {color: #8B949E !important; font-size: 0.8rem !important;}
    div[data-testid="stMetric"] [data-testid="stMetricValue"] {color: #C9D1D9 !important;}
    .green-card {background: #1A7F37; border: 1px solid #238636; border-radius: 10px; padding: 24px; margin-bottom: 16px;}
    .green-card h1 {color: white; margin: 0; font-size: 3rem;}
    .green-card p {color: #C5E8D0; margin: 4px 0 0 0;}
    .info-bar {background: #262730; border: 1px solid #30363D; border-radius: 6px; padding: 8px 14px; margin-bottom: 12px; color: #8B949E; font-size: 0.85rem;}
    .section-title {color: #484F58; letter-spacing: 2px; font-size: 0.75rem; font-weight: 700; border-bottom: 1px solid #30363D; padding-bottom: 6px; margin: 20px 0 10px 0;}
    .type-badge {display: inline-block; padding: 2px 10px; border-radius: 4px; font-weight: 700; font-size: 0.75rem; color: white;}
    .card-metric {background: #161B22; border: 1px solid #30363D; border-radius: 8px; padding: 16px; text-align: center;}
</style>
""", unsafe_allow_html=True)

TYPE_COLORS = {"VGP": "#2EA043", "SP": "#6366F1", "VV": "#D29922", "REP": "#FF4B4B", "SKL": "#3FB950",
               "SKLSK": "#818CF8", "AATSKL": "#F97316", "AHUSKL": "#EC4899", "PRR": "#8B949E"}
TYPE_ORDER = ["VGP", "VV", "REP", "SP", "SKL"]

# ─── Persistence ─────────────────────────────────────
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)

def get_saved(prefix):
    files = glob.glob(os.path.join(DATA_DIR, f"{prefix}_*.xlsx"))
    if not files:
        files = glob.glob(os.path.join(DATA_DIR, f"{prefix}.xlsx"))
    return files[0] if files else None

def save_file(prefix, name, raw):
    for old in glob.glob(os.path.join(DATA_DIR, f"{prefix}*.xlsx")):
        os.remove(old)
    path = os.path.join(DATA_DIR, f"{prefix}_{name}")
    with open(path, "wb") as f:
        f.write(raw)
    commit_to_github(f"{prefix}_{name}", raw)
    return path

def commit_to_github(filename, raw_bytes):
    try:
        token = st.secrets["GITHUB_TOKEN"]
        repo = st.secrets["GITHUB_REPO"]
    except Exception:
        return
    api = f"https://api.github.com/repos/{repo}/contents/data/{filename}"
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github+json"}
    sha = None
    r = requests.get(api, headers=headers)
    if r.status_code == 200:
        sha = r.json().get("sha")
    payload = {"message": f"update {filename}", "content": base64.b64encode(raw_bytes).decode("utf-8")}
    if sha:
        payload["sha"] = sha
    requests.put(api, headers=headers, json=payload)

# ─── Parse ───────────────────────────────────────────
def parse(path):
    df = pd.read_excel(path, engine='openpyxl')
    df['doklad_type'] = df['Doklad'].astype(str).str.extract(r'^([A-Z]+)')

    # Operátor
    if 'Spustil' in df.columns:
        df['_op'] = df['Spustil']
        df['_op_label'] = 'Spustil'
    elif 'Potvrzovač' in df.columns:
        df['_op'] = df['Potvrzovač']
        df['_op_label'] = 'Potvrzovač'
    else:
        df['_op'] = 'N/A'
        df['_op_label'] = 'Operátor'

    # Sekcia
    if 'Zdroj.lokace' in df.columns:
        df['section'] = df['Zdroj.lokace'].astype(str).str.extract(r'^(\d+[A-Z]+)')
        df['floor'] = df['section'].astype(str).str[0]
        df['_loc_label'] = 'Zdroj.lokace'
    elif 'Stanice lokace' in df.columns:
        df['section'] = df['Stanice lokace'].astype(str)
        df['floor'] = df['section'].str.extract(r'^([A-Z]+)')
        df['_loc_label'] = 'Stanice lokace'
    else:
        df['section'] = 'N/A'
        df['floor'] = 'N/A'
        df['_loc_label'] = 'Sekcia'

    # Dátum
    df['_date'] = pd.NaT
    for col in ['BranchProcessingFinishTime', 'Konec Zpracování na Pob']:
        if col in df.columns:
            df['_date'] = pd.to_datetime(df[col], errors='coerce')
            break
    if df['_date'].isna().all():
        for col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                df['_date'] = df[col]
                break

    return df

# ─── Dashboard renderer ─────────────────────────────
def render_dashboard(df, title_suffix="", key_prefix="a"):
    total_jbl = len(df)
    if total_jbl == 0:
        st.warning("Žiadne dáta po filtrovaní.")
        return

    total_qty = int(df['Množství'].sum())
    op_label = df['_op_label'].iloc[0] if '_op_label' in df.columns else 'Operátor'
    loc_label = df['_loc_label'].iloc[0] if '_loc_label' in df.columns else 'Sekcia'

    # Obdobie
    try:
        d_min = df['_date'].dropna().min()
        d_max = df['_date'].dropna().max()
        obdobie = f" · Obdobie: <b>{d_min.strftime('%d.%m.%Y')}</b> – <b>{d_max.strftime('%d.%m.%Y')}</b>"
    except Exception:
        obdobie = ""

    st.markdown(f'<div class="info-bar">📂 {total_jbl:,} JBL · {total_qty:,} ks{obdobie}</div>', unsafe_allow_html=True)

    # ── Hero + KPIs ──────────────────────────────────
    c1, c2 = st.columns([5, 5])
    with c1:
        st.markdown(f"""
        <div class="green-card">
            <p style="font-size:0.8rem; letter-spacing:1px;">CELKOVÉ JBL{title_suffix}</p>
            <h1>{total_jbl:,}</h1>
            <p>{total_qty:,} kusov celkovo</p>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        m1, m2, m3 = st.columns(3)
        m1.metric("Unikátne doklady", f"{df['Doklad'].nunique():,}")
        m2.metric("Unikátne produkty", f"{df['Produkt'].nunique():,}")
        m3.metric(op_label, f"{df['_op'].nunique()}")
        m4, m5, m6 = st.columns(3)
        m4.metric("Priemer ks/JBL", f"{df['Množství'].mean():.1f}")
        m5.metric("Medián ks/JBL", f"{df['Množství'].median():.0f}")
        m6.metric("Max ks", f"{df['Množství'].max():,}")

    # ── Doklad breakdown ─────────────────────────────
    st.markdown('<div class="section-title">ROZDELENIE PODĽA TYPU DOKLADU</div>', unsafe_allow_html=True)

    type_counts = df['doklad_type'].value_counts()
    type_pcts = (type_counts / len(df) * 100).round(1)

    fig_bar = go.Figure()
    for t in type_counts.index:
        pct = type_pcts[t]
        fig_bar.add_trace(go.Bar(
            x=[pct], y=[""], orientation='h', name=t,
            marker_color=TYPE_COLORS.get(t, "#666"),
            text=f"{t} {pct}%", textposition='inside',
            textfont=dict(color='white', size=12),
            hovertemplate=f"{t}: {type_counts[t]:,} JBL ({pct}%)<extra></extra>"
        ))
    fig_bar.update_layout(barmode='stack', height=50, margin=dict(l=0,r=0,t=0,b=0),
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        showlegend=False, xaxis=dict(visible=False), yaxis=dict(visible=False))
    st.plotly_chart(fig_bar, use_container_width=True, config={'displayModeBar': False}, key=f"{key_prefix}_chart_1")

    # Type cards
    active_types = [t for t in type_counts.index if type_counts[t] > 0]
    cols = st.columns(min(len(active_types), 6))
    for i, t in enumerate(active_types[:6]):
        with cols[i]:
            grp = df[df['doklad_type'] == t]
            pct = len(grp) / len(df) * 100
            color = TYPE_COLORS.get(t, "#666")
            st.markdown(f"""
            <div style="background:#161B22; border:1px solid #30363D; border-top:3px solid {color}; border-radius:8px; padding:12px;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                    <span style="color:{color}; font-size:1.1rem; font-weight:700;">● {t}</span>
                    <span style="color:#8B949E; font-size:0.85rem;">{pct:.1f}%</span>
                </div>
                <div style="border-top:1px solid #30363D; padding-top:8px;">
                    <div style="display:flex; justify-content:space-between;"><span style="color:#8B949E; font-size:0.7rem;">JBL</span><span style="color:#C9D1D9; font-weight:700;">{len(grp):,}</span></div>
                    <div style="display:flex; justify-content:space-between;"><span style="color:#8B949E; font-size:0.7rem;">Doklady</span><span style="color:#C9D1D9; font-weight:700;">{grp['Doklad'].nunique():,}</span></div>
                    <div style="display:flex; justify-content:space-between;"><span style="color:#8B949E; font-size:0.7rem;">Množstvo</span><span style="color:#C9D1D9; font-weight:700;">{int(grp['Množství'].sum()):,}</span></div>
                    <div style="display:flex; justify-content:space-between;"><span style="color:#8B949E; font-size:0.7rem;">Produkty</span><span style="color:#C9D1D9; font-weight:700;">{grp['Produkt'].nunique():,}</span></div>
                    <div style="display:flex; justify-content:space-between;"><span style="color:#8B949E; font-size:0.7rem;">{op_label}</span><span style="color:#C9D1D9; font-weight:700;">{grp['_op'].nunique()}</span></div>
                </div>
            </div>
            """, unsafe_allow_html=True)

    # ── Operátori ────────────────────────────────────
    st.markdown(f'<div class="section-title">{op_label.upper()} – TOP 15</div>', unsafe_allow_html=True)

    top_ops = df.groupby('_op').agg(
        jbl=('Doklad', 'count'), qty=('Množství', 'sum'),
        dok=('Doklad', 'nunique'), prod=('Produkt', 'nunique')
    ).sort_values('jbl', ascending=False).head(15).reset_index()
    top_ops['ratio'] = (top_ops['qty'] / top_ops['jbl']).round(1)

    dom_type = df.groupby(['_op', 'doklad_type']).size().reset_index(name='cnt')
    dom_type = dom_type.loc[dom_type.groupby('_op')['cnt'].idxmax()][['_op', 'doklad_type', 'cnt']]
    top_ops = top_ops.merge(dom_type, on='_op', how='left')

    c1, c2 = st.columns([6, 4])
    with c1:
        top_rev = top_ops.iloc[::-1]
        fig_ops = go.Figure()
        fig_ops.add_trace(go.Bar(
            x=top_rev['jbl'], y=top_rev['_op'].str.split(' ').str[0],
            orientation='h', marker_color='#2EA043',
            text=top_rev['jbl'].apply(lambda x: f"{x:,}"),
            textposition='outside', textfont=dict(color='#3FB950', size=11),
            hovertemplate='%{y}: %{x:,} JBL<extra></extra>'
        ))
        fig_ops.update_layout(height=450, margin=dict(l=0,r=40,t=10,b=10),
            paper_bgcolor='#161B22', plot_bgcolor='#161B22',
            xaxis=dict(showgrid=False, visible=False, range=[0, top_ops['jbl'].max()*1.2]),
            yaxis=dict(showgrid=False, tickfont=dict(color='#C9D1D9', size=11)),
            font=dict(color='#C9D1D9'))
        st.plotly_chart(fig_ops, use_container_width=True, config={'displayModeBar': False}, key=f"{key_prefix}_chart_2")

    with c2:
        st.markdown(f"**JBL vs Množstvo – Top 5**")
        for _, row in top_ops.head(5).iterrows():
            short = row['_op'].split(' ')[0] if isinstance(row['_op'], str) else '?'
            st.markdown(f"""
            <div style="background:#161B22; border:1px solid #30363D; border-radius:6px; padding:8px 12px; margin-bottom:6px;">
                <div style="display:flex; justify-content:space-between;">
                    <span style="color:#C9D1D9; font-weight:600;">{short}</span>
                    <span style="color:#3FB950;">{row['jbl']:,} JBL</span>
                </div>
                <div style="display:flex; justify-content:space-between;">
                    <span style="color:#484F58;">⌀ {row['ratio']} ks/JBL</span>
                    <span style="color:#8B949E;">{int(row['qty']):,} ks</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("**Dominantný typ dokladu**")
        for _, row in top_ops.head(10).iterrows():
            short = row['_op'].split(' ')[0] if isinstance(row['_op'], str) else '?'
            dt = row['doklad_type'] if pd.notna(row['doklad_type']) else '?'
            dc = TYPE_COLORS.get(dt, '#666')
            st.markdown(f"""
            <div style="display:flex; align-items:center; gap:8px; padding:3px 0;">
                <span style="color:#C9D1D9; width:100px; font-size:0.85rem;">{short}</span>
                <span class="type-badge" style="background:{dc};">{dt}</span>
                <span style="color:#8B949E; font-size:0.85rem;">{int(row['cnt']):,}</span>
            </div>
            """, unsafe_allow_html=True)

    # ── Množstvo ─────────────────────────────────────
    st.markdown('<div class="section-title">ANALÝZA MNOŽSTVA</div>', unsafe_allow_html=True)
    c1, c2 = st.columns([5, 5])

    with c1:
        bins = [0, 1, 5, 20, 100, float('inf')]
        labels_q = ['1 ks', '2–5 ks', '6–20 ks', '21–100 ks', '100+ ks']
        colors_q = ['#2EA043', '#6366F1', '#D29922', '#FF4B4B', '#F85149']
        df_q = df.copy()
        df_q['bucket'] = pd.cut(df_q['Množství'], bins=bins, labels=labels_q, right=True)
        bucket_counts = df_q['bucket'].value_counts().reindex(labels_q)

        fig_dist = go.Figure()
        for i, (lbl, cnt) in enumerate(bucket_counts.items()):
            if pd.isna(cnt): cnt = 0
            pct = cnt / len(df) * 100
            fig_dist.add_trace(go.Bar(x=[pct], y=[lbl], orientation='h',
                marker_color=colors_q[i], text=f"{pct:.1f}% · {cnt:,} JBL", textposition='inside',
                textfont=dict(color='white', size=11)))
        fig_dist.update_layout(height=300, margin=dict(l=0,r=0,t=10,b=10), barmode='stack',
            paper_bgcolor='#161B22', plot_bgcolor='#161B22', showlegend=False,
            xaxis=dict(visible=False), yaxis=dict(tickfont=dict(color='#C9D1D9', size=12), autorange='reversed'))
        st.plotly_chart(fig_dist, use_container_width=True, config={'displayModeBar': False}, key=f"{key_prefix}_chart_3")

    with c2:
        st.markdown("**Množstvo podľa typu dokladu**")
        qty_stats = df.groupby('doklad_type')['Množství'].agg(['mean', 'median', 'max', 'sum']).round(1)
        qty_stats.columns = ['Priemer', 'Medián', 'Max', 'Celkom']
        qty_stats['Celkom'] = qty_stats['Celkom'].astype(int)
        qty_stats['Max'] = qty_stats['Max'].astype(int)
        qty_stats['Medián'] = qty_stats['Medián'].astype(int)
        st.dataframe(qty_stats, use_container_width=True, key=f"{key_prefix}_df_4")

    # ── Sekcie / Stanice ─────────────────────────────
    st.markdown(f'<div class="section-title">{loc_label.upper()}</div>', unsafe_allow_html=True)
    c1, c2 = st.columns([5, 5])

    with c1:
        sec_counts = df['section'].value_counts().head(15)
        sec_df = sec_counts.reset_index()
        sec_df.columns = ['section', 'count']

        fig_sec = go.Figure()
        sec_rev = sec_df.iloc[::-1]
        fig_sec.add_trace(go.Bar(x=sec_rev['count'], y=sec_rev['section'],
            orientation='h', marker_color='#2EA043',
            text=sec_rev['count'].apply(lambda x: f"{x:,}"),
            textposition='outside', textfont=dict(size=10, color='#C9D1D9')))
        fig_sec.update_layout(height=400, margin=dict(l=0,r=40,t=10,b=10),
            paper_bgcolor='#161B22', plot_bgcolor='#161B22',
            xaxis=dict(showgrid=False, visible=False, range=[0, sec_counts.max()*1.15]),
            yaxis=dict(tickfont=dict(color='#C9D1D9', size=11)))
        st.plotly_chart(fig_sec, use_container_width=True, config={'displayModeBar': False}, key=f"{key_prefix}_chart_5")

    with c2:
        st.markdown("**Doklad × Sekcia/Stanica**")
        for t in df['doklad_type'].value_counts().head(6).index:
            grp = df[df['doklad_type'] == t]
            top3 = grp['section'].value_counts().head(3)
            dc = TYPE_COLORS.get(t, '#666')
            items = " · ".join([f"{s} ({c})" for s, c in top3.items()])
            st.markdown(f"""
            <div style="background:#161B22; border-left:3px solid {dc}; border-radius:0 6px 6px 0; padding:8px 12px; margin-bottom:6px;">
                <span style="color:{dc}; font-weight:700;">● {t}</span>
                <div style="color:#8B949E; font-size:0.8rem; margin-top:4px;">{items}</div>
            </div>
            """, unsafe_allow_html=True)

    # ── Produkty ─────────────────────────────────────
    st.markdown('<div class="section-title">TOP 15 PRODUKTOV</div>', unsafe_allow_html=True)
    c1, c2 = st.columns([6, 4])

    with c1:
        top_prod = df['Produkt'].value_counts().head(15).reset_index()
        top_prod.columns = ['Produkt', 'count']
        prod_type = df.groupby(['Produkt', 'doklad_type']).size().reset_index(name='cnt')
        prod_type = prod_type.loc[prod_type.groupby('Produkt')['cnt'].idxmax()][['Produkt', 'doklad_type']]
        top_prod = top_prod.merge(prod_type, on='Produkt', how='left')
        top_prod['color'] = top_prod['doklad_type'].map(TYPE_COLORS).fillna('#666')

        fig_prod = go.Figure()
        tp_rev = top_prod.iloc[::-1]
        fig_prod.add_trace(go.Bar(x=tp_rev['count'], y=tp_rev['Produkt'],
            orientation='h', marker_color=tp_rev['color'],
            text=tp_rev['count'].apply(lambda x: f"{x:,}"),
            textposition='outside', textfont=dict(color='#D29922', size=11)))
        fig_prod.update_layout(height=450, margin=dict(l=0,r=40,t=10,b=10),
            paper_bgcolor='#161B22', plot_bgcolor='#161B22',
            xaxis=dict(showgrid=False, visible=False, range=[0, top_prod['count'].max()*1.2]),
            yaxis=dict(tickfont=dict(color='#C9D1D9', size=10)))
        st.plotly_chart(fig_prod, use_container_width=True, config={'displayModeBar': False}, key=f"{key_prefix}_chart_6")

    with c2:
        st.markdown("**Top 3 produkty podľa typu**")
        for t in df['doklad_type'].value_counts().head(5).index:
            grp = df[df['doklad_type'] == t]
            top3 = grp['Produkt'].value_counts().head(3)
            dc = TYPE_COLORS.get(t, '#666')
            items = " · ".join([f"{p} ({c})" for p, c in top3.items()])
            st.markdown(f"""
            <div style="background:#161B22; border-left:3px solid {dc}; border-radius:0 6px 6px 0; padding:8px 12px; margin-bottom:6px;">
                <span style="color:{dc}; font-weight:700;">● {t}</span>
                <div style="color:#8B949E; font-size:0.8rem; margin-top:4px;">{items}</div>
            </div>
            """, unsafe_allow_html=True)

    # ── Raw data ─────────────────────────────────────
    with st.expander("📋 Zobraziť surové dáta", key=f"{key_prefix}_exp"):
        st.dataframe(df, use_container_width=True, height=400, key=f"{key_prefix}_df_8")
        st.download_button("⬇ CSV", df.to_csv(index=False).encode('utf-8'), "stow_filtered.csv", "text/csv", key=f"{key_prefix}_dl_9")


# ═════════════════════════════════════════════════════
# SIDEBAR
# ═════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("### ⚙ Parametre")

    st.markdown("**📥 Prijímanie (Spustil)**")
    up1 = st.file_uploader("STOW AS Report", type=["xlsx"], key="up1")
    if up1 is not None:
        save_file("STOW", up1.name, up1.getvalue())

    st.markdown("**📥 Potvrdzovanie (Potvrzovač)**")
    up2 = st.file_uploader("STOW AS Report 2", type=["xlsx"], key="up2")
    if up2 is not None:
        save_file("CONFIRM", up2.name, up2.getvalue())

    # Load saved files
    f1 = get_saved("STOW")
    f2 = get_saved("CONFIRM")

    if f1:
        st.success(f"✅ Prijímanie: {os.path.basename(f1)}")
    if f2:
        st.success(f"✅ Potvrdzovanie: {os.path.basename(f2)}")

    if not f1 and not f2:
        st.info("Nahraj aspoň jeden STOW AS Report")
        st.stop()

    # Parse both
    df1 = parse(f1) if f1 else pd.DataFrame()
    df2 = parse(f2) if f2 else pd.DataFrame()

    st.divider()
    if st.button("🗑 Odstrániť všetky súbory"):
        for old in glob.glob(os.path.join(DATA_DIR, "*.xlsx")):
            os.remove(old)
        st.rerun()

# ═════════════════════════════════════════════════════
# MAIN – TABS
# ═════════════════════════════════════════════════════
st.markdown("# 📦 STOW AS Report")

tabs = []
tab_names = []
if len(df1) > 0:
    tab_names.append(f"📥 Prijímanie ({len(df1):,} JBL)")
if len(df2) > 0:
    tab_names.append(f"✅ Potvrdzovanie ({len(df2):,} JBL)")

if len(tab_names) == 2:
    tab1, tab2 = st.tabs(tab_names)
    with tab1:
        render_dashboard(df1, " · PRIJÍMANIE", key_prefix="stow")
    with tab2:
        render_dashboard(df2, " · POTVRDZOVANIE", key_prefix="conf")
elif len(df1) > 0:
    render_dashboard(df1, " · PRIJÍMANIE", key_prefix="stow")
else:
    render_dashboard(df2, " · POTVRDZOVANIE", key_prefix="conf")
