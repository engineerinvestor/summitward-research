"""Quality Minus Junk (QMJ): in-sample, post-publication, and fund loadings.

Supports https://summitward.com/learn/quality-minus-junk.

Requires numpy, pandas, openpyxl (AQR spreadsheets) and yfinance.

Sources (Ken French CSVs committed in ./data/; AQR and Yahoo downloaded on
first run and cached in ./.cache/, which is not committed):
  * Ken French data library (Tuck), monthly, percent returns converted to
    decimals:
      - F-F_Research_Data_Factors: Mkt-RF, SMB, HML, RF (from 1926-07)
      - F-F_Research_Data_5_Factors_2x3: Mkt-RF, SMB, HML, RMW, CMA, RF
        (from 1963-07)
      - F-F_Momentum_Factor: Mom
  * AQR "Quality Minus Junk: Factors, Monthly" xlsx, sheet "QMJ Factors",
    columns USA and Global (decimal monthly self-financing excess returns).
  * AQR "Betting Against Beta: Equity Factors, Monthly" xlsx, sheet
    "BAB Factors", column USA.
  * Yahoo Finance via yfinance: daily adjusted closes (auto_adjust=True, so
    dividends are reinvested), resampled to the last trading day of each
    month. The current, incomplete month is dropped.

AQR reconstructs the full QMJ history on every update, so these figures
differ from the tables in Asness, Frazzini and Pedersen (2019), and a later
download can move them. The paper's sample ends 2016-12, so 2017-01 onward
is treated as post-publication.

Sections:
  1. QMJ summary statistics by period (USA and Global), including a run that
     drops July 2026, the largest QMJ month in the USA file, so the reader
     can see how much the post-2016 average depends on one month.
  2. QMJ regressions: four-factor (FF3 + Mom) 1957-07..2016-12 as a rough
     check against the paper's 0.60%/month; FF5 + Mom 1963-07..2016-12
     (paper: 0.33%/month with its own factor construction); the same model
     and one with BAB added over 2017-01 to the latest month.
  3. Fund regressions over each fund's own window and over a common window:
     FF5 + Mom (RMW is the profitability loading), FF3 + Mom + QMJ (QMJ is the
     quality loading), and FF5 + Mom + QMJ (does QMJ add anything once RMW is
     in the model).

Methods:
  * Annualized mean = 12 x monthly mean; vol = sqrt(12) x monthly std
    (ddof=1); Sharpe = annualized mean / annualized vol (QMJ and BAB are
    already excess returns); t-stat of the mean = mean / (std / sqrt(n)).
  * OLS by numpy with classical and Newey-West (6 lags, Bartlett) t-stats.
    Alpha is 12 x the monthly intercept.
  * Nothing here is a forecast. Every figure describes a named past window.
"""

from __future__ import annotations

import json
import time
import urllib.request
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"  # committed Ken French CSVs
CACHE = HERE / ".cache"  # AQR and Yahoo downloads, not redistributed
OUT = HERE / "output"
CACHE.mkdir(exist_ok=True)
OUT.mkdir(exist_ok=True)
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"
)
FRENCH = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/{}_CSV.zip"
AQR_BASE = "https://www.aqr.com/-/media/AQR/Documents/Insights/Data-Sets/"
AQR_QMJ = AQR_BASE + "Quality-Minus-Junk-Factors-Monthly.xlsx"
AQR_BAB = AQR_BASE + "Betting-Against-Beta-Equity-Factors-Monthly.xlsx"

# (ticker, label, group). Group sorts the guide's table by what the fund
# tries to do rather than alphabetically.
FUNDS = [
    ("AVUV", "Avantis US Small Cap Value", "Screened SCV"),
    ("DFSV", "Dimensional US Small Cap Value", "Screened SCV"),
    ("DFAT", "Dimensional US Targeted Value", "Screened SCV"),
    ("IJS", "iShares S&P SmallCap 600 Value", "Index SCV"),
    ("VBR", "Vanguard Morningstar Small-Cap Value", "Index SCV"),
    ("IWN", "iShares Russell 2000 Value", "Index SCV"),
    ("QUAL", "iShares MSCI USA Quality Factor", "Quality"),
    ("SPHQ", "Invesco S&P 500 Quality", "Quality"),
    ("JQUA", "JPMorgan US Quality Factor", "Quality"),
    ("VTI", "Vanguard Total Stock Market", "Market"),
]
# Common window: every fund above except DFSV and DFAT, whose short histories
# would shrink the shared window to a stretch too short to mean much. They
# keep their own-window rows, each labelled with its window.
COMMON = ["AVUV", "IJS", "VBR", "IWN", "QUAL", "SPHQ", "JQUA", "VTI"]

FF5 = ["Mkt-RF", "SMB", "HML", "RMW", "CMA"]
MODELS = {
    "ff5mom": FF5 + ["Mom"],
    "ff3mom_qmj": ["Mkt-RF", "SMB", "HML", "Mom", "QMJ"],
    "ff5mom_qmj": FF5 + ["Mom", "QMJ"],
}
NW_LAGS = 6
RESULTS: dict = {"sources": {}, "failures": []}


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


def aqr_sheet(url: str, dest: str, sheet: str, cols: list[str]) -> pd.DataFrame:
    raw = pd.read_excel(fetch(url, CACHE / dest), sheet, header=None)
    hdr = raw.index[raw.iloc[:, 0].astype(str).str.strip() == "DATE"][0]
    body = raw.iloc[hdr + 1 :].copy()
    body.columns = [str(c).strip() for c in raw.iloc[hdr]]
    dates = pd.to_datetime(body["DATE"], format="%m/%d/%Y", errors="coerce")
    body = body[dates.notna()]
    body.index = dates[dates.notna()] + pd.offsets.MonthEnd(0)
    return body[cols].apply(pd.to_numeric, errors="coerce")


def summary(r: pd.Series) -> dict:
    r = r.dropna()
    n = len(r)
    mean, sd = r.mean(), r.std(ddof=1)
    wealth = (1 + r).cumprod()
    dd = wealth / wealth.cummax() - 1
    return {
        "start": ym(r.index[0]),
        "end": ym(r.index[-1]),
        "n": n,
        "mean_monthly": float(mean),
        "mean_ann": float(12 * mean),
        "vol_ann": float(np.sqrt(12) * sd),
        "sharpe": float(12 * mean / (np.sqrt(12) * sd)),
        "t_mean": float(mean / (sd / np.sqrt(n))),
        "max_drawdown": float(dd.min()),
        "pct_months_positive": float((r > 0).mean()),
    }


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
    names = ["alpha"] + list(X.columns)
    return {
        "start": ym(d.index[0]),
        "end": ym(d.index[-1]),
        "n": int(n),
        "r2": float(r2),
        "alpha_monthly": float(b[0]),
        "alpha_ann": float(12 * b[0]),
        "coef": {nm: float(v) for nm, v in zip(names, b, strict=True)},
        "t": {nm: float(v) for nm, v in zip(names, b / se, strict=True)},
        "t_nw": {nm: float(v) for nm, v in zip(names, b / se_nw, strict=True)},
    }


def fmt_reg(label: str, r: dict) -> str:
    lines = [
        f"{label}: {r['start']}..{r['end']} n={r['n']} R2={r['r2']:.2f} "
        f"alpha={r['alpha_monthly'] * 100:+.2f}%/mo "
        f"({r['alpha_ann'] * 100:+.2f}%/yr, t={r['t']['alpha']:.2f}, "
        f"NW t={r['t_nw']['alpha']:.2f})"
    ]
    for nm, v in r["coef"].items():
        if nm != "alpha":
            lines.append(
                f"    {nm:>7s} {v:+.3f} (t={r['t'][nm]:.2f}, "
                f"NW t={r['t_nw'][nm]:.2f})"
            )
    return "\n".join(lines)


def fmt_sum(label: str, s: dict) -> str:
    return (
        f"  {label:34s} {s['start']}..{s['end']} n={s['n']:3d} "
        f"mean={s['mean_monthly'] * 100:+.2f}%/mo ({s['mean_ann'] * 100:+.1f}%/yr) "
        f"vol={s['vol_ann'] * 100:.1f}% Sharpe={s['sharpe']:.2f} "
        f"t={s['t_mean']:.2f} maxDD={s['max_drawdown'] * 100:.1f}% "
        f"up={s['pct_months_positive'] * 100:.0f}%"
    )


# ---------------------------------------------------------------- load data
print("Loading Ken French factors")
ff3 = french_main("F-F_Research_Data_Factors")
ff5 = french_main("F-F_Research_Data_5_Factors_2x3")
mom = french_main("F-F_Momentum_Factor").iloc[:, 0].rename("Mom")
print(
    f"  FF3 {ym(ff3.index[0])}..{ym(ff3.index[-1])}; "
    f"FF5 {ym(ff5.index[0])}..{ym(ff5.index[-1])}; "
    f"Mom {ym(mom.index[0])}..{ym(mom.index[-1])}"
)

print("Loading AQR QMJ and BAB")
qmj_all = aqr_sheet(AQR_QMJ, "qmj.xlsx", "QMJ Factors", ["USA", "Global"])
qmj = qmj_all["USA"].dropna().rename("QMJ")
qmj_g = qmj_all["Global"].dropna().rename("QMJ_Global")
bab = (
    aqr_sheet(AQR_BAB, "bab.xlsx", "BAB Factors", ["USA"])["USA"]
    .dropna()
    .rename("BAB")
)
print(
    f"  QMJ USA {ym(qmj.index[0])}..{ym(qmj.index[-1])}; "
    f"Global {ym(qmj_g.index[0])}..{ym(qmj_g.index[-1])}; "
    f"BAB USA {ym(bab.index[0])}..{ym(bab.index[-1])}"
)
RESULTS["sources"].update(
    {
        "french_ff5": [ym(ff5.index[0]), ym(ff5.index[-1])],
        "aqr_qmj_usa": [ym(qmj.index[0]), ym(qmj.index[-1])],
        "aqr_qmj_global": [ym(qmj_g.index[0]), ym(qmj_g.index[-1])],
        "aqr_bab_usa": [ym(bab.index[0]), ym(bab.index[-1])],
    }
)

END = min(qmj.index[-1], ff5.index[-1], mom.index[-1])
fac3 = ff3.join(mom, how="inner").join(qmj, how="left")
fac = ff5.join(mom, how="inner").join(qmj, how="left").join(bab, how="left")
fac = fac.loc[:END]
fac3 = fac3.loc[:END]
RESULTS["sources"]["analysis_end"] = ym(END)

# ============================================================ 1. summary
print("\n1. QMJ summary statistics (raw long/short returns, not alphas)")
periods = {
    "usa_1957_2016": qmj.loc["1957-07":"2016-12"],
    "usa_1963_2016": qmj.loc["1963-07":"2016-12"],
    "usa_2017_end": qmj.loc["2017-01":END],
    "usa_2017_2026_06": qmj.loc["2017-01":"2026-06"],
    "usa_full": qmj.loc[:END],
    "global_1989_2016": qmj_g.loc["1989-07":"2016-12"],
    "global_2017_end": qmj_g.loc["2017-01":END],
    "global_2017_2026_06": qmj_g.loc["2017-01":"2026-06"],
}
RESULTS["summary"] = {}
for key, series in periods.items():
    s = summary(series)
    RESULTS["summary"][key] = s
    print(fmt_sum(key, s))

# Rank of July 2026 and the calendar-year count of losing years since 2017,
# reported as counts only (the year-by-year series is AQR's to publish).
ranked = qmj.loc[:END].sort_values(ascending=False)
jul26 = pd.Timestamp("2026-07-31")
RESULTS["jul_2026"] = {
    "usa": float(qmj.get(jul26, np.nan)),
    "rank_of_n": [int(ranked.index.get_loc(jul26)) + 1, len(ranked)],
    "rmw_same_month": float(fac.loc[jul26, "RMW"]),
    "mom_same_month": float(fac.loc[jul26, "Mom"]),
}
yearly = (1 + qmj.loc["2017-01":"2025-12"]).groupby(qmj.loc["2017":"2025"].index.year).prod() - 1
RESULTS["post_2016_calendar_years"] = {
    "years": len(yearly),
    "losing_years": int((yearly < 0).sum()),
    "best_year": int(yearly.idxmax()),
    "worst_year": int(yearly.idxmin()),
}
print(
    f"  July 2026 USA QMJ {RESULTS['jul_2026']['usa'] * 100:+.1f}%, rank "
    f"{RESULTS['jul_2026']['rank_of_n'][0]} of {RESULTS['jul_2026']['rank_of_n'][1]}; "
    f"RMW {RESULTS['jul_2026']['rmw_same_month'] * 100:+.1f}%, "
    f"Mom {RESULTS['jul_2026']['mom_same_month'] * 100:+.1f}%"
)
print(f"  2017-2025 calendar years: {RESULTS['post_2016_calendar_years']}")

# ============================================================ 2. regressions
print("\n2. QMJ factor regressions (USA)")
RESULTS["qmj_regressions"] = {}


def run(key: str, y: pd.Series, X: pd.DataFrame) -> None:
    r = ols(y, X)
    RESULTS["qmj_regressions"][key] = r
    print(fmt_reg(key, r))


c4 = ["Mkt-RF", "SMB", "HML", "Mom"]
c6 = FF5 + ["Mom"]
run("ff3mom_1957_2016", qmj.loc["1957-07":"2016-12"], fac3.loc["1957-07":"2016-12", c4])
run("ff5mom_1963_2016", qmj.loc["1963-07":"2016-12"], fac.loc["1963-07":"2016-12", c6])
run("ff5mom_2017_end", qmj.loc["2017-01":END], fac.loc["2017-01":END, c6])
run("ff5mom_bab_1963_2016", qmj.loc["1963-07":"2016-12"], fac.loc["1963-07":"2016-12", c6 + ["BAB"]])
run("ff5mom_bab_2017_end", qmj.loc["2017-01":END], fac.loc["2017-01":END, c6 + ["BAB"]])
corr = fac.loc["1963-07":END, ["QMJ", "RMW", "CMA", "BAB", "HML", "SMB", "Mkt-RF"]].corr()
RESULTS["qmj_correlations_1963_end"] = corr["QMJ"].round(3).to_dict()
print("  corr with QMJ 1963-07..end:", RESULTS["qmj_correlations_1963_end"])

# ============================================================ 3. funds
print("\nLoading Yahoo Finance (daily adjusted closes -> month-end)")
tickers = [t for t, _, _ in FUNDS]
px_cache = CACHE / "yahoo_daily.csv"
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
last_day = px.index.max()
me = px.resample("ME").last()
if last_day.normalize() < last_day.normalize() + pd.offsets.BMonthEnd(0):
    me = me.iloc[:-1]
rets = me.pct_change(fill_method=None)
RESULTS["sources"]["yahoo_last_day"] = str(last_day.date())
for t in tickers:
    s = rets[t].dropna()
    big = s[s.abs() > 0.25]
    print(f"   {t:5s} {ym(s.index[0])}..{ym(s.index[-1])} n={len(s)}"
          + (f"  |r|>25%: {[(ym(i), round(v, 3)) for i, v in big.items()]}" if len(big) else ""))


def fund_rows(start=None) -> list[dict]:
    rows = []
    for t, label, group in FUNDS:
        if start is not None and t not in COMMON:
            continue
        y = rets[t].dropna()
        if start is not None:
            y = y.loc[start:]
        y = (y - fac["RF"]).dropna().loc[:END]
        # Skip the first month, whose return can be a partial month.
        if start is None:
            y = y.iloc[1:]
        row = {"ticker": t, "label": label, "group": group}
        for name, cols in MODELS.items():
            row[name] = ols(y, fac[cols])
        rows.append(row)
    return rows


def show(rows: list[dict]) -> None:
    for row in rows:
        a = row["ff5mom"]
        b = row["ff3mom_qmj"]
        c = row["ff5mom_qmj"]
        print(
            f"  {row['ticker']:5s} {a['start']}..{a['end']} n={a['n']:3d} | "
            f"FF5+Mom: SMB {a['coef']['SMB']:+.2f} HML {a['coef']['HML']:+.2f} "
            f"RMW {a['coef']['RMW']:+.2f}({a['t_nw']['RMW']:+.1f}) "
            f"CMA {a['coef']['CMA']:+.2f} Mom {a['coef']['Mom']:+.2f} "
            f"R2 {a['r2']:.2f} | FF3+Mom+QMJ: QMJ {b['coef']['QMJ']:+.2f}"
            f"({b['t_nw']['QMJ']:+.1f}) HML {b['coef']['HML']:+.2f} R2 {b['r2']:.2f} | "
            f"FF5+Mom+QMJ: QMJ {c['coef']['QMJ']:+.2f}({c['t_nw']['QMJ']:+.1f}) "
            f"RMW {c['coef']['RMW']:+.2f}"
        )


print("\n3a. Funds, own windows")
own = fund_rows()
show(own)
common_start = max(
    rets[t].dropna().index[1] for t in COMMON
)
print(f"\n3b. Funds, common window from {ym(common_start)}")
common = fund_rows(common_start)
show(common)
RESULTS["funds_own_window"] = own
RESULTS["funds_common_window"] = {"start": ym(common_start), "rows": common}

(OUT / "results.json").write_text(json.dumps(RESULTS, indent=2, default=str))
print(f"\nSaved {(OUT / 'results.json').relative_to(HERE)}")
if RESULTS["failures"]:
    print("FAILURES:", RESULTS["failures"])
