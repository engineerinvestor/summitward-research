"""How precisely factor loadings and factor premiums are known, and what that
does to the expected return a loading implies.

Supports https://summitward.com/learn/factor-loadings-expected-returns.

Requires numpy, pandas and yfinance.

Sources (Ken French CSVs committed in ./data/; Yahoo downloaded on first run
and cached in ./.cache/, which is not committed):
  * Ken French data library (Tuck), monthly, percent converted to decimals:
      - F-F_Research_Data_5_Factors_2x3: Mkt-RF, SMB, HML, RMW, CMA, RF
      - F-F_Momentum_Factor: Mom
    Data cut through August 2026, downloaded October 2026 (CIZ-format CRSP
    inputs, which the library has used since its January 2025 release).
  * Yahoo Finance via yfinance: daily adjusted closes (auto_adjust=True),
    resampled to month-end.

Sections:
  1. Premiums, 1963-07 to 2026-08: annualized arithmetic mean of each factor,
     classical and Newey-West (Bartlett, 6 and 12 lags) standard errors, 95%
     intervals, the years of data an i.i.d. estimate would need for a +/-1 and
     +/-2 point interval, and rolling 10-, 20- and 30-year means (overlapping
     windows, so the shares are descriptive, not independent trials).
  1b. Check: means capped at 2026-06, to compare with the premia hard-coded in
     Summitward's factor-exposure blender (7.21 / 2.24 / 3.58 / 2.87 / 2.95).
  2. Fund loadings on the five factors, with classical and Newey-West (6 lag)
     standard errors: every fund over the common window 2019-10 to 2026-08
     (AVUV's history sets the start), and each fund over its own history.
  3. Implied edge over VTI: the difference in loadings times the premium
     vector, with a standard error from the Newey-West (12 lag) covariance of
     the factor means. The loading difference comes from regressing each
     fund's return minus VTI's on the factors, which also gives its own
     covariance; section 3 reports both error sources.
  4. Realized: each fund against VTI over the common window. CAGR, arithmetic
     means, volatility, and the loading difference times the factor means
     realized in that window.

Nothing here is a forecast. Every figure describes a named past window.
"""

from __future__ import annotations

import json
import math
import time
import urllib.request
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
CACHE = HERE / ".cache"
OUT = HERE / "output"
for p in (DATA, CACHE, OUT):
    p.mkdir(exist_ok=True)
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"
)
FRENCH = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/{}_CSV.zip"

FACTORS = ["Mkt-RF", "SMB", "HML", "RMW", "CMA"]
PREM_START, END = "1963-07", "2026-08"
COMMON_START = "2019-10"
FUNDS = [
    ("VTI", "Vanguard Total Stock Market ETF"),
    ("VBR", "Vanguard Small-Cap Value ETF"),
    ("DFSVX", "DFA U.S. Small Cap Value Portfolio (Institutional)"),
    ("AVUV", "Avantis U.S. Small Cap Value ETF"),
]
SCENARIOS = [
    ("full", "Full 1963-2026 averages", 1.0),
    ("mp", "Style premia x 0.42 (McLean-Pontiff post-publication)", 0.42),
    ("half", "Style premia x 0.5", 0.5),
    ("zero", "Style premia zero, market premium kept", 0.0),
]
Z95 = 1.959964
RESULTS: dict = {
    "sources": {},
    "data_vintage": "Ken French library, cut through 2026-08",
}


# ---------------------------------------------------------------- utilities
def fetch(url: str, dest: Path) -> Path:
    if not dest.exists():
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=60) as r:
            dest.write_bytes(r.read())
    return dest


def ym(idx) -> str:
    return pd.Timestamp(idx).strftime("%Y-%m")


def french_main(name: str) -> pd.DataFrame:
    """The first monthly (YYYYMM-indexed) block of a French CSV, in decimals."""
    local = DATA / f"{name}.csv"
    if local.exists():
        text = local.read_text(encoding="latin-1")
    else:
        z = zipfile.ZipFile(fetch(FRENCH.format(name), CACHE / f"{name}.zip"))
        text = z.read(z.namelist()[0]).decode("latin-1")
        local.write_text(text, encoding="latin-1")
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
        "coef": {nm: float(v) for nm, v in zip(names, b, strict=True)},
        "se": {nm: float(v) for nm, v in zip(names, se_cl, strict=True)},
        "se_nw": {nm: float(v) for nm, v in zip(names, se_nw, strict=True)},
        "_V_nw_slopes": V_nw[1:, 1:],
    }


def norm_cdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


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
    r = m.pct_change().dropna()
    return r


# ---------------------------------------------------------------- load data
print("Loading factors")
ff5 = french_main("F-F_Research_Data_5_Factors_2x3")
mom = french_main("F-F_Momentum_Factor")
mom.columns = [c.strip() for c in mom.columns]
F = ff5.join(mom[["Mom"]], how="left")
F = F.loc[PREM_START:END]
assert ym(F.index[0]) == PREM_START and ym(F.index[-1]) == END, (
    F.index[0],
    F.index[-1],
)
assert F.isna().sum().sum() == 0
RESULTS["sources"]["french"] = {
    "ff5": "F-F_Research_Data_5_Factors_2x3",
    "mom": "F-F_Momentum_Factor",
    "window": [PREM_START, END],
    "n": len(F),
}

# ---------------------------------------------------------------- section 1
print(f"\n1. Premiums, {PREM_START} to {END} ({len(F)} months), % a year")
T = len(F)
prem = {}
for c in FACTORS + ["Mom"]:
    x = F[c].to_numpy()
    mu = x.mean() * 12
    sd_m = x.std(ddof=1)
    se_cl = sd_m / math.sqrt(T) * 12
    xc = (x - x.mean())[:, None]
    se_nw6 = math.sqrt(nw_cov(xc, 6)[0, 0] / T) * 12
    se_nw12 = math.sqrt(nw_cov(xc, 12)[0, 0] / T) * 12
    sd_a = sd_m * math.sqrt(12)
    roll = {}
    for yrs in (10, 20, 30):
        W = yrs * 12
        rm = pd.Series(x).rolling(W).mean().dropna().to_numpy() * 12
        roll[str(yrs)] = {
            "windows": len(rm),
            "share_negative": float((rm < 0).mean()),
            "min": float(rm.min()),
            "max": float(rm.max()),
            "latest": float(rm[-1]),
        }
    prem[c] = {
        "mean": mu,
        "sd_monthly": sd_m,
        "sd_annual": sd_a,
        "se_classical": se_cl,
        "se_nw6": se_nw6,
        "se_nw12": se_nw12,
        "t_nw12": mu / se_nw12,
        "ci95_nw12": [mu - Z95 * se_nw12, mu + Z95 * se_nw12],
        "years_for_pm1pt": (Z95 * sd_a / 0.01) ** 2,
        "years_for_pm2pt": (Z95 * sd_a / 0.02) ** 2,
        "rolling": roll,
    }
    p = prem[c]
    print(
        f"  {c:7s} mean {100 * mu:5.2f}  sd/mo {100 * sd_m:4.2f}  "
        f"SE cl {100 * se_cl:4.2f} nw6 {100 * se_nw6:4.2f} nw12 {100 * se_nw12:4.2f}  "
        f"t {p['t_nw12']:4.2f}  95% [{100 * p['ci95_nw12'][0]:5.2f}, "
        f"{100 * p['ci95_nw12'][1]:5.2f}]  yrs +/-1pt {p['years_for_pm1pt']:4.0f}  "
        f"+/-2pt {p['years_for_pm2pt']:4.0f}"
    )
    print(
        "          rolling share < 0: "
        + "  ".join(
            f"{k}y {100 * v['share_negative']:3.0f}% "
            f"[{100 * v['min']:5.1f}, {100 * v['max']:5.1f}] latest {100 * v['latest']:5.1f}"
            for k, v in roll.items()
        )
    )
RESULTS["premiums"] = prem

# trailing 20-year mean and its +/-1.96 classical SE band, every December,
# for the guide's chart
chart = []
for c in ["SMB", "HML", "RMW", "CMA"]:
    x = F[c]
    m20 = x.rolling(240).mean() * 12
    s20 = x.rolling(240).std(ddof=1) / math.sqrt(240) * 12
    for dt in m20.dropna().index:
        if dt.month == 12 or dt == m20.index[-1]:
            chart.append(
                {
                    "factor": c,
                    "end": ym(dt),
                    "mean": round(float(m20[dt]) * 100, 3),
                    "lo": round(float(m20[dt] - Z95 * s20[dt]) * 100, 3),
                    "hi": round(float(m20[dt] + Z95 * s20[dt]) * 100, 3),
                }
            )
RESULTS["rolling20_chart"] = chart

# covariance of the five factor means (annualized), NW 12 lags
X5 = F[FACTORS].to_numpy()
S12 = nw_cov(X5 - X5.mean(0), 12)
Sigma_lam = S12 / T * 144
lam = X5.mean(0) * 12
corr = Sigma_lam / np.sqrt(np.outer(np.diag(Sigma_lam), np.diag(Sigma_lam)))
RESULTS["premium_vector"] = dict(zip(FACTORS, lam.tolist(), strict=True))
RESULTS["premium_cov_nw12"] = Sigma_lam.tolist()
RESULTS["premium_corr_nw12"] = corr.round(3).tolist()
print("  correlation of factor-mean estimates (NW 12):")
for i, c in enumerate(FACTORS):
    print(f"    {c:7s} " + " ".join(f"{v:5.2f}" for v in corr[i]))

# ---------------------------------------------------------------- section 1b
chk = ff5.loc[PREM_START:"2026-06", FACTORS].mean() * 1200
print("\n1b. Means capped at 2026-06 (blender check: 7.21 2.24 3.58 2.87 2.95):")
print("    " + "  ".join(f"{c} {v:.2f}" for c, v in chk.items()))
RESULTS["check_to_2026_06"] = {c: float(v) for c, v in chk.items()}

# ---------------------------------------------------------------- section 2
print("\n2. Fund loadings, FF5, classical SE and NW(6) SE")
rets = {t: yahoo_monthly(t) for t, _ in FUNDS}
Fx = ff5.loc[:END]
loads: dict = {"common": {}, "own": {}}
for t, name in FUNDS:
    r = rets[t]
    ex = (r - Fx["RF"]).dropna()
    for key, start in (("common", COMMON_START), ("own", None)):
        y = ex.loc[start:END] if start else ex.loc[:END]
        res = ols(y, Fx[FACTORS])
        res.pop("_V_nw_slopes")
        res["name"] = name
        loads[key][t] = res
        print(
            f"  {key:6s} {t:6s} {res['start']} to {res['end']} n={res['n']:3d} "
            f"R2 {res['r2']:.3f} alpha {100 * res['alpha_ann']:5.2f} (nw se "
            f"{100 * res['alpha_se_nw_ann']:.2f})  "
            + " ".join(
                f"{c}:{res['coef'][c]:.3f}({res['se'][c]:.3f}/{res['se_nw'][c]:.3f})"
                for c in FACTORS
            )
        )
RESULTS["loadings"] = loads

# ---------------------------------------------------------------- section 3
print("\n3. Implied edge over VTI from loading differences, % a year")
edges: dict = {}
vti = rets["VTI"]
for t, _ in FUNDS[1:]:
    diff = (rets[t] - vti).dropna().loc[COMMON_START:END]
    res = ols(diff, Fx[FACTORS])
    Vb = res.pop("_V_nw_slopes")
    db = np.array([res["coef"][c] for c in FACTORS])
    out = {"window": [res["start"], res["end"]], "n": res["n"], "delta_beta": {}}
    out["delta_beta"] = {
        c: {"coef": res["coef"][c], "se_nw": res["se_nw"][c]} for c in FACTORS
    }
    out["delta_beta_cov_nw"] = Vb.tolist()
    out["alpha_diff_ann"] = res["alpha_ann"]
    out["r2"] = res["r2"]
    for key, label, s in SCENARIOS:
        scale = np.array([1.0, s, s, s, s])
        lam_s = lam * scale
        Sig_s = Sigma_lam * np.outer(scale, scale)
        m = float(db @ lam_s)
        se_lam = float(math.sqrt(db @ Sig_s @ db))
        se_beta = float(math.sqrt(lam_s @ Vb @ lam_s))
        se_tot = math.sqrt(se_lam**2 + se_beta**2)
        contrib = dict(zip(FACTORS, (db * lam_s).tolist(), strict=True))
        out[key] = {
            "label": label,
            "edge": m,
            "se_premium": se_lam,
            "se_loading": se_beta,
            "se_total": se_tot,
            "ci95": [m - Z95 * se_tot, m + Z95 * se_tot],
            "z": m / se_tot if se_tot > 0 else None,
            "contrib": contrib,
        }
        print(
            f"  {t:6s} {key:4s} edge {100 * m:5.2f}  SE from premia {100 * se_lam:.2f}  "
            f"from loadings {100 * se_beta:.2f}  total {100 * se_tot:.2f}  95% "
            f"[{100 * out[key]['ci95'][0]:5.2f}, {100 * out[key]['ci95'][1]:5.2f}]  "
            + " ".join(f"{c}:{100 * v:.2f}" for c, v in contrib.items())
        )
    edges[t] = out
RESULTS["edges_vs_vti"] = edges

# ---------------------------------------------------------------- section 4
print(f"\n4. Realized, {COMMON_START} to {END}")
win = pd.concat({t: rets[t] for t, _ in FUNDS}, axis=1).loc[COMMON_START:END].dropna()
Fw = Fx.loc[win.index, FACTORS]
yrs = len(win) / 12
fmean = Fw.mean() * 12
real: dict = {
    "window": [ym(win.index[0]), ym(win.index[-1])],
    "n": len(win),
    "factor_means": {c: float(v) for c, v in fmean.items()},
    "funds": {},
}
print(
    "  factor means in window: "
    + "  ".join(f"{c} {100 * v:.2f}" for c, v in fmean.items())
)
for t, _ in FUNDS:
    r = win[t]
    cagr = (1 + r).prod() ** (1 / yrs) - 1
    mu = r.mean() * 12
    vol = r.std(ddof=1) * math.sqrt(12)
    real["funds"][t] = {
        "cagr": float(cagr),
        "arith": float(mu),
        "vol": float(vol),
        "arith_minus_half_var": float(mu - vol**2 / 2),
    }
    print(
        f"  {t:6s} CAGR {100 * cagr:6.2f}  arith {100 * mu:6.2f}  vol {100 * vol:5.2f}  "
        f"mu - s^2/2 {100 * (mu - vol**2 / 2):6.2f}"
    )
for t, _ in FUNDS[1:]:
    db = np.array([edges[t]["delta_beta"][c]["coef"] for c in FACTORS])
    explained = float(db @ fmean.to_numpy())
    gap_ar = real["funds"][t]["arith"] - real["funds"]["VTI"]["arith"]
    gap_g = real["funds"][t]["cagr"] - real["funds"]["VTI"]["cagr"]
    real["funds"][t].update(
        {
            "arith_gap_vs_vti": gap_ar,
            "cagr_gap_vs_vti": gap_g,
            "explained_by_realized_factors": explained,
        }
    )
    print(
        f"  {t:6s} vs VTI: arith gap {100 * gap_ar:5.2f}  CAGR gap {100 * gap_g:5.2f}  "
        f"delta-beta x realized factors {100 * explained:5.2f}  "
        f"implied at full premia {100 * edges[t]['full']['edge']:5.2f}"
    )
RESULTS["realized"] = real

(OUT / "results.json").write_text(json.dumps(RESULTS, indent=1))
print("\nWrote output/results.json")
