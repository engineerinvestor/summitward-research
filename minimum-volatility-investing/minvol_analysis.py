"""Minimum-volatility equities (USMV) and Betting Against Beta: empirical record.

Supports https://summitward.com/learn/minimum-volatility-investing.

Requires numpy, pandas, openpyxl (AQR spreadsheet) and yfinance.

Sources (Ken French CSVs committed in ./data/; AQR and Yahoo downloaded on
first run and cached in ./.cache/, which is not committed):
  * Ken French data library (Tuck), monthly, percent returns converted to decimals:
      - F-F_Research_Data_5_Factors_2x3: Mkt-RF, SMB, HML, RMW, CMA, RF
      - F-F_Momentum_Factor: Mom
      - Portfolios_Formed_on_BETA: quintiles sorted on trailing 60-month
        Scholes-Williams beta, formed each June. The "Value Weighted Returns --
        Monthly" and "Equal Weighted Returns -- Monthly" sections are parsed by
        their section headers (the file also holds annual returns, firm counts,
        firm size and prior-beta sections, which are ignored).
      - Portfolios_Formed_on_VAR: quintiles sorted on 60-day total return
        variance, formed monthly. Same section handling.
  * AQR "Betting Against Beta: Equity Factors, Monthly" xlsx, sheet
    "BAB Factors", column USA (decimal monthly self-financing excess returns).
  * Yahoo Finance via yfinance: daily adjusted closes (auto_adjust=True, so
    dividends are reinvested), resampled to the last trading day of each month;
    monthly total return = pct change of month-end adjusted close. The current,
    incomplete month is dropped.

Windows:
  * Flat SML: 1963-07 to latest French month (whole), 1963-07..1999-12,
    2000-01..latest, and 2011-11..latest (live USMV period).
  * BAB: 1930-12 (first AQR USA obs) to latest AQR month; sub-periods before
    2014-01 (Frazzini-Pedersen published in JFE Jan 2014), 2014-01..latest,
    2011-11..latest. FF5+Mom regression from 1963-07 (FF5 start).
  * ETFs: 2011-11 (USMV's first full month) to the last common month of ETF
    data and French RF.

Methods:
  * Annualized arithmetic mean = 12 x monthly mean; vol = sqrt(12) x monthly
    std (ddof=1); Sharpe = annualized mean excess / annualized vol of excess.
  * CAGR = geometric, from cumulative total return over n months.
  * Max drawdown on month-end cumulative wealth (1+r). For BAB (a
    self-financing excess return) wealth = cumprod(1 + BAB), i.e. the return on
    a cash-collateralized position minus cash.
  * OLS by numpy: classical t = b / sqrt(diag(s2 (X'X)^-1)); Newey-West t with
    6 lags (Bartlett weights). Alphas annualized as 12 x monthly intercept.
  * Capture ratios: arithmetic mean of fund return in months the benchmark
    was up (down) divided by the benchmark's mean in those months.
  * Hypothetical mixes are rebalanced monthly, gross of trading costs and
    taxes; leverage is financed at RF + spread.
"""

from __future__ import annotations

import io
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
AQR_URL = (
    "https://www.aqr.com/-/media/AQR/Documents/Insights/Data-Sets/"
    "Betting-Against-Beta-Equity-Factors-Monthly.xlsx"
)
TICKERS = [
    "USMV", "SPLV", "VTI", "ITOT", "ACWV", "VT", "BTAL", "BIL", "IEF",
    "EFAV", "EFA", "EEMV", "EEM", "ACWI", "SPY",
]
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


def french_sections(name: str) -> dict[str, pd.DataFrame]:
    """Parse every monthly (YYYYMM-indexed) section of a French CSV by header."""
    local = DATA / f"{name}.csv"
    if local.exists():
        text = local.read_text(encoding="latin-1")
    else:
        z = zipfile.ZipFile(fetch(FRENCH.format(name), CACHE / f"{name}.zip"))
        text = z.read(z.namelist()[0]).decode("latin-1")
    lines = text.splitlines()
    out: dict[str, pd.DataFrame] = {}
    i = 0
    title = "main"
    while i < len(lines):
        ln = lines[i]
        if ln.startswith(",") and i + 1 < len(lines):
            # header row; title is previous non-blank line (or "main")
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
                parts = [p.strip() for p in lines[k].split(",")]
                rows.append(parts)
                k += 1
            if rows and len(rows[0][0]) == 6:  # monthly YYYYMM
                df = pd.DataFrame(
                    [[float(x) for x in r[1:]] for r in rows],
                    index=pd.to_datetime([r[0] for r in rows], format="%Y%m")
                    + pd.offsets.MonthEnd(0),
                    columns=cols,
                )
                df = df.mask(df <= -99.99)  # French missing-data codes
                key = title if title not in out else f"{title} ({len(out)})"
                out[key] = df / 100.0
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
    # Newey-West
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
    res = {
        "start": ym(d.index[0]),
        "end": ym(d.index[-1]),
        "n": int(n),
        "r2": float(r2),
        "alpha_ann": float(12 * b[0]),
    }
    res["coef"] = {nm: float(v) for nm, v in zip(names, b, strict=True)}
    res["t"] = {nm: float(v) for nm, v in zip(names, b / se, strict=True)}
    res["t_nw"] = {nm: float(v) for nm, v in zip(names, b / se_nw, strict=True)}
    return res


def fmt_reg(label: str, r: dict) -> str:
    parts = [
        f"{label}: {r['start']}..{r['end']} n={r['n']} R2={r['r2']:.2f} "
        f"alpha={r['alpha_ann'] * 100:+.2f}%/yr "
        f"(t={r['t']['alpha']:.2f}, NW t={r['t_nw']['alpha']:.2f})"
    ]
    for nm, v in r["coef"].items():
        if nm == "alpha":
            continue
        parts.append(
            f"    {nm:>7s} {v:+.3f} (t={r['t'][nm]:.2f}, NW t={r['t_nw'][nm]:.2f})"
        )
    return "\n".join(parts)


def max_dd(r: pd.Series) -> dict:
    r = r.dropna()
    w = (1 + r).cumprod()
    w0 = pd.concat([pd.Series([1.0], index=[r.index[0] - pd.offsets.MonthEnd(1)]), w])
    peak = w0.cummax()
    dd = w0 / peak - 1
    trough = dd.idxmin()
    pk = w0.loc[:trough].idxmax()
    rec = w0.loc[trough:][w0.loc[trough:] >= peak.loc[trough]]
    return {
        "max_dd": float(dd.min()),
        "peak": ym(pk),
        "trough": ym(trough),
        "recovered": ym(rec.index[0]) if len(rec) else None,
    }


def perf(total: pd.Series, rf: pd.Series | None, excess: bool = False) -> dict:
    """Stats for a monthly return series. If excess=True, total is already excess."""
    total = total.dropna()
    ex = total if excess else (total - rf.reindex(total.index))
    n = len(total)
    out = {
        "start": ym(total.index[0]),
        "end": ym(total.index[-1]),
        "n": n,
        "mean_ann": float(12 * total.mean()),
        "mean_excess_ann": float(12 * ex.mean()),
        "vol_ann": float(np.sqrt(12) * ex.std(ddof=1)),
        "sharpe": float(12 * ex.mean() / (np.sqrt(12) * ex.std(ddof=1))),
        "cagr": float((1 + total).prod() ** (12 / n) - 1),
        "worst_12m": float(((1 + total).rolling(12).apply(np.prod, raw=True) - 1).min()),
    }
    w12 = (1 + total).rolling(12).apply(np.prod, raw=True) - 1
    out["worst_12m_end"] = ym(w12.idxmin())
    out.update(max_dd(total))
    return out


def pct(x, d=1):
    return "n/a" if x is None else f"{100 * x:.{d}f}%"


# ---------------------------------------------------------------- data
print("=" * 78)
print("Loading Ken French data")
ff5 = next(iter(french_sections("F-F_Research_Data_5_Factors_2x3").values()))  # first (monthly) section
mom = next(iter(french_sections("F-F_Momentum_Factor").values()))
mom.columns = ["Mom"]
fac = ff5.join(mom, how="left")
RF = fac["RF"]
beta_secs = french_sections("Portfolios_Formed_on_BETA")
var_secs = french_sections("Portfolios_Formed_on_VAR")
for nm, secs in [("BETA", beta_secs), ("VAR", var_secs)]:
    print(f"  Portfolios_Formed_on_{nm} monthly sections parsed: {list(secs)}")
VW_KEY = "Value Weighted Returns -- Monthly"
EW_KEY = "Equal Weighted Returns -- Monthly"
QUINT = ["Lo 20", "Qnt 2", "Qnt 3", "Qnt 4", "Hi 20"]
beta_vw = beta_secs[VW_KEY][QUINT]
beta_ew = beta_secs[EW_KEY][QUINT]
var_vw = var_secs[VW_KEY][QUINT]
var_ew = var_secs[EW_KEY][QUINT]
FRENCH_END = fac.index[-1]
print(
    f"  FF5 {ym(fac.index[0])}..{ym(FRENCH_END)}; Mom through {ym(mom.index[-1])}; "
    f"BETA VW {ym(beta_vw.index[0])}..{ym(beta_vw.index[-1])}; "
    f"VAR VW {ym(var_vw.index[0])}..{ym(var_vw.index[-1])}"
)
RESULTS["sources"]["french_end"] = ym(FRENCH_END)
RESULTS["sources"]["french_sections_used"] = [VW_KEY, EW_KEY]

print("Loading AQR BAB")
bab = None
try:
    xl = fetch(AQR_URL, CACHE / "bab.xlsx")
    raw = pd.read_excel(xl, "BAB Factors", header=None)
    hdr_row = raw.index[raw.iloc[:, 0].astype(str).str.strip() == "DATE"][0]
    body = raw.iloc[hdr_row + 1 :].copy()
    body.columns = [str(c).strip() for c in raw.iloc[hdr_row]]
    body = body[pd.to_datetime(body["DATE"], format="%m/%d/%Y", errors="coerce").notna()]
    body.index = pd.to_datetime(body["DATE"], format="%m/%d/%Y") + pd.offsets.MonthEnd(0)
    bab = pd.to_numeric(body["USA"], errors="coerce").dropna().rename("BAB")
    print(f"  AQR BAB USA {ym(bab.index[0])}..{ym(bab.index[-1])} n={len(bab)}")
    RESULTS["sources"]["aqr_bab_usa"] = [ym(bab.index[0]), ym(bab.index[-1])]
except Exception as exc:  # noqa: BLE001
    print("  AQR download/parse failed:", exc)
    RESULTS["failures"].append(f"AQR BAB: {exc}")

print("Loading Yahoo Finance (daily adjusted closes -> month-end)")
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
                    t, start="2007-01-01", auto_adjust=True, progress=False
                )
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
# drop an incomplete trailing month
if last_day.normalize() < last_day.normalize() + pd.offsets.BMonthEnd(0):
    me = me.iloc[:-1]
etf = me.pct_change(fill_method=None)
print(f"  Yahoo daily data through {last_day.date()}; last full month {ym(etf.index[-1])}")
for t in etf.columns:
    s = etf[t].dropna()
    print(f"   {t:5s} {ym(s.index[0])}..{ym(s.index[-1])} n={len(s)}")
RESULTS["sources"]["yahoo_last_day"] = str(last_day.date())

START = pd.Timestamp("2011-11-30")
END = min(etf.index[-1], FRENCH_END)
win = etf.loc[START:END]
rf_w = RF.loc[START:END]
missing = win[["USMV", "SPLV", "VTI"]].isna().sum()
print(f"  ETF window {ym(START)}..{ym(END)} n={len(win)}; missing months: {missing.to_dict()}")
# RF gap handling: French RF runs through FRENCH_END; if ETF data ran further,
# we would fill with BIL minus 0.0 (BIL total return) for those months.
if etf.index[-1] > FRENCH_END:
    print(
        f"  NOTE: ETF data runs to {ym(etf.index[-1])}, French RF to {ym(FRENCH_END)}; "
        "window truncated at French end so RF is never proxied."
    )
RESULTS["sources"]["etf_window"] = [ym(START), ym(END), len(win)]
# cross-check: French RF vs BIL total return
cmp = pd.concat([rf_w, win["BIL"]], axis=1).dropna()
print(
    f"  RF check: French RF {12 * cmp['RF'].mean() * 100:.2f}%/yr vs BIL "
    f"{12 * cmp['BIL'].mean() * 100:.2f}%/yr over {ym(cmp.index[0])}..{ym(cmp.index[-1])}"
)

# ============================================================ 1. flat SML
print("\n" + "=" * 78)
print("1. Flat security market line: French beta- and variance-sorted quintiles")
mkt = fac["Mkt-RF"]


def sml_table(port: pd.DataFrame, start, end) -> list[dict]:
    rows = []
    for c in port.columns:
        r = port[c].loc[start:end]
        ex = (r - RF.reindex(r.index)).dropna()
        reg = ols(ex, mkt.loc[ex.index].to_frame())
        rows.append(
            {
                "portfolio": c,
                "start": ym(ex.index[0]),
                "end": ym(ex.index[-1]),
                "n": len(ex),
                "mean_excess_ann": float(12 * ex.mean()),
                "vol_ann": float(np.sqrt(12) * ex.std(ddof=1)),
                "sharpe": float(np.sqrt(12) * ex.mean() / ex.std(ddof=1)),
                "beta": reg["coef"]["Mkt-RF"],
                "alpha_ann": reg["alpha_ann"],
                "alpha_t": reg["t"]["alpha"],
                "alpha_t_nw": reg["t_nw"]["alpha"],
                "cagr_total": float((1 + r).prod() ** (12 / len(r)) - 1),
            }
        )
    return rows


def print_sml(title, rows):
    print(f"\n  {title}: {rows[0]['start']}..{rows[0]['end']} n={rows[0]['n']}")
    print(f"  {'port':7s} {'ExRet':>7s} {'Vol':>6s} {'Sharpe':>6s} {'Beta':>5s} {'Alpha':>7s} {'t':>5s} {'NWt':>5s} {'CAGR':>6s}")
    for r in rows:
        print(
            f"  {r['portfolio']:7s} {r['mean_excess_ann'] * 100:6.2f}% {r['vol_ann'] * 100:5.1f}% "
            f"{r['sharpe']:6.2f} {r['beta']:5.2f} {r['alpha_ann'] * 100:+6.2f}% "
            f"{r['alpha_t']:5.2f} {r['alpha_t_nw']:5.2f} {r['cagr_total'] * 100:5.1f}%"
        )


periods = {
    "full": ("1963-07-31", FRENCH_END),
    "1963-1999": ("1963-07-31", "1999-12-31"),
    "2000-latest": ("2000-01-31", FRENCH_END),
    "2011-11-latest": ("2011-11-30", FRENCH_END),
}
RESULTS["sml"] = {}
for sort_name, vw, ew in [("beta", beta_vw, beta_ew), ("variance", var_vw, var_ew)]:
    for wname, port in [("VW", vw), ("EW", ew)]:
        for pname, (s, e) in periods.items():
            rows = sml_table(port, s, e)
            key = f"{sort_name}_{wname}_{pname}"
            RESULTS["sml"][key] = rows
            print_sml(f"{sort_name}-sorted quintiles, {wname}, {pname}", rows)
# market benchmark row for reference
mref = {}
for pname, (s, e) in periods.items():
    m = mkt.loc[s:e]
    mref[pname] = {
        "start": ym(m.index[0]), "end": ym(m.index[-1]), "n": len(m),
        "mean_excess_ann": float(12 * m.mean()),
        "vol_ann": float(np.sqrt(12) * m.std()),
        "sharpe": float(np.sqrt(12) * m.mean() / m.std()),
    }
    print(f"  Market (Mkt-RF) {pname}: ExRet {mref[pname]['mean_excess_ann'] * 100:.2f}% "
          f"vol {mref[pname]['vol_ann'] * 100:.1f}% Sharpe {mref[pname]['sharpe']:.2f} n={len(m)}")
RESULTS["sml"]["market"] = mref

# ============================================================ 2. BAB
print("\n" + "=" * 78)
print("2. AQR Betting Against Beta, USA")
RESULTS["bab"] = {}
if bab is not None:
    bab_periods = {
        "full": (bab.index[0], bab.index[-1]),
        "pre-2014": (bab.index[0], "2013-12-31"),
        "2014-latest": ("2014-01-31", bab.index[-1]),
        "2011-11-latest": ("2011-11-30", bab.index[-1]),
        "1963-07-latest": ("1963-07-31", bab.index[-1]),
    }
    for pname, (s, e) in bab_periods.items():
        st = perf(bab.loc[s:e], None, excess=True)
        RESULTS["bab"][pname] = st
        print(
            f"  {pname:15s} {st['start']}..{st['end']} n={st['n']}: mean {st['mean_ann'] * 100:.2f}% "
            f"vol {st['vol_ann'] * 100:.1f}% Sharpe {st['sharpe']:.2f} "
            f"MaxDD {st['max_dd'] * 100:.1f}% ({st['peak']}->{st['trough']}, recovered {st['recovered']}) "
            f"worst12m {st['worst_12m'] * 100:.1f}% (ending {st['worst_12m_end']})"
        )
    Xf = fac[["Mkt-RF", "SMB", "HML", "RMW", "CMA", "Mom"]]
    for pname, s in [("1963-07-latest", "1963-07-31"), ("2014-latest", "2014-01-31"),
                     ("2011-11-latest", "2011-11-30")]:
        r = ols(bab.loc[s:], Xf.loc[s:])
        RESULTS["bab"][f"reg_ff5mom_{pname}"] = r
        print(fmt_reg(f"  BAB on FF5+Mom {pname}", r))
    # calendar-year BAB returns since 2011
    bab_cy = (1 + bab.loc["2012":]).groupby(bab.loc["2012":].index.year).prod() - 1
    RESULTS["bab"]["calendar_years"] = {int(k): float(v) for k, v in bab_cy.items()}
    print("  BAB calendar years:", {k: pct(v) for k, v in RESULTS["bab"]["calendar_years"].items()})

# ============================================================ 3. USMV live
print("\n" + "=" * 78)
print(f"3. USMV live record {ym(START)}..{ym(END)}")
RESULTS["live"] = {}
for t in ["USMV", "SPLV", "VTI", "ITOT", "ACWV", "VT", "BTAL", "IEF"]:
    s = win[t].dropna()
    if not len(s):
        continue
    st = perf(s, rf_w)
    RESULTS["live"][t] = st
    print(
        f"  {t:5s} {st['start']}..{st['end']} n={st['n']}: CAGR {st['cagr'] * 100:.2f}% "
        f"vol {st['vol_ann'] * 100:.1f}% Sharpe {st['sharpe']:.2f} "
        f"MaxDD {st['max_dd'] * 100:.1f}% ({st['peak']}->{st['trough']}, rec {st['recovered']})"
    )


def capm_and_capture(fund: str, bench: str) -> dict:
    d = win[[fund, bench]].dropna()
    exf = d[fund] - rf_w.loc[d.index]
    exb = d[bench] - rf_w.loc[d.index]
    reg = ols(exf, exb.rename(f"{bench}-RF").to_frame())
    up = d[bench] > 0
    dn = d[bench] < 0
    rel = (1 + d).groupby(d.index.year).prod() - 1
    diff = rel[fund] - rel[bench]
    full_years = [y for y in diff.index if (d.index.year == y).sum() == 12]
    diff_full = diff.loc[full_years]
    out = {
        "capm": reg,
        "up_capture": float(d.loc[up, fund].mean() / d.loc[up, bench].mean()),
        "down_capture": float(d.loc[dn, fund].mean() / d.loc[dn, bench].mean()),
        "n_up": int(up.sum()),
        "n_down": int(dn.sum()),
        "pct_months_outperform": float((d[fund] > d[bench]).mean()),
        "worst_cal_year_rel": {"year": int(diff_full.idxmin()), "diff": float(diff_full.min())},
        "best_cal_year_rel": {"year": int(diff_full.idxmax()), "diff": float(diff_full.max())},
        "years_outperformed": int((diff_full > 0).sum()),
        "years_counted": len(full_years),
        "cagr_diff": float(
            (1 + d[fund]).prod() ** (12 / len(d)) - (1 + d[bench]).prod() ** (12 / len(d))
        ),
    }
    return out


for f, b in [("USMV", "VTI"), ("SPLV", "VTI"), ("USMV", "SPLV"), ("ACWV", "VT")]:
    o = capm_and_capture(f, b)
    RESULTS["live"][f"{f}_vs_{b}"] = o
    c = o["capm"]
    print(
        f"  {f} vs {b}: beta {c['coef'][b + '-RF']:.3f} (t={c['t'][b + '-RF']:.1f}), "
        f"alpha {c['alpha_ann'] * 100:+.2f}%/yr (t={c['t']['alpha']:.2f}, NW t={c['t_nw']['alpha']:.2f}), "
        f"R2 {c['r2']:.2f}, n={c['n']} {c['start']}..{c['end']}"
    )
    print(
        f"     up capture {o['up_capture'] * 100:.0f}% (n={o['n_up']}), down capture "
        f"{o['down_capture'] * 100:.0f}% (n={o['n_down']}); beat {b} in "
        f"{o['years_outperformed']}/{o['years_counted']} full calendar years; worst year "
        f"{o['worst_cal_year_rel']['year']} {o['worst_cal_year_rel']['diff'] * 100:+.1f}pp; best "
        f"{o['best_cal_year_rel']['year']} {o['best_cal_year_rel']['diff'] * 100:+.1f}pp; "
        f"CAGR gap {o['cagr_diff'] * 100:+.2f}pp/yr"
    )

cy_src = etf.loc["2012-01-31":END, ["USMV", "SPLV", "VTI", "ACWV", "VT", "BTAL"]]
cy = (1 + cy_src).groupby(cy_src.index.year).prod() - 1
cy_n = cy_src.groupby(cy_src.index.year).count()
print("\n  Calendar-year total returns (last year is YTD through " + ym(END) + ")")
print("  year   USMV    SPLV     VTI  USMV-VTI  ACWV     VT   BTAL")
RESULTS["calendar_years"] = {}
for y in cy.index:
    row = cy.loc[y]
    RESULTS["calendar_years"][int(y)] = {k: float(v) for k, v in row.items()} | {
        "months": int(cy_n.loc[y, "VTI"])
    }
    print(
        f"  {y}{'*' if cy_n.loc[y, 'VTI'] < 12 else ' '} {row.USMV * 100:6.1f}% {row.SPLV * 100:6.1f}% "
        f"{row.VTI * 100:6.1f}% {(row.USMV - row.VTI) * 100:+7.1f}pp {row.ACWV * 100:6.1f}% "
        f"{row.VT * 100:6.1f}% {row.BTAL * 100:6.1f}%"
    )

# ============================================================ 4. fewer stocks vs min vol
print("\n" + "=" * 78)
print("4. Hypothetical: VTI + cash vs USMV, and levered USMV vs VTI (monthly rebalanced, gross)")
d = win[["USMV", "VTI"]].dropna()
rf_d = rf_w.loc[d.index]
beta_u = RESULTS["live"]["USMV_vs_VTI"]["capm"]["coef"]["VTI-RF"]
vol_u = RESULTS["live"]["USMV"]["vol_ann"]
vol_v = RESULTS["live"]["VTI"]["vol_ann"]
RESULTS["mix"] = {"beta_usmv": beta_u, "vol_usmv": vol_u, "vol_vti": vol_v}
mixes = {}
w_b = beta_u
w_v = vol_u / vol_v
mixes[f"VTI {w_b:.0%} + cash (beta-matched)"] = w_b * d["VTI"] + (1 - w_b) * rf_d
mixes[f"VTI {w_v:.0%} + cash (vol-matched)"] = w_v * d["VTI"] + (1 - w_v) * rf_d
mixes["USMV"] = d["USMV"]
mixes["VTI"] = d["VTI"]
for spread in (0.005, 0.015):
    L_vol = vol_v / vol_u
    L_b = 1 / beta_u
    fin = rf_d + spread / 12
    mixes[f"USMV x{L_vol:.2f} (vol-matched), fin RF+{spread:.1%}"] = L_vol * d["USMV"] - (L_vol - 1) * fin
    mixes[f"USMV x{L_b:.2f} (beta 1), fin RF+{spread:.1%}"] = L_b * d["USMV"] - (L_b - 1) * fin
RESULTS["mix"]["weights"] = {"vti_beta_matched": w_b, "vti_vol_matched": w_v,
                             "lev_vol_matched": vol_v / vol_u, "lev_beta1": 1 / beta_u}
print(f"  USMV beta to VTI {beta_u:.3f}; vol USMV {vol_u * 100:.2f}% vs VTI {vol_v * 100:.2f}%")
print(f"  {'strategy':48s} {'CAGR':>6s} {'Vol':>6s} {'Sharpe':>6s} {'MaxDD':>7s} {'beta':>5s}")
RESULTS["mix"]["table"] = {}
for nm, s in mixes.items():
    st = perf(s, rf_d)
    b = ols(s - rf_d, (d["VTI"] - rf_d).rename("VTI-RF").to_frame())["coef"]["VTI-RF"]
    st["beta_vti"] = b
    RESULTS["mix"]["table"][nm] = st
    print(
        f"  {nm:48s} {st['cagr'] * 100:5.2f}% {st['vol_ann'] * 100:5.1f}% {st['sharpe']:6.2f} "
        f"{st['max_dd'] * 100:6.1f}% {b:5.2f}  ({st['start']}..{st['end']} n={st['n']}, "
        f"DD {st['peak']}->{st['trough']})"
    )

# ============================================================ 5. factor regressions
print("\n" + "=" * 78)
print("5. Factor regressions (monthly excess returns)")
RESULTS["factor_regs"] = {}
Xf = fac[["Mkt-RF", "SMB", "HML", "RMW", "CMA", "Mom"]]
for t in ["USMV", "SPLV", "ACWV", "VTI"]:
    ex = (win[t] - rf_w).dropna()
    r = ols(ex, Xf.loc[ex.index])
    RESULTS["factor_regs"][f"{t}_ff5mom"] = r
    print(fmt_reg(f"  {t} on FF5+Mom", r))
    r1 = ols(ex, Xf.loc[ex.index, ["Mkt-RF"]])
    RESULTS["factor_regs"][f"{t}_capm_french"] = r1
    print(f"  {t} CAPM vs French Mkt-RF: alpha {r1['alpha_ann'] * 100:+.2f}% (t={r1['t']['alpha']:.2f}) "
          f"beta {r1['coef']['Mkt-RF']:.3f} n={r1['n']}")
if bab is not None:
    for t in ["USMV", "SPLV"]:
        ex = (win[t] - rf_w).dropna()
        X = pd.concat([fac["Mkt-RF"], bab], axis=1).reindex(ex.index)
        r = ols(ex, X)
        RESULTS["factor_regs"][f"{t}_mkt_bab"] = r
        print(fmt_reg(f"  {t} on Mkt-RF + BAB", r))
        X2 = pd.concat([Xf, bab], axis=1).reindex(ex.index)
        r2 = ols(ex, X2)
        RESULTS["factor_regs"][f"{t}_ff5mom_bab"] = r2
        print(fmt_reg(f"  {t} on FF5+Mom+BAB", r2))

# ============================================================ 6. rate sensitivity
print("\n" + "=" * 78)
print("6. Rate sensitivity: (USMV - VTI) on IEF total return")
RESULTS["rates"] = {}
d6 = win[["USMV", "VTI", "SPLV", "IEF"]].dropna()
for f in ["USMV", "SPLV"]:
    spread = (d6[f] - d6["VTI"]).rename("spread")
    r = ols(spread, d6[["IEF"]])
    RESULTS["rates"][f"{f}_minus_VTI_on_IEF"] = r
    print(fmt_reg(f"  {f}-VTI on IEF", r))
    X = pd.concat([d6["IEF"], (d6["VTI"] - rf_w.loc[d6.index]).rename("VTI-RF")], axis=1)
    r2 = ols(spread, X)
    RESULTS["rates"][f"{f}_minus_VTI_on_IEF_and_VTI"] = r2
    print(fmt_reg(f"  {f}-VTI on IEF + VTI excess", r2))
y22 = (1 + etf.loc["2022", ["USMV", "SPLV", "VTI", "IEF"]]).prod() - 1
RESULTS["rates"]["cy2022"] = {k: float(v) for k, v in y22.items()}
print("  2022 calendar-year returns:", {k: pct(v) for k, v in y22.items()})
# worst 12-month-change in 10Y proxy: show 2022 monthly correlation
c22 = etf.loc["2022", ["USMV", "VTI", "IEF"]]
print(f"  2022 monthly corr(USMV-VTI, IEF) = {(c22['USMV'] - c22['VTI']).corr(c22['IEF']):.2f} (n=12)")


# ============================================================ 8. international min vol
print("\n" + "=" * 78)
print("8. International min-vol funds vs parents, and the Feb-Mar 2020 crash (daily)")
RESULTS["intl"] = {}
for f, b in [("EFAV", "EFA"), ("EEMV", "EEM"), ("ACWV", "ACWI"), ("USMV", "VTI")]:
    d8 = win[[f, b]].dropna()
    rf8 = rf_w.loc[d8.index]
    sf, sb = perf(d8[f], rf8), perf(d8[b], rf8)
    reg = ols(d8[f] - rf8, (d8[b] - rf8).rename("parent").to_frame())
    y20 = (1 + etf.loc["2020", [f, b]]).prod() - 1
    y22 = (1 + etf.loc["2022", [f, b]]).prod() - 1
    # daily Feb-Mar 2020: fixed dates 2020-02-19 close to 2020-03-23 close,
    # plus each fund's own max peak-to-trough inside Feb 1-Apr 30 2020
    dp = px.loc["2020-02-01":"2020-04-30", [f, b]]
    fixed = px.loc["2020-03-23", [f, b]] / px.loc["2020-02-19", [f, b]] - 1
    own = {}
    for t in (f, b):
        w = dp[t]
        dd = w / w.cummax() - 1
        tr = dd.idxmin()
        own[t] = {"dd": float(dd.min()), "peak": str(w.loc[:tr].idxmax().date()),
                  "trough": str(tr.date())}
    o = {
        "fund": sf, "parent": sb,
        "beta": reg["coef"]["parent"], "beta_t": reg["t"]["parent"],
        "alpha_ann": reg["alpha_ann"], "alpha_t": reg["t"]["alpha"],
        "alpha_t_nw": reg["t_nw"]["alpha"], "r2": reg["r2"],
        "cy2020": {k: float(v) for k, v in y20.items()},
        "cy2022": {k: float(v) for k, v in y22.items()},
        "crash_2020_02_19_to_03_23": {k: float(v) for k, v in fixed.items()},
        "crash_2020_own_peak_trough": own,
    }
    RESULTS["intl"][f"{f}_vs_{b}"] = o
    print(f"  {f} vs {b} ({sf['start']}..{sf['end']}, n={sf['n']}):")
    for lab, st in ((f, sf), (b, sb)):
        print(f"     {lab:5s} CAGR {st['cagr'] * 100:5.2f}% vol {st['vol_ann'] * 100:4.1f}% "
              f"Sharpe {st['sharpe']:.2f} MaxDD {st['max_dd'] * 100:.1f}% "
              f"({st['peak']}->{st['trough']}, rec {st['recovered']})")
    print(f"     beta {o['beta']:.2f} alpha {o['alpha_ann'] * 100:+.2f}%/yr (t={o['alpha_t']:.2f}, "
          f"NW t={o['alpha_t_nw']:.2f}) R2 {o['r2']:.2f}")
    print(f"     2020 CY: {pct(y20[f])} vs {pct(y20[b])}; 2022 CY: {pct(y22[f])} vs {pct(y22[b])}")
    print(f"     2020-02-19 -> 2020-03-23 close-to-close: {pct(fixed[f])} vs {pct(fixed[b])}")
    print(f"     own daily peak->trough Feb-Apr 2020: {f} {pct(own[f]['dd'])} "
          f"({own[f]['peak']}->{own[f]['trough']}), {b} {pct(own[b]['dd'])} "
          f"({own[b]['peak']}->{own[b]['trough']})")
spy = px.loc["2020-03-23", "SPY"] / px.loc["2020-02-19", "SPY"] - 1
RESULTS["intl"]["SPY_2020_02_19_to_03_23"] = float(spy)
print(f"  SPY (total return, adj close) 2020-02-19 -> 2020-03-23: {pct(spy)}  "
      "(S&P 500 price index is -33.9% on these dates)")

# ============================================================ sanity
print("\n" + "=" * 78)
print("Sanity checks")
vti_cagr = RESULTS["live"]["VTI"]["cagr"]
itot_cagr = RESULTS["live"].get("ITOT", {}).get("cagr")
print(f"  VTI CAGR {vti_cagr * 100:.2f}% (expected ~13-15%); ITOT {pct(itot_cagr, 2)}")
mk = (mkt + RF).loc[START:END]
print(f"  French Mkt (Mkt-RF+RF) CAGR same window {((1 + mk).prod() ** (12 / len(mk)) - 1) * 100:.2f}%; "
      f"corr(VTI, French Mkt) = {win['VTI'].corr(mk):.4f}")
RESULTS["sanity"] = {
    "vti_cagr": vti_cagr,
    "french_mkt_cagr_same_window": float((1 + mk).prod() ** (12 / len(mk)) - 1),
    "corr_vti_french_mkt": float(win["VTI"].corr(mk)),
}

out = OUT / "results.json"
out.write_text(json.dumps(RESULTS, indent=2, default=str))
print(f"\nSaved {out.relative_to(HERE)}")

# ============================================================ BAB pre-publication alpha
# FF5 + Mom regression of US BAB over 1963-07..2013-12 only, so the
# pre-publication row does not overlap the post-2014 window.
r_pre = ols(bab.loc["1963-07":"2013-12"], fac[["Mkt-RF", "SMB", "HML", "RMW", "CMA", "Mom"]])
RESULTS["bab"]["ff5mom_1963_2013"] = r_pre
print(f"BAB FF5+Mom 1963-07..2013-12: alpha {r_pre['alpha_ann'] * 100:.2f}%/yr "
      f"t {r_pre['t']['alpha']:.2f} n {r_pre['n']} RMW {r_pre['coef']['RMW']:.2f}")
out.write_text(json.dumps(RESULTS, indent=2, default=str))

# ============================================================ chart export
# Compact JSON for the two guide charts: growth of $1 (USMV, VTI, the
# vol-matched VTI + T-bill mix) and the beta-quintile excess returns.
growth_cols = {"usmv": d["USMV"], "vti": d["VTI"],
               "mix": w_v * d["VTI"] + (1 - w_v) * rf_d}
chart = {
    "window": {"start": str(d.index[0])[:7], "end": str(d.index[-1])[:7], "n": len(d)},
    "mixWeight": round(float(w_v), 4),
    "growth": {"ym": [int(str(i)[:4] + str(i)[5:7]) for i in d.index]},
    "quintiles": [
        {"q": r["portfolio"], "beta": round(r["beta"], 3),
         "excess": round(r["mean_excess_ann"], 4), "sharpe": round(r["sharpe"], 3),
         "capm": round(r["beta"] * float(mkt.loc["1963-07":END].mean() * 12), 4)}
        for r in RESULTS["sml"]["beta_VW_full"]
    ],
    "quintileWindow": {"start": RESULTS["sml"]["beta_VW_full"][0]["start"],
                       "end": RESULTS["sml"]["beta_VW_full"][0]["end"],
                       "n": RESULTS["sml"]["beta_VW_full"][0]["n"],
                       "marketExcess": round(float(mkt.loc["1963-07":END].mean() * 12), 4)},
}
for k, s in growth_cols.items():
    chart["growth"][k] = [round(float(x), 4) for x in (1 + s).cumprod()]
(OUT / "min-vol-chart.json").write_text(json.dumps(chart, separators=(",", ":")))
print(f"Saved {(OUT / 'min-vol-chart.json').relative_to(HERE)}")
