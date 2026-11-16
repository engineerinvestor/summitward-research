"""What drove the 2025-26 run in systematic small-value funds.

Supports https://summitward.com/learn/is-the-value-premium-back.

Requires numpy, pandas and yfinance.

Sources (Ken French CSVs committed in ./data/; Yahoo downloaded on first run
and cached in ./.cache/, which is not committed):
  * Ken French data library (Tuck), monthly, percent converted to decimals,
    cut through September 2026 (202609 CRSP; Bloomberg for developed ex-US),
    downloaded Nov 15, 2026:
      - F-F_Research_Data_5_Factors_2x3 and F-F_Momentum_Factor (U.S.)
      - Developed_ex_US_5_Factors and Developed_ex_US_Mom_Factor
  * Yahoo Finance via yfinance: daily adjusted closes (auto_adjust=True, so
    market price with distributions reinvested, not NAV), resampled to
    month-end, read Nov 15, 2026.
  * Issuer figures typed in below (ISSUER_RETURNS, DFSV_CALENDAR,
    DISTRIBUTIONS_2026) with their URLs and as-of dates. They are NAV returns
    and are quoted as published, not recomputed.

Sections:
  1. Issuer NAV returns as published (Oct 31 / Sep 30, 2026).
  2. DFSV calendar-year returns before and after the Sep 25, 2026 merger into
     the U.S. Small Cap Value Portfolio (DFSVX).
  3. Matched-window market-price returns, Oct 2019 to Oct 2026 (AVUV and
     AVDV both started trading Sep 24, 2019, so Sep 30, 2019 is the first
     month-end), plus trailing 12 and 36 months to Oct 2026. CAGR, monthly
     volatility (annualized), worst peak-to-trough on month-end closes.
  4. Factor attribution of the last 12 months, out of sample. Loadings on
     the five Fama-French factors plus momentum are estimated Oct 2019 to
     Sep 2025 (72 months) with Newey-West (6 lag) standard errors, then
     multiplied by the factor returns of Oct 2025 to Sep 2026. The fund's
     realized excess return over those 12 months is split into the part the
     earlier loadings predict, factor by factor, and the residual. Sums are
     arithmetic sums of monthly returns (additive by construction), and the
     compounded predicted and actual totals are reported beside them.
     U.S. funds use U.S. factors; AVDV uses developed ex-US factors.
     The AVUV-minus-IWN gap is attributed the same way using the loading
     difference from a regression of the return difference.
  5. Full-window regressions Oct 2019 to Sep 2026 (84 months) for the
     intercept and its Newey-West interval.

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
FRENCH_HTTP = "http://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/{}_CSV.zip"

FACTORS = ["Mkt-RF", "SMB", "HML", "RMW", "CMA", "MOM"]
EST_START, EST_END = "2019-10", "2025-09"
ATT_START, ATT_END = "2025-10", "2026-09"
FULL_START, FULL_END = "2019-10", "2026-09"
PX_START, PX_END = "2019-09", "2026-10"  # month-ends bounding the price window

US_FUNDS = ["AVUV", "DFSVX", "IWN", "VTI"]
DEV_FUNDS = ["AVDV"]
PRICE_FUNDS = [
    ("AVUV", "Avantis U.S. Small Cap Value ETF"),
    ("DFSVX", "DFA U.S. Small Cap Value Portfolio (Institutional)"),
    ("IWN", "iShares Russell 2000 Value ETF"),
    ("VTI", "Vanguard Total Stock Market ETF"),
    ("SPY", "SPDR S&P 500 ETF"),
    ("VT", "Vanguard Total World Stock ETF"),
    ("AVDV", "Avantis International Small Cap Value ETF"),
    ("DISVX", "DFA International Small Cap Value Portfolio (Institutional)"),
    ("VSS", "Vanguard FTSE All-World ex-US Small-Cap ETF"),
    ("VXUS", "Vanguard Total International Stock ETF"),
    ("QVAL", "Alpha Architect U.S. Quantitative Value ETF"),
]

# ---------------------------------------------------------------- issuer data
AVANTIS_AVUV = (
    "https://www.avantisinvestors.com/avantis-investments/"
    "avantis-us-small-cap-value-etf/"
)
AVANTIS_AVDV = (
    "https://www.avantisinvestors.com/avantis-investments/"
    "avantis-international-small-cap-value-etf/"
)
DFA_DFSV = (
    "https://www.dimensional.com/chmedia/82775/source/download/"
    "us-small-cap-value-etf.pdf"
)
QVAL_URL = "https://funds.alphaarchitect.com/qval/"
SPY_URL = (
    "https://www.ssga.com/us/en/intermediary/etfs/"
    "state-street-spdr-sp-500-etf-trust-spy"
)
ISSUER_RETURNS = [
    # NAV total returns in percent; 3y, 5y and since-inception annualized.
    {
        "fund": "AVUV",
        "as_of": "2026-10-31",
        "ytd": 22.20,
        "1y": 27.93,
        "3y": 20.47,
        "5y": 11.33,
        "since_inception": 15.37,
        "inception": "2019-09-24",
        "expense_ratio": 0.25,
        "source": AVANTIS_AVUV,
    },
    {
        "fund": "Russell 2000 Value Index (AVUV benchmark)",
        "as_of": "2026-10-31",
        "ytd": 19.90,
        "1y": 23.49,
        "3y": 21.37,
        "5y": 7.53,
        "source": AVANTIS_AVUV,
    },
    {
        "fund": "AVDV",
        "as_of": "2026-10-31",
        "ytd": 14.06,
        "1y": 21.84,
        "3y": 28.25,
        "5y": 13.68,
        "since_inception": 14.30,
        "inception": "2019-09-24",
        "expense_ratio": 0.36,
        "source": AVANTIS_AVDV,
    },
    {
        "fund": "MSCI World ex USA Small Cap Index (AVDV benchmark)",
        "as_of": "2026-10-31",
        "ytd": 7.99,
        "1y": 12.52,
        "3y": 20.48,
        "5y": 5.54,
        "source": AVANTIS_AVDV,
    },
    {
        "fund": "DFSV (ETF class of the U.S. Small Cap Value Portfolio)",
        "as_of": "2026-09-30",
        "1y": 19.19,
        "3y": 16.27,
        "5y": 10.97,
        "since_inception": 11.35,
        "inception": "1993-03-02 (oldest share class)",
        "expense_ratio": 0.27,
        "source": DFA_DFSV,
    },
    {
        "fund": "QVAL",
        "as_of": "2026-10-31",
        "ytd": 33.96,
        "1y": 42.22,
        "3y": 24.29,
        "5y": 14.52,
        "10y": 12.92,
        "since_inception": 9.95,
        "inception": "2014-10-21",
        "expense_ratio": 0.28,
        "source": QVAL_URL,
    },
    {
        "fund": "AVUV",
        "as_of": "2026-09-30",
        "ytd": 16.60,
        "1y": 19.91,
        "source": AVANTIS_AVUV,
    },
    {
        "fund": "Russell 2000 Value Index (AVUV benchmark)",
        "as_of": "2026-09-30",
        "ytd": 16.96,
        "1y": 20.77,
        "source": AVANTIS_AVUV,
    },
    {
        "fund": "AVDV",
        "as_of": "2026-09-30",
        "ytd": 18.87,
        "1y": 26.99,
        "source": AVANTIS_AVDV,
    },
    {
        "fund": "S&P 500 Index",
        "as_of": "2026-09-30",
        "ytd": 12.75,
        "1y": 15.74,
        "source": SPY_URL,
    },
    {
        "fund": "S&P 500 Index",
        "as_of": "2026-10-31",
        "ytd": 11.77,
        "1y": 12.11,
        "3y": 23.40,
        "5y": 12.06,
        "source": SPY_URL,
    },
]
DFSV_CALENDAR = {
    # Calendar-year NAV returns, percent.
    "old_etf_fact_sheet_2025-12-31": {"2023": 19.23, "2024": 7.27, "2025": 8.51},
    "current_fact_sheet_2026-09-30": {"2023": 18.91, "2024": 9.57, "2025": 8.38},
    "sources": [
        "https://www.sec.gov/Archives/edgar/data/0001816125/000207184426000684/"
        "dfasupplementreetfshareclass.htm",
        "https://www.dimensional.com/chmedia/521500/source/download/"
        "upcoming-fund-mergers-client-ready.pdf",
        DFA_DFSV,
    ],
}
DISTRIBUTIONS_2026 = {
    # Estimated per-share distributions for 2026, as of Sep 30, 2026.
    "avantis": {
        "AVUV": {"st_gain": 0.0, "lt_gain": 0.0, "ordinary_income": 0.6874},
        "AVDV": {"st_gain": 0.0, "lt_gain": 0.0, "ordinary_income": 2.2327},
        "AVES": {"st_gain": 0.0, "lt_gain": 0.0},
        "pay_date": "2026-12-18",
        "source": "https://www.avantisinvestors.com/avantis-resources/en-us/"
        "estimated-distributions/",
    },
    "dimensional": {
        "DFSV": {"capital_gain": 0.0},
        "DISV": {"capital_gain": 0.0},
        "DFEV": {"capital_gain": 0.0},
        "DISVX": {"capital_gain": 1.577, "pct_of_nav": 4.50},
        "source": "https://www.dimensional.com/chmedia/520859/source/download/"
        "2026-capital-gain-distribution-estimates.pdf",
    },
}

AVDV_PREMIUM = {
    # premiumDiscount object embedded in the Avantis AVDV fund page.
    "as_of": "2026-11-13",
    "premium_discount_pct": 0.54,
    "source": AVANTIS_AVDV,
}
X_TABLE = {
    # Portfolio Visualizer "Performance Summary" table in a public X post read
    # Nov 15, 2026 (annualized return column; window not shown in the table).
    "AVDV": 14.59,
    "VXUS": 10.10,
    "DISVX": 14.03,
    "VSS": 8.39,
}

RESULTS: dict = {
    "data_vintage": "Ken French library 202609 cut; Yahoo read 2026-11-15",
    "issuer_returns": ISSUER_RETURNS,
    "dfsv_calendar": DFSV_CALENDAR,
    "distributions_2026": DISTRIBUTIONS_2026,
    "avdv_premium": AVDV_PREMIUM,
    "x_table": X_TABLE,
}


# ---------------------------------------------------------------- utilities
def fetch(name: str, dest: Path) -> Path:
    if not dest.exists():
        last = None
        for tmpl in (FRENCH, FRENCH_HTTP):
            try:
                req = urllib.request.Request(
                    tmpl.format(name), headers={"User-Agent": UA}
                )
                with urllib.request.urlopen(req, timeout=60) as r:
                    dest.write_bytes(r.read())
                return dest
            except OSError as exc:
                last = exc
        raise RuntimeError(f"download failed for {name}: {last}")
    return dest


def ym(idx) -> str:
    return pd.Timestamp(idx).strftime("%Y-%m")


def french_main(name: str) -> pd.DataFrame:
    """The first monthly (YYYYMM-indexed) block of a French CSV, in decimals."""
    local = DATA / f"{name}.csv"
    if local.exists():
        text = local.read_text(encoding="latin-1")
    else:
        z = zipfile.ZipFile(fetch(name, CACHE / f"{name}.zip"))
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
    """Bartlett long-run covariance of the rows of u."""
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
    u = Xv * e[:, None]
    S = nw_cov(u, lags) * n
    V_nw = XtXi @ S @ XtXi * n / (n - k)
    r2 = 1 - (e @ e) / np.sum((yv - yv.mean()) ** 2)
    names = ["alpha"] + list(X.columns)
    se_nw = np.sqrt(np.diag(V_nw))
    return {
        "start": ym(d.index[0]),
        "end": ym(d.index[-1]),
        "n": int(n),
        "r2": round(float(r2), 3),
        "resid_sd_ann": round(float(math.sqrt(e @ e / (n - k)) * math.sqrt(12)), 4),
        "alpha_ann": round(float(12 * b[0]), 4),
        "alpha_ci95_ann": [
            round(float(12 * (b[0] - 1.96 * se_nw[0])), 4),
            round(float(12 * (b[0] + 1.96 * se_nw[0])), 4),
        ],
        "coef": {nm: round(float(v), 4) for nm, v in zip(names, b, strict=True)},
        "t_nw": {
            nm: round(float(v / s), 2) for nm, v, s in zip(names, b, se_nw, strict=True)
        },
    }


def yahoo_daily(ticker: str) -> pd.Series:
    local = CACHE / f"{ticker}.csv"
    if not local.exists():
        import yfinance as yf

        for attempt in range(3):
            px = yf.download(
                ticker,
                start="2019-01-01",
                end="2026-11-14",
                auto_adjust=True,
                progress=False,
            )
            if len(px):
                break
            time.sleep(3 * (attempt + 1))
        close = px["Close"]
        if isinstance(close, pd.DataFrame):
            close = close.iloc[:, 0]
        close.to_csv(local)
    return pd.read_csv(local, index_col=0, parse_dates=True).iloc[:, 0]


def month_end_closes(ticker: str) -> pd.Series:
    m = yahoo_daily(ticker).resample("ME").last()
    return m[(m.index >= pd.Timestamp(PX_START) + pd.offsets.MonthEnd(0))]


def window_stats(closes: pd.Series, start: str, end: str) -> dict:
    s = closes[
        (closes.index >= pd.Timestamp(start) + pd.offsets.MonthEnd(0))
        & (closes.index <= pd.Timestamp(end) + pd.offsets.MonthEnd(0))
    ]
    r = s.pct_change().dropna()
    months = len(r)
    total = s.iloc[-1] / s.iloc[0] - 1
    cagr = (1 + total) ** (12 / months) - 1 if months >= 12 else None
    wealth = s / s.cummax()
    return {
        "start": ym(s.index[0]),
        "end": ym(s.index[-1]),
        "months": months,
        "total": round(float(total), 4),
        "cagr": round(float(cagr), 4) if cagr is not None else None,
        "vol_ann": round(float(r.std(ddof=1) * math.sqrt(12)), 4),
        "max_drawdown_month_end": round(float(wealth.min() - 1), 4),
    }


def pct(x: float | None, d: int = 1) -> str:
    return "n/a" if x is None else f"{100 * x:.{d}f}%"


# ---------------------------------------------------------------- 1-2. issuer
print("1. Issuer NAV returns as published (percent)")
for row in ISSUER_RETURNS:
    keys = [k for k in ("ytd", "1y", "3y", "5y", "since_inception") if k in row]
    print(
        f"  {row['fund']} as of {row['as_of']}: "
        + ", ".join(f"{k} {row[k]}" for k in keys)
    )
print("\n2. DFSV calendar returns, old ETF vs current fact sheet (percent)")
for y in ("2023", "2024", "2025"):
    old = DFSV_CALENDAR["old_etf_fact_sheet_2025-12-31"][y]
    new = DFSV_CALENDAR["current_fact_sheet_2026-09-30"][y]
    print(f"  {y}: old ETF {old}, now shown {new}, difference {new - old:+.2f}")

# ---------------------------------------------------------------- 3. prices
print("\n3. Market-price returns from Yahoo (distributions reinvested)")
closes = {t: month_end_closes(t) for t, _ in PRICE_FUNDS}
windows = {
    "since_avuv_inception": (PX_START, PX_END),
    "trailing_36m": ("2023-10", PX_END),
    "trailing_12m": ("2025-10", PX_END),
}
price_stats: dict = {}
for wname, (a, b) in windows.items():
    price_stats[wname] = {}
    print(f"  {wname} ({a} to {b} month-ends)")
    for t, label in PRICE_FUNDS:
        st = window_stats(closes[t], a, b)
        price_stats[wname][t] = st
        print(
            f"    {t:6s} total {pct(st['total'])}, CAGR {pct(st['cagr'], 2)}, "
            f"vol {pct(st['vol_ann'])}, worst drawdown {pct(st['max_drawdown_month_end'])}"
        )
RESULTS["price_windows"] = price_stats

# Rolling 12-month AVUV minus VTI and minus VT, since inception
r = pd.DataFrame(
    {t: closes[t].pct_change() for t in ("AVUV", "VTI", "VT", "IWN")}
).dropna()
r = r[r.index <= pd.Timestamp(PX_END) + pd.offsets.MonthEnd(0)]  # drop partial Nov
roll = (1 + r).rolling(12).apply(np.prod, raw=True) - 1
roll = roll.dropna()
share = {
    f"AVUV_beat_{b}": round(float((roll["AVUV"] > roll[b]).mean()), 3)
    for b in ("VTI", "VT", "IWN")
}
share["windows"] = len(roll)
share["first_end"] = ym(roll.index[0])
share["last_end"] = ym(roll.index[-1])
print(f"  rolling 12-month windows where AVUV led: {share}")
RESULTS["rolling_12m_share"] = share

# Where AVDV's three-year lead over AVUV was built, and the two months that
# separate the 12 months to September from the 12 months to October.
extra = {
    "oct2023_to_oct2025": {
        t: window_stats(closes[t], "2023-10", "2025-10") for t in ("AVUV", "AVDV")
    },
    "oct2025_to_sep2026": {
        t: window_stats(closes[t], "2025-09", "2026-09")
        for t in ("AVUV", "AVDV", "SPY", "VTI")
    },
    "single_months": {
        t: {
            ym(k): round(float(v), 4)
            for k, v in closes[t].pct_change().items()
            if ym(k) in ("2025-10", "2026-10")
        }
        for t in ("AVUV", "SPY", "AVDV")
    },
}
cal: dict = {}
for t in ("DFSV", "DFSVX"):
    ye = yahoo_daily(t).resample("YE").last()
    cal[t] = {
        str(i.year): round(float(ye.iloc[k] / ye.iloc[k - 1] - 1), 4)
        for k, i in enumerate(ye.index)
        if k > 0 and i.year in (2023, 2024, 2025)
    }
extra["calendar_market_price"] = cal
RESULTS["extra_windows"] = extra
print(f"  extra windows: {json.dumps(extra)}")

# ---------------------------------------------------------------- 4-5. factors
print("\n4. Factor attribution, out of sample")
us = french_main("F-F_Research_Data_5_Factors_2x3")
us_mom = french_main("F-F_Momentum_Factor")
us_mom.columns = ["MOM"]
us = us.join(us_mom, how="inner")
dev = french_main("Developed_ex_US_5_Factors")
dev_mom = french_main("Developed_ex_US_Mom_Factor")
dev_mom.columns = ["MOM"]
dev = dev.join(dev_mom, how="inner")
for frame, name in ((us, "U.S."), (dev, "developed ex-US")):
    print(f"  {name} factors through {ym(frame.index[-1])}")


def monthly_returns(ticker: str) -> pd.Series:
    return yahoo_daily(ticker).resample("ME").last().pct_change().dropna()


def sl(frame, a, b):
    return frame[
        (frame.index >= pd.Timestamp(a) + pd.offsets.MonthEnd(0))
        & (frame.index <= pd.Timestamp(b) + pd.offsets.MonthEnd(0))
    ]


def attribute(excess: pd.Series, F: pd.DataFrame) -> dict:
    est = ols(sl(excess, EST_START, EST_END), sl(F[FACTORS], EST_START, EST_END))
    full = ols(sl(excess, FULL_START, FULL_END), sl(F[FACTORS], FULL_START, FULL_END))
    fa = sl(F, ATT_START, ATT_END)
    ya = sl(excess, ATT_START, ATT_END)
    assert len(fa) == len(ya) == 12, (len(fa), len(ya))
    contrib = {f: round(float(est["coef"][f] * fa[f].sum()), 4) for f in FACTORS}
    predicted_sum = sum(contrib.values())
    actual_sum = float(ya.sum())
    rf = fa["RF"]
    pred_monthly = fa[FACTORS].to_numpy() @ np.array([est["coef"][f] for f in FACTORS])
    pred_total = float(np.prod(1 + rf.to_numpy() + pred_monthly) - 1)
    act_total = float(np.prod(1 + rf.to_numpy() + ya.to_numpy()) - 1)
    return {
        "estimation": est,
        "full_window": full,
        "attribution_window": f"{ATT_START} to {ATT_END}",
        "factor_sums": {f: round(float(fa[f].sum()), 4) for f in FACTORS + ["RF"]},
        "contribution_sum": contrib,
        "predicted_excess_sum": round(predicted_sum, 4),
        "actual_excess_sum": round(actual_sum, 4),
        "residual_sum": round(actual_sum - predicted_sum, 4),
        "predicted_total_compounded": round(pred_total, 4),
        "actual_total_compounded": round(act_total, 4),
    }


attrib: dict = {}
rets = {t: monthly_returns(t) for t in US_FUNDS + DEV_FUNDS}
for t in US_FUNDS:
    ex = (rets[t] - us["RF"]).dropna()
    attrib[t] = attribute(ex, us)
for t in DEV_FUNDS:
    ex = (rets[t] - dev["RF"]).dropna()
    attrib[t] = attribute(ex, dev)

# AVUV minus IWN: the factor model on the return difference (no RF).
gap = (rets["AVUV"] - rets["IWN"]).dropna()
est_gap = ols(sl(gap, EST_START, EST_END), sl(us[FACTORS], EST_START, EST_END))
fa = sl(us, ATT_START, ATT_END)
gap_contrib = {f: round(float(est_gap["coef"][f] * fa[f].sum()), 4) for f in FACTORS}
gap_actual = float(sl(gap, ATT_START, ATT_END).sum())
attrib["AVUV_minus_IWN"] = {
    "estimation": est_gap,
    "contribution_sum": gap_contrib,
    "predicted_sum": round(sum(gap_contrib.values()), 4),
    "actual_sum": round(gap_actual, 4),
    "residual_sum": round(gap_actual - sum(gap_contrib.values()), 4),
}
RESULTS["attribution"] = attrib

# How unusual the attribution window was for the profitability factor:
# trailing 12-month sums of monthly RMW since the factor starts (1963-07).
rmw12 = us["RMW"].rolling(12).sum().dropna()
latest = float(rmw12.loc[pd.Timestamp(ATT_END) + pd.offsets.MonthEnd(0)])
RESULTS["rmw_12m"] = {
    "window": f"{ATT_START} to {ATT_END}",
    "sum": round(latest, 4),
    "share_of_12m_windows_at_or_below": round(float((rmw12 <= latest).mean()), 3),
    "windows": len(rmw12),
    "first_end": ym(rmw12.index[0]),
    "worst": round(float(rmw12.min()), 4),
    "worst_end": ym(rmw12.idxmin()),
}
print(f"  RMW trailing 12-month sum: {RESULTS['rmw_12m']}")

for t, a in attrib.items():
    if t == "AVUV_minus_IWN":
        print(f"  {t}: loadings {a['estimation']['coef']}")
        print(
            f"    contributions {a['contribution_sum']}, predicted {pct(a['predicted_sum'])}, "
            f"actual {pct(a['actual_sum'])}, residual {pct(a['residual_sum'])}"
        )
        continue
    e = a["estimation"]
    print(
        f"  {t}: est {e['start']}..{e['end']} n={e['n']} R2={e['r2']} "
        f"residual sd {pct(e['resid_sd_ann'])}/yr"
    )
    print(f"    loadings {e['coef']}")
    print(f"    t(NW6)   {e['t_nw']}")
    print(f"    factor sums {a['factor_sums']}")
    print(f"    contributions {a['contribution_sum']}")
    print(
        f"    predicted excess {pct(a['predicted_excess_sum'])}, actual {pct(a['actual_excess_sum'])}, "
        f"residual {pct(a['residual_sum'])}; compounded total predicted "
        f"{pct(a['predicted_total_compounded'])} vs actual {pct(a['actual_total_compounded'])}"
    )
    f = a["full_window"]
    print(
        f"    full {f['start']}..{f['end']} n={f['n']}: alpha {pct(f['alpha_ann'], 2)}/yr "
        f"(95% CI {pct(f['alpha_ci95_ann'][0], 2)} to {pct(f['alpha_ci95_ann'][1], 2)}), "
        f"t {f['t_nw']['alpha']}"
    )

# ---------------------------------------------------------------- export
(OUT / "results.json").write_text(json.dumps(RESULTS, indent=2) + "\n")
compact = {
    "window": f"{ATT_START} to {ATT_END}",
    "estimation_window": f"{EST_START} to {EST_END}",
    "funds": {
        t: {
            "contribution": attrib[t]["contribution_sum"],
            "predicted": attrib[t]["predicted_excess_sum"],
            "actual": attrib[t]["actual_excess_sum"],
            "residual": attrib[t]["residual_sum"],
        }
        for t in ("AVUV", "DFSVX", "IWN", "AVDV")
    },
    "avuv_minus_iwn": attrib["AVUV_minus_IWN"],
}
(OUT / "is-the-value-premium-back.json").write_text(
    json.dumps(compact, indent=2) + "\n"
)
print("\nWrote output/results.json and output/is-the-value-premium-back.json")
