"""Factor loadings of ETFs that screen on return on invested capital.

Supports https://summitward.com/learn/roic-return-on-invested-capital.

Question: do funds that select stocks on ROIC (or on ratings built on ROIC)
carry measurable exposure to the Fama-French profitability factor (RMW), and
how does it compare with a quality ETF and a profitability-screened small-cap
value fund?

Funds:
  MOAT  VanEck Morningstar Wide Moat (moat ratings rest on ROIC vs WACC)
  LCOW  Pacer S&P 500 Quality FCF Aristocrats (5-yr FCF margin and ROIC)
  GFLW  VictoryShares Free Cash Flow Growth (FCF ROIC)
  QUAL  iShares MSCI USA Quality Factor (ROE, leverage, earnings variability)
  AVUV  Avantis US Small Cap Value (value plus cash-based profitability)
  VTI   Vanguard Total Stock Market (market reference)

Data:
  * Ken French data library, 202608 CRSP database (committed in data/).
  * Yahoo Finance via yfinance: daily adjusted closes (auto_adjust=True),
    month-end, cached in .cache/ and not redistributed.

Model: Fama-French five factors plus momentum on fund excess returns (over
French RF). Alpha is 12x the monthly intercept. t-statistics are Newey-West
with 6 lags, from a numpy OLS. Each fund runs over its own full history
(first, possibly partial, month dropped). LCOW and GFLW have under two years
of returns, too short for their loadings to mean much; they are printed for
completeness. MOAT and QUAL are also split at 2020, and every fund is rerun on
FF5 without momentum.

These describe past windows, not forecasts. Short windows give wide
confidence intervals; read the t-statistics.

    pip install numpy pandas yfinance
    python3 roic_etf_loadings.py
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
CACHE = HERE / ".cache"
OUT = HERE / "output"
CACHE.mkdir(exist_ok=True)
OUT.mkdir(exist_ok=True)

FUNDS = [
    ("MOAT", "VanEck Morningstar Wide Moat"),
    ("LCOW", "Pacer S&P 500 Quality FCF Aristocrats"),
    ("GFLW", "VictoryShares Free Cash Flow Growth"),
    ("QUAL", "iShares MSCI USA Quality Factor"),
    ("AVUV", "Avantis US Small Cap Value"),
    ("VTI", "Vanguard Total Stock Market"),
]
FACTORS = ["Mkt-RF", "SMB", "HML", "RMW", "CMA", "Mom"]
NW_LAGS = 6
RESULTS: dict = {"sources": {}, "own": [], "failures": []}


def ym(idx) -> str:
    return pd.Timestamp(idx).strftime("%Y-%m")


def french_main(name: str) -> pd.DataFrame:
    """First monthly (YYYYMM-indexed) block of a committed French CSV, decimals."""
    lines = (DATA / f"{name}.csv").read_text(encoding="latin-1").splitlines()
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


def ols(y: pd.Series, X: pd.DataFrame, lags: int = NW_LAGS) -> dict:
    d = pd.concat([y.rename("y"), X], axis=1).dropna()
    yv = d["y"].to_numpy()
    Xv = np.column_stack([np.ones(len(d)), d[X.columns].to_numpy()])
    n, k = Xv.shape
    XtXi = np.linalg.inv(Xv.T @ Xv)
    b = XtXi @ Xv.T @ yv
    e = yv - Xv @ b
    u = Xv * e[:, None]
    S = u.T @ u
    for L in range(1, lags + 1):
        w = 1 - L / (lags + 1)
        G = u[L:].T @ u[:-L]
        S += w * (G + G.T)
    V = XtXi @ S @ XtXi * n / (n - k)
    se_nw = np.sqrt(np.diag(V))
    r2 = 1 - (e @ e) / np.sum((yv - yv.mean()) ** 2)
    names = ["alpha"] + list(X.columns)
    return {
        "start": ym(d.index[0]),
        "end": ym(d.index[-1]),
        "n": int(n),
        "r2": float(r2),
        "alpha_ann": float(12 * b[0]),
        "coef": {nm: float(v) for nm, v in zip(names, b, strict=True)},
        "t_nw": {nm: float(v) for nm, v in zip(names, b / se_nw, strict=True)},
    }


def show(label: str, r: dict) -> None:
    c, t = r["coef"], r["t_nw"]
    print(
        f"  {label:5s} {r['start']}..{r['end']} n={r['n']:3d} R2={r['r2']:.2f} "
        f"alpha={r['alpha_ann'] * 100:+.1f}%/yr (t={t['alpha']:+.1f}) | "
        + " ".join(f"{f} {c[f]:+.2f}({t[f]:+.1f})" for f in FACTORS)
    )


# ------------------------------------------------------------------ factors
ff5 = french_main("F-F_Research_Data_5_Factors_2x3")
mom = french_main("F-F_Momentum_Factor")
mom.columns = ["Mom"]
fac = ff5.join(mom, how="inner")
END = fac.index.max()
RESULTS["sources"]["french_end"] = ym(END)
print("French factors through", ym(END))

# -------------------------------------------------------------------- funds
px_cache = CACHE / "yahoo_daily.csv"
tickers = [t for t, _ in FUNDS]
if px_cache.exists():
    px = pd.read_csv(px_cache, index_col=0, parse_dates=True)
else:
    import yfinance as yf

    frames = {}
    for t in tickers:
        for attempt in range(5):
            try:
                d = yf.download(t, start="2000-01-01", auto_adjust=True, progress=False)
                if len(d):
                    frames[t] = d["Close"].squeeze().rename(t)
                    break
            except Exception as exc:  # noqa: BLE001
                print("   retry", t, exc)
            time.sleep(3 * (attempt + 1))
        else:
            RESULTS["failures"].append(f"Yahoo {t}")
    px = pd.DataFrame(frames)
    px.to_csv(px_cache)
RESULTS["sources"]["yahoo_last_day"] = str(px.index.max().date())
rets = px.resample("ME").last().pct_change(fill_method=None)

excess = {}
for t, _ in FUNDS:
    s = rets[t].dropna().iloc[1:]  # drop a possibly partial first month
    excess[t] = (s - fac["RF"]).dropna().loc[:END]
    print(f"   {t:5s} {ym(excess[t].index[0])}..{ym(excess[t].index[-1])} n={len(excess[t])}")

print("\nOwn windows, FF5 + momentum")
for t, label in FUNDS:
    r = ols(excess[t], fac[FACTORS])
    show(t, r)
    RESULTS["own"].append({"ticker": t, "label": label, **r})

print("\nRobustness, FF5 without momentum, own windows")
RESULTS["ff5_only"] = []
for t, label in FUNDS:
    r = ols(excess[t], fac[FACTORS[:-1]])
    print(f"  {t:5s} RMW {r['coef']['RMW']:+.2f}(t={r['t_nw']['RMW']:+.1f}) "
          f"HML {r['coef']['HML']:+.2f} CMA {r['coef']['CMA']:+.2f} R2={r['r2']:.2f}")
    RESULTS["ff5_only"].append({"ticker": t, **r})

print("\nMOAT and QUAL by sub-period, FF5 + momentum")
RESULTS["subperiods"] = []
for t in ["MOAT", "QUAL"]:
    for lo, hi in [(None, "2019-12-31"), ("2020-01-31", None)]:
        r = ols(excess[t].loc[lo:hi], fac[FACTORS])
        show(t, r)
        RESULTS["subperiods"].append({"ticker": t, **r})

(OUT / "results.json").write_text(json.dumps(RESULTS, indent=2))
print("\nwrote output/results.json")
