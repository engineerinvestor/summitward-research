"""Look-through comparison of AVUC with AVUS, plus AVNC and AVTM composition.

Every input is a holdings file dated 2026-11-09 (see README), so no repricing
is needed. Prints the report the guide quotes and writes out/results.json.

Definitions
- Weights are shares of total market value. "Equity weights" drop cash,
  T-bill funds and ETF lines, then rescale the remaining stocks to sum to one.
- Issuers are keyed by the first six CUSIP characters, so share classes
  (GOOGL/GOOG, FOXA/FOX) collapse. iShares files carry no CUSIP, so their
  tickers are mapped to CUSIPs through the Avantis and State Street files;
  unmapped tickers stay keyed by ticker.
- Overlap(A, B) = sum over issuers of min(wA, wB). Active share = 1 - overlap.
- Look-through expands an ETF position into that ETF's own stock weights.
  ETFs without a holdings file stay unexpanded; the report prints their share.
- "Russell value share" applies to Russell 1000 stocks only. Each stock's
  market cap splits between the Russell 1000 Value and Growth indexes, so
  w_IWB = a * w_IWD + (1 - a) * w_IWF, where a is value's share of index cap.
  a is fitted by least squares across stocks; a stock's value fraction is
  a * w_IWD / w_IWB. A fund's value share is its weight-averaged value
  fraction. The index itself scores a by construction.

Usage:
    python3 analyze.py
"""

import csv
import json
import re
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
OUT = HERE / "out"
DATE = "2026-11-09"

ETF_TYPES = {
    "MANAGED INVESTMENT COMPANIES",
    "UNIT INVESTMENT TRUSTS- ETF",
    "MANAGED BOND INVESTMENT COMPANIES",
}
STOCK_TYPES = {
    "COMMON STOCK",
    "FOREIGN ADR COMMON (DTC ELIGIBLE)",
    "FOREIGN COMMON STOCK",
    "FOREIGN COMMON STOCK (USD)",
    "OTHER FOREIGN SECURITIES",
    "REIT",
}
# Style buckets for AVUC's contributed ETFs (hand-assigned from fund names).
BUCKET = {
    "Growth": "IWF IWO VUG MGK VBK VOT IVW QQQ QQQM",
    "Value": "IWD VTV VIOV VBR VOE IWN IVE",
    "Broad market": "IVV IWB OEF SPY VTI VO IJH VB VXF IJR VTHR IWC IWM DIA VOO AVUS AAUS",
    "Sector or theme": (
        "IYW SMH XLK SOXX GDX VHT XLC XLY VGT ITA PHO VNQ VDE XAR PPA XLF NLR "
        "IGV PUI VFH IGF XLB XLV XLI XLE XLP"
    ),
    "Dividend": "VYM FDVV VIG",
    "Other factor or rules-based": "AVUQ AVUV AIVL FNDA RSP",
    "International": "SPEM EWU",
    "T-bills": "SGOV",
}
BUCKET_OF = {t: b for b, ts in BUCKET.items() for t in ts.split()}
SPONSORS = [
    ("ISHARES", "iShares"),
    ("VANGUARD", "Vanguard"),
    ("STATE STREET", "State Street"),
    ("SPDR", "State Street"),
    ("INVESCO", "Invesco"),
    ("AVANTIS", "Avantis"),
    ("VANECK", "VanEck"),
    ("WISDOMTREE", "WisdomTree"),
    ("ALPHA ARCHITECT", "Alpha Architect"),
    ("SCHWAB", "Schwab"),
    ("FIDELITY", "Fidelity"),
    ("FRANKLIN", "Franklin"),
    ("GOLDMAN", "Goldman Sachs"),
    ("DIMENSIONAL", "Dimensional"),
]


def norm(t) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(t).upper())


def sponsor(name: str) -> str:
    up = name.upper()
    return next((label for key, label in SPONSORS if key in up), "Other")


def load_avantis(ticker: str) -> pd.DataFrame:
    df = pd.read_csv(DATA / f"{ticker}_{DATE}.csv", dtype=str, keep_default_na=False)
    df["mv"] = pd.to_numeric(df["baseMarketValue"], errors="coerce").fillna(0.0)
    df["w"] = df["mv"] / df["mv"].sum()
    return df


def load_ishares(ticker: str) -> pd.DataFrame:
    lines = (DATA / f"ishares_{ticker}.csv").read_text(encoding="utf-8").splitlines()
    head = next(i for i, ln in enumerate(lines) if ln.startswith("Ticker,"))
    rows = []
    for r in csv.DictReader(lines[head:]):
        if r.get("Asset Class") != "Equity":
            continue
        if r.get("Exchange", "").startswith("NO MARKET"):
            continue  # unlisted stubs
        mv = float(r["Market Value"].replace(",", "") or 0)
        rows.append({"ticker": r["Ticker"], "name": r["Name"], "mv": mv})
    df = pd.DataFrame(rows)
    df["w"] = df["mv"] / df["mv"].sum()
    return df


def load_ssga(ticker: str) -> pd.DataFrame:
    raw = pd.read_excel(DATA / f"ssga_{ticker}.xlsx", header=None, engine="openpyxl")
    head = raw.index[raw[0].astype(str).str.strip().eq("Name")][0]
    df = raw.iloc[head + 1 :, :5].copy()
    df.columns = ["name", "ticker", "cusip", "sedol", "weight"]
    df = df[pd.to_numeric(df["weight"], errors="coerce").notna()]
    df = df[df["ticker"].astype(str).str.strip().ne("-")]
    df["w"] = df["weight"].astype(float)
    df["w"] = df["w"] / df["w"].sum()
    return df


# ---------------------------------------------------------------- keys
AV = {
    t: load_avantis(t) for t in ["AVUC", "AVUS", "AVNC", "AVTM", "AVDE", "AVEM", "AVUQ"]
}
SS = {t: load_ssga(t) for t in ["XLY", "SPY"]}
ISH_LIST = ["IWF", "IWD", "IWB", "IVV", "OEF", "IYW", "IWO", "SOXX", "IJH", "IWV"]
ISH = {t: load_ishares(t) for t in ISH_LIST}

CUSIP_OF: dict[str, str] = {}
# Build the ticker map from U.S. listings only. The international funds and
# foreign ordinary shares carry local tickers that collide with U.S. ones
# (Deutsche Telekom trades as "DTE" in Frankfurt; DTE Energy is DTE in New York).
_US_LISTED = [
    df[df["securityType"].ne("FOREIGN COMMON STOCK")]
    for t, df in AV.items()
    if t in ("AVUS", "AVUC", "AVTM", "AVUQ")
]
for df in list(SS.values()) + _US_LISTED:
    for t, c in zip(df["ticker"], df["cusip"], strict=True):
        if isinstance(c, str) and len(c) >= 6 and norm(t):
            CUSIP_OF.setdefault(norm(t), c[:6])


def issuer(ticker, cusip=None) -> str:
    if isinstance(cusip, str) and len(cusip) >= 6:
        return cusip[:6]
    return CUSIP_OF.get(norm(ticker), "T:" + norm(ticker))


NAME_OF: dict[str, str] = {}


def stock_weights(df: pd.DataFrame, has_type: bool) -> dict[str, float]:
    """Issuer -> weight within df's stocks (sums to one)."""
    out: dict[str, float] = defaultdict(float)
    sel = df[df["securityType"].isin(STOCK_TYPES)] if has_type else df
    total = sel["w"].sum()
    for _, r in sel.iterrows():
        k = issuer(r["ticker"], r.get("cusip"))
        out[k] += r["w"] / total
        NAME_OF.setdefault(k, str(r["name"])[:34])
    return dict(out)


HOLDINGS = {}  # ETF ticker -> issuer weights, for look-through
for t, df in ISH.items():
    HOLDINGS[t] = stock_weights(df, has_type=False)
for t, df in SS.items():
    HOLDINGS[t] = stock_weights(df, has_type=False)
for t in ["AVUS", "AVUQ"]:
    HOLDINGS[t] = stock_weights(AV[t], has_type=True)


def overlap(a: dict, b: dict) -> float:
    return sum(min(w, b.get(k, 0.0)) for k, w in a.items())


def look_through(df: pd.DataFrame) -> tuple[dict, float, float, list]:
    """Direct stocks plus expanded ETFs. Returns weights (renormalized over the
    covered part), the expanded ETF share, the unexpanded ETF share, and the
    list of unexpanded positions."""
    agg: dict[str, float] = defaultdict(float)
    expanded = unexpanded = 0.0
    missing = []
    for _, r in df.iterrows():
        typ, w = r["securityType"], r["w"]
        if typ in STOCK_TYPES:
            k = issuer(r["ticker"], r["cusip"])
            agg[k] += w
            NAME_OF.setdefault(k, r["name"][:34])
        elif typ in ETF_TYPES:
            if r["ticker"] in HOLDINGS:
                expanded += w
                for k, wk in HOLDINGS[r["ticker"]].items():
                    agg[k] += w * wk
            elif r["ticker"] != "SGOV":
                unexpanded += w
                missing.append((r["ticker"], w))
    total = sum(agg.values())
    return {k: v / total for k, v in agg.items()}, expanded, unexpanded, missing


def look_through_raw(df: pd.DataFrame) -> tuple[dict, float]:
    """Unrescaled look-through weights (shares of the whole fund) and the
    unexpanded ETF share, for bounding what the unexpanded lines could change."""
    agg: dict[str, float] = defaultdict(float)
    unexpanded = 0.0
    for _, r in df.iterrows():
        typ, w = r["securityType"], r["w"]
        if typ in STOCK_TYPES:
            agg[issuer(r["ticker"], r["cusip"])] += w
        elif typ in ETF_TYPES:
            if r["ticker"] in HOLDINGS:
                for k, wk in HOLDINGS[r["ticker"]].items():
                    agg[k] += w * wk
            elif r["ticker"] != "SGOV":
                unexpanded += w
    return dict(agg), unexpanded


def bottom_band(weights: dict, bench: dict, share: float = 0.9) -> float:
    """Weight in the benchmark's smallest issuers making up its last 1 - share."""
    order = sorted(bench.items(), key=lambda kv: -kv[1])
    small, cum = set(), 0.0
    for k, w in order:
        if cum >= share:
            small.add(k)
        cum += w
    return sum(w for k, w in weights.items() if k in small)


def size_buckets(weights: dict, bench: dict) -> dict:
    """Shares in the largest issuers making up 50% of the benchmark's cap, the
    next 40%, the last 10%, and names outside the benchmark."""
    order = sorted(bench.items(), key=lambda kv: -kv[1])
    band, cum = {}, 0.0
    for k, w in order:
        band[k] = (
            "top 50%" if cum < 0.5 else ("next 40%" if cum < 0.9 else "bottom 10%")
        )
        cum += w
    out = defaultdict(float)
    for k, w in weights.items():
        out[band.get(k, "not in Russell 3000 proxy")] += w
    return {
        b: round(float(out[b]) * 100, 2)
        for b in ["top 50%", "next 40%", "bottom 10%", "not in Russell 3000 proxy"]
    }


def value_fractions() -> tuple[dict, float, float]:
    b, v, g = HOLDINGS["IWB"], HOLDINGS["IWD"], HOLDINGS["IWF"]
    keys = sorted(b)
    y = np.array([b[k] for k in keys])
    xv = np.array([v.get(k, 0.0) for k in keys])
    xg = np.array([g.get(k, 0.0) for k in keys])
    # y - xg = a * (xv - xg)
    d = xv - xg
    a = float(np.dot(d, y - xg) / np.dot(d, d))
    fit = a * xv + (1 - a) * xg
    r2 = 1 - np.sum((y - fit) ** 2) / np.sum((y - y.mean()) ** 2)
    frac = {}
    for k in keys:
        den = a * v.get(k, 0.0) + (1 - a) * g.get(k, 0.0)
        if den > 0:
            frac[k] = a * v.get(k, 0.0) / den
    return frac, a, float(r2)


def value_share(weights: dict, frac: dict) -> tuple[float, float]:
    inside = {k: w for k, w in weights.items() if k in frac}
    tot = sum(inside.values())
    return sum(w * frac[k] for k, w in inside.items()) / tot, tot


def pct(x: float, nd: int = 2) -> float:
    return round(float(x) * 100, nd)


def main() -> None:
    OUT.mkdir(exist_ok=True)
    res: dict = {"as_of": DATE}
    avuc, avus = AV["AVUC"], AV["AVUS"]

    # ------------------------------------------------ AVUC composition
    print(f"Holdings files dated {DATE}\n")
    comp = defaultdict(float)
    for _, r in avuc.iterrows():
        typ = r["securityType"]
        kind = (
            "ETF"
            if typ in ETF_TYPES
            else "stock"
            if typ in STOCK_TYPES
            else "cash/other"
        )
        comp[kind] += r["w"]
    etfs = avuc[avuc["securityType"].isin(ETF_TYPES)].copy()
    etfs["bucket"] = etfs["ticker"].map(BUCKET_OF).fillna("UNASSIGNED")
    etfs["sponsor"] = etfs["name"].map(sponsor)
    by_bucket = etfs.groupby("bucket")["w"].sum().sort_values(ascending=False)
    by_sponsor = etfs.groupby("sponsor")["w"].sum().sort_values(ascending=False)
    nonus = avuc[
        (avuc["securityType"].isin(STOCK_TYPES)) & (avuc["country"] != "UNITED STATES")
    ]
    print("AVUC composition (% of market value)")
    print(
        f"  AUM ${avuc['mv'].sum():,.0f}; {len(avuc)} lines; {len(etfs)} ETF positions"
    )
    for k in ["stock", "ETF", "cash/other"]:
        print(f"  {k:10s} {pct(comp[k]):6.2f}")
    print("  ETF sleeve by style:")
    for b, w in by_bucket.items():
        print(f"    {b:28s} {pct(w):6.2f}")
    print("  ETF sleeve by sponsor:")
    for s, w in by_sponsor.items():
        print(f"    {s:28s} {pct(w):6.2f}")
    print("  Largest ETF positions:")
    for _, r in etfs.sort_values("w", ascending=False).head(10).iterrows():
        print(f"    {r['ticker']:6s} {pct(r['w'], 3):6.3f}  {r['bucket']}")
    print(
        f"  Non-U.S. stocks (ADRs and foreign shares): {pct(nonus['w'].sum())}% in {len(nonus)} names"
    )
    for _, r in nonus.sort_values("w", ascending=False).head(5).iterrows():
        print(f"    {r['ticker']:6s} {pct(r['w'], 3):6.3f}  {r['name'][:40]}")
    avus_nonus = avus[
        (avus["securityType"].isin(STOCK_TYPES)) & (avus["country"] != "UNITED STATES")
    ]
    print(
        f"  AVUS non-U.S. stocks for comparison: {pct(avus_nonus['w'].sum())}% in {len(avus_nonus)} names\n"
    )
    res["avuc_composition"] = {
        "aum": round(float(avuc["mv"].sum())),
        "lines": int(len(avuc)),
        "etf_positions": int(len(etfs)),
        "stock_pct": pct(comp["stock"]),
        "etf_pct": pct(comp["ETF"]),
        "cash_other_pct": pct(comp["cash/other"]),
        "etf_by_style": {b: pct(w) for b, w in by_bucket.items()},
        "etf_by_sponsor": {s: pct(w) for s, w in by_sponsor.items()},
        "top_etfs": {
            r["ticker"]: pct(r["w"], 3)
            for _, r in etfs.sort_values("w", ascending=False).head(10).iterrows()
        },
        "non_us_stock_pct": pct(nonus["w"].sum()),
        "non_us_stock_names": int(len(nonus)),
        "avus_non_us_stock_pct": pct(avus_nonus["w"].sum()),
    }

    # ------------------------------------------------ overlap and active share
    w_avus = stock_weights(avus, has_type=True)
    w_avuc_direct = stock_weights(avuc, has_type=True)
    w_avuc_lt, exp, unexp, missing = look_through(avuc)
    r3000 = HOLDINGS["IWV"]
    etf_total = comp["ETF"]
    sgov = float(avuc.loc[avuc["ticker"] == "SGOV", "w"].sum())
    print("Look-through coverage of AVUC's ETF sleeve")
    print(
        f"  ETF sleeve {pct(etf_total)}%: expanded {pct(exp)}%, unexpanded {pct(unexp)}%, SGOV {pct(sgov)}%"
    )
    print(
        f"  Expanded share of the non-T-bill sleeve: {pct(exp / (etf_total - sgov), 1)}%"
    )
    print(
        "  Largest unexpanded:",
        ", ".join(
            f"{t} {pct(w, 3)}" for t, w in sorted(missing, key=lambda x: -x[1])[:8]
        ),
    )
    ov = {
        "AVUC direct vs AVUS": overlap(w_avuc_direct, w_avus),
        "AVUC look-through vs AVUS": overlap(w_avuc_lt, w_avus),
        "AVUS vs Russell 3000 (IWV)": overlap(w_avus, r3000),
        "AVUC direct vs Russell 3000 (IWV)": overlap(w_avuc_direct, r3000),
        "AVUC look-through vs Russell 3000 (IWV)": overlap(w_avuc_lt, r3000),
    }
    print("\nOverlap (sum of smaller weights); active share = 100 - overlap")
    for k, v in ov.items():
        print(f"  {k:42s} {pct(v):6.2f}")
    res["coverage"] = {
        "etf_pct": pct(etf_total),
        "expanded_pct": pct(exp),
        "unexpanded_pct": pct(unexp),
        "sgov_pct": pct(sgov),
        "expanded_share_of_non_tbill_sleeve": pct(exp / (etf_total - sgov), 1),
    }
    res["overlap_pct"] = {k: pct(v) for k, v in ov.items()}

    # ------------------------------------------------ largest names
    print("\nLargest issuers: AVUC look-through vs AVUS vs Russell 3000 proxy (%)")
    top = sorted(w_avuc_lt.items(), key=lambda kv: -kv[1])[:15]
    rows = []
    for k, w in top:
        rows.append(
            {
                "issuer": NAME_OF.get(k, k),
                "avuc_look_through": pct(w),
                "avuc_direct_pct_of_fund": pct(
                    w_avuc_direct.get(k, 0.0) * comp["stock"]
                ),
                "avus": pct(w_avus.get(k, 0.0)),
                "russell3000": pct(r3000.get(k, 0.0)),
            }
        )
        print(
            f"  {NAME_OF.get(k, k):34s} {pct(w):6.2f} {pct(w_avus.get(k, 0.0)):6.2f} {pct(r3000.get(k, 0.0)):6.2f}"
        )
    res["top_issuers"] = rows

    diff = {
        k: w_avuc_lt.get(k, 0.0) - w_avus.get(k, 0.0)
        for k in set(w_avuc_lt) | set(w_avus)
    }
    ranked = sorted(diff.items(), key=lambda kv: -kv[1])
    active = []
    print("\nLargest active weights, AVUC look-through minus AVUS (points)")
    for k, d in ranked[:7] + ranked[-3:]:
        active.append(
            {
                "issuer": NAME_OF.get(k, k),
                "avuc_look_through": pct(w_avuc_lt.get(k, 0.0)),
                "avus": pct(w_avus.get(k, 0.0)),
                "difference": pct(d),
                "russell3000": pct(r3000.get(k, 0.0)),
                "avuc_direct_pct_of_fund": pct(
                    w_avuc_direct.get(k, 0.0) * comp["stock"]
                ),
            }
        )
        print(
            f"  {NAME_OF.get(k, k):34s} {pct(d):+6.2f}"
            f"   (held directly: {pct(w_avuc_direct.get(k, 0.0) * comp['stock']):.2f}% of the fund)"
        )
    res["active_weights_vs_avus"] = active
    top10 = lambda wts: pct(sum(sorted(wts.values(), reverse=True)[:10]))  # noqa: E731
    res["top10_concentration"] = {
        "avuc_look_through": top10(w_avuc_lt),
        "avus": top10(w_avus),
        "russell3000": top10(r3000),
    }
    print("  Top-10 issuer concentration:", res["top10_concentration"])

    # ------------------------------------------------ size and value
    sb = {
        "AVUS": size_buckets(w_avus, r3000),
        "AVUC look-through": size_buckets(w_avuc_lt, r3000),
        "AVUC direct": size_buckets(w_avuc_direct, r3000),
        "Russell 3000 proxy": size_buckets(r3000, r3000),
    }
    print("\nSize bands by Russell 3000 cap rank (% of each portfolio)")
    for k, v in sb.items():
        print(f"  {k:20s} {v}")
    res["size_bands"] = sb

    frac, a, r2 = value_fractions()
    vs = {
        "AVUS": value_share(w_avus, frac),
        "AVUC direct": value_share(w_avuc_direct, frac),
        "AVUC look-through": value_share(w_avuc_lt, frac),
        "Russell 1000 (IWB)": value_share(HOLDINGS["IWB"], frac),
    }
    print(
        f"\nRussell value share (Russell 1000 stocks only). Fitted a = {a:.4f}, R^2 = {r2:.5f}"
    )
    pair: dict[str, float] = defaultdict(float)
    for t in ("IWF", "IWD"):
        w = float(avuc.loc[avuc["ticker"] == t, "w"].sum())
        for k, x in HOLDINGS[t].items():
            pair[k] += w * x
    tot_pair = sum(pair.values())
    pair = {k: v / tot_pair for k, v in pair.items()}
    vs["IWF + IWD as AVUC holds them"] = value_share(pair, frac)
    for k, (s, cov) in vs.items():
        print(
            f"  {k:20s} value share {pct(s, 1):5.1f}%   (R1000 stocks are {pct(cov, 1)}% of it)"
        )
    res["russell_value_share"] = {
        "fitted_value_share_of_r1000_cap": round(a, 4),
        "fit_r2": round(r2, 5),
        **{
            k: {"value_share_pct": pct(s, 1), "r1000_coverage_pct": pct(c, 1)}
            for k, (s, c) in vs.items()
        },
    }

    # ------------------------------------------------ bounds for unexpanded ETFs
    # The central look-through figures drop the unexpanded ETF lines and rescale.
    # Here they stay in the denominator (AVUC's equity, excluding T-bills and
    # cash) and are assigned the least and most favorable composition.
    raw, u = look_through_raw(avuc)
    den = sum(raw.values()) + u
    lt = {k: v / den for k, v in raw.items()}
    ov_lo = overlap(lt, w_avus)
    bot_lo = bottom_band(lt, r3000)
    r1k = {k: w for k, w in raw.items() if k in frac}
    r1k_val = sum(w * frac[k] for k, w in r1k.items())
    r1k_tot = sum(r1k.values())
    bounds = {
        "unexpanded_share_of_equity_pct": pct(u / den),
        "overlap_with_avus_pct": [pct(ov_lo), pct(min(ov_lo + u / den, 1.0))],
        "smallest_10pct_band_pct": [pct(bot_lo), pct(bot_lo + u / den)],
        "russell_value_share_pct": [
            pct(r1k_val / (r1k_tot + u), 1),
            pct((r1k_val + u) / (r1k_tot + u), 1),
        ],
    }
    print(
        f"\nBounds if the unexpanded {bounds['unexpanded_share_of_equity_pct']}% "
        "of AVUC's equity held the least or most favorable stocks"
    )
    print(
        f"  Overlap with AVUS            {bounds['overlap_with_avus_pct']} (central {pct(ov['AVUC look-through vs AVUS'])})"
    )
    print(
        f"  Smallest 10% band            {bounds['smallest_10pct_band_pct']} (central {sb['AVUC look-through']['bottom 10%']}; AVUS {sb['AVUS']['bottom 10%']})"
    )
    print(
        f"  Russell value share          {bounds['russell_value_share_pct']} (central {pct(vs['AVUC look-through'][0], 1)}; AVUS {pct(vs['AVUS'][0], 1)})"
    )
    res["bounds_unexpanded"] = bounds

    # ------------------------------------------------ AVNC
    avnc = AV["AVNC"]
    netf = avnc[avnc["securityType"].isin(ETF_TYPES)].copy()
    netf["sponsor"] = netf["name"].map(sponsor)
    us_direct = avnc[
        (avnc["securityType"].isin(STOCK_TYPES)) & (avnc["country"] == "UNITED STATES")
    ]
    us_etf = netf[netf["ticker"].isin(["AAUS", "AAEQ"])]
    print("\nAVNC composition")
    print(
        f"  AUM ${avnc['mv'].sum():,.0f}; ETF sleeve {pct(netf['w'].sum())}% in {len(netf)} positions"
    )
    for _, r in netf.sort_values("w", ascending=False).head(8).iterrows():
        print(f"    {r['ticker']:6s} {pct(r['w'], 3):6.3f}  {r['sponsor']}")
    print(
        f"  By sponsor: { {s: pct(w) for s, w in netf.groupby('sponsor')['w'].sum().sort_values(ascending=False).items()} }"
    )
    print(
        f"  U.S. stocks held directly {pct(us_direct['w'].sum())}% ({len(us_direct)} names) + U.S. equity ETFs {pct(us_etf['w'].sum())}%"
    )
    res["avnc"] = {
        "aum": round(float(avnc["mv"].sum())),
        "etf_pct": pct(netf["w"].sum()),
        "etf_positions": int(len(netf)),
        "top_etfs": {
            r["ticker"]: pct(r["w"], 3)
            for _, r in netf.sort_values("w", ascending=False).head(8).iterrows()
        },
        "etf_by_sponsor": {
            s: pct(w)
            for s, w in netf.groupby("sponsor")["w"]
            .sum()
            .sort_values(ascending=False)
            .items()
        },
        "us_direct_pct": pct(us_direct["w"].sum()),
        "us_direct_names": int(len(us_direct)),
        "us_equity_etf_pct": pct(us_etf["w"].sum()),
    }

    # ------------------------------------------------ AVTM
    avtm = AV["AVTM"]
    country = defaultdict(float)
    tetf = avtm[avtm["securityType"].isin(ETF_TYPES)]
    for _, r in avtm.iterrows():
        if r["securityType"] in STOCK_TYPES:
            country[r["country"]] += r["w"]
        elif r["ticker"] in AV:
            sub = AV[r["ticker"]]
            sub = sub[sub["securityType"].isin(STOCK_TYPES)]
            for c, w in sub.groupby("country")["w"].sum().items():
                country[c] += r["w"] * w / sub["w"].sum()
        elif r["securityType"] in ETF_TYPES:
            country["UNEXPANDED ETF"] += r["w"]
    tot = sum(country.values())
    print("\nAVTM look-through")
    print(
        f"  AUM ${avtm['mv'].sum():,.0f}; Avantis ETF sleeve {pct(tetf['w'].sum())}%:",
        ", ".join(
            f"{t} {pct(w)}"
            for t, w in zip(tetf["ticker"], tetf["w"], strict=True)
            if w > 0.0001
        ),
    )
    us = country["UNITED STATES"] / tot
    print(
        f"  U.S. {pct(us)}%; Japan {pct(country['JAPAN'] / tot)}%; non-U.S. {pct(1 - us)}%"
    )
    res["avtm"] = {
        "aum": round(float(avtm["mv"].sum())),
        "etf_pct": pct(tetf["w"].sum()),
        "etfs": {
            t: pct(w)
            for t, w in zip(tetf["ticker"], tetf["w"], strict=True)
            if w > 0.0001
        },
        "us_pct_look_through": pct(us),
    }

    # ------------------------------------------------ embedded gains (N-CSR)
    print("\nUnrealized gain as a share of investments, Aug 31 2026 (Form N-CSR)")
    res["embedded_gain_pct"] = {}
    with (DATA / "ncsr_2026-08-31_tax_basis.csv").open() as f:
        for r in csv.DictReader(f):
            cost, gain = float(r["federal_tax_cost"]), float(r["net_tax_appreciation"])
            share = gain / (cost + gain)
            res["embedded_gain_pct"][r["fund"]] = pct(share, 1)
            print(
                f"  {r['fund']}: ${gain / 1e6:,.1f}M on ${(cost + gain) / 1e6:,.1f}M = {pct(share, 1)}%"
            )

    # ------------------------------------------------ Sep 30 characteristics
    fs = {}
    with (DATA / "factsheets_2026-09-30.csv").open() as f:
        for r in csv.DictReader(f):
            fs[r["portfolio"]] = {
                k: float(r[k])
                for k in ("mkt_cap_bn", "book_to_market", "profits_to_book")
            }
    blend = {
        k: 0.7 * fs["AVDE"][k] + 0.3 * fs["AVEM"][k]
        for k in ("mkt_cap_bn", "book_to_market", "profits_to_book")
    }
    bench_blend = {
        k: 0.7 * fs["MSCI World ex USA IMI"][k]
        + 0.3 * fs["MSCI Emerging Markets IMI"][k]
        for k in ("book_to_market", "profits_to_book")
    }
    print("\nFact-sheet characteristics, Sep 30 2026 (weighted averages)")
    for name in ("AVNC", "AVNM", "AVDE", "AVEM", "MSCI ACWI ex USA IMI"):
        print(f"  {name:22s} {fs[name]}")
    print(
        f"  70% AVDE + 30% AVEM    B/M {blend['book_to_market']:.3f}, "
        f"profits/book {blend['profits_to_book']:.3f}, mkt cap ${blend['mkt_cap_bn']:.1f}B"
    )
    print(
        f"  70/30 of their benchmarks: B/M {bench_blend['book_to_market']:.3f}, "
        f"profits/book {bench_blend['profits_to_book']:.3f}"
    )
    res["factsheets_2026_09_30"] = {
        **fs,
        "AVDE 70 / AVEM 30": {k: round(v, 3) for k, v in blend.items()},
        "benchmarks 70 / 30": {k: round(v, 3) for k, v in bench_blend.items()},
    }

    # ------------------------------------------------ trading
    print("\nTrading on the Avantis fund pages, Nov 9 2026")
    res["trading_2026_11_09"] = {}
    with (DATA / "trading_2026-11-09.csv").open() as f:
        for r in csv.DictReader(f):
            print(
                f"  {r['ticker']}: 30-day median bid-ask spread {r['median_spread_30d_pct']}%, "
                f"spread {r['spread_pct']}%, volume {int(r['volume']):,}"
            )
            res["trading_2026_11_09"][r["ticker"]] = {
                "median_spread_30d_pct": float(r["median_spread_30d_pct"]),
                "spread_pct": float(r["spread_pct"]),
                "volume": int(r["volume"]),
            }

    (OUT / "results.json").write_text(json.dumps(res, indent=2))
    print("\nwrote out/results.json")


if __name__ == "__main__":
    main()
