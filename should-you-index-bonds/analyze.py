"""Bond index funds vs systematic bond funds: holdings, returns, factor tilts.

Reads data/ (written by fetch_data.py) and prints every number the guide
https://summitward.com/learn/should-you-index-bonds quotes. Rules were fixed
before the run (see README):

A. Holdings mix by N-PORT category for AGG, BND, DFCF and AVIG, as a percent
   of net assets (sums exceed 100 when TBA forwards or securities-lending
   collateral are reported alongside the bonds).
B. Corporate issuer concentration in AGG and BND: corporate (and REIT) debt
   grouped by LEI, falling back to the issuer name when no LEI is reported.
C. Each systematic fund against each index fund over their common live
   window: CAGR, volatility, maximum drawdown, tracking error, beta.
D. The monthly return difference regressed on a term factor (IEF minus BIL)
   and a credit factor (SPIB minus IEI, two ETFs of similar duration), OLS
   with Newey-West standard errors. Robustness: credit as LQD minus IEF.
E. A static replica for DFCF and AVIG made of BND and VCIT, with the VCIT
   weight set so the replica's corporate share equals the fund's in its first
   public N-PORT filing (BND and VCIT shares from their filings on or before
   that date), rebalanced every January. Fund minus replica, as in C and D.
F. Years of data needed before an edge of a given size reaches t = 1.96 on
   average at the measured tracking error: (1.96 * TE / edge) ** 2.

Market-price total returns from yfinance adjusted closes; ETF returns are at
market price, not NAV.
"""

import glob
import gzip
import json
import math
import re
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
OUT = HERE / "output"

PAIRS = [  # (fund, index fund, first return month)
    ("AVIG", "AGG", "2020-11"),
    ("AVIG", "BND", "2020-11"),
    ("DFCF", "AGG", "2021-12"),
    ("DFCF", "BND", "2021-12"),
    ("DFAPX", "VBTLX", "2011-04"),
]
END = "2026-10"
EDGES = [0.10, 0.25, 0.50]  # percent per year

GOVT_REL = {"NUSS", "MUN", "Supranational", "Provincial", "non-U.S. government agency"}

# Filers classify supranational and foreign-agency issuers inconsistently:
# Vanguard and Avantis file them as corporate, Dimensional as Supranational.
# These names are moved to "Other government-related" for every fund.
SUPRA = re.compile(
    r"RECONSTRUCTION|EUROPEAN INVESTMENT BANK|INTER-AMERICAN|ASIAN DEVELOPMENT"
    r"|ASIAN INFRASTRUCTURE|INTERNATIONAL FINANCE CORP|COUNCIL OF EUROPE"
    r"|NORDIC INVESTMENT|AFRICAN DEVELOPMENT|KREDITANSTALT|^KFW$"
    r"|INTERNATIONAL DEVELOPMENT ASSOCIATION",
    re.I,
)


def holdings(path: str) -> tuple[pd.DataFrame, str]:
    with gzip.open(path, "rt") as f:
        header = f.readline().strip("# \n")
    d = pd.read_csv(path, comment="#", dtype=str, keep_default_na=False)
    d["pct"] = pd.to_numeric(d.pct_val, errors="coerce").fillna(0.0)
    supra = d.issuer_cat.isin(["CORP"]) & d.name.str.contains(SUPRA)
    d.loc[supra, "issuer_cat"] = "Supranational"
    return d, header


def bucket(row) -> str:
    ic, ac = row.issuer_cat, row.asset_cat
    if ic == "UST":
        return "US Treasury"
    if ic in ("USGA", "USGSE") and ac == "ABS-MBS":
        return "Agency MBS"
    if ic in ("USGA", "USGSE"):
        return "Agency debt"
    if ic in ("CORP", "REIT") and ac == "DBT":
        return "Corporate bonds"
    if ac.startswith("ABS"):
        return "Other securitized"
    if ic in GOVT_REL:
        return "Other government-related"
    if ac == "STIV" or ic == "RF":
        return "Cash and collateral"
    return "Other"


def mix(d: pd.DataFrame) -> dict:
    b = d.apply(bucket, axis=1)
    return {k: round(float(v), 2) for k, v in d.groupby(b).pct.sum().sort_values(ascending=False).items()}


def corp_share(d: pd.DataFrame) -> float:
    m = d.issuer_cat.isin(["CORP", "REIT"]) & (d.asset_cat == "DBT")
    return float(d.loc[m, "pct"].sum())


def concentration(d: pd.DataFrame) -> dict:
    c = d[d.issuer_cat.isin(["CORP", "REIT"]) & (d.asset_cat == "DBT")].copy()
    c["key"] = np.where(c.lei.str.len() == 20, c.lei, "NAME:" + c.name.str.upper())
    names = c.groupby("key").name.agg(lambda s: s.value_counts().index[0])
    w = c.groupby("key").pct.sum().sort_values(ascending=False)
    sleeve = w.sum()
    share = w / sleeve
    top = [{"issuer": names[k], "pct": round(float(v), 3)} for k, v in w.head(10).items()]
    return {
        "corporate_pct": round(float(sleeve), 2),
        "issuers": int(len(w)),
        "positions": int(len(c)),
        "largest": top[0],
        "top10": top,
        "top10_pct": round(float(w.head(10).sum()), 2),
        "top25_pct": round(float(w.head(25).sum()), 2),
        "top50_pct": round(float(w.head(50).sum()), 2),
        "effective_issuers": round(float(1 / (share**2).sum()), 0),
        "largest_position_pct": round(float(c.pct.max()), 3),
        "treasury_pct": round(float(d.loc[d.issuer_cat == "UST", "pct"].sum()), 2),
    }


def stats(r: pd.Series) -> dict:
    n = len(r)
    wealth = (1 + r).cumprod()
    cagr = wealth.iloc[-1] ** (12 / n) - 1
    dd = (wealth / wealth.cummax().clip(lower=1.0) - 1).min()
    return {
        "cagr": 100 * cagr,
        "vol": 100 * r.std(ddof=1) * math.sqrt(12),
        "max_dd": 100 * dd,
        "total": 100 * (wealth.iloc[-1] - 1),
    }


def nw_ols(y: np.ndarray, X: np.ndarray, lags: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, float]:
    """OLS coefficients, plain and Newey-West standard errors, R^2."""
    n, k = X.shape
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    e = y - X @ beta
    xtx_inv = np.linalg.inv(X.T @ X)
    se_ols = np.sqrt(np.diag(xtx_inv) * (e @ e) / (n - k))
    S = (X * e[:, None]).T @ (X * e[:, None])
    for L in range(1, lags + 1):
        wgt = 1 - L / (lags + 1)
        G = (X[L:] * e[L:, None]).T @ (X[:-L] * e[:-L, None])
        S += wgt * (G + G.T)
    cov = xtx_inv @ S @ xtx_inv * n / (n - k)
    se_nw = np.sqrt(np.diag(cov))
    r2 = 1 - (e @ e) / ((y - y.mean()) @ (y - y.mean()))
    return beta, se_ols, se_nw, float(r2)


def nw_lags(n: int) -> int:
    return int(math.floor(4 * (n / 100) ** (2 / 9)))


def regress(active: pd.Series, factors: pd.DataFrame) -> dict:
    df = pd.concat([active.rename("y"), factors], axis=1).dropna()
    X = np.column_stack([np.ones(len(df)), df[factors.columns].to_numpy()])
    y = df.y.to_numpy()
    lags = nw_lags(len(df))
    b, se, se_nw, r2 = nw_ols(y, X, lags)
    resid_te = np.std(y - X @ b, ddof=X.shape[1]) * math.sqrt(12) * 100
    out = {
        "n": len(df),
        "nw_lags": lags,
        "alpha_pct_yr": 1200 * b[0],
        "alpha_t": b[0] / se[0],
        "alpha_t_nw": b[0] / se_nw[0],
        "r2": r2,
        "residual_te": resid_te,
    }
    for i, c in enumerate(factors.columns, start=1):
        out[f"beta_{c}"] = b[i]
        out[f"t_{c}"] = b[i] / se[i]
        out[f"t_nw_{c}"] = b[i] / se_nw[i]
    return out


def compare(fund: pd.Series, index: pd.Series, factors: dict[str, pd.DataFrame]) -> dict:
    df = pd.concat([fund.rename("f"), index.rename("i")], axis=1).dropna()
    active = df.f - df.i
    n = len(df)
    te = active.std(ddof=1) * math.sqrt(12) * 100
    cov = np.cov(df.f, df.i, ddof=1)
    sf, si = stats(df.f), stats(df.i)
    res = {
        "start": df.index[0],
        "end": df.index[-1],
        "months": n,
        "fund": sf,
        "index": si,
        "cagr_gap": sf["cagr"] - si["cagr"],
        "tracking_error": te,
        "beta": cov[0, 1] / cov[1, 1],
        "active_mean_pct_yr": 1200 * active.mean(),
        "active_t": active.mean() / (active.std(ddof=1) / math.sqrt(n)),
        "years_to_t2": {f"{e:.2f}": (1.96 * te / e) ** 2 for e in EDGES},
    }
    for name, f in factors.items():
        res[f"regression_{name}"] = regress(active, f.loc[df.index])
    return res


def replica_returns(r: pd.DataFrame, w: float, start: str, monthly: bool = False) -> pd.Series:
    """BND/VCIT mix reset to (1 - w, w) each January (or every month)."""
    sub = r.loc[start:END, ["BND", "VCIT"]]
    out, hold = [], None
    for m, row in sub.iterrows():
        if hold is None or monthly or m.endswith("-01"):
            hold = np.array([1 - w, w])
        gross = hold * (1 + row.to_numpy())
        out.append(gross.sum() / hold.sum() - 1)
        hold = gross
    return pd.Series(out, index=sub.index)


def period_of(path: str) -> str:
    return Path(path).name.split("_")[-1].removesuffix(".csv.gz")


def first_file(ticker: str, which: str) -> str:
    files = sorted(glob.glob(str(DATA / f"holdings_{ticker}_*.csv.gz")))
    return files[0] if which == "first" else files[-1]


def file_on_or_before(ticker: str, period: str) -> str:
    files = sorted(glob.glob(str(DATA / f"holdings_{ticker}_*.csv.gz")))
    ok = [f for f in files if period_of(f) <= period]
    return ok[-1]


def main() -> None:
    OUT.mkdir(exist_ok=True)
    results: dict = {}
    lines: list[str] = []

    def p(s: str = "") -> None:
        print(s)
        lines.append(s)

    # A. Holdings mix
    p("A. Holdings mix, % of net assets (latest public N-PORT-P)")
    results["mix"] = {}
    for t in ("AGG", "BND", "DFCF", "AVIG"):
        d, hdr = holdings(first_file(t, "last"))
        period = period_of(first_file(t, "last"))
        m = mix(d)
        results["mix"][t] = {"period": period, "buckets": m, "corporate": round(corp_share(d), 2)}
        p(f"  {t} {period}: " + ", ".join(f"{k} {v}" for k, v in m.items()))

    # B. Concentration
    p()
    p("B. Corporate issuer concentration (corporate and REIT debt, by LEI)")
    results["concentration"] = {}
    for t in ("AGG", "BND"):
        d, _ = holdings(first_file(t, "last"))
        c = concentration(d)
        c["period"] = period_of(first_file(t, "last"))
        results["concentration"][t] = c
        p(
            f"  {t} {c['period']}: Treasury {c['treasury_pct']}%, corporate {c['corporate_pct']}% "
            f"in {c['issuers']} issuers ({c['positions']} bonds); largest {c['largest']['issuer']} "
            f"{c['largest']['pct']}%; top 10 {c['top10_pct']}%, top 25 {c['top25_pct']}%, "
            f"top 50 {c['top50_pct']}%; effective issuers {c['effective_issuers']:.0f}; "
            f"largest single bond {c['largest_position_pct']}%"
        )
        p("    top 10: " + "; ".join(f"{x['issuer']} {x['pct']}" for x in c["top10"]))

    # C-D. Returns and regressions
    prices = pd.read_csv(DATA / "monthly_prices.csv", index_col=0)
    r = prices.pct_change(fill_method=None)
    factors = {
        "main": pd.DataFrame({"term": r.IEF - r.BIL, "credit": r.SPIB - r.IEI}),
        "lqd": pd.DataFrame({"term": r.IEF - r.BIL, "credit": r.LQD - r.IEF}),
    }
    p()
    p("C-D. Systematic fund vs index fund (monthly, market-price total returns)")
    results["pairs"] = {}
    for fund, idx, start in PAIRS:
        sub = r.loc[start:END]
        res = compare(sub[fund], sub[idx], factors)
        results["pairs"][f"{fund}-{idx}"] = res
        rm, rl = res["regression_main"], res["regression_lqd"]
        p(
            f"  {fund} vs {idx} {res['start']} to {res['end']} ({res['months']} mo): "
            f"CAGR {res['fund']['cagr']:.2f} vs {res['index']['cagr']:.2f} (gap {res['cagr_gap']:+.2f}); "
            f"vol {res['fund']['vol']:.2f} vs {res['index']['vol']:.2f}; "
            f"max DD {res['fund']['max_dd']:.1f} vs {res['index']['max_dd']:.1f}; "
            f"TE {res['tracking_error']:.2f}; beta {res['beta']:.2f}; active t {res['active_t']:.2f}"
        )
        p(
            f"    SPIB-IEI model: alpha {rm['alpha_pct_yr']:+.2f}%/yr (t {rm['alpha_t']:.2f}, NW{rm['nw_lags']} {rm['alpha_t_nw']:.2f}); "
            f"credit {rm['beta_credit']:.3f} (NW t {rm['t_nw_credit']:.1f}); term {rm['beta_term']:.3f} (NW t {rm['t_nw_term']:.1f}); "
            f"R2 {rm['r2']:.2f}; residual TE {rm['residual_te']:.2f}"
        )
        p(
            f"    LQD-IEF model:  alpha {rl['alpha_pct_yr']:+.2f}%/yr (NW t {rl['alpha_t_nw']:.2f}); "
            f"credit {rl['beta_credit']:.3f} (NW t {rl['t_nw_credit']:.1f}); term {rl['beta_term']:.3f} (NW t {rl['t_nw_term']:.1f}); R2 {rl['r2']:.2f}"
        )
        p("    years to t=1.96 at this TE: " + ", ".join(f"{k}%/yr edge {v:.0f}" for k, v in res["years_to_t2"].items()))

    # Calendar-year returns
    p()
    p("Calendar-year market-price total returns, %")
    cal = {}
    for t in ("AGG", "BND", "AVIG", "DFCF", "DFAPX", "VBTLX"):
        yr = (1 + r[t]).groupby(r.index.str[:4]).prod() - 1
        counts = r[t].dropna().groupby(r[t].dropna().index.str[:4]).size()
        cal[t] = {y: round(100 * float(v), 2) for y, v in yr.items() if y >= "2021" and counts.get(y, 0) == (10 if y == "2026" else 12)}
    results["calendar"] = cal
    for t, v in cal.items():
        p(f"  {t}: " + ", ".join(f"{y} {x:+.2f}" for y, x in v.items()) + " (2026 = Jan-Oct)")

    # E. Static replica
    p()
    p("E. Static replica: BND + VCIT matched to each fund's first-filing corporate share")
    results["replica"] = {}
    for fund, start in (("AVIG", "2020-11"), ("DFCF", "2021-12")):
        f0 = first_file(fund, "first")
        period = period_of(f0)
        c_fund = corp_share(holdings(f0)[0])
        f_bnd = file_on_or_before("BND", period)
        f_vcit = file_on_or_before("VCIT", period)
        c_bnd = corp_share(holdings(f_bnd)[0])
        c_vcit = corp_share(holdings(f_vcit)[0])
        w = (c_fund - c_bnd) / (c_vcit - c_bnd)
        rep = replica_returns(r, w, start)
        res = compare(r.loc[start:END, fund], rep, factors)
        res.update(
            {
                "weight_vcit": w,
                "fund_corporate": c_fund,
                "bnd_corporate": c_bnd,
                "vcit_corporate": c_vcit,
                "fund_filing": period,
                "bnd_filing": period_of(f_bnd),
                "vcit_filing": period_of(f_vcit),
            }
        )
        # Sensitivity (not the pre-set test): monthly rebalancing, and the
        # weight implied by the fund's latest filing, which uses information
        # from the end of the window.
        sens = {}
        rep_m = replica_returns(r, w, start, monthly=True)
        sens["monthly_rebalance_gap"] = compare(r.loc[start:END, fund], rep_m, {})["cagr_gap"]
        c_last = corp_share(holdings(first_file(fund, "last"))[0])
        c_bnd_last = corp_share(holdings(first_file("BND", "last"))[0])
        w_last = (c_last - c_bnd_last) / (c_vcit - c_bnd_last)
        rep_l = replica_returns(r, w_last, start)
        sens["latest_weight"] = w_last
        sens["latest_weight_gap"] = compare(r.loc[start:END, fund], rep_l, {})["cagr_gap"]
        res["sensitivity"] = sens
        results["replica"][fund] = res
        rm = res["regression_main"]
        p(
            f"  {fund}: corporate {c_fund:.2f}% ({period}); BND {c_bnd:.2f}% ({res['bnd_filing']}), "
            f"VCIT {c_vcit:.2f}% ({res['vcit_filing']}) -> VCIT weight {w:.3f}"
        )
        p(
            f"    {res['start']} to {res['end']} ({res['months']} mo): CAGR fund {res['fund']['cagr']:.2f} vs replica "
            f"{res['index']['cagr']:.2f} (gap {res['cagr_gap']:+.2f}); vol {res['fund']['vol']:.2f} vs {res['index']['vol']:.2f}; "
            f"max DD {res['fund']['max_dd']:.1f} vs {res['index']['max_dd']:.1f}; TE {res['tracking_error']:.2f}; active t {res['active_t']:.2f}"
        )
        p(
            f"    SPIB-IEI model on fund minus replica: alpha {rm['alpha_pct_yr']:+.2f}%/yr (NW t {rm['alpha_t_nw']:.2f}); "
            f"credit {rm['beta_credit']:.3f} (NW t {rm['t_nw_credit']:.1f}); term {rm['beta_term']:.3f} (NW t {rm['t_nw_term']:.1f}); R2 {rm['r2']:.2f}"
        )
        p(
            f"    sensitivity: monthly rebalancing gap {sens['monthly_rebalance_gap']:+.2f}; "
            f"latest-filing weight {sens['latest_weight']:.3f} gap {sens['latest_weight_gap']:+.2f}"
        )

    # Compact file for the guide
    guide = {
        "asOf": END,
        "mix": results["mix"],
        "concentration": {
            t: {k: v for k, v in c.items() if k != "top10"} | {"top10": c["top10"]}
            for t, c in results["concentration"].items()
        },
        "pairs": {
            k: {
                "start": v["start"],
                "end": v["end"],
                "months": v["months"],
                "fundCagr": round(v["fund"]["cagr"], 2),
                "indexCagr": round(v["index"]["cagr"], 2),
                "cagrGap": round(v["cagr_gap"], 2),
                "fundVol": round(v["fund"]["vol"], 2),
                "indexVol": round(v["index"]["vol"], 2),
                "fundMaxDd": round(v["fund"]["max_dd"], 1),
                "indexMaxDd": round(v["index"]["max_dd"], 1),
                "te": round(v["tracking_error"], 2),
                "activeT": round(v["active_t"], 2),
                "alpha": round(v["regression_main"]["alpha_pct_yr"], 2),
                "alphaT": round(v["regression_main"]["alpha_t_nw"], 2),
                "credit": round(v["regression_main"]["beta_credit"], 3),
                "creditT": round(v["regression_main"]["t_nw_credit"], 1),
                "term": round(v["regression_main"]["beta_term"], 3),
                "termT": round(v["regression_main"]["t_nw_term"], 1),
                "r2": round(v["regression_main"]["r2"], 2),
            }
            for k, v in results["pairs"].items()
        },
        "replica": {
            k: {
                "weightVcit": round(v["weight_vcit"], 3),
                "fundCorporate": round(v["fund_corporate"], 2),
                "fundFiling": v["fund_filing"],
                "start": v["start"],
                "end": v["end"],
                "months": v["months"],
                "fundCagr": round(v["fund"]["cagr"], 2),
                "replicaCagr": round(v["index"]["cagr"], 2),
                "cagrGap": round(v["cagr_gap"], 2),
                "fundMaxDd": round(v["fund"]["max_dd"], 1),
                "replicaMaxDd": round(v["index"]["max_dd"], 1),
                "fundVol": round(v["fund"]["vol"], 2),
                "replicaVol": round(v["index"]["vol"], 2),
                "te": round(v["tracking_error"], 2),
                "activeT": round(v["active_t"], 2),
                "alpha": round(v["regression_main"]["alpha_pct_yr"], 2),
                "alphaT": round(v["regression_main"]["alpha_t_nw"], 2),
            }
            for k, v in results["replica"].items()
        },
        "calendar": results["calendar"],
    }
    (OUT / "results.json").write_text(json.dumps(results, indent=2, default=float))
    (OUT / "should-you-index-bonds.json").write_text(json.dumps(guide, indent=2))
    (OUT / "output.txt").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
