"""Funds that each tried one way to improve on plain small-cap value, measured
against AVUV with six factors, and how long a real edge would take to show.

Supports https://summitward.com/learn/better-small-cap-value-fund.

Requires numpy, pandas and yfinance.

Sources (Ken French CSVs committed in ./data/; Yahoo downloaded on first run
and cached in ./.cache/, which is not committed):
  * Ken French data library (Tuck), monthly, percent converted to decimals:
      - F-F_Research_Data_5_Factors_2x3: Mkt-RF, SMB, HML, RMW, CMA, RF
      - F-F_Momentum_Factor: Mom
    Files built from the 202609 CRSP database (the same files as
    quant-investing-factor-risk-models, CIZ-format CRSP inputs).
  * Yahoo Finance via yfinance: daily adjusted closes (auto_adjust=True),
    resampled to month-end.

Funds, each standing for one idea:
  AVUV   baseline (Avantis U.S. Small Cap Value ETF)
  DFSVX  baseline (Dimensional U.S. Small Cap Value Portfolio; DFSV has been an
         ETF share class of this fund since 2026-09-25)
  DFFVX  wider targeted value including mid caps (Dimensional U.S. Targeted
         Value Portfolio; DFAT's fund since 2026-10-02)
  BOSVX  deeper value, more small companies (Bridgeway Omni Small-Cap Value)
  CALF   free-cash-flow yield, about 200 names (Pacer US Small Cap Cash Cows)
  XSVM   value plus momentum, about 120 names (Invesco S&P SmallCap Value with
         Momentum; current index since 2019-06-21)
  VBR    plain small-cap value index (Vanguard; renamed from CRSP to Morningstar
         in July 2026)
  IWN    plain small-cap value index (iShares Russell 2000 Value)
  AIEQ   machine-learning stock selection, all caps (Amplify AI Powered
         Equity; actively managed with EquBot as sub-adviser until it began
         tracking the EquBot index on 2024-01-29)
  VTI    total market, for AIEQ's comparison

Sections:
  A. Common window 2019-10 to 2026-09 (AVUV's history sets the start). Each
     fund's excess return on FF5 + Mom with Newey-West (6 lag) standard
     errors; CAGR, arithmetic mean, volatility, maximum drawdown.
  B. Each fund minus AVUV on the same six factors: loading differences,
     active alpha with Newey-West t, raw tracking error, residual tracking
     error, the t-statistic of the raw active mean, and the years of data an
     i.i.d. test would need to detect a 1%/yr edge at that tracking error.
  C. Implied edge over AVUV: loading differences times the 1963-07 to
     2026-09 factor means (full and x0.42 style premia, the McLean-Pontiff
     post-publication haircut), with the fee difference subtracted. These are
     what the loadings imply under stated premia, not forecasts.
  D. Own-history regressions by regime (DFSVX, DFFVX, BOSVX, CALF, XSVM from
     2019-07, AIEQ active and index eras), plus AIEQ's CAGR against VTI.
  F. After-the-fact attribution: each fund's arithmetic gap to AVUV split
     into loading gap times the factor returns realized in the window, plus
     the alpha gap. This describes the window; it predicts nothing.
  E. Pipeline check: AVUV excess return on FF5, 2019-10 to 2026-08, must
     match the loadings published by factor-loadings-expected-returns to 2 dp.

Writes output/results.json (everything) and output/better-scv-scoreboard.json
(the compact file the guide's tables and calculator read).

Nothing here is a forecast. Every figure describes a named past window.
"""

from __future__ import annotations

import json
import math
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
CACHE = HERE / ".cache"
OUT = HERE / "output"
for p in (DATA, CACHE, OUT):
    p.mkdir(exist_ok=True)

FACTORS = ["Mkt-RF", "SMB", "HML", "RMW", "CMA", "Mom"]
FF5 = FACTORS[:5]
PREM_START, END = "1963-07", "2026-09"
COMMON_START = "2019-10"
Z95 = 1.959964
MP_SCALE = 0.42  # McLean-Pontiff: post-publication returns 58% lower

# ticker, label, idea, net expense ratio % (issuer/prospectus, Nov 2026)
FUNDS = [
    ("AVUV", "Avantis U.S. Small Cap Value ETF", "Baseline", 0.25),
    ("DFSVX", "Dimensional U.S. Small Cap Value (DFSV)", "Baseline", 0.27),
    ("DFFVX", "Dimensional U.S. Targeted Value (DFAT)", "Wider, adds mid caps", 0.26),
    ("BOSVX", "Bridgeway Omni Small-Cap Value", "Deeper value, smaller stocks", 0.47),
    ("CALF", "Pacer US Small Cap Cash Cows ETF", "Free-cash-flow yield", 0.59),
    ("XSVM", "Invesco S&P SmallCap Value with Momentum", "Value plus momentum", 0.36),
    ("VBR", "Vanguard Morningstar Small-Cap Value ETF", "Plain index", 0.05),
    ("IWN", "iShares Russell 2000 Value ETF", "Plain index", 0.24),
    ("AIEQ", "Amplify AI Powered Equity ETF", "Machine learning, all caps", 0.75),
]
EXTRA = ["VTI"]
TICKERS = [f[0] for f in FUNDS] + EXTRA
FEE = {f[0]: f[3] / 100 for f in FUNDS}

REGIMES = [
    ("DFSVX", None, END, "Full history"),
    ("DFFVX", None, END, "Full history"),
    ("BOSVX", None, END, "Full history"),
    ("CALF", None, END, "Full history"),
    ("XSVM", "2019-07", END, "Current index (from 2019-06-21)"),
    ("AIEQ", "2017-11", "2024-01", "Active, EquBot sub-adviser"),
    ("AIEQ", "2024-02", END, "EquBot index"),
    ("AIEQ", "2017-11", END, "Full history"),
]

PUBLISHED_AVUV_FF5 = {  # factor-loadings-expected-returns, 2019-10..2026-08
    "Mkt-RF": 1.0612,
    "SMB": 0.8899,
    "HML": 0.5451,
    "RMW": 0.2198,
    "CMA": -0.0489,
}

RESULTS: dict = {"data_vintage": "Ken French library, 202609 CRSP database"}


# ---------------------------------------------------------------- utilities
def ym(idx) -> str:
    return pd.Timestamp(idx).strftime("%Y-%m")


def french_main(name: str) -> pd.DataFrame:
    """The first monthly (YYYYMM-indexed) block of a French CSV, in decimals."""
    text = (DATA / f"{name}.csv").read_text(encoding="latin-1")
    lines = text.splitlines()
    for i, ln in enumerate(lines):
        if ln.startswith(","):
            cols = [c.strip() for c in ln.split(",")[1:]]
            rows = []
            for row in lines[i + 1 :]:
                parts = [p.strip() for p in row.split(",")]
                if len(parts[0]) != 6 or not parts[0].isdigit():
                    break
                rows.append(parts)
            idx = pd.to_datetime([r[0] for r in rows], format="%Y%m")
            frame = pd.DataFrame(
                [[float(x) for x in r[1:]] for r in rows],
                index=idx + pd.offsets.MonthEnd(0),
                columns=cols,
            )
            return frame / 100.0
    raise ValueError(f"no monthly block in {name}")


def yahoo_monthly(ticker: str) -> pd.Series:
    local = CACHE / f"{ticker}.csv"
    if not local.exists():
        import yfinance as yf

        for attempt in range(3):
            px = yf.download(
                ticker, start="1990-01-01", auto_adjust=True, progress=False
            )
            if len(px):
                break
            time.sleep(3 * (attempt + 1))
        close = px["Close"]
        if isinstance(close, pd.DataFrame):
            close = close.iloc[:, 0]
        close.to_csv(local)
    close = pd.read_csv(local, index_col=0, parse_dates=True).iloc[:, 0]
    m = close.resample("ME").last()
    # the first return runs from the inception month's last close, so it
    # covers a full month
    return m.pct_change().dropna()


def nw_cov(u: np.ndarray, lags: int) -> np.ndarray:
    """Bartlett long-run covariance of the rows of u (already demeaned)."""
    n = len(u)
    S = u.T @ u / n
    for L in range(1, lags + 1):
        G = u[L:].T @ u[:-L] / n
        S += (1 - L / (lags + 1)) * (G + G.T)
    return S


def ols(y: pd.Series, X: pd.DataFrame, lags: int = 6) -> dict:
    d = pd.concat([y.rename("y"), X], axis=1).dropna()
    yv = d["y"].to_numpy()
    Xv = np.column_stack([np.ones(len(d)), d[X.columns].to_numpy()])
    n, k = Xv.shape
    XtXi = np.linalg.inv(Xv.T @ Xv)
    b = XtXi @ Xv.T @ yv
    e = yv - Xv @ b
    s2 = e @ e / (n - k)
    V_cl = s2 * XtXi
    u = Xv * e[:, None]
    S = nw_cov(u, lags) * n
    V_nw = XtXi @ S @ XtXi * n / (n - k)
    r2 = 1 - (e @ e) / np.sum((yv - yv.mean()) ** 2)
    names = ["alpha"] + list(X.columns)
    se_cl = np.sqrt(np.diag(V_cl))
    se_nw = np.sqrt(np.diag(V_nw))
    return {
        "start": ym(d.index[0]),
        "end": ym(d.index[-1]),
        "n": int(n),
        "r2": float(r2),
        "alpha_ann": float(12 * b[0]),
        "alpha_se_nw_ann": float(12 * se_nw[0]),
        "alpha_t_nw": float(b[0] / se_nw[0]),
        "coef": {nm: float(v) for nm, v in zip(names, b, strict=True)},
        "se": {nm: float(v) for nm, v in zip(names, se_cl, strict=True)},
        "se_nw": {nm: float(v) for nm, v in zip(names, se_nw, strict=True)},
        "resid_sd_ann": float(math.sqrt(12 * (e @ e) / (n - 1))),
        "_V_nw_slopes": V_nw[1:, 1:],
    }


def stats(r: pd.Series) -> dict:
    yrs = len(r) / 12
    wealth = (1 + r).cumprod()
    dd = float((wealth / wealth.cummax() - 1).min())
    return {
        "start": ym(r.index[0]),
        "end": ym(r.index[-1]),
        "n": len(r),
        "cagr": float(wealth.iloc[-1] ** (1 / yrs) - 1),
        "arith": float(12 * r.mean()),
        "vol": float(math.sqrt(12) * r.std(ddof=1)),
        "max_dd": dd,
    }


def strip(d: dict) -> dict:
    return {k: v for k, v in d.items() if not k.startswith("_")}


def r4(x: float) -> float:
    return round(float(x), 4)


# ---------------------------------------------------------------- load data
print("Loading data")
ff5 = french_main("F-F_Research_Data_5_Factors_2x3")
mom = french_main("F-F_Momentum_Factor")
mom.columns = [c.strip() for c in mom.columns]
F = ff5.join(mom[["Mom"]], how="left").loc[:END]
assert ym(F.index[-1]) == END, F.index[-1]
assert F.loc[PREM_START:END].isna().sum().sum() == 0
rets = {t: yahoo_monthly(t).loc[:END] for t in TICKERS}
for t in TICKERS:
    print(f"  {t:6s} {ym(rets[t].index[0])} to {ym(rets[t].index[-1])}")
    assert ym(rets[t].index[-1]) == END, (t, rets[t].index[-1])
RESULTS["sources"] = {
    "french": ["F-F_Research_Data_5_Factors_2x3", "F-F_Momentum_Factor"],
    "yahoo": TICKERS,
    "yahoo_read": time.strftime("%Y-%m-%d"),
    "fund_first_month": {t: ym(rets[t].index[0]) for t in TICKERS},
}
RESULTS["fees"] = FEE
X6 = F[FACTORS]
RF = F["RF"]

# ---------------------------------------------------------------- section E
print("\nE. Pipeline check: AVUV excess on FF5, 2019-10 to 2026-08")
chk = ols((rets["AVUV"] - RF).loc[COMMON_START:"2026-08"], F[FF5])
for c, v in PUBLISHED_AVUV_FF5.items():
    print(f"  {c:7s} ours {chk['coef'][c]:+.4f}  published {v:+.4f}")
    assert round(chk["coef"][c], 2) == round(v, 2), (c, chk["coef"][c], v)
RESULTS["pipeline_check"] = {
    "window": [chk["start"], chk["end"]],
    "ours": {c: chk["coef"][c] for c in FF5},
    "published": PUBLISHED_AVUV_FF5,
    "match_2dp": True,
}

# ---------------------------------------------------------------- section A
print(f"\nA. Common window {COMMON_START} to {END}: excess returns on FF5 + Mom")
secA: dict = {}
for t, label, idea, _ in FUNDS + [("VTI", "Vanguard Total Stock Market", "", 0)]:
    r = rets[t].loc[COMMON_START:END]
    reg = ols(r - RF, X6)
    reg.pop("_V_nw_slopes")
    st = stats(r)
    secA[t] = {"label": label, "idea": idea, "stats": st, "ff6": reg}
    print(
        f"  {t:6s} n={reg['n']}  CAGR {100 * st['cagr']:6.2f}  arith "
        f"{100 * st['arith']:6.2f}  vol {100 * st['vol']:5.2f}  maxDD "
        f"{100 * st['max_dd']:6.1f}  R2 {reg['r2']:.3f}  alpha "
        f"{100 * reg['alpha_ann']:+5.2f} (t {reg['alpha_t_nw']:+.2f})"
    )
    print(
        "         "
        + " ".join(f"{c}:{reg['coef'][c]:+.2f}({reg['se_nw'][c]:.2f})" for c in FACTORS)
    )
RESULTS["A"] = secA

# ---------------------------------------------------------------- section B
print(f"\nB. Each fund minus AVUV, {COMMON_START} to {END}, on FF5 + Mom")
secB: dict = {}
avuv = rets["AVUV"]
for t, label, idea, _ in FUNDS[1:]:
    active = (rets[t] - avuv).dropna().loc[COMMON_START:END]
    reg = ols(active, X6)
    Vb = reg.pop("_V_nw_slopes")
    te = float(math.sqrt(12) * active.std(ddof=1))
    mu = float(12 * active.mean())
    t_raw = mu / (te / math.sqrt(len(active) / 12))
    secB[t] = {
        "label": label,
        "idea": idea,
        "window": [reg["start"], reg["end"]],
        "n": reg["n"],
        "te_raw": te,
        "te_resid": reg["resid_sd_ann"],
        "active_arith": mu,
        "active_cagr": secA[t]["stats"]["cagr"] - secA["AVUV"]["stats"]["cagr"],
        "t_raw_mean": t_raw,
        "years_to_detect_1pct_raw": (2 * te / 0.01) ** 2,
        "years_to_detect_1pct_resid": (2 * reg["resid_sd_ann"] / 0.01) ** 2,
        "reg": reg,
        "_Vb": Vb,
    }
    print(
        f"  {t:6s} TE {100 * te:5.2f} resid TE {100 * reg['resid_sd_ann']:5.2f}  "
        f"active arith {100 * mu:+6.2f} (t {t_raw:+.2f})  CAGR gap "
        f"{100 * secB[t]['active_cagr']:+6.2f}  alpha {100 * reg['alpha_ann']:+5.2f} "
        f"(t {reg['alpha_t_nw']:+.2f})  R2 {reg['r2']:.2f}  yrs@1% "
        f"{secB[t]['years_to_detect_1pct_raw']:5.0f}/"
        f"{secB[t]['years_to_detect_1pct_resid']:4.0f}"
    )
    print(
        "         d-beta "
        + " ".join(f"{c}:{reg['coef'][c]:+.2f}({reg['se_nw'][c]:.2f})" for c in FACTORS)
    )

# ---------------------------------------------------------------- section C
print(f"\nC. Implied edge over AVUV, premia {PREM_START} to {END}, % a year")
Fp = F.loc[PREM_START:END, FACTORS].to_numpy()
T = len(Fp)
lam = Fp.mean(0) * 12
Sigma_lam = nw_cov(Fp - Fp.mean(0), 12) / T * 144
RESULTS["premium_window"] = [PREM_START, END]
RESULTS["premium_vector"] = dict(zip(FACTORS, lam.tolist(), strict=True))
print("  premia: " + "  ".join(f"{c} {100 * v:.2f}" for c, v in zip(FACTORS, lam)))
for t in secB:
    reg = secB[t]["reg"]
    db = np.array([reg["coef"][c] for c in FACTORS])
    Vb = secB[t].pop("_Vb")
    dfee = FEE[t] - FEE["AVUV"]
    secB[t]["fee_diff"] = dfee
    out = {}
    for key, s in (("full", 1.0), ("mp", MP_SCALE)):
        scale = np.array([1.0, s, s, s, s, s])
        lam_s = lam * scale
        Sig_s = Sigma_lam * np.outer(scale, scale)
        m = float(db @ lam_s)
        se_tot = math.sqrt(float(db @ Sig_s @ db) + float(lam_s @ Vb @ lam_s))
        contrib = dict(zip(FACTORS, (db * lam_s).tolist(), strict=True))
        # style-only: drop the market term, so a higher beta (more market
        # exposure, which an investor can add by holding more of any fund)
        # does not count as an edge
        sel = np.array([0.0, 1, 1, 1, 1, 1])
        m_style = float((db * sel) @ lam_s)
        se_style = math.sqrt(
            float((db * sel) @ Sig_s @ (db * sel))
            + float((lam_s * sel) @ Vb @ (lam_s * sel))
        )
        out[key] = {
            "gross": m,
            "net_of_fee_diff": m - dfee,
            "style_net_of_fee_diff": m_style - dfee,
            "style_ci95": [
                m_style - dfee - Z95 * se_style,
                m_style - dfee + Z95 * se_style,
            ],
            "se": se_tot,
            "ci95": [m - dfee - Z95 * se_tot, m - dfee + Z95 * se_tot],
            "contrib": contrib,
        }
    secB[t]["implied"] = out
    f, mp = out["full"], out["mp"]
    print(
        f"  {t:6s} fee diff {100 * dfee:+.2f}  full: net {100 * f['net_of_fee_diff']:+5.2f} "
        f"[{100 * f['ci95'][0]:+5.2f}, {100 * f['ci95'][1]:+5.2f}]  x0.42: net "
        f"{100 * mp['net_of_fee_diff']:+5.2f}  style-only full "
        f"{100 * f['style_net_of_fee_diff']:+5.2f} [{100 * f['style_ci95'][0]:+5.2f}, "
        f"{100 * f['style_ci95'][1]:+5.2f}] x0.42 {100 * mp['style_net_of_fee_diff']:+5.2f}"
        "\n         contrib(full) "
        + " ".join(f"{c}:{100 * v:+.2f}" for c, v in f["contrib"].items())
    )
RESULTS["B"] = secB

# ---------------------------------------------------------------- section F
print(f"\nF. After-the-fact attribution of each gap vs AVUV, {COMMON_START} to {END}")
Fw = F.loc[COMMON_START:END, FACTORS]
fmean = Fw.mean() * 12
RESULTS["window_factor_means"] = {c: float(v) for c, v in fmean.items()}
print(
    "  factor means in window: "
    + "  ".join(f"{c} {100 * v:.2f}" for c, v in fmean.items())
)
for t in secB:
    reg = secB[t]["reg"]
    parts = {c: reg["coef"][c] * float(fmean[c]) for c in FACTORS}
    secB[t]["attribution"] = {
        "parts": parts,
        "factors_total": sum(parts.values()),
        "alpha": reg["alpha_ann"],
        "active_arith": secB[t]["active_arith"],
    }
    print(
        f"  {t:6s} arith gap {100 * secB[t]['active_arith']:+6.2f} = factors "
        f"{100 * sum(parts.values()):+6.2f} + alpha {100 * reg['alpha_ann']:+6.2f}  "
        + " ".join(f"{c}:{100 * v:+.2f}" for c, v in parts.items())
    )

# ---------------------------------------------------------------- section D
print("\nD. Own-history regressions by regime (excess returns on FF5 + Mom)")
secD = []
for t, start, end, regime in REGIMES:
    r = rets[t].loc[start:end] if start else rets[t].loc[:end]
    reg = ols(r - RF, X6)
    reg.pop("_V_nw_slopes")
    st = stats(r)
    row = {"ticker": t, "regime": regime, "stats": st, "ff6": reg}
    if t == "AIEQ":
        v = rets["VTI"].loc[r.index[0] : r.index[-1]]
        row["vti_stats"] = stats(v)
        act = (r - v).dropna()
        te = float(math.sqrt(12) * act.std(ddof=1))
        mu = float(12 * act.mean())
        row["vs_vti"] = {
            "te_raw": te,
            "active_arith": mu,
            "t_raw_mean": mu / (te / math.sqrt(len(act) / 12)),
        }
    secD.append(row)
    print(
        f"  {t:6s} {regime:32s} {reg['start']}..{reg['end']} n={reg['n']:3d}  "
        f"CAGR {100 * st['cagr']:6.2f}  alpha {100 * reg['alpha_ann']:+5.2f} "
        f"(t {reg['alpha_t_nw']:+.2f})  R2 {reg['r2']:.2f}"
    )
    print(
        "         "
        + " ".join(f"{c}:{reg['coef'][c]:+.2f}({reg['se_nw'][c]:.2f})" for c in FACTORS)
    )
    if t == "AIEQ":
        vv = row["vs_vti"]
        print(
            f"         VTI CAGR same months {100 * row['vti_stats']['cagr']:6.2f}  "
            f"TE vs VTI {100 * vv['te_raw']:5.2f}  active arith "
            f"{100 * vv['active_arith']:+6.2f} (t {vv['t_raw_mean']:+.2f})"
        )
RESULTS["D"] = secD

# ---------------------------------------------------------------- outputs
(OUT / "results.json").write_text(json.dumps(RESULTS, indent=1, default=float))

compact = {
    "vintage": "French 202609; Yahoo adjusted closes read "
    + RESULTS["sources"]["yahoo_read"],
    "window": [COMMON_START, END],
    "n": secA["AVUV"]["ff6"]["n"],
    "premiumWindow": [PREM_START, END],
    "windowFactorMeans": {
        c: r4(100 * v) for c, v in RESULTS["window_factor_means"].items()
    },
    "funds": [],
}
for t, label, idea, fee in FUNDS:
    a = secA[t]
    row = {
        "ticker": t,
        "label": label,
        "idea": idea,
        "fee": fee,
        "cagr": r4(100 * a["stats"]["cagr"]),
        "vol": r4(100 * a["stats"]["vol"]),
        "maxDd": r4(100 * a["stats"]["max_dd"]),
        "alpha": r4(100 * a["ff6"]["alpha_ann"]),
        "alphaT": r4(a["ff6"]["alpha_t_nw"]),
        "r2": r4(a["ff6"]["r2"]),
        "beta": {c: r4(a["ff6"]["coef"][c]) for c in FACTORS},
        "betaSe": {c: r4(a["ff6"]["se_nw"][c]) for c in FACTORS},
    }
    if t in secB:
        b = secB[t]
        row["vsAvuv"] = {
            "teRaw": r4(100 * b["te_raw"]),
            "teResid": r4(100 * b["te_resid"]),
            "activeArith": r4(100 * b["active_arith"]),
            "activeCagr": r4(100 * b["active_cagr"]),
            "tRawMean": r4(b["t_raw_mean"]),
            "alpha": r4(100 * b["reg"]["alpha_ann"]),
            "alphaT": r4(b["reg"]["alpha_t_nw"]),
            "dBeta": {c: r4(b["reg"]["coef"][c]) for c in FACTORS},
            "dBetaSe": {c: r4(b["reg"]["se_nw"][c]) for c in FACTORS},
            "impliedNetFull": r4(100 * b["implied"]["full"]["net_of_fee_diff"]),
            "impliedCiFull": [r4(100 * x) for x in b["implied"]["full"]["ci95"]],
            "impliedNetMp": r4(100 * b["implied"]["mp"]["net_of_fee_diff"]),
            "impliedCiMp": [r4(100 * x) for x in b["implied"]["mp"]["ci95"]],
            "styleNetFull": r4(100 * b["implied"]["full"]["style_net_of_fee_diff"]),
            "styleCiFull": [r4(100 * x) for x in b["implied"]["full"]["style_ci95"]],
            "styleNetMp": r4(100 * b["implied"]["mp"]["style_net_of_fee_diff"]),
            "attrMkt": r4(100 * b["attribution"]["parts"]["Mkt-RF"]),
            "attrFactors": r4(100 * b["attribution"]["factors_total"]),
            "styleCiMp": [r4(100 * x) for x in b["implied"]["mp"]["style_ci95"]],
        }
    compact["funds"].append(row)
compact["regimes"] = [
    {
        "ticker": d["ticker"],
        "regime": d["regime"],
        "start": d["ff6"]["start"],
        "end": d["ff6"]["end"],
        "n": d["ff6"]["n"],
        "cagr": r4(100 * d["stats"]["cagr"]),
        "alpha": r4(100 * d["ff6"]["alpha_ann"]),
        "alphaT": r4(d["ff6"]["alpha_t_nw"]),
        "r2": r4(d["ff6"]["r2"]),
        "beta": {c: r4(d["ff6"]["coef"][c]) for c in FACTORS},
        **(
            {
                "vtiCagr": r4(100 * d["vti_stats"]["cagr"]),
                "teVsVti": r4(100 * d["vs_vti"]["te_raw"]),
                "activeVsVti": r4(100 * d["vs_vti"]["active_arith"]),
                "tVsVti": r4(d["vs_vti"]["t_raw_mean"]),
            }
            if "vti_stats" in d
            else {}
        ),
    }
    for d in secD
]
(OUT / "better-scv-scoreboard.json").write_text(
    json.dumps(compact, separators=(",", ":")) + "\n"
)
print("\nWrote output/results.json and output/better-scv-scoreboard.json")
