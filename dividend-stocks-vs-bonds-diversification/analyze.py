"""Are dividend stocks better diversifiers than bonds? A rerun of BofA's 34-of-40 statistic.

Supports https://summitward.com/learn/dividend-stocks-vs-bonds-diversification.

Requires numpy, pandas and yfinance.

The claim tested (BofA Global Research, Nov 2, 2026, as summarized by UnHideA):
"a factor constructed from the highest-yielding tenth of S&P 500 stocks had
returns relative to the index that were negatively correlated with index returns
in 34 of the past 40 years. In four of the past five years, its negative
correlation was stronger than that of gold, bonds, real estate and alternative
assets."

For any portfolio D and market M, within any sample,
    Cov(R_D - R_M, R_M) = Cov(R_D, R_M) - Var(R_M) = (beta - 1) Var(R_M),
so the correlation of relative returns with the market is negative exactly when
the in-sample beta is below 1. This script counts calendar years with a negative
absolute correlation Corr(R_D, R_M) and with a negative relative correlation
Corr(R_D - R_M, R_M), for high-dividend portfolios, a stock/T-bill mix, bonds,
gold and REITs, and runs the factor regressions.

Sources (Ken French CSVs committed in ./data/; Yahoo downloaded on first run and
cached in ./.cache/, which is not committed):
  * Ken French data library (Tuck), files built from the 202609 CRSP database,
    monthly percent returns converted to decimals:
      - Portfolios_Formed_on_D-P: sorted each June on trailing 12-month dividends
        per dollar of June market equity, NYSE breakpoints, NYSE/AMEX/NASDAQ
        stocks; non-payers sit only in the "<= 0" column. Sections "Value Weight
        Returns -- Monthly", "Equal Weight Returns -- Monthly" and "Number of
        Firms in Portfolios" are parsed by header.
      - F-F_Research_Data_Factors: Mkt-RF, SMB, HML, RF. Market total return is
        Mkt-RF + RF (CRSP value-weighted index); RF is the one-month T-bill.
      - F-F_Research_Data_5_Factors_2x3: Mkt-RF, SMB, HML, RMW, CMA, RF.
      - F-F_Momentum_Factor: Mom.
  * Yahoo Finance via yfinance: daily dividend-adjusted closes (auto_adjust=True),
    1985-01-01 to the 2026-11-23 close (end date frozen so reruns reproduce).
    Monthly returns are month-end to month-end; November 2026 is incomplete and
    dropped from monthly series. Mutual funds (VUSTX, VBMFX, VGSIX) rely on
    Yahoo's distribution adjustment, which can misstate single months.

Methods:
  * Calendar-year statistics use that year's 12 monthly returns (French and
    mutual-fund series) or its daily returns (ETFs). Only complete years count.
  * beta = Cov(R_D, R_M) / Var(R_M) within the same sample.
  * The 70/30 control holds 70% market and 30% T-bills, rebalanced monthly. The
    beta-matched control uses the top decile's 1986-2025 beta as its market weight.
  * OLS by numpy: classical t = b / sqrt(diag(s2 (X'X)^-1)); Newey-West t with 6
    lags (Bartlett weights). Alpha annualized as 12 x monthly intercept.
  * No fees, taxes or trading costs.
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
CACHE.mkdir(exist_ok=True)

YAHOO_START = "1985-01-01"
YAHOO_END = "2026-11-24"  # exclusive; last session is 2026-11-23
TICKERS = [
    "^SP500TR", "VUSTX", "VBMFX", "VGSIX", "GLD", "GC=F",
    "SPY", "SPYD", "SCHD", "VYM", "TLT", "IEF", "BND", "VNQ",
]
YEARS = list(range(1986, 2026))  # the 40 calendar years 1986-2025
NW_LAGS = 6
R: dict = {}


# ---------------------------------------------------------------- utilities
def rnd(x, d=4):
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return None
    return round(float(x), d)


def ym(idx) -> str:
    return pd.Timestamp(idx).strftime("%Y-%m")


def french_sections(name: str) -> dict[str, pd.DataFrame]:
    """Parse every monthly (YYYYMM-indexed) section of a committed French CSV."""
    text = (DATA / f"{name}.csv").read_text(encoding="latin-1")
    lines = text.splitlines()
    out: dict[str, pd.DataFrame] = {}
    i = 0
    title = "main"
    while i < len(lines):
        ln = lines[i]
        if ln.startswith(",") and i + 1 < len(lines):
            j = i - 1
            while j >= 0 and not lines[j].strip():
                j -= 1
            prev = lines[j].strip() if j >= 0 else ""
            if prev and not prev[:1].isdigit() and "," not in prev:
                title = prev
            cols = [c.strip() for c in ln.split(",")[1:]]
            rows = []
            k = i + 1
            while k < len(lines) and lines[k].strip():
                rows.append([p.strip() for p in lines[k].split(",")])
                k += 1
            if rows and len(rows[0][0]) == 6:
                df = pd.DataFrame(
                    [[float(x) for x in r[1:]] for r in rows],
                    index=pd.to_datetime([r[0] for r in rows], format="%Y%m")
                    + pd.offsets.MonthEnd(0),
                    columns=cols,
                )
                df = df.mask(df <= -99.99)
                key = title if title not in out else f"{title} ({len(out)})"
                out[key] = df
            i = k
            title = "main"
            continue
        i += 1
    return out


def ols(y: pd.Series, X: pd.DataFrame, lags: int = NW_LAGS) -> dict:
    d = pd.concat([y.rename("y"), X], axis=1).dropna()
    yv = d["y"].to_numpy()
    Xv = np.column_stack([np.ones(len(d)), d[X.columns].to_numpy()])
    n, k = Xv.shape
    XtXi = np.linalg.inv(Xv.T @ Xv)
    b = XtXi @ Xv.T @ yv
    e = yv - Xv @ b
    s2 = e @ e / (n - k)
    se = np.sqrt(np.diag(s2 * XtXi))
    u = Xv * e[:, None]
    S = u.T @ u
    for L in range(1, lags + 1):
        w = 1 - L / (lags + 1)
        G = u[L:].T @ u[:-L]
        S += w * (G + G.T)
    V = XtXi @ S @ XtXi * n / (n - k)
    se_nw = np.sqrt(np.diag(V))
    r2 = 1 - (e @ e) / np.sum((yv - yv.mean()) ** 2)
    adj = 1 - (1 - r2) * (n - 1) / (n - k)
    names = ["alpha"] + list(X.columns)
    return {
        "start": ym(d.index[0]),
        "end": ym(d.index[-1]),
        "n": int(n),
        "r2": rnd(r2),
        "adj_r2": rnd(adj),
        "alpha_ann": rnd(12 * b[0], 5),
        "coef": {nm: rnd(v) for nm, v in zip(names, b, strict=True)},
        "t": {nm: rnd(v, 2) for nm, v in zip(names, b / se, strict=True)},
        "t_nw": {nm: rnd(v, 2) for nm, v in zip(names, b / se_nw, strict=True)},
    }


def fmt_reg(label: str, r: dict) -> str:
    out = [
        f"{label}: {r['start']}..{r['end']} n={r['n']} adjR2={r['adj_r2']:.3f} "
        f"alpha={r['alpha_ann'] * 100:+.2f}%/yr "
        f"(t={r['t']['alpha']:.2f}, NW t={r['t_nw']['alpha']:.2f})"
    ]
    for nm, v in r["coef"].items():
        if nm != "alpha":
            out.append(
                f"    {nm:>7s} {v:+.3f} (t={r['t'][nm]:.2f}, NW t={r['t_nw'][nm]:.2f})"
            )
    return "\n".join(out)


def year_stats(p: pd.Series, m: pd.Series) -> dict | None:
    d = pd.concat([p.rename("p"), m.rename("m")], axis=1).dropna()
    if len(d) < 3:
        return None
    pv, mv = d["p"].to_numpy(), d["m"].to_numpy()
    rel = pv - mv
    beta = np.cov(pv, mv)[0, 1] / np.var(mv, ddof=1)
    return {
        "n": len(d),
        "abs": float(np.corrcoef(pv, mv)[0, 1]),
        "rel": float(np.corrcoef(rel, mv)[0, 1]),
        "beta": float(beta),
        "ret_p": float(np.prod(1 + pv) - 1),
        "ret_m": float(np.prod(1 + mv) - 1),
    }


def annual_rows(p: pd.Series, m: pd.Series, years, full: int) -> list[dict]:
    """Per-year stats, keeping only complete years (`full` observations)."""
    rows = []
    for y in years:
        mask = p.index.year == y
        s = year_stats(p[mask], m[m.index.year == y])
        if s is None or s["n"] < full:
            continue
        # identity check: sign of relative correlation equals sign of beta - 1
        assert np.sign(round(s["rel"], 12)) == np.sign(round(s["beta"] - 1, 12)), y
        rows.append({"year": y, **s})
    return rows


def count(rows: list[dict]) -> dict:
    return {
        "n": len(rows),
        "first": rows[0]["year"] if rows else None,
        "last": rows[-1]["year"] if rows else None,
        "abs_neg": sum(r["abs"] < 0 for r in rows),
        "rel_neg": sum(r["rel"] < 0 for r in rows),
    }


def monthly_full_years(p: pd.Series, m: pd.Series, years) -> list[dict]:
    return annual_rows(p, m, years, 12)


def window_stats(p: pd.Series, m: pd.Series, start, end) -> dict:
    d = pd.concat([p.rename("p"), m.rename("m")], axis=1).loc[start:end].dropna()
    s = year_stats(d["p"], d["m"])
    rel = d["p"] - d["m"]
    if np.allclose(rel, 0):  # the market against itself
        slope, s["rel"] = 0.0, float("nan")
    else:
        slope = ols(rel, d[["m"]])["coef"]["m"]
    return {
        "start": ym(d.index[0]),
        "end": ym(d.index[-1]),
        "n": len(d),
        "beta": rnd(s["beta"]),
        "abs": rnd(s["abs"]),
        "rel": rnd(s["rel"]),
        "vol": rnd(d["p"].std(ddof=1) * np.sqrt(12)),
        "beta_rel_regression": slope,
    }


# ---------------------------------------------------------------- data
print("=" * 78)
print("Loading Ken French data (202609 CRSP cut)")
ff3 = next(iter(french_sections("F-F_Research_Data_Factors").values())) / 100
ff5 = next(iter(french_sections("F-F_Research_Data_5_Factors_2x3").values())) / 100
mom = next(iter(french_sections("F-F_Momentum_Factor").values())) / 100
mom.columns = ["Mom"]
dp = french_sections("Portfolios_Formed_on_D-P")
VW = dp["Value Weight Returns -- Monthly"] / 100
EW = dp["Equal Weight Returns -- Monthly"] / 100
NFIRMS = dp["Number of Firms in Portfolios"]
MKT = (ff3["Mkt-RF"] + ff3["RF"]).rename("MKT")
RF = ff3["RF"]
FRENCH_END = MKT.index[-1]
print(f"  Market and RF {ym(MKT.index[0])}..{ym(FRENCH_END)}")
print(f"  D/P VW {ym(VW.index[0])}..{ym(VW.index[-1])}; columns {list(VW.columns)}")
R["meta"] = {
    "french_cut": "202609",
    "french_end": ym(FRENCH_END),
    "years": [YEARS[0], YEARS[-1]],
    "yahoo_end_exclusive": YAHOO_END,
}

print("Loading Yahoo Finance daily adjusted closes")
px_cache = CACHE / "yahoo_daily.csv"
if px_cache.exists():
    px = pd.read_csv(px_cache, index_col=0, parse_dates=True)
else:
    import yfinance as yf

    frames = {}
    for t in TICKERS:
        for attempt in range(5):
            try:
                d = yf.download(
                    t, start=YAHOO_START, end=YAHOO_END,
                    auto_adjust=True, progress=False,
                )
                if len(d):
                    frames[t] = d["Close"].squeeze().rename(t)
                    break
            except Exception as exc:  # noqa: BLE001
                print("   retry", t, exc)
            time.sleep(3 * (attempt + 1))
        else:
            raise SystemExit(f"Yahoo download failed for {t}")
    px = pd.DataFrame(frames)
    px.to_csv(px_cache)
last_day = px.index.max()
print(f"  Yahoo daily data through {last_day.date()}")
R["meta"]["yahoo_last_day"] = str(last_day.date())
me = px.resample("ME").last()
me = me.loc[: pd.Timestamp("2026-10-31")]  # drop incomplete November 2026
mret = me.pct_change(fill_method=None)
dret = px.pct_change(fill_method=None)
for t in TICKERS:
    s = px[t].dropna()
    print(f"   {t:9s} {s.index[0].date()}..{s.index[-1].date()}")

# ---------------------------------------------------------------- 1. French counts
print("=" * 78)
print("1. Ken French dividend-yield portfolios vs the CRSP market, calendar years")
print("   (12 monthly returns per year). abs = Corr(R_D, R_M); rel = Corr(R_D - R_M, R_M)")
variants = [
    ("vw_hi10", "Top 10% by yield, value-weighted", VW["Hi 10"]),
    ("ew_hi10", "Top 10% by yield, equal-weighted", EW["Hi 10"]),
    ("vw_hi20", "Top 20% by yield, value-weighted", VW["Hi 20"]),
    ("ew_hi20", "Top 20% by yield, equal-weighted", EW["Hi 20"]),
    ("vw_hi30", "Top 30% by yield, value-weighted", VW["Hi 30"]),
]
french_counts = []
rows_by_key = {}
for key, label, s in variants:
    rows = monthly_full_years(s, MKT, YEARS)
    rows_full = monthly_full_years(s, MKT, range(1928, 2026))
    c, cf = count(rows), count(rows_full)
    rows_by_key[key] = rows
    french_counts.append(
        {"key": key, "label": label, **c,
         "full_history": cf}
    )
    print(
        f"  {label:36s} 1986-2025: abs neg {c['abs_neg']:2d}/{c['n']}, "
        f"rel neg {c['rel_neg']:2d}/{c['n']} | 1928-2025: abs {cf['abs_neg']}/{cf['n']}, "
        f"rel {cf['rel_neg']}/{cf['n']}"
    )
R["french_counts"] = french_counts

# robustness: S&P 500 total return as the market (from 1989, first full year)
sp_m = mret["^SP500TR"]
print("  Robustness, S&P 500 total return (^SP500TR) as the market, 1989-2025:")
sp_rob = []
for key, label, s in variants[:3]:
    c = count(monthly_full_years(s, sp_m, YEARS))
    sp_rob.append({"key": key, "label": label, **c})
    print(f"    {label:36s} abs neg {c['abs_neg']}/{c['n']}, rel neg {c['rel_neg']}/{c['n']}")
corr_mkt_sp = MKT.to_frame().join(sp_m.rename("sp")).dropna().corr().iloc[0, 1]
print(f"    monthly corr of CRSP market with ^SP500TR: {corr_mkt_sp:.3f}")
R["sp500tr_robustness"] = {"rows": sp_rob, "corr_crsp_sp500tr": rnd(corr_mkt_sp, 3)}

# per-year table for the top decile (VW), the series charted in the guide
print("  Per year, top 10% value-weighted (abs corr / rel corr / beta / decile ret / market ret):")
dec_rows = rows_by_key["vw_hi10"]
for r in dec_rows:
    flag = "  <- beta > 1" if r["beta"] > 1 else ""
    print(
        f"    {r['year']} {r['abs']:+.3f} {r['rel']:+.3f} {r['beta']:5.2f} "
        f"{r['ret_p'] * 100:+6.1f}% {r['ret_m'] * 100:+6.1f}%{flag}"
    )
R["decile_years"] = [
    {"year": r["year"], "abs": rnd(r["abs"], 3), "rel": rnd(r["rel"], 3),
     "beta": rnd(r["beta"], 3), "ret": rnd(r["ret_p"]), "mkt": rnd(r["ret_m"])}
    for r in dec_rows
]
beta_gt1 = [r["year"] for r in dec_rows if r["beta"] > 1]
abs_neg_years = [r["year"] for r in dec_rows if r["abs"] < 0]
down = [r for r in dec_rows if r["ret_m"] < 0]
down_lost = [r for r in down if r["ret_p"] < 0]
print(f"  beta > 1 (positive relative correlation) in: {beta_gt1}")
print(f"  negative absolute correlation in: {abs_neg_years}")
print(
    f"  market down years: {[r['year'] for r in down]}; decile also lost money in "
    f"{len(down_lost)} of {len(down)}: {[r['year'] for r in down_lost]}"
)
for r in down:
    print(f"    {r['year']}: market {r['ret_m'] * 100:+.1f}%, top decile {r['ret_p'] * 100:+.1f}%")
R["decile_summary"] = {
    "beta_gt1_years": beta_gt1,
    "abs_neg_years": abs_neg_years,
    "market_down_years": [
        {"year": r["year"], "mkt": rnd(r["ret_m"]), "ret": rnd(r["ret_p"])} for r in down
    ],
    "down_years_decile_lost": len(down_lost),
}
nf = NFIRMS.loc["1986-01":"2025-12"]
R["firm_counts"] = {
    k: {"min": int(nf[k].min()), "max": int(nf[k].max()), "median": int(nf[k].median())}
    for k in ["Hi 10", "Hi 20"]
}
print(f"  firms in portfolio 1986-2025: {R['firm_counts']}")

# ---------------------------------------------------------------- 2. controls
print("=" * 78)
print("2. Controls with no stock selection")
full = window_stats(VW["Hi 10"], MKT, "1986-01", "2025-12")
w_beta = full["beta"]
controls = [
    ("mix_70_30", "70% market, 30% T-bills", 0.7 * MKT + 0.3 * RF),
    ("mix_beta", f"{w_beta:.0%} market, rest T-bills (top decile's beta)",
     w_beta * MKT + (1 - w_beta) * RF),
]
ctrl_out = []
for key, label, s in controls:
    c = count(monthly_full_years(s, MKT, YEARS))
    cf = count(monthly_full_years(s, MKT, range(1928, 2026)))
    ctrl_out.append({"key": key, "label": label, **c, "full_history": cf})
    print(
        f"  {label:46s} abs neg {c['abs_neg']}/{c['n']}, rel neg {c['rel_neg']}/{c['n']}"
        f" | 1928-2025 rel {cf['rel_neg']}/{cf['n']}"
    )
R["controls"] = ctrl_out
R["beta_matched_weight"] = w_beta

# ---------------------------------------------------------------- 3. other assets
print("=" * 78)
print("3. Bonds, gold and REITs vs the CRSP market, same two statistics")
others = [
    ("vustx", "Long-term Treasuries (VUSTX)", mret["VUSTX"]),
    ("vbmfx", "Total bond market (VBMFX)", mret["VBMFX"]),
    ("gld", "Gold (GLD)", mret["GLD"]),
    ("gcf", "Gold futures (GC=F)", mret["GC=F"]),
    ("vgsix", "REITs (VGSIX)", mret["VGSIX"]),
]
other_out = []
for key, label, s in others:
    rows = monthly_full_years(s, MKT, YEARS)
    c = count(rows)
    yrs = [r["year"] for r in rows]
    dec_same = count([r for r in dec_rows if r["year"] in yrs])
    other_out.append({"key": key, "label": label, **c, "decile_same_years": dec_same})
    print(
        f"  {label:30s} {c['first']}-{c['last']}: abs neg {c['abs_neg']:2d}/{c['n']}, "
        f"rel neg {c['rel_neg']:2d}/{c['n']} | top decile same years: abs "
        f"{dec_same['abs_neg']}/{dec_same['n']}, rel {dec_same['rel_neg']}/{dec_same['n']}"
    )
    pos = [r["year"] for r in rows if r["rel"] >= 0]
    if pos:
        print(f"      years with non-negative relative correlation: {pos}")
R["other_assets"] = other_out

# BofA's own text applies the cross-asset comparison to 34 of the past 40 years:
# the decile's relative-return correlation "more negatively correlated with S&P
# 500 returns than gold, bonds real estate and alternatives". Count the years in
# which the decile's relative correlation is below each asset's correlation,
# scoring the asset on its actual returns (mixed) and on its relative returns
# (same treatment as the decile).
print("  BofA's 40-year cross-asset comparison, top 10% VW relative correlation vs:")
dec_by_year = {r["year"]: r for r in dec_rows}
by_asset = {}
year_sets = {}
for key, label, s in others:
    if key == "gcf":
        continue
    rows = {r["year"]: r for r in monthly_full_years(s, MKT, YEARS)}
    year_sets[key] = rows
    mixed = sum(dec_by_year[y]["rel"] < r["abs"] for y, r in rows.items())
    same = sum(dec_by_year[y]["rel"] < r["rel"] for y, r in rows.items())
    yrs = sorted(rows)
    by_asset[key] = {"label": label, "n": len(rows), "first": yrs[0], "last": yrs[-1],
                     "mixed": int(mixed), "same": int(same)}  # fmt: skip
    print(
        f"    {label:30s} {yrs[0]}-{yrs[-1]} n={len(rows)}: below its actual corr "
        f"{mixed}, below its relative corr {same}"
    )
bond_years = sorted(year_sets["vustx"])
mixed_all = same_all = 0
for y in bond_years:
    avail = [year_sets[k][y] for k in year_sets if y in year_sets[k]]
    d = dec_by_year[y]["rel"]
    mixed_all += all(d < r["abs"] for r in avail)
    same_all += all(d < r["rel"] for r in avail)
print(
    f"    Every available asset at once (bonds, REITs from 1997, gold from 2005), "
    f"{bond_years[0]}-{bond_years[-1]}: mixed {mixed_all} of {len(bond_years)}, "
    f"same {same_all} of {len(bond_years)}"
)
R["bofa_40yr_test"] = {
    "by_asset": by_asset,
    "all_available": {"n": len(bond_years), "first": bond_years[0],
                      "last": bond_years[-1], "mixed": int(mixed_all),
                      "same": int(same_all)},  # fmt: skip
}

# the counts table charted in the guide
chart = []
lookup = {d["key"]: d for d in french_counts + ctrl_out + other_out}
for key, short in [
    ("vw_hi10", "Top 10% dividend yield"),
    ("vw_hi20", "Top 20% dividend yield"),
    ("mix_70_30", "70% stocks, 30% T-bills"),
    ("vustx", "Long-term Treasuries"),
    ("vbmfx", "Total bond market"),
    ("gld", "Gold (GLD)"),
    ("vgsix", "REITs"),
]:
    d = lookup[key]
    chart.append(
        {"key": key, "label": short, "n": d["n"], "first": d["first"], "last": d["last"],
         "abs_neg": d["abs_neg"], "rel_neg": d["rel_neg"]}
    )
R["counts_chart"] = chart

# ---------------------------------------------------------------- 4. full period
print("=" * 78)
print("4. Full-period monthly statistics (1986-01..2025-12 or the asset's own window)")
fp = []
for key, label, s in [
    ("vw_hi10", "Top 10% VW", VW["Hi 10"]),
    ("ew_hi10", "Top 10% EW", EW["Hi 10"]),
    ("vw_hi20", "Top 20% VW", VW["Hi 20"]),
    ("market", "CRSP market", MKT),
    ("vustx", "VUSTX", mret["VUSTX"]),
    ("vbmfx", "VBMFX", mret["VBMFX"]),
    ("gld", "GLD", mret["GLD"]),
    ("vgsix", "VGSIX", mret["VGSIX"]),
]:
    w = window_stats(s, MKT, "1986-01", "2025-12")
    fp.append({"key": key, "label": label, **w})
    print(
        f"  {label:12s} {w['start']}..{w['end']} n={w['n']}: beta {w['beta']:+.3f} "
        f"abs {w['abs']:+.3f} rel {'n/a' if w['rel'] is None else format(w['rel'], '+.3f')} "
        f"vol {w['vol'] * 100:.1f}% | "
        f"regression slope of relative returns {w['beta_rel_regression']:+.4f}"
    )
    assert abs(w["beta_rel_regression"] - (w["beta"] - 1)) < 1e-3
R["full_period"] = fp

# ---------------------------------------------------------------- 4b. long history
print("=" * 78)
print("4b. Long history, July 1927 to June 2026: risk, a beta-matched blend, and")
print("    every U.S. market decline of 20% or more (monthly, peak to trough)")


def long_stats(r: pd.Series, rf: pd.Series) -> dict:
    n = len(r)
    wealth = (1 + r).cumprod()
    ex = r - rf
    return {
        "cagr": rnd(wealth.iloc[-1] ** (12 / n) - 1),
        "vol": rnd(r.std(ddof=1) * np.sqrt(12)),
        "sharpe": rnd(ex.mean() * 12 / (ex.std(ddof=1) * np.sqrt(12)), 3),
        "max_dd": rnd((wealth / wealth.cummax() - 1).min()),
    }


LH = slice("1927-07", "2026-06")
mkt_lh, rf_lh = MKT.loc[LH], RF.loc[LH]
long_out = {"start": "1927-07", "end": "2026-06", "n": int(len(mkt_lh))}
for key, s in [("vw_hi10", VW["Hi 10"]), ("vw_hi30", VW["Hi 30"])]:
    sl = s.loc[LH]
    b = year_stats(sl, mkt_lh)["beta"]
    blend = b * mkt_lh + (1 - b) * rf_lh
    long_out[key] = {"beta": rnd(b, 3), **long_stats(sl, rf_lh),
                     "blend": long_stats(blend, rf_lh)}  # fmt: skip
long_out["market"] = long_stats(mkt_lh, rf_lh)
for k in ["vw_hi10", "vw_hi30"]:
    d = long_out[k]
    print(
        f"  {k}: beta {d['beta']:.3f} CAGR {d['cagr'] * 100:.2f}% vol {d['vol'] * 100:.2f}% "
        f"Sharpe {d['sharpe']:.3f} maxDD {d['max_dd'] * 100:.1f}% | beta-matched blend CAGR "
        f"{d['blend']['cagr'] * 100:.2f}% vol {d['blend']['vol'] * 100:.2f}% Sharpe "
        f"{d['blend']['sharpe']:.3f}"
    )
m = long_out["market"]
print(f"  market: CAGR {m['cagr'] * 100:.2f}% vol {m['vol'] * 100:.2f}% Sharpe {m['sharpe']:.3f}")

# drawdown episodes: from each market peak to the lowest month-end before the
# market regains that peak; keep declines of 20% or more
w = (1 + mkt_lh).cumprod()
episodes, peak_i, trough_i = [], 0, 0
vals = w.to_numpy()
for i in range(1, len(vals)):
    if vals[i] >= vals[peak_i]:
        if vals[trough_i] / vals[peak_i] - 1 <= -0.20:
            episodes.append((peak_i, trough_i))
        peak_i = trough_i = i
    elif vals[i] < vals[trough_i]:
        trough_i = i
if vals[trough_i] / vals[peak_i] - 1 <= -0.20 and trough_i > peak_i:
    episodes.append((peak_i, trough_i))
ep_out = []
for pk, tr in episodes:
    win = slice(w.index[pk + 1], w.index[tr])  # returns after the peak month-end
    row = {"peak": ym(w.index[pk]), "trough": ym(w.index[tr]),
           "market": rnd(np.prod(1 + mkt_lh.loc[win]) - 1)}  # fmt: skip
    for key, s in [("vw_hi10", VW["Hi 10"]), ("vw_hi30", VW["Hi 30"])]:
        row[key] = rnd(np.prod(1 + s.loc[win]) - 1)
    ep_out.append(row)
    print(
        f"  {row['peak']} -> {row['trough']}: market {row['market'] * 100:+.1f}%, "
        f"top 10% {row['vw_hi10'] * 100:+.1f}%, top 30% {row['vw_hi30'] * 100:+.1f}%"
    )
worse10 = sum(e["vw_hi10"] < e["market"] for e in ep_out)
worse30 = sum(e["vw_hi30"] < e["market"] for e in ep_out)
print(
    f"  {len(ep_out)} declines of 20%+: top 10% fell further in {worse10}, "
    f"top 30% in {worse30}"
)
long_out["declines_20pct"] = {"episodes": ep_out, "worse_hi10": worse10,
                              "worse_hi30": worse30}  # fmt: skip
R["long_history"] = long_out

# ---------------------------------------------------------------- 4c. common window
print("=" * 78)
print("4c. Common window 2005-01 to 2025-12: size of the differences, not just signs")
CW = slice("2005-01", "2025-12")
cw_rows = []
for key, label, s in [
    ("vw_hi10", "Top 10% by yield", VW["Hi 10"]),
    ("market", "U.S. market", MKT),
    ("vustx", "Long-term Treasuries (VUSTX)", mret["VUSTX"]),
    ("vbmfx", "Total bond market (VBMFX)", mret["VBMFX"]),
    ("gld", "Gold (GLD)", mret["GLD"]),
    ("vgsix", "REITs (VGSIX)", mret["VGSIX"]),
]:
    d = pd.concat([s.rename("p"), MKT.rename("m")], axis=1).loc[CW].dropna()
    st = year_stats(d["p"], d["m"])
    wealth = (1 + d["p"]).cumprod()
    cw_rows.append({
        "key": key, "label": label, "n": len(d),
        "corr": rnd(st["abs"], 3), "beta": rnd(st["beta"], 3),
        "vol": rnd(d["p"].std(ddof=1) * np.sqrt(12)),
        "max_dd": rnd((wealth / wealth.cummax() - 1).min()),
        "cagr": rnd(wealth.iloc[-1] ** (12 / len(d)) - 1),
    })  # fmt: skip
cwd = pd.concat(
    [VW["Hi 10"].rename("vw_hi10"), MKT.rename("market"), mret["VUSTX"].rename("vustx"),
     mret["VBMFX"].rename("vbmfx"), mret["GLD"].rename("gld"),
     mret["VGSIX"].rename("vgsix")], axis=1,
).loc[CW].dropna()  # fmt: skip
cut = cwd["market"].quantile(0.10)
worst = cwd[cwd["market"] <= cut]
for r in cw_rows:
    r["worst10_avg"] = rnd(worst[r["key"]].mean())
    print(
        f"  {r['label']:30s} n={r['n']} corr {r['corr']:+.2f} beta {r['beta']:+.2f} "
        f"vol {r['vol'] * 100:5.1f}% maxDD {r['max_dd'] * 100:6.1f}% "
        f"CAGR {r['cagr'] * 100:5.2f}% worst-10% months avg {r['worst10_avg'] * 100:+.2f}%"
    )
print(f"  worst 10% of market months: n={len(worst)}, market return <= {cut * 100:.2f}%")
R["common_window"] = {"start": "2005-01", "end": "2025-12", "n": int(len(cwd)),
                      "worst10_n": int(len(worst)), "rows": cw_rows}  # fmt: skip

# sampling noise in the yearly signs (12 monthly observations per year)
rel = np.array([r["rel"] for r in dec_rows])
noise = {"n": len(rel), "within_033": int((np.abs(rel) < 0.33).sum()),
         "below_neg033": int((rel < -0.33).sum())}  # fmt: skip
print(
    f"  Top 10% yearly relative correlations within 0.33 of zero (about one standard "
    f"error with 12 months): {noise['within_033']} of {noise['n']}; below -0.33: "
    f"{noise['below_neg033']}"
)
R["sign_noise"] = noise

# cross-check the unusual 2023 long-Treasury beta with an independent fund
chk = {}
for t in ["VUSTX", "TLT"]:
    s = mret[t]
    st = year_stats(s[s.index.year == 2023], MKT[MKT.index.year == 2023])
    chk[t] = {"beta": rnd(st["beta"], 3), "corr": rnd(st["abs"], 3), "ret": rnd(st["ret_p"])}
print(f"  2023 long-Treasury check vs the market: {chk}")
R["treasury_2023_check"] = chk

# ---------------------------------------------------------------- 5. regressions
print("=" * 78)
print("5. Factor regressions, excess returns over T-bills (OLS, Newey-West 6 lags)")
f5 = ff5.join(mom, how="left")
regs = {}
specs = [
    ("capm", ["Mkt-RF"], ff3),
    ("ff3", ["Mkt-RF", "SMB", "HML"], ff3),
    ("ff5_mom", ["Mkt-RF", "SMB", "HML", "RMW", "CMA", "Mom"], f5),
]
for pkey, s in [("vw_hi10", VW["Hi 10"]), ("vw_hi20", VW["Hi 20"]), ("ew_hi10", EW["Hi 10"])]:
    regs[pkey] = {}
    for name, cols, F in specs:
        y = (s - F["RF"]).loc["1986-01":"2025-12"]
        r = ols(y, F[cols].loc["1986-01":"2025-12"])
        regs[pkey][name] = r
        print(fmt_reg(f"  {pkey} {name}", r))
    y = (s - f5["RF"]).loc["1986-01":]
    r = ols(y, f5[["Mkt-RF", "SMB", "HML", "RMW", "CMA", "Mom"]].loc["1986-01":])
    regs[pkey]["ff5_mom_latest"] = r
    print(fmt_reg(f"  {pkey} ff5_mom through latest", r))
R["regressions"] = regs

# ---------------------------------------------------------------- 6. ETFs, daily
print("=" * 78)
print("6. Dividend ETFs vs SPY, daily returns, complete calendar years")
etf_out = []
for t, first in [("SPYD", 2016), ("SCHD", 2012), ("VYM", 2007)]:
    rows = []
    for y in range(first, 2026):
        mask = dret.index.year == y
        s = year_stats(dret[t][mask], dret["SPY"][mask])
        rows.append({"year": y, **s})
        assert np.sign(round(s["rel"], 12)) == np.sign(round(s["beta"] - 1, 12))
    c = count(rows)
    pos = [r["year"] for r in rows if r["rel"] >= 0]
    etf_out.append({"ticker": t, **c, "beta_gt1_years": pos,
                    "beta_by_year": {r["year"]: rnd(r["beta"], 3) for r in rows}})
    print(f"  {t}: abs neg {c['abs_neg']}/{c['n']}, rel neg {c['rel_neg']}/{c['n']}; beta>1 in {pos}")
R["etf_daily_counts"] = etf_out

# ---------------------------------------------------------------- 7. recent years
print("=" * 78)
print("7. The 'four of the past five years' comparison, daily returns vs SPY")
print("   (SPYD stands in for the top-yield decile of the S&P 500; 2026 is to Nov 23)")
recent = []
assets = ["SPYD", "TLT", "IEF", "BND", "GLD", "VNQ"]
for y in range(2021, 2027):
    mask = dret.index.year == y
    row = {"year": y, "n": int(mask.sum()), "partial": y == 2026}
    for a in assets:
        s = year_stats(dret[a][mask], dret["SPY"][mask])
        row[a] = {"abs": rnd(s["abs"], 3), "rel": rnd(s["rel"], 3), "beta": rnd(s["beta"], 3)}
    recent.append(row)
    print(
        f"  {y}{'*' if y == 2026 else ' '} n={row['n']:3d} SPYD abs {row['SPYD']['abs']:+.2f} "
        f"rel {row['SPYD']['rel']:+.2f} | abs: "
        + " ".join(f"{a} {row[a]['abs']:+.2f}" for a in assets[1:])
        + " | rel: "
        + " ".join(f"{a} {row[a]['rel']:+.2f}" for a in assets[1:])
    )
# under mixed scoring: SPYD relative vs each other asset's absolute
for row in recent:
    if row["partial"]:
        continue
    beats_mixed = all(row["SPYD"]["rel"] < row[a]["abs"] for a in assets[1:])
    beats_same = all(row["SPYD"]["rel"] < row[a]["rel"] for a in assets[1:])
    row["spyd_rel_below_all_abs"] = beats_mixed
    row["spyd_rel_below_all_rel"] = beats_same
mixed = sum(r.get("spyd_rel_below_all_abs", False) for r in recent)
same = sum(r.get("spyd_rel_below_all_rel", False) for r in recent)
print(
    f"  2021-2025: SPYD's relative correlation was below every other asset's ABSOLUTE "
    f"correlation in {mixed} of 5 years; below every other asset's RELATIVE correlation "
    f"in {same} of 5"
)
R["recent_daily"] = recent
R["recent_daily_summary"] = {"mixed_scoring_years": mixed, "same_scoring_years": same}

# monthly version against the CRSP market, for the French top decile
print("  Monthly version, 2021-2025, vs CRSP market:")
rm = []
for y in range(2021, 2026):
    row = {"year": y}
    for key, s in [("vw_hi10", VW["Hi 10"]), ("vustx", mret["VUSTX"]),
                   ("vbmfx", mret["VBMFX"]), ("gld", mret["GLD"]), ("vgsix", mret["VGSIX"])]:
        st = year_stats(s[s.index.year == y], MKT[MKT.index.year == y])
        row[key] = {"abs": rnd(st["abs"], 3), "rel": rnd(st["rel"], 3)}
    rm.append(row)
    print(
        f"    {y} top decile rel {row['vw_hi10']['rel']:+.2f} | abs: "
        + " ".join(f"{k} {row[k]['abs']:+.2f}" for k in ["vustx", "vbmfx", "gld", "vgsix"])
        + " | rel: "
        + " ".join(f"{k} {row[k]['rel']:+.2f}" for k in ["vustx", "vbmfx", "gld", "vgsix"])
    )
R["recent_monthly"] = rm

# ---------------------------------------------------------------- 8. episodes
print("=" * 78)
print("8. Episodes")
r22 = {}
for t in ["SPY", "SCHD", "SPYD", "VYM", "BND", "GLD"]:
    s = px[t].dropna()
    r22[t] = rnd(s.loc[:"2022-12-31"].iloc[-1] / s.loc[:"2021-12-31"].iloc[-1] - 1)
print("  2022 total return: " + ", ".join(f"{k} {v * 100:+.1f}%" for k, v in r22.items()))
R["returns_2022"] = r22
factor_years = {}
for y in [2000, 2001, 2022]:
    hml = float(np.prod(1 + ff3["HML"][ff3.index.year == y]) - 1)
    mkt = float(np.prod(1 + MKT[MKT.index.year == y]) - 1)
    print(f"  {y} value factor (HML) {hml * 100:+.1f}%; CRSP market {mkt * 100:+.1f}%")
    factor_years[str(y)] = {"hml": rnd(hml), "mkt": rnd(mkt)}
R["factor_years"] = factor_years
covid = {}
for t in ["SPY", "SCHD", "SPYD", "VYM"]:
    s = px[t].dropna()
    pk = s.loc["2020-01-01":"2020-02-29"]
    pk_date = pk.idxmax()
    tr = s.loc[pk_date:"2020-04-30"]
    tr_date = tr.idxmin()
    covid[t] = {
        "peak": str(pk_date.date()),
        "trough": str(tr_date.date()),
        "drawdown": rnd(tr.min() / pk.max() - 1),
    }
    print(
        f"  COVID {t}: {covid[t]['drawdown'] * 100:+.1f}% "
        f"({covid[t]['peak']} to {covid[t]['trough']})"
    )
R["covid"] = covid
m20 = dret.index.year == 2020
b20 = year_stats(dret["SPYD"][m20], dret["SPY"][m20])["beta"]
print(f"  SPYD daily beta to SPY in 2020: {b20:.2f}")
R["spyd_beta_2020"] = rnd(b20, 3)

# trailing correlations ending Oct 31, 2026 (monthly)
print("  Trailing monthly correlation with SPY ending 2026-10:")
tc = {}
for t in ["SCHD", "SPYD", "VYM"]:
    tc[t] = {}
    for yrs in [1, 3, 5, 10]:
        d = mret[[t, "SPY"]].loc[:"2026-10-31"].dropna().iloc[-12 * yrs:]
        tc[t][f"{yrs}y"] = rnd(d.corr().iloc[0, 1], 3)
    roll = mret[[t, "SPY"]].dropna().loc[:"2026-10-31"]
    rc = roll[t].rolling(12).corr(roll["SPY"]).loc["2024-11-30":]
    tc[t]["rolling12_min_since_2024_11"] = rnd(rc.min(), 2)
    tc[t]["rolling12_max_since_2024_11"] = rnd(rc.max(), 2)
    print(f"    {t}: {tc[t]}")
d = me[["SCHD", "SPY"]].loc["2025-10-31":"2026-10-31"]
tc["schd_spy_12m_returns"] = {
    "SCHD": rnd(d["SCHD"].iloc[-1] / d["SCHD"].iloc[0] - 1),
    "SPY": rnd(d["SPY"].iloc[-1] / d["SPY"].iloc[0] - 1),
}
print(f"    12 months to 2026-10: {tc['schd_spy_12m_returns']}")
R["trailing_corr"] = tc

# ---------------------------------------------------------------- write
(HERE / "results.json").write_text(json.dumps(R, indent=1) + "\n")
print("=" * 78)
print("Wrote results.json")
