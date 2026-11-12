"""
Multifraktal Finansal Analiz Platformu
  1) Muzy, Sornette, Delour, Arneodo (2001) hiyerarşik portföy modeli
     Markowitz etkin sınırı -> P1/P2/P10 -> lambda^2 -> C4 -> a, w*, a* -> geçerlilik
  2) MFDFA (h(q), tau(q), f(alpha)) + karıştırılmış (shuffle) seri testi
Günlük birimler: tau gün, T (integral ölçek) gün.
  C4(günlük) = -12 s^4 L^2 tau ln(tau/T) [+ 16 s^6 tau^2 ihmal edilen log-normal terim]
"""
import io
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from scipy.optimize import brentq, minimize

st.set_page_config(page_title="Multifraktal Portföy Analizi", page_icon="📈", layout="wide")
CFG = {"toImageButtonOptions": {"format": "png", "scale": 3}, "displaylogo": False}
COLORS = ["#1f77b4", "#d62728", "#2ca02c", "#ff7f0e", "#9467bd", "#8c564b", "#e377c2", "#17becf"]


# ───────────────────────── VERİ ─────────────────────────
def to_num(s):
    if s.dtype.kind in "fi":
        return s.astype(float)
    x = s.astype(str).str.strip().str.replace(r"[^\d,.\-eE]", "", regex=True)
    both = x.str.contains(",", regex=False) & x.str.contains(".", regex=False)
    x = x.where(~both, x.str.replace(".", "", regex=False))
    x = x.str.replace(",", ".", regex=False)
    return pd.to_numeric(x, errors="coerce")


@st.cache_data(show_spinner=False)
def load_table(name, raw):
    if name.lower().endswith((".xlsx", ".xls")):
        return pd.read_excel(io.BytesIO(raw))
    for enc in ("utf-8-sig", "cp1254", "latin-1"):
        try:
            return pd.read_csv(io.BytesIO(raw), sep=None, engine="python", encoding=enc)
        except Exception:
            continue
    raise ValueError("Dosya okunamadı")


@st.cache_data(show_spinner=False)
def demo_data(n=3136, k=10, seed=7):
    rng = np.random.default_rng(seed)

    def ar(phi, s):
        e, x = rng.normal(0, s, n), np.zeros(n)
        for t in range(1, n):
            x[t] = phi * x[t - 1] + e[t]
        return x
    f, common, out = rng.normal(0, 1, n), ar(0.985, 0.12), {}
    for j in range(k):
        vol = 0.014 * np.exp(0.6 * common + 0.4 * ar(0.98, 0.10))
        r = np.clip(0.0018 + vol * (0.5 * f + 0.866 * rng.normal(0, 1, n)), -0.15, 0.15)
        out[f"DEMO{j + 1}"] = 100 * np.cumprod(1 + r)
    df = pd.DataFrame(out)
    df.insert(0, "Tarih", pd.bdate_range(end="2026-11-12", periods=n))
    return df


def prepare(df, date_col, kind):
    d = df.copy()
    if date_col != "(yok)":
        d[date_col] = pd.to_datetime(d[date_col], dayfirst=True, errors="coerce")
        d = d.dropna(subset=[date_col]).sort_values(date_col).set_index(date_col)
    num = pd.DataFrame({c: to_num(d[c]) for c in d.columns if c != date_col})
    num = num.loc[:, num.notna().mean() > 0.5]
    if kind == "Fiyat":
        ret = num.where(num > 0).pct_change(fill_method=None)
    elif kind == "Getiri (%)":
        ret = num / 100
    else:
        ret = num
    return ret.replace([np.inf, -np.inf], np.nan).dropna(how="all")


# ───────────────────────── MARKOWITZ ─────────────────────────
def gmv_w(V):
    Vi, one = np.linalg.pinv(V), np.ones(len(V))
    return Vi @ one / (one @ Vi @ one)


def target_w(R, V, r):  # KOD TEZ: w = g V^-1 1 + h V^-1 R
    Vi, one = np.linalg.pinv(V), np.ones(len(R))
    A, B, C = one @ Vi @ one, one @ Vi @ R, R @ Vi @ R
    dl = A * C - B ** 2
    return ((C - B * r) / dl) * (Vi @ one) + ((A * r - B) / dl) * (Vi @ R)


def long_only_w(R, V, r=None):
    n = len(R)
    cons = [{"type": "eq", "fun": lambda w: w.sum() - 1}]
    if r is not None:
        cons.append({"type": "eq", "fun": lambda w: w @ R - r})
    res = minimize(lambda w: w @ V @ w, np.ones(n) / n, bounds=[(0, 1)] * n,
                   constraints=cons, method="SLSQP", options={"maxiter": 500})
    return res.x


def get_w(R, V, r, short):
    if r is None:
        return gmv_w(V) if short else long_only_w(R, V)
    return target_w(R, V, r) if short else long_only_w(R, V, float(np.clip(r, R.min(), R.max())))


# ───────────────────────── MULTİFRAKTAL PARAMETRELER ─────────────────────────
def est_lambda2(r, method, lmin, lmax):
    """lambda^2 tahmini. Kovaryans: Cov(ln|eta(t+dt)|, ln|eta(t)|) = -lambda^2 ln(dt/T)."""
    eta = np.log1p(np.asarray(r, float))
    if method.startswith("Kovaryans"):
        w = np.full(len(eta), np.nan)
        nz = np.abs(eta) > 1e-12
        w[nz] = np.log(np.abs(eta[nz]))
        lags = np.unique(np.round(np.geomspace(lmin, lmax, 30)).astype(int))
        xs, ys = [], []
        for L in lags:
            a, b = w[L:], w[:-L]
            m = np.isfinite(a) & np.isfinite(b)
            if m.sum() > 30:
                xs.append(np.log(L))
                ys.append(np.mean(a[m] * b[m]) - a[m].mean() * b[m].mean())
        xs, ys = np.array(xs), np.array(ys)
        sl, ic = np.polyfit(xs, ys, 1)
        r2 = 1 - ((ys - (sl * xs + ic)) ** 2).sum() / ((ys - ys.mean()) ** 2).sum()
        lam2 = -sl
        T_est = float(np.exp(ic / lam2)) if lam2 > 0 else np.nan
        return dict(lam2=lam2, T_est=T_est, r2=r2, x=xs, y=ys, fit=sl * xs + ic, kind="cov")
    # zeta(q) yöntemi: zeta(q) = h q - lambda^2 q^2 / 2
    qs = np.arange(1, 5.01, 0.5)
    scales = np.unique(np.geomspace(1, 64, 12).astype(int))
    lnM = np.zeros((len(qs), len(scales)))
    for j, s in enumerate(scales):
        n = len(eta) // s
        ag = eta[:n * s].reshape(n, s).sum(1)
        ag = np.abs(ag - ag.mean())
        ag = ag[ag > 0]
        for i, q in enumerate(qs):
            lnM[i, j] = np.log(np.mean(ag ** q))
    zeta = np.array([np.polyfit(np.log(scales), lnM[i], 1)[0] for i in range(len(qs))])
    c = np.polyfit(qs, zeta, 2)
    lam2 = -2 * c[0]
    r2 = 1 - ((zeta - np.polyval(c, qs)) ** 2).sum() / ((zeta - zeta.mean()) ** 2).sum()
    return dict(lam2=lam2, T_est=np.nan, r2=r2, x=qs, y=zeta, fit=np.polyval(c, qs), kind="zeta", h=c[1])


def c4_terms(sig, lam2, ratio, T):
    tau = ratio * T
    L = np.log(ratio)
    mf = -12 * sig ** 4 * lam2 * tau * L
    ln_ = 16 * sig ** 6 * tau ** 2
    vr = (4 / 3) * sig ** 2 * tau / (lam2 * abs(L)) if lam2 > 0 else np.inf
    return tau, mf, ln_, vr


def tau_star(sig, lam2, T):
    if lam2 <= 0:
        return 0.0
    f = lambda t: (4 / 3) * sig ** 2 * t - lam2 * abs(np.log(t / T))
    try:
        return brentq(f, 1e-6, T * (1 - 1e-9))
    except Exception:
        return np.nan


def mix_rows(a_list, sig, c1, mu0, c4m, lam2):
    dl = c1 - mu0
    rows = []
    for a in a_list:
        w = (a * dl / (4 * c4m)) ** (1 / 3) if dl > 0 and c4m > 0 else 0.0
        rows.append({"a": a, "γ=(24/a)^(1/3)": (24 / a) ** (1 / 3), "w* (riskli pay)": w,
                     "Nakit payı": 1 - w, "C1 günlük": mu0 + w * dl, "C1 yıllık (basit)": (mu0 + w * dl) * 252,
                     "σ günlük": w * sig, "C4 günlük": w ** 4 * c4m, "Sharpe": dl / sig if sig > 0 else np.nan,
                     "λ²": lam2})
    return pd.DataFrame(rows)


def show(df, sci=(), pct=(), h=None):
    cc = {}
    for c in df.columns:
        if c in sci:
            cc[c] = st.column_config.NumberColumn(c, format="%.3e")
        elif c in pct:
            cc[c] = st.column_config.NumberColumn(c, format="%.2f%%")
    kw = {"height": h} if h else {}
    st.dataframe(df, width="stretch", column_config=cc, **kw)


# ───────────────────────── MFDFA ─────────────────────────
@st.cache_data(show_spinner=False)
def mfdfa(x, q_list, scales, order=1):
    prof = np.cumsum(x - np.mean(x))
    N = len(prof)
    F = np.full((len(q_list), len(scales)), np.nan)
    for i, s in enumerate(scales):
        ns = N // s
        if ns < 4:
            continue
        segs = np.vstack([prof[:ns * s].reshape(ns, s), prof[N - ns * s:].reshape(ns, s)])
        V = np.vander(np.arange(s), order + 1)
        coef = np.linalg.lstsq(V, segs.T, rcond=None)[0]
        var = np.mean((segs - (V @ coef).T) ** 2, axis=1)
        var = var[var > 0]
        for j, q in enumerate(q_list):
            F[j, i] = np.exp(0.5 * np.mean(np.log(var))) if abs(q) < 1e-8 else np.mean(var ** (q / 2)) ** (1 / q)
    ls, hq, r2 = np.log(scales), [], []
    for j in range(len(q_list)):
        ok = np.isfinite(F[j]) & (F[j] > 0)
        if ok.sum() > 2:
            sl, ic = np.polyfit(ls[ok], np.log(F[j, ok]), 1)
            res = np.log(F[j, ok]) - (sl * ls[ok] + ic)
            hq.append(sl)
            r2.append(1 - (res ** 2).sum() / ((np.log(F[j, ok]) - np.log(F[j, ok]).mean()) ** 2).sum())
        else:
            hq.append(np.nan)
            r2.append(np.nan)
    hq, q = np.array(hq), np.array(q_list)
    tq = q * hq - 1
    al = np.gradient(tq, q)
    return F, pd.DataFrame({"q": q, "h(q)": hq, "τ(q)": tq, "α": al, "f(α)": q * al - tq, "R²": r2})


# ═════════════════════════ ARAYÜZ ═════════════════════════
st.title("📈 Multifraktal Finans Piyasaları Analiz Platformu")
st.caption("Muzy–Sornette–Delour–Arneodo (2001) hiyerarşik portföy modeli + MFDFA")

with st.sidebar:
    st.header("⚙️ Genel Ayarlar")
    up = st.file_uploader("Fiyat/getiri dosyası (CSV / Excel)", type=["csv", "xlsx", "xls"])
    st.caption("Biçim: ilk sütun tarih, diğerleri hisse kapanış fiyatları (geniş tablo). 1.234,56 gibi Türkçe sayılar desteklenir.")
    kind = st.selectbox("Veri türü", ["Fiyat", "Getiri (ondalık)", "Getiri (%)"])
    T = st.number_input("T: integral ölçek (iş günü)", 20, 2000, 252)
    taus_txt = st.text_input("Yatırım ufukları τ/T", "0.20, 0.50, 0.70, 0.90")
    short = st.checkbox("Açığa satışa izin ver", True)
    st.subheader("λ² tahmini")
    method = st.selectbox("Yöntem", ["Kovaryans (denklem 23)", "ζ(q) parabolü (denklem 17)"])
    lmin, lmax = st.slider("Gecikme aralığı (gün)", 1, 500, (2, 120))
    st.subheader("Etkin sınır portföyleri")
    st.caption("P1 = minimum varyans. Pk = P1 ile üst getiri arasında eşit aralıklı ızgaranın k. noktası.")
    ngrid = st.number_input("Izgara nokta sayısı", 3, 50, 10)
    pk_txt = st.text_input("Portföyler (k)", "2, 10")
    top_ret = st.number_input("Izgara üst getirisi (günlük %, 0 = en yüksek hisse ortalaması)", 0.0, 10.0, 0.0, 0.01)
    custom_txt = st.text_input("Özel hedef getiriler (günlük %, virgülle)", "")
    st.subheader("Risk toleransı a")
    a_abs_txt = st.text_input("Mutlak a değerleri", "0.0001, 0.001, 0.01")
    a_frac_txt = st.text_input("a* çarpanları", "0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.2")


def parse_list(t, cast=float):
    out = []
    for p in t.replace(";", ",").split(","):
        try:
            out.append(cast(p.strip()))
        except Exception:
            pass
    return out


taus = [x for x in parse_list(taus_txt) if 0 < x < 1]
a_abs, a_frac = parse_list(a_abs_txt), parse_list(a_frac_txt)
if not taus:
    st.error("τ/T değerleri 0 ile 1 arasında olmalı.")
    st.stop()

if up is not None:
    raw_df = load_table(up.name, up.getvalue())
    st.success(f"Yüklendi: {up.name} ({len(raw_df)} satır, {raw_df.shape[1]} sütun)")
else:
    raw_df = demo_data()
    st.info("💡 Dosya yüklenmedi: SENTETİK DEMO veri gösteriliyor. Gerçek analiz için sol menüden kendi veri setinizi yükleyin.")

guess = next((c for c in raw_df.columns if str(c).lower() in ("tarih", "date", "time", "datetime", "dönem")), raw_df.columns[0])
dc = st.sidebar.selectbox("Tarih sütunu", ["(yok)"] + list(raw_df.columns), index=1 + list(raw_df.columns).index(guess))
ret = prepare(raw_df, dc, kind)
all_cols = list(ret.columns)

tabs = st.tabs(["📋 Veri & Sepetler", "💼 Portföyler", "🧬 λ² / Multifraktallik", "📉 C₄ & Ufuk",
                "🎚️ Risk toleransı (a)", "🔬 MFDFA", "📥 İndir"])

# ── Sekme 1: veri ve sepet tanımı
with tabs[0]:
    st.subheader("Sepet tanımı")
    sig_ = abs(hash(tuple(all_cols))) % 10**6  # veri değişince sepet seçimleri sıfırlansın
    nb = st.number_input("Sepet sayısı", 1, 4, 2)
    baskets = {}
    for i in range(nb):
        c1, c2, c3 = st.columns([1, 4, 1])
        nm = c1.text_input("Ad", f"Sepet {i + 1}", key=f"bn{i}")
        cols = c2.multiselect("Hisseler", all_cols, default=all_cols[5 * i:5 * i + 5], key=f"bc{i}_{sig_}")
        rf = c3.number_input("Yıllık risksiz getiri %", 0.0, 500.0, 35.0, 0.01, key=f"rf{i}")
        if len(cols) >= 2:
            baskets[nm] = (cols, rf / 100)
    c1, c2 = st.columns([1, 2])
    prev = raw_df.head(10).copy()
    if dc != "(yok)":
        prev[dc] = pd.to_datetime(prev[dc], dayfirst=True, errors="coerce").dt.strftime("%d.%m.%Y")
    c1.dataframe(prev, width="stretch", hide_index=True)
    if len(all_cols):
        fig = go.Figure()
        cum = (1 + ret[all_cols[:8]].fillna(0)).cumprod()
        for c in cum.columns:
            fig.add_trace(go.Scatter(x=cum.index, y=cum[c], name=c, mode="lines"))
        fig.update_layout(title="Kümülatif getiri (ilk 8 sütun)", template="plotly_white", height=330, margin=dict(t=40, b=10))
        c2.plotly_chart(fig, width="stretch", config=CFG)
    st.caption(f"{len(ret)} getiri günü · μ₀ = ln(1+rf)/T günlük (ekran çıktılarıyla uyumlu).")
    if not baskets:
        st.warning("En az 2 hisseli bir sepet tanımlayın.")
        st.stop()


# ── Analiz motoru
def analyze(name, cols, rf):
    X = ret[cols].dropna()
    R, V = X.mean().values, X.cov().values
    top = top_ret / 100 if top_ret > 0 else R.max()
    w1 = get_w(R, V, None, short)
    r1 = float(w1 @ R)
    grid = np.linspace(r1, max(top, r1 + 1e-9), int(ngrid))
    pf = {"P1": w1}
    for k in parse_list(pk_txt, int):
        if 2 <= k <= ngrid:
            pf[f"P{k}"] = get_w(R, V, grid[k - 1], short)
    for j, rr in enumerate(parse_list(custom_txt)):
        pf[f"Özel{j + 1}"] = get_w(R, V, rr / 100, short)
    fr = []
    for rr in np.linspace(r1, max(top, r1 * 1.0001), 40):
        w = get_w(R, V, rr, short)
        fr.append((float(np.sqrt(w @ V @ w)), float(w @ R)))
    mu0 = np.log1p(rf) / T
    P = {}
    for p, w in pf.items():
        s = X.values @ w
        lam = est_lambda2(s, method, lmin, lmax)
        P[p] = dict(w=w, c1=s.mean(), sig=s.std(ddof=1), lam=lam, lam2=max(lam["lam2"], 1e-9),
                    gross=np.abs(w).sum(), nshort=int((w < -1e-9).sum()))
    return dict(cols=cols, rf=rf, mu0=mu0, P=P, frontier=fr, n=len(X), R=R)


res = {n: analyze(n, c, r) for n, (c, r) in baskets.items()}

# özet tablolar
w_rows, sum_rows, h_rows, lam_rows = [], [], [], []
for bn, b in res.items():
    for pn, p in b["P"].items():
        w_rows.append({"Sepet": bn, "Portföy": pn, **dict(zip(b["cols"], p["w"] * 100))})
        sh = (p["c1"] - b["mu0"]) / p["sig"]
        sum_rows.append({"Sepet": bn, "Portföy": pn, "C1 günlük %": p["c1"] * 100, "C1 yıllık % (basit)": p["c1"] * 25200,
                         "σ günlük %": p["sig"] * 100, "λ²": p["lam"]["lam2"], "Sharpe": sh,
                         "Brüt pozisyon %": p["gross"] * 100, "Açık pozisyon sayısı": p["nshort"], "rf yıllık %": b["rf"] * 100})
        lam_rows.append({"Sepet": bn, "Portföy": pn, "λ²": p["lam"]["lam2"], "R²": p["lam"]["r2"],
                         "T tahmini (gün)": p["lam"]["T_est"], "Not": "λ²≤0: model dışı" if p["lam"]["lam2"] <= 0 else ""})
        ts = tau_star(p["sig"], p["lam2"], T)
        for r_ in taus:
            tau, mf, ln_, vr = c4_terms(p["sig"], p["lam2"], r_, T)
            dl = p["c1"] - b["mu0"]
            h_rows.append({"Sepet": bn, "Portföy": pn, "τ/T": r_, "τ (gün)": tau, "C4 (çok-ölçekli terim)": mf,
                           "C4 (iki terim)": mf + ln_, "İhmal/korunan oran": vr, "τ* (gün)": ts,
                           "a* (w*=1)": 4 * mf / dl if dl > 0 else np.nan,
                           "γ*": (24 / (4 * mf / dl)) ** (1 / 3) if dl > 0 else np.nan,
                           "Geçerlilik": "✅ geçerli" if vr < 1 else "⚠️ yorumlanamaz"})
W_df, S_df, L_df, H_df = map(pd.DataFrame, (w_rows, sum_rows, lam_rows, h_rows))

# ── Sekme 2: portföyler
with tabs[1]:
    st.subheader("Tam yatırım özeti")
    show(S_df, sci=())
    st.subheader("Ağırlıklar (%)  — negatif değer açığa satış")
    show(W_df)
    cA, cB = st.columns(2)
    for bn, b in res.items():
        fig = go.Figure()
        for i, (pn, p) in enumerate(b["P"].items()):
            fig.add_trace(go.Bar(x=b["cols"], y=p["w"] * 100, name=pn, marker_color=COLORS[i % 8]))
        fig.update_layout(barmode="group", title=f"{bn}: portföy ağırlıkları (%)", template="plotly_white", height=360)
        cA.plotly_chart(fig, width="stretch", config=CFG)
        fr = np.array(b["frontier"])
        fg = go.Figure(go.Scatter(x=fr[:, 0] * 100, y=fr[:, 1] * 100, mode="lines", name="Etkin sınır"))
        for i, (pn, p) in enumerate(b["P"].items()):
            fg.add_trace(go.Scatter(x=[p["sig"] * 100], y=[p["c1"] * 100], mode="markers+text", text=[pn],
                                    textposition="top center", marker=dict(size=11, color=COLORS[(i + 1) % 8]), name=pn))
        fg.update_layout(title=f"{bn}: Markowitz etkin sınırı", xaxis_title="σ günlük %", yaxis_title="C1 günlük %",
                         template="plotly_white", height=360)
        cB.plotly_chart(fg, width="stretch", config=CFG)

# ── Sekme 3: λ²
with tabs[2]:
    st.subheader("λ² (kesiklilik / aralıklılık) tahmini")
    st.caption("Kovaryans yönteminde eğim −λ², kesişimden ln T bulunur. λ², nakitle karıştırmada (sabit çarpan) değişmez.")
    show(L_df)
    cols_ = st.columns(2)
    k = 0
    for bn, b in res.items():
        for pn, p in b["P"].items():
            lm = p["lam"]
            fg = go.Figure()
            fg.add_trace(go.Scatter(x=lm["x"], y=lm["y"], mode="markers", name="veri"))
            fg.add_trace(go.Scatter(x=lm["x"], y=lm["fit"], mode="lines", name="doğrusal/parabolik uyum"))
            xt, yt = ("ln(Δt)", "Cov(ω(t+Δt), ω(t))") if lm["kind"] == "cov" else ("q", "ζ(q)")
            fg.update_layout(title=f"{bn} · {pn}: λ²={lm['lam2']:.4f}, R²={lm['r2']:.2f}", xaxis_title=xt, yaxis_title=yt,
                             template="plotly_white", height=300, margin=dict(t=40))
            cols_[k % 2].plotly_chart(fg, width="stretch", config=CFG)
            k += 1

# ── Sekme 4: C4 ve ufuk
with tabs[3]:
    st.subheader("Dördüncü kümülant C₄ ve yatırım ufku (tam yatırım, günlük)")
    st.warning("C₄ bir kuyruk-duyarlılık göstergesidir; kayıp olasılığı veya VaR değildir. 'İhmal/korunan oran' > 1 ise yaklaşık "
               "formül o ufukta güvenilmezdir; C₄'ün düşmesi riskin azaldığı anlamına gelmez.")
    show(H_df, sci=("C4 (çok-ölçekli terim)", "C4 (iki terim)"), h=420)
    for tab_name, val, fmt in [("C4 (çok-ölçekli terim)", "C₄ tablosu", True), ("a* (w*=1)", "a* tablosu", False),
                               ("İhmal/korunan oran", "Geçerlilik oranı", False)]:
        pv = H_df.pivot_table(index=["Sepet", "Portföy"], columns="τ/T", values=tab_name, sort=False)
        st.markdown(f"**{val}**")
        st.dataframe(pv.style.format("{:.3e}" if fmt else "{:.4g}"), width="stretch")
    xs = np.linspace(0.02, 0.98, 120)
    for bn, b in res.items():
        fg = go.Figure()
        for i, (pn, p) in enumerate(b["P"].items()):
            mf = [c4_terms(p["sig"], p["lam2"], x, T)[1] for x in xs]
            fl = [c4_terms(p["sig"], p["lam2"], x, T)[1] + c4_terms(p["sig"], p["lam2"], x, T)[2] for x in xs]
            fg.add_trace(go.Scatter(x=xs, y=mf, name=f"{pn} çok-ölçekli", line=dict(color=COLORS[i % 8])))
            fg.add_trace(go.Scatter(x=xs, y=fl, name=f"{pn} iki terim", line=dict(color=COLORS[i % 8], dash="dash")))
            ts = tau_star(p["sig"], p["lam2"], T) / T
            if np.isfinite(ts) and 0 < ts < 1:
                fg.add_vline(x=ts, line=dict(color=COLORS[i % 8], dash="dot"), annotation_text=f"{pn} τ*")
        fg.update_layout(title=f"{bn}: günlük C₄(τ/T)  (kesikli = ihmal edilen terim eklenmiş; noktalı dikey = τ*)",
                         xaxis_title="τ/T", yaxis_title="C₄", yaxis_type="log", template="plotly_white", height=420)
        st.plotly_chart(fg, width="stretch", config=CFG)
    fp = go.Figure(go.Scatter(x=xs, y=-xs * np.log(xs), mode="lines"))
    fp.add_vline(x=1 / np.e, line_dash="dot", annotation_text="1/e")
    fp.update_layout(title="φ(τ/T) = −(τ/T)·ln(τ/T)", template="plotly_white", height=300)
    st.plotly_chart(fp, width="stretch", config=CFG)

# ── Sekme 5: a
with tabs[4]:
    c1, c2, c3 = st.columns(3)
    bsel = c1.selectbox("Sepet", list(res))
    psel = c2.selectbox("Portföy", list(res[bsel]["P"]))
    tsel = c3.selectbox("τ/T", taus)
    b, p = res[bsel], res[bsel]["P"][psel]
    tau, mf, ln_, vr = c4_terms(p["sig"], p["lam2"], tsel, T)
    dl = p["c1"] - b["mu0"]
    if dl <= 0:
        st.error("Portföyün getirisi risksiz getirinin altında: riskli paya yatırım yapılmaz (a* tanımsız).")
    else:
        astar = 4 * mf / dl
        al = sorted(set(a_abs + [f * astar for f in a_frac]))
        mt = mix_rows(al, p["sig"], p["c1"], b["mu0"], mf, p["lam"]["lam2"])
        mt.insert(1, "a/a*", mt["a"] / astar)
        full_c4, full_c1 = mf, p["c1"]
        mt["C4 azalma % (tam yat.'a göre)"] = (1 - mt["C4 günlük"] / full_c4) * 100
        mt["C1 kaybı % (tam yat.'a göre)"] = (1 - (mt["C1 günlük"] - b["mu0"]) / dl) * 100
        st.markdown(f"a* = **{astar:.6f}** · γ* = **{(24 / astar) ** (1 / 3):.2f}** · τ = {tau:.1f} gün · "
                    f"{'✅ formül geçerli' if vr < 1 else '⚠️ formül bu ufukta güvenilmez'} (oran {vr:.2f})")
        show(mt, sci=("C4 günlük",))
        ax = np.linspace(1e-4, 1.5 * astar, 150)
        mm = mix_rows(ax, p["sig"], p["c1"], b["mu0"], mf, p["lam"]["lam2"])
        f1 = go.Figure()
        f1.add_trace(go.Scatter(x=ax / astar, y=mm["w* (riskli pay)"], name="w*"))
        f1.add_trace(go.Scatter(x=ax / astar, y=mm["Nakit payı"], name="Nakit"))
        f1.update_layout(title="Riskli pay ve nakit payı (a/a*)", template="plotly_white", height=340)
        f2 = go.Figure(go.Scatter(x=mm["C4 günlük"], y=mm["C1 günlük"] * 100, mode="lines"))
        f2.update_layout(title="C₁–C₄ etkin sınırı (a boyunca)", xaxis_title="C₄", yaxis_title="C₁ günlük %",
                         template="plotly_white", height=340)
        g1, g2 = st.columns(2)
        g1.plotly_chart(f1, width="stretch", config=CFG)
        g2.plotly_chart(f2, width="stretch", config=CFG)
        st.caption("w*>1 bölgesi kaldıraç demektir; kaldıraçlı serilerde sabit λ² varsayımı dikkatle yorumlanmalıdır. "
                   "a büyüdükçe γ düşer: a riskten kaçınma değil, getiriye verilen göreli ağırlıktır.")

# ── Sekme 6: MFDFA
with tabs[5]:
    st.subheader("MFDFA (ileri+geri segmentasyon, q=0 dahil)")
    src = st.selectbox("Seri", all_cols + [f"{bn}·{pn}" for bn, b in res.items() for pn in b["P"]])
    if "·" in src and src not in all_cols:
        bn_, pn_ = src.split("·")
        Xb = ret[res[bn_]["cols"]].dropna()
        series = Xb.values @ res[bn_]["P"][pn_]["w"]
    else:
        series = ret[src].dropna().values
    series = np.asarray(series, float)
    c1, c2, c3, c4 = st.columns(4)
    qmin, qmax = c1.number_input("q min", value=-4.0), c2.number_input("q max", value=4.0)
    qstep = c3.number_input("q adım", 0.1, 2.0, 0.5)
    order = c4.selectbox("Trend derecesi", [1, 2, 3])
    s1, s2 = st.slider("Ölçek aralığı", 5, max(60, len(series) // 4), (10, max(40, len(series) // 10)))
    if st.button("🚀 MFDFA çalıştır", type="primary"):
        q = np.round(np.arange(qmin, qmax + qstep / 2, qstep), 6)
        sc = np.unique(np.geomspace(s1, s2, 18).astype(int)).astype(float)
        sc = sc.astype(int)
        F, df_o = mfdfa(series, q, sc, order)
        rng = np.random.default_rng(0)
        F2, df_sh = mfdfa(rng.permutation(series), q, sc, order)
        st.session_state["mf"] = (q, sc, F, df_o, df_sh)
    if "mf" in st.session_state:
        q, sc, F, df_o, df_sh = st.session_state["mf"]
        dh, dhs = np.nanmax(df_o["h(q)"]) - np.nanmin(df_o["h(q)"]), np.nanmax(df_sh["h(q)"]) - np.nanmin(df_sh["h(q)"])
        da = np.nanmax(df_o["α"]) - np.nanmin(df_o["α"])
        a0 = df_o["α"].iloc[int(np.nanargmax(df_o["f(α)"]))]
        h2 = df_o.iloc[(df_o["q"] - 2).abs().argmin()]["h(q)"]
        m = st.columns(5)
        m[0].metric("Δh (orijinal)", f"{dh:.3f}")
        m[1].metric("Δh (shuffle)", f"{dhs:.3f}")
        m[2].metric("Δα", f"{da:.3f}")
        m[3].metric("α₀", f"{a0:.3f}")
        m[4].metric("h(2)", f"{h2:.3f}")
        st.caption("Shuffle sonrası Δh hâlâ yüksekse multifraktallik kalın kuyruktan, belirgin düşüyorsa uzun hafızadan gelir.")
        g1, g2 = st.columns(2)
        f1 = go.Figure()
        f1.add_trace(go.Scatter(x=df_o["q"], y=df_o["h(q)"], name="orijinal", mode="lines+markers"))
        f1.add_trace(go.Scatter(x=df_sh["q"], y=df_sh["h(q)"], name="shuffle", mode="lines+markers"))
        f1.update_layout(title="h(q)", xaxis_title="q", template="plotly_white", height=340)
        f2 = go.Figure()
        f2.add_trace(go.Scatter(x=df_o["α"], y=df_o["f(α)"], name="orijinal", mode="lines+markers"))
        f2.add_trace(go.Scatter(x=df_sh["α"], y=df_sh["f(α)"], name="shuffle", mode="lines+markers"))
        f2.update_layout(title="Singülarite spektrumu f(α)", xaxis_title="α", template="plotly_white", height=340)
        g1.plotly_chart(f1, width="stretch", config=CFG)
        g2.plotly_chart(f2, width="stretch", config=CFG)
        f3 = go.Figure()
        for qq in [v for v in (-4, -2, 0, 2, 4) if v in q]:
            j = list(q).index(qq)
            f3.add_trace(go.Scatter(x=np.log(sc), y=np.log(F[j]), mode="lines+markers", name=f"q={qq:g}"))
        f3.update_layout(title="ln F_q(s) – ln s (ölçekleme kalitesi)", template="plotly_white", height=340)
        st.plotly_chart(f3, width="stretch", config=CFG)
        show(df_o)

# ── Sekme 7: indir
with tabs[6]:
    st.subheader("Tüm sonuçları Excel olarak indir")
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        S_df.to_excel(xw, sheet_name="Ozet", index=False)
        W_df.to_excel(xw, sheet_name="Agirliklar", index=False)
        L_df.to_excel(xw, sheet_name="Lambda2", index=False)
        H_df.to_excel(xw, sheet_name="C4_Ufuk_Gecerlilik", index=False)
        for bn, b in res.items():
            for pn, p in b["P"].items():
                dl = p["c1"] - b["mu0"]
                if dl <= 0:
                    continue
                for r_ in taus:
                    _, mf, _, _ = c4_terms(p["sig"], p["lam2"], r_, T)
                    al = sorted(set(a_abs + [f * 4 * mf / dl for f in a_frac]))
                    mix_rows(al, p["sig"], p["c1"], b["mu0"], mf, p["lam"]["lam2"]).to_excel(
                        xw, sheet_name=f"{bn[:8]}_{pn}_{r_:.2f}"[:31], index=False)
        if "mf" in st.session_state:
            st.session_state["mf"][3].to_excel(xw, sheet_name="MFDFA", index=False)
    st.download_button("📥 Excel (.xlsx) indir", buf.getvalue(), "multifraktal_portfoy_sonuclari.xlsx",
                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary")
    st.info("Grafikleri yüksek çözünürlüklü PNG olarak indirmek için grafiğin sağ üstündeki 📷 simgesine tıklayın (3× çözünürlük).")
    st.caption("Model notları: C₄ tek dönemlik pertürbasyon açılımıdır; τ* üzerindeki ufuklar ekonomik sonuç olarak yorumlanmamalıdır. "
               "Sonuçlar veri penceresine, rf ve T varsayımına bağlıdır.")
