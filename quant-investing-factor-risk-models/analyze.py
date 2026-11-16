"""How much of a factor fund's difference from the total market is factor
exposure, and how stable that difference is.

Supports https://summitward.com/learn/quant-investing-factor-risk-models.

Requires numpy, pandas and yfinance.

Sources (Ken French CSVs committed in ./data/; Yahoo downloaded on first run
and cached in ./.cache/, which is not committed):
  * Ken French data library (Tuck), monthly, percent converted to decimals:
      - F-F_Research_Data_5_Factors_2x3: Mkt-RF, SMB, HML, RMW, CMA, RF
      - F-F_Momentum_Factor: Mom
    Files built from the 202609 CRSP database, downloaded 2026-11-16 (CIZ-format
    CRSP inputs, which the library has used since its January 2025 release).
  * Yahoo Finance via yfinance: daily adjusted closes (auto_adjust=True),
    resampled to month-end.

Sections:
  A. Active-risk decomposition. For each fund, regress its monthly return minus
     VTI's on six factors (FF5 plus momentum) with an intercept, over the common
     window 2019-10 to 2026-09 (AVUV's history sets the start) and over each
     fund's own history. In-sample OLS makes the decomposition exact:
       Var(active) = db' S_f db + Var(resid)
     where S_f is the factor covariance over the same months and every variance
     uses the n - 1 divisor. Reports tracking error, the factor share of
     tracking-error variance (the regression R-squared), residual tracking
     error, each factor's Euler contribution db_k (S_f db)_k, and the residual
     correlation between funds.
  B. Mixes against VTI over the common window, using the same exact identity at
     the portfolio level (monthly rebalanced to fixed weights).
  C. Tracking-error stability. A 30% DFSVX sleeve against the French market
     (Mkt-RF + RF): trailing 60-month tracking error against the realized
     tracking error of the next 12 months, every month. A 12-month standard
     deviation is noisy even when the true value never changes, so the ratio is
     compared with the band that i.i.d. normal sampling alone would produce.
  D. Pipeline check: AVUV minus VTI on FF5 over 2019-10 to 2026-08 should match
     the loadings published by factor-loadings-expected-returns to 2 dp.

Also writes the JSON behind the guide's calculator to
output/quant-risk-model.json (copied into the site by hand). Section A2 adds
the French 12-industry portfolios (value-weighted) to test how much of what the
six factors miss is industry tilts.

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
LONG_START, END = "1963-07", "2026-09"
COMMON_START = "2019-10"
FUNDS = [
    ("VTI", "Vanguard Total Stock Market ETF"),
    ("VBR", "Vanguard Small-Cap Value ETF"),
    ("AVUV", "Avantis U.S. Small Cap Value ETF"),
    ("DFSVX", "DFA U.S. Small Cap Value Portfolio"),
    ("USMV", "iShares MSCI USA Min Vol Factor ETF"),
    ("QUAL", "iShares MSCI USA Quality Factor ETF"),
    ("MTUM", "iShares MSCI USA Momentum Factor ETF"),
]
TICKERS = [t for t, _ in FUNDS]
MIXES = [
    ("VTI 70 / AVUV 30", {"VTI": 0.7, "AVUV": 0.3}),
    ("VTI 70 / AVUV 15 / DFSVX 15", {"VTI": 0.7, "AVUV": 0.15, "DFSVX": 0.15}),
    ("VTI 70 / AVUV 15 / MTUM 15", {"VTI": 0.7, "AVUV": 0.15, "MTUM": 0.15}),
    ("VTI 70 / AVUV 15 / QUAL 15", {"VTI": 0.7, "AVUV": 0.15, "QUAL": 0.15}),
    ("VTI 70 / USMV 30", {"VTI": 0.7, "USMV": 0.3}),
]
SLEEVE, TRAIL, AHEAD = 0.30, 60, 12
RESULTS: dict = {"data_vintage": "Ken French library, 202609 CRSP database"}


# ---------------------------------------------------------------- utilities
def ym(idx) -> str:
    return pd.Timestamp(idx).strftime("%Y-%m")


def rel(p: Path) -> str:
    return str(p.relative_to(HERE))


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
    return m.pct_change().dropna()


def ols(y: pd.Series, X: pd.DataFrame) -> dict:
    """OLS with intercept. Returns coefficients, fitted and residual series."""
    d = pd.concat([y.rename("y"), X], axis=1).dropna()
    yv = d["y"].to_numpy()
    Xv = np.column_stack([np.ones(len(d)), d[X.columns].to_numpy()])
    b = np.linalg.solve(Xv.T @ Xv, Xv.T @ yv)
    e = yv - Xv @ b
    return {
        "index": d.index,
        "alpha": float(b[0]),
        "beta": b[1:],
        "resid": pd.Series(e, index=d.index),
        "y": pd.Series(yv, index=d.index),
    }


def decompose(y: pd.Series, X: pd.DataFrame) -> dict:
    """Exact in-sample split of Var(y) into factor and residual parts."""
    r = ols(y, X)
    Fm = X.loc[r["index"]].to_numpy()
    S = np.cov(Fm, rowvar=False, ddof=1)
    db = r["beta"]
    Sdb = S @ db
    contrib = db * Sdb
    var_f = float(db @ Sdb)
    var_e = float(r["resid"].var(ddof=1))
    var_y = float(r["y"].var(ddof=1))
    assert abs(var_f + var_e - var_y) < 1e-12 * max(1.0, var_y) + 1e-14, (
        var_f + var_e - var_y
    )
    return {
        "start": ym(r["index"][0]),
        "end": ym(r["index"][-1]),
        "n": len(r["index"]),
        "te": math.sqrt(12 * var_y),
        "te_factor": math.sqrt(12 * var_f),
        "te_resid": math.sqrt(12 * var_e),
        "factor_share": var_f / var_y,
        "alpha_ann": 12 * r["alpha"],
        "delta_beta": dict(zip(X.columns, db.tolist(), strict=True)),
        "contrib_share": dict(zip(X.columns, (contrib / var_y).tolist(), strict=True)),
        "resid_share": var_e / var_y,
        "_resid": r["resid"],
        "_S": S,
    }


def chi2_quantile(p: float, k: int) -> float:
    """Wilson-Hilferty approximation, adequate for k = 11 at the 5%/95% points."""
    z = {0.05: -1.6448536, 0.95: 1.6448536}[p]
    return k * (1 - 2 / (9 * k) + z * math.sqrt(2 / (9 * k))) ** 3


# ---------------------------------------------------------------- load data
print("Loading data")
ff5 = french_main("F-F_Research_Data_5_Factors_2x3")
mom = french_main("F-F_Momentum_Factor")
mom.columns = [c.strip() for c in mom.columns]
F = ff5.join(mom[["Mom"]], how="left").loc[:END]
assert ym(F.index[-1]) == END, F.index[-1]
assert F.loc[LONG_START:END].isna().sum().sum() == 0
rets = {t: yahoo_monthly(t) for t in TICKERS}
for t in TICKERS:
    print(f"  {t:6s} {ym(rets[t].index[0])} to {ym(rets[t].index[-1])}")
RESULTS["sources"] = {
    "french": ["F-F_Research_Data_5_Factors_2x3", "F-F_Momentum_Factor"],
    "yahoo": TICKERS,
    "fund_first_month": {t: ym(rets[t].index[0]) for t in TICKERS},
}
vti = rets["VTI"]
X6 = F[FACTORS]

# ---------------------------------------------------------------- section A
print("\nA. Active risk against VTI, six factors (FF5 + Mom), annualized %")
secA: dict = {"common": {}, "own": {}}
resid_common = {}
for t, name in FUNDS[1:]:
    active = (rets[t] - vti).dropna()
    for key, start in (("common", COMMON_START), ("own", None)):
        y = active.loc[start:END] if start else active.loc[:END]
        d = decompose(y, X6)
        if key == "common":
            resid_common[t] = d["_resid"]
        d.pop("_resid")
        d.pop("_S")
        d["name"] = name
        secA[key][t] = d
        print(
            f"  {key:6s} {t:6s} {d['start']}..{d['end']} n={d['n']:3d}  "
            f"TE {100 * d['te']:5.2f}  factor share {100 * d['factor_share']:5.1f}%  "
            f"resid TE {100 * d['te_resid']:4.2f}  alpha {100 * d['alpha_ann']:5.2f}"
        )
        print(
            "         loadings  "
            + " ".join(f"{c}:{v:+.3f}" for c, v in d["delta_beta"].items())
        )
        print(
            "         var share "
            + " ".join(f"{c}:{100 * v:+5.1f}" for c, v in d["contrib_share"].items())
            + f" resid:{100 * d['resid_share']:5.1f}"
        )
R = pd.DataFrame(resid_common)
rc = R.corr()
print("\n  Residual correlations, common window:")
print("         " + " ".join(f"{c:>6s}" for c in rc.columns))
for i in rc.index:
    print(f"  {i:6s} " + " ".join(f"{v:6.2f}" for v in rc.loc[i]))
secA["resid_corr_common"] = {i: rc.loc[i].round(4).to_dict() for i in rc.index}
RESULTS["A"] = secA

# ---------------------------------------------------------------- section A2
print("\nA2. Adding industry tilts: FF6 vs FF6 + 11 industry-minus-market spreads")
ind = french_main("12_Industry_Portfolios").loc[:END]
assert (ind.loc["2001":END] > -0.99).all().all()
mkt_tot = F["Mkt-RF"] + F["RF"]
IND = [c for c in ind.columns if c != "Other"]
spreads = ind[IND].sub(mkt_tot, axis=0).add_suffix("-Mkt")
X17 = X6.join(spreads, how="inner")


def r2_pair(y: pd.Series, X: pd.DataFrame) -> tuple[float, float, int, int]:
    r = ols(y, X)
    yv = r["y"]
    ssr = float((r["resid"] ** 2).sum())
    sst = float(((yv - yv.mean()) ** 2).sum())
    n, k = len(yv), X.shape[1]
    r2 = 1 - ssr / sst
    adj = 1 - (1 - r2) * (n - 1) / (n - k - 1)
    return r2, adj, n, k


secA2: dict = {}
for t, _ in FUNDS[1:]:
    active = (rets[t] - vti).dropna().loc[:END]
    for key, start in (("common", COMMON_START), ("own", None)):
        y = active.loc[start:] if start else active
        r6, a6, n, _ = r2_pair(y, X6)
        r17, a17, _, k17 = r2_pair(y, X17)
        secA2.setdefault(key, {})[t] = {
            "n": n,
            "r2_ff6": r6,
            "adj_r2_ff6": a6,
            "r2_ff6_ind": r17,
            "adj_r2_ff6_ind": a17,
            "k_ff6_ind": k17,
        }
        print(
            f"  {key:6s} {t:6s} n={n:3d}  FF6 R2 {100 * r6:5.1f} (adj {100 * a6:5.1f})"
            f"  FF6+ind R2 {100 * r17:5.1f} (adj {100 * a17:5.1f})"
        )
RESULTS["A2"] = secA2

# ---------------------------------------------------------------- section B
print(f"\nB. Mixes against VTI, {COMMON_START}..{END}, monthly rebalanced")
win = pd.concat({t: rets[t] for t in TICKERS}, axis=1).loc[COMMON_START:END]
assert win.notna().all().all()
secB = {}
for label, w in MIXES:
    port = sum(wt * win[t] for t, wt in w.items())
    d = decompose(port - win["VTI"], X6)
    d.pop("_resid")
    d.pop("_S")
    d["weights"] = w
    secB[label] = d
    print(
        f"  {label:28s} TE {100 * d['te']:4.2f}  factor share "
        f"{100 * d['factor_share']:5.1f}%  resid TE {100 * d['te_resid']:4.2f}"
    )
    print(
        "      loadings  "
        + " ".join(f"{c}:{v:+.3f}" for c, v in d["delta_beta"].items())
    )
    print(
        "      var share "
        + " ".join(f"{c}:{100 * v:+5.1f}" for c, v in d["contrib_share"].items())
        + f" resid:{100 * d['resid_share']:5.1f}"
    )
RESULTS["B"] = secB

# ---------------------------------------------------------------- section C
print(f"\nC. Tracking-error stability: {int(SLEEVE * 100)}% DFSVX sleeve vs market")
mkt = F["Mkt-RF"] + F["RF"]
act = (SLEEVE * (rets["DFSVX"] - mkt)).dropna().loc[:END]
fc = act.rolling(TRAIL).std(ddof=1) * math.sqrt(12)
rz = act.rolling(AHEAD).std(ddof=1).shift(-AHEAD) * math.sqrt(12)
pair = pd.concat({"forecast": fc, "realized": rz}, axis=1).dropna()
ratio = pair["realized"] / pair["forecast"]
k = AHEAD - 1
lo_band = math.sqrt(chi2_quantile(0.05, k) / k)
hi_band = math.sqrt(chi2_quantile(0.95, k) / k)
outside = float(((ratio < lo_band) | (ratio > hi_band)).mean())
above = float((ratio > hi_band).mean())
below = float((ratio < lo_band).mean())
real12 = rz.dropna()
worst = ratio.sort_values(ascending=False).head(8)
cal_years = act.groupby(act.index.year).std(ddof=1) * math.sqrt(12)
cal_years = cal_years[act.groupby(act.index.year).size() == 12]
secC = {
    "sleeve": SLEEVE,
    "active_window": [ym(act.index[0]), ym(act.index[-1])],
    "n_active": len(act),
    "full_te": float(act.std(ddof=1) * math.sqrt(12)),
    "pairs_window": [ym(pair.index[0]), ym(pair.index[-1])],
    "n_pairs": len(pair),
    "realized12_min": float(real12.min()),
    "realized12_min_end": ym(real12.idxmin() + pd.offsets.MonthEnd(AHEAD)),
    "realized12_max": float(real12.max()),
    "realized12_max_end": ym(real12.idxmax() + pd.offsets.MonthEnd(AHEAD)),
    "ratio_median": float(ratio.median()),
    "ratio_p10": float(ratio.quantile(0.10)),
    "ratio_p90": float(ratio.quantile(0.90)),
    "iid_band": [lo_band, hi_band],
    "share_outside_band": outside,
    "share_above_band": above,
    "share_below_band": below,
    "worst_underforecasts": [
        {
            "forecast_month": ym(i),
            "forecast": float(pair.loc[i, "forecast"]),
            "realized_next12": float(pair.loc[i, "realized"]),
            "ratio": float(v),
        }
        for i, v in worst.items()
    ],
    "calendar_year_te": {int(y): float(v) for y, v in cal_years.items()},
}
print(
    f"  active {secC['active_window'][0]}..{secC['active_window'][1]} "
    f"n={secC['n_active']}  full-period TE {100 * secC['full_te']:.2f}"
)
print(
    f"  forecast months {secC['pairs_window'][0]}..{secC['pairs_window'][1]} "
    f"n={secC['n_pairs']}"
)
print(
    f"  realized next-12 TE: min {100 * secC['realized12_min']:.2f} (12 mo to "
    f"{secC['realized12_min_end']}), max {100 * secC['realized12_max']:.2f} "
    f"(12 mo to {secC['realized12_max_end']})"
)
print(
    f"  realized/forecast: median {secC['ratio_median']:.2f}, p10 "
    f"{secC['ratio_p10']:.2f}, p90 {secC['ratio_p90']:.2f}"
)
print(
    f"  i.i.d. 90% band for a 12-month SD ratio [{lo_band:.3f}, {hi_band:.3f}]; "
    f"outside {100 * outside:.1f}% (expected 10%): above {100 * above:.1f}%, "
    f"below {100 * below:.1f}%"
)
print("  largest realized/forecast ratios:")
for wv in secC["worst_underforecasts"]:
    print(
        f"    forecast at {wv['forecast_month']}: {100 * wv['forecast']:.2f} -> "
        f"next 12 mo {100 * wv['realized_next12']:.2f} (x{wv['ratio']:.2f})"
    )
print(
    "  calendar-year TE: "
    + " ".join(f"{y}:{100 * v:.1f}" for y, v in secC["calendar_year_te"].items())
)
RESULTS["C"] = secC

# ---------------------------------------------------------------- section D
print("\nD. Pipeline check against factor-loadings-expected-returns (FF5, to 2026-08)")
pub = json.loads(
    (HERE.parent / "factor-loadings-expected-returns/output/results.json").read_text()
)["edges_vs_vti"]["AVUV"]["delta_beta"]
chk = ols((rets["AVUV"] - vti).loc[COMMON_START:"2026-08"], F[FF5])
diffs = {c: (float(chk["beta"][i]), pub[c]["coef"]) for i, c in enumerate(FF5)}
for c, (mine, theirs) in diffs.items():
    print(f"  {c:7s} this run {mine:+.4f}  published {theirs:+.4f}")
    assert abs(mine - theirs) < 0.01, (c, mine, theirs)
print("  matches to 2 dp")
RESULTS["D"] = {c: {"this_run": a, "published": b} for c, (a, b) in diffs.items()}

# ---------------------------------------------------------------- calculator
Fc = X6.loc[COMMON_START:END]
S_common = np.cov(Fc.to_numpy(), rowvar=False, ddof=1)
S_long = np.cov(X6.loc[LONG_START:END].to_numpy(), rowvar=False, ddof=1)
resid_cols = ["VTI"] + [t for t in TICKERS if t != "VTI"]
Rfull = R.copy()
Rfull.insert(0, "VTI", 0.0)
Rfull = Rfull[resid_cols]
S_e = np.cov(Rfull.to_numpy(), rowvar=False, ddof=1)
calc_funds = []
for t, name in FUNDS:
    db = [0.0] * 6 if t == "VTI" else list(secA["common"][t]["delta_beta"].values())
    calc_funds.append({"ticker": t, "name": name, "deltaBeta": db})
# exact check: the calculator's math reproduces section B
order = {t: i for i, t in enumerate(resid_cols)}
for label, w in MIXES:
    wv = np.zeros(len(resid_cols))
    for t, wt in w.items():
        wv[order[t]] = wt
    dbp = sum(wt * np.array(calc_funds[order[t]]["deltaBeta"]) for t, wt in w.items())
    te = math.sqrt(12 * (dbp @ S_common @ dbp + wv @ S_e @ wv))
    assert abs(te - secB[label]["te"]) < 1e-10, (label, te, secB[label]["te"])
calc = {
    "dataVintage": "Ken French 202609 CRSP database; Yahoo adjusted closes",
    "commonWindow": [COMMON_START, END],
    "nCommon": len(Fc),
    "longWindow": [LONG_START, END],
    "factors": FACTORS,
    "funds": calc_funds,
    "factorCov": {"fund": S_common.tolist(), "long": S_long.tolist()},
    "residCov": S_e.tolist(),
    "mixes": [
        {
            "label": label,
            "weights": w,
            "te": secB[label]["te"],
            "factorShare": secB[label]["factor_share"],
        }
        for label, w in MIXES
    ],
    "teHistory": [
        {
            "m": ym(i),
            "f": round(100 * float(pair.loc[i, "forecast"]), 3),
            "r": round(100 * float(pair.loc[i, "realized"]), 3),
        }
        for i in pair.index
    ],
    "teBand": [lo_band, hi_band],
}
(OUT / "quant-risk-model.json").write_text(json.dumps(calc, separators=(",", ":")))
(OUT / "results.json").write_text(json.dumps(RESULTS, indent=1))
print(f"\nWrote {rel(OUT / 'results.json')} and {rel(OUT / 'quant-risk-model.json')}")
