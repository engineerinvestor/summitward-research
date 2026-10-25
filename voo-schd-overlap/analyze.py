"""VOO vs SCHD: holdings overlap, return co-movement and factor loadings.

Reads the files fetch_data.py writes and prints every number the Summitward
guide quotes (summitward.com/learn/voo-schd-overlap); also writes
out/results.json.

Holdings
    SCHD: Schwab full holdings, 2026-10-13. VOO proxy: IVV (same S&P 500
    index), repriced to 2026-10-13 as quantity x that day's close, so both
    sides share one date. Overlap = sum of min(w_a, w_b) over stocks held by
    both, with each fund's stock weights summing to 1. For long-only funds this
    equals 1 - Active Share (Cremers and Petajisto 2009). Matched by ticker.

Returns
    Adjusted daily closes (Yahoo Finance), 2011-10-20 (SCHD's first close) to
    2026-10-23. Monthly statistics use full calendar months, Nov 2011 to
    Sep 2026 (179 months). Mixes rebalance monthly.

Factors
    Fama-French five factors (French library, 202608 file), monthly OLS with
    Newey-West (6 lag) standard errors, Nov 2011 to Aug 2026.

Usage:
    python3 analyze.py
"""

import csv
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
DATA, OUT = HERE / "data", HERE / "out"
SCHD_FILE = DATA / "schd_holdings_2026-10-13.csv"
NON_STOCK = {"GVMXX", "USD", "FAZ6", "DMZ6"}  # money fund, cash, two futures
SAME_ISSUER = {"GOOG": "GOOGL", "FOX": "FOXA", "NWS": "NWSA"}
FUNDS = ["IVV", "RSP", "SCHD", "IJH", "VXUS", "BND"]
MONTHS = ("2011-11", "2026-09")
FACTOR_END = "2026-08"
MIXES = [0.0, 0.1, 0.2, 0.3, 0.5, 1.0]
results: dict = {}


def pct(x: float, d: int = 2) -> str:
    return f"{100 * x:.{d}f}%"


# ------------------------------------------------------------------ holdings
def load_voo() -> pd.DataFrame:
    lines = (DATA / "ivv_latest.csv").read_text(encoding="utf-8-sig").splitlines()
    as_of = next(ln for ln in lines if ln.startswith("Fund Holdings as of"))
    head = next(i for i, ln in enumerate(lines) if ln.startswith("Ticker,"))
    rows = [
        r
        for r in csv.DictReader(lines[head:])
        if r.get("Asset Class") == "Equity"
        and r["Exchange"] != "NO MARKET (E.G. UNLISTED)"
    ]
    df = pd.DataFrame(
        {
            "ticker": [r["Ticker"].replace(" ", ".") for r in rows],
            "name": [r["Name"] for r in rows],
            "sector": [r["Sector"] for r in rows],
            "qty": [float(r["Quantity"].replace(",", "")) for r in rows],
            "w_reported": [float(r["Weight (%)"]) / 100 for r in rows],
        }
    ).set_index("ticker")
    closes = pd.read_csv(DATA / "constituent_closes.csv", index_col=0)
    closes.index = closes.index.str.replace(" ", ".")
    df = df.join(closes)
    assert df["close_schd_date"].notna().all(), "missing closes"
    mv_then = df["qty"] * df["close_schd_date"]
    mv_now = df["qty"] * df["close_ivv_date"]
    df["w"] = mv_then / mv_then.sum()
    df["w_file_date"] = mv_now / mv_now.sum()
    print(f"IVV file {as_of.split(',', 1)[1]}: {len(df)} stock lines")
    return df


def load_schd() -> pd.DataFrame:
    df = pd.read_csv(SCHD_FILE, dtype={"cusip": str}).set_index("ticker")
    df["w_reported"] = df["weight_pct"] / 100
    stocks = df[~df.index.isin(NON_STOCK)].copy()
    stocks["w"] = stocks["w_reported"] / stocks["w_reported"].sum()
    print(
        f"SCHD 2026-10-13: {len(df)} lines, {len(stocks)} stocks, "
        f"non-stock lines {pct(df.loc[df.index.isin(NON_STOCK), 'w_reported'].sum())}"
    )
    return stocks


def overlap(a: pd.Series, b: pd.Series) -> float:
    idx = a.index.intersection(b.index)
    return float(np.minimum(a[idx], b[idx]).sum())


def active_share(a: pd.Series, b: pd.Series) -> float:
    u = a.index.union(b.index)
    return 0.5 * float((a.reindex(u, fill_value=0) - b.reindex(u, fill_value=0)).abs().sum())


def by_issuer(w: pd.Series) -> pd.Series:
    return w.groupby(lambda t: SAME_ISSUER.get(t, t)).sum()


def eff_n(w: pd.Series) -> float:
    return 1.0 / float((w**2).sum())


def holdings() -> None:
    print("\n=== Holdings (2026-10-13) ===")
    voo, schd = load_voo(), load_schd()
    wv, ws = voo["w"], schd["w"]
    shared = ws.index.intersection(wv.index)
    only_schd = ws.index.difference(wv.index)

    ov = overlap(wv, ws)
    ov_file_date = overlap(voo["w_file_date"], ws)
    ov_reported = overlap(voo["w_reported"], schd["w_reported"])
    ash = active_share(wv, ws)
    cov_s = float(ws[shared].sum())
    cov_v = float(wv[shared].sum())
    print(f"overlap by weight             {pct(ov)}   (1 - active share = {pct(1 - ash)})")
    print(f"  with IVV weights unrepriced {pct(ov_file_date)};  as reported, no rescaling {pct(ov_reported)}")
    print(f"shared stocks                 {len(shared)} of SCHD's {len(ws)}, of VOO's {len(wv)}")
    print(f"SCHD weight in VOO stocks     {pct(cov_s)}")
    print(f"VOO weight in SCHD stocks     {pct(cov_v)}")
    print(
        f"SCHD decomposition: matched {pct(ov)}, extra weight in shared stocks "
        f"{pct(cov_s - ov)}, outside the S&P 500 {pct(1 - cov_s)} ({len(only_schd)} stocks)"
    )

    # Where SCHD's weight is the smaller one (the min picks SCHD's side).
    smaller = [t for t in shared if ws[t] < wv[t]]
    print(f"shared stocks where SCHD weight < VOO weight: {len(smaller)} {smaller}")

    top = ws.sort_values(ascending=False).head(15)
    tbl = pd.DataFrame({"SCHD": top, "VOO": wv.reindex(top.index)})
    tbl["counted"] = np.minimum(tbl["SCHD"], tbl["VOO"].fillna(0))
    print("\nSCHD top 15: SCHD weight, VOO weight, counted toward overlap")
    print((100 * tbl).round(2).to_string())
    print("\nLargest SCHD stocks outside the S&P 500:")
    print((100 * ws[only_schd].sort_values(ascending=False).head(12)).round(2).to_string())

    # Concentration, looked through to issuers.
    vi, si = by_issuer(wv), by_issuer(ws)
    u = vi.index.union(si.index)
    vi, si = vi.reindex(u, fill_value=0), si.reindex(u, fill_value=0)
    conc = {}
    for x in MIXES:
        w = (1 - x) * vi + x * si
        conc[f"{int(100 * x)}"] = {
            "effective_n": eff_n(w),
            "top10": float(w.sort_values(ascending=False).head(10).sum()),
        }
    print("\nSCHD share | effective number of stocks (1/sum w^2) | top-10 weight")
    for k, v in conc.items():
        print(f"  {k:>3}%      {v['effective_n']:7.1f}    {pct(v['top10'], 1)}")
    mix = 0.8 * vi + 0.2 * si
    print("\n80/20 VOO/SCHD, ten largest stocks:")
    print((100 * mix.sort_values(ascending=False).head(10)).round(2).to_string())

    # Sector weights where both sides can be classified with IVV's GICS labels.
    sec_v = voo.groupby("sector")["w"].sum()
    sec_s = ws[shared].groupby(voo.loc[shared, "sector"]).sum()
    print("\nVOO sector weights, and SCHD's shared-stock weight by the same labels:")
    print(
        (100 * pd.DataFrame({"VOO": sec_v, "SCHD_shared": sec_s}).fillna(0))
        .round(1)
        .sort_values("VOO", ascending=False)
        .to_string()
    )

    # S&P MidCap 400 (IJH) and S&P 500 should share no stocks.
    ijh_lines = (DATA / "ijh_latest.csv").read_text(encoding="utf-8-sig").splitlines()
    head = next(i for i, ln in enumerate(ijh_lines) if ln.startswith("Ticker,"))
    ijh = {r["Ticker"].replace(" ", ".") for r in csv.DictReader(ijh_lines[head:]) if r.get("Asset Class") == "Equity"}
    print(f"\nIJH stocks: {len(ijh)}; shared with the S&P 500 file: {sorted(ijh & set(wv.index))}")

    # Equal-weight S&P 500 (RSP) at a rebalance date: every stock line 1/n.
    rsp = pd.Series(1.0 / len(wv), index=wv.index)
    ov_rsp = overlap(wv, rsp)
    print(f"\nVOO vs equal-weight S&P 500 (RSP at rebalance): overlap {pct(ov_rsp, 1)}")

    results["holdings"] = {
        "date": "2026-10-13",
        "overlap": ov,
        "overlap_unrepriced": ov_file_date,
        "overlap_reported_weights": ov_reported,
        "active_share": ash,
        "n_shared": len(shared),
        "n_schd": len(ws),
        "n_voo": len(wv),
        "n_schd_only": len(only_schd),
        "schd_in_voo_stocks": cov_s,
        "voo_in_schd_stocks": cov_v,
        "top15": {t: {"schd": float(tbl.loc[t, "SCHD"]), "voo": float(tbl.loc[t, "VOO"])} for t in tbl.index},
        "concentration": conc,
        "overlap_rsp": ov_rsp,
    }


# ------------------------------------------------------------------- returns
def load_prices() -> pd.DataFrame:
    px = pd.read_csv(DATA / "fund_prices_daily.csv", index_col=0, parse_dates=True)
    return px.dropna()


def monthly(px: pd.DataFrame) -> pd.DataFrame:
    m = px.resample("ME").last().pct_change()
    return m.loc[MONTHS[0] : MONTHS[1]]


def max_dd(p: pd.Series) -> float:
    return float((p / p.cummax() - 1).min())


def returns() -> None:
    px = load_prices()
    d = px.pct_change().dropna()
    m = monthly(px)
    print(f"\n=== Returns: daily {d.index[0].date()} to {d.index[-1].date()}, "
          f"monthly {m.index[0]:%Y-%m} to {m.index[-1]:%Y-%m} ({len(m)} months) ===")

    pair = {}
    print("fund  | corr daily | corr monthly | beta | R2 | tracking err/yr | vol/yr | down-mo corr | up-mo corr")
    down, up = m["VOO"] < 0, m["VOO"] > 0
    for f in FUNDS:
        cd = d["VOO"].corr(d[f])
        cm = m["VOO"].corr(m[f])
        beta = m[f].cov(m["VOO"]) / m["VOO"].var()
        te = (m[f] - m["VOO"]).std() * math.sqrt(12)
        vol = m[f].std() * math.sqrt(12)
        cdn = m.loc[down, "VOO"].corr(m.loc[down, f])
        cup = m.loc[up, "VOO"].corr(m.loc[up, f])
        pair[f] = dict(corr_daily=cd, corr_monthly=cm, beta=beta, r2=cm**2,
                       te=te, vol=vol, corr_down=cdn, corr_up=cup)
        print(f"{f:5} | {cd:.3f} | {cm:.3f} | {beta:.2f} | {cm**2:.2f} | {pct(te,1)} | {pct(vol,1)} | {cdn:.2f} | {cup:.2f}")
    print(f"VOO vol/yr {pct(m['VOO'].std() * math.sqrt(12), 1)}; down months {int(down.sum())}, up months {int(up.sum())}")

    # Rolling and recent correlation, VOO-SCHD.
    roll36 = m["VOO"].rolling(36).corr(m["SCHD"]).dropna()
    d26 = d.loc["2026"]
    last252 = d.iloc[-252:]
    rec = {
        "roll36_min": float(roll36.min()), "roll36_min_end": f"{roll36.idxmin():%Y-%m}",
        "roll36_max": float(roll36.max()), "roll36_max_end": f"{roll36.idxmax():%Y-%m}",
        "roll36_last": float(roll36.iloc[-1]),
        "ytd2026_daily": float(d26["VOO"].corr(d26["SCHD"])),
        "trailing252_daily": float(last252["VOO"].corr(last252["SCHD"])),
        "trailing12m_monthly": float(m["VOO"].iloc[-12:].corr(m["SCHD"].iloc[-12:])),
    }
    yearly = {}
    for y, g in d.groupby(d.index.year):
        yearly[str(y)] = {f: float(g["VOO"].corr(g[f])) for f in ["SCHD", "RSP", "IJH"]}
    rec["by_year_daily"] = yearly
    q = d.loc["2026"].groupby(d.loc["2026"].index.quarter)
    rec["q2026_daily"] = {f"Q{k}": float(g["VOO"].corr(g["SCHD"])) for k, g in q}
    dn = m.loc[down]
    rec["down_months"] = {
        "n": int(down.sum()),
        "schd_also_down": int((dn["SCHD"] < 0).sum()),
        "voo_mean": float(dn["VOO"].mean()),
        "schd_mean": float(dn["SCHD"].mean()),
        "down_capture": float(dn["SCHD"].mean() / dn["VOO"].mean()),
        "up_capture": float(m.loc[up, "SCHD"].mean() / m.loc[up, "VOO"].mean()),
    }
    print("\nVOO-SCHD correlation:")
    for k, v in rec.items():
        if isinstance(v, dict):
            print(f"  {k}:")
            for kk, vv in v.items():
                print(f"    {kk}: {vv if not isinstance(vv, dict) else {a: round(b, 2) for a, b in vv.items()}}")
        else:
            print(f"  {k:22} {v if isinstance(v, str) else round(v, 3)}")

    # Calendar-year total returns.
    ye = px.resample("YE").last()
    first = px.iloc[0]
    cal = ye.pct_change()
    cal.iloc[0] = ye.iloc[0] / first - 1
    cal.index = [f"{i.year}" + ("*" if i.year in (2011, 2026) else "") for i in cal.index]
    print("\nCalendar returns (2011 from 10/20; 2026 through 10/23):")
    print((100 * cal[["VOO", "SCHD"]]).round(1).to_string())
    gap = (cal["SCHD"] - cal["VOO"]).abs()
    print(f"mean absolute VOO-SCHD calendar gap, 2012-2025: {pct(gap.iloc[1:-1].mean(), 1)}")

    yrs = (px.index[-1] - px.index[0]).days / 365.25
    cagr = (px.iloc[-1] / px.iloc[0]) ** (1 / yrs) - 1
    print("\nAnnualized total return over the window:", {k: pct(v, 2) for k, v in cagr.items()})

    dds = {}
    for label, (a, b) in {"2020": ("2020-01-01", "2020-12-31"), "2022": ("2022-01-01", "2022-12-31")}.items():
        seg = px.loc[a:b]
        dds[label] = {f: max_dd(seg[f]) for f in ["VOO", "SCHD"]}
    dds["full"] = {f: max_dd(px[f]) for f in ["VOO", "SCHD"]}
    print("Max drawdown within window (daily closes):",
          {k: {f: pct(v, 1) for f, v in x.items()} for k, x in dds.items()})

    # Mixes, rebalanced monthly.
    print("\nSCHD share | vol/yr | tracking err vs VOO | diversification ratio | ann. return")
    mixes = {}
    sv, ss = m["VOO"].std(), m["SCHD"].std()
    for x in MIXES:
        r = (1 - x) * m["VOO"] + x * m["SCHD"]
        vol = r.std() * math.sqrt(12)
        te = (r - m["VOO"]).std() * math.sqrt(12)
        dr = ((1 - x) * sv + x * ss) / r.std()
        ann = (1 + r).prod() ** (12 / len(r)) - 1
        mixes[f"{int(100 * x)}"] = dict(vol=vol, te=te, dr=dr, ann=ann)
        print(f"  {int(100*x):>3}%      {pct(vol,2)}   {pct(te,2)}   {dr:.3f}   {pct(ann,2)}")

    alt = {}
    for f in ["BND", "VXUS"]:
        r = 0.8 * m["VOO"] + 0.2 * m[f]
        alt[f] = dict(vol=r.std() * math.sqrt(12), ann=(1 + r).prod() ** (12 / len(r)) - 1)
        print(f"  80% VOO / 20% {f}: vol {pct(alt[f]['vol'])}, ann. return {pct(alt[f]['ann'])}")

    results["returns"] = {
        "daily_window": [f"{d.index[0].date()}", f"{d.index[-1].date()}"],
        "monthly_window": [f"{m.index[0]:%Y-%m}", f"{m.index[-1]:%Y-%m}"],
        "n_months": len(m),
        "voo_vol": float(m["VOO"].std() * math.sqrt(12)),
        "pairs": pair,
        "schd_corr": rec,
        "calendar": {k: {"VOO": float(v["VOO"]), "SCHD": float(v["SCHD"])} for k, v in cal.iterrows()},
        "cagr": {k: float(v) for k, v in cagr.items()},
        "drawdowns": dds,
        "mixes": mixes,
        "alt_sleeves_20pct": alt,
    }


# ------------------------------------------------------------------- factors
def french() -> pd.DataFrame:
    lines = (DATA / "F-F_Research_Data_5_Factors_2x3.csv").read_text(encoding="latin-1").splitlines()
    i = next(i for i, ln in enumerate(lines) if ln.startswith(",Mkt-RF"))
    cols = [c.strip() for c in lines[i].split(",")[1:]]
    rows = []
    for ln in lines[i + 1 :]:
        p = [x.strip() for x in ln.split(",")]
        if len(p[0]) != 6 or not p[0].isdigit():
            break
        rows.append(p)
    idx = pd.to_datetime([r[0] for r in rows], format="%Y%m") + pd.offsets.MonthEnd(0)
    return pd.DataFrame([[float(x) for x in r[1:]] for r in rows], index=idx, columns=cols) / 100


def nw_cov(u: np.ndarray, lags: int) -> np.ndarray:
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
    V = XtXi @ (nw_cov(Xv * e[:, None], lags) * n) @ XtXi * n / (n - k)
    se = np.sqrt(np.diag(V))
    names = ["alpha"] + list(X.columns)
    return {
        "start": f"{d.index[0]:%Y-%m}", "end": f"{d.index[-1]:%Y-%m}", "n": int(n),
        "r2": float(1 - e @ e / np.sum((yv - yv.mean()) ** 2)),
        "coef": dict(zip(names, map(float, b), strict=True)),
        "t": dict(zip(names, map(float, b / se), strict=True)),
    }


def factors() -> None:
    ff = french()
    m = monthly(load_prices()).loc[:FACTOR_END]
    X = ff[["Mkt-RF", "SMB", "HML", "RMW", "CMA"]]
    out = {}
    print(f"\n=== Fama-French 5 factors, {m.index[0]:%Y-%m} to {FACTOR_END}, NW(6) t-stats ===")
    for f in ["VOO", "SCHD"]:
        r = ols(m[f] - ff["RF"], X)
        out[f] = r
        c, t = r["coef"], r["t"]
        print(f"{f:5} n={r['n']} R2={r['r2']:.3f} alpha/yr={pct(12 * c['alpha'])} (t {t['alpha']:.1f})  " +
              "  ".join(f"{k} {c[k]:.2f} (t {t[k]:.1f})" for k in X.columns))
    # SCHD regressed on VOO alone: how much of SCHD's variance VOO explains.
    rf = ff["RF"].reindex(m.index)
    r = ols(m["SCHD"] - rf, (m["VOO"] - rf).to_frame("VOO"))
    out["SCHD_on_VOO"] = r
    print(f"SCHD on VOO alone: beta {r['coef']['VOO']:.2f}, R2 {r['r2']:.3f}")
    results["factors"] = out


if __name__ == "__main__":
    holdings()
    returns()
    factors()
    OUT.mkdir(exist_ok=True)
    (OUT / "results.json").write_text(json.dumps(results, indent=2, default=float))
    print("\nwrote out/results.json")
