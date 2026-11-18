"""Did holding the tech sector from the dot-com peak eventually pay off?

Tests the claim in Jeff Yass's Nov 6, 2026 WSJ op-ed that investors who held the
whole internet sector long enough came out ahead. Prints every figure quoted in
the Summitward guide https://summitward.com/learn/does-a-crash-prove-a-bubble
and writes results.json next to this script.

Data (all in data/):
  5_Industry_Portfolios.csv     Ken French Data Library, built from the 202609
                                CRSP database. HiTec = Business Equipment,
                                Telephone and Television Transmission (SIC codes
                                in Siccodes5.txt). Value- and equal-weighted.
  F-F_Research_Data_Factors.csv Same CRSP cut. Market = Mkt-RF + RF; T-bills = RF.
  cpi_u_nsa.json                BLS CPI-U, U.S. city average, all items, not
                                seasonally adjusted (series CUUR0000SA0), from
                                the BLS public API. October 2025 was never
                                published (2025 lapse in appropriations); it is
                                filled with the geometric mean of Sep and Nov 2025.

HiTec is broader than "internet stocks": it holds hardware, software, chips and
telecom carriers, while most e-commerce firms (SIC 5000-5999) sit in Cnsmr.
French's page does not document delisting treatment. Research portfolios carry
no fees, trading costs or taxes.

Entry dates are fixed in advance: invest at the close of Dec 1998, Dec 1999,
Mar 2000 (the HiTec value-weighted peak month-end) and Dec 2000. The window ends
Sep 2026, the last month in the 202609 files.

    python3 analyze.py
"""

import csv
import json
import math
from pathlib import Path

HERE = Path(__file__).parent
DATA = HERE / "data"
END = "202609"
ENTRIES = {"Dec 1998": "199812", "Dec 1999": "199912", "Mar 2000": "200003", "Dec 2000": "200012"}


def read_block(path, header):
    """Monthly block starting at a title line -> {yyyymm: {col: decimal return}}."""
    lines = path.read_text(errors="ignore").splitlines()
    start = next(i for i, ln in enumerate(lines) if ln.strip().startswith(header.strip()))
    if not lines[start].startswith(","):
        start += 1
    cols = [c.strip() for c in lines[start].split(",")][1:]
    out = {}
    for row in csv.reader(lines[start + 1 :]):
        key = row[0].strip() if row else ""
        if len(key) != 6 or not key.isdigit():
            break
        vals = [float(v) for v in row[1:]]
        if any(v <= -99.99 for v in vals):
            raise ValueError(f"missing value in {path.name} {key}")
        out[key] = {c: v / 100 for c, v in zip(cols, vals)}
    return out


vw = read_block(DATA / "5_Industry_Portfolios.csv", "Average Value Weighted Returns -- Monthly")
ew = read_block(DATA / "5_Industry_Portfolios.csv", "Average Equal Weighted Returns -- Monthly")
ff = read_block(DATA / "F-F_Research_Data_Factors.csv", ",Mkt-RF")  # first block is monthly
cpi = {k: float(v) for k, v in json.loads((DATA / "cpi_u_nsa.json").read_text()).items()}
cpi["202510"] = math.sqrt(cpi["202509"] * cpi["202511"])

months = sorted(m for m in set(vw) & set(ew) & set(ff) if m <= END)
assert months[-1] == END, months[-1]
RET = {
    "hitec_vw": {m: vw[m]["HiTec"] for m in months},
    "hitec_ew": {m: ew[m]["HiTec"] for m in months},
    "market": {m: ff[m]["Mkt-RF"] + ff[m]["RF"] for m in months},
    "tbill": {m: ff[m]["RF"] for m in months},
}


def wealth_path(key, entry):
    """[(yyyymm, wealth)] for $1 invested at the close of `entry`, starting at 1."""
    path, w = [(entry, 1.0)], 1.0
    for m in months:
        if entry < m <= END:
            w *= 1 + RET[key][m]
            path.append((m, w))
    return path


def label(m):
    return f"{['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][int(m[4:]) - 1]} {m[:4]}"


def months_between(a, b):
    return (int(b[:4]) - int(a[:4])) * 12 + int(b[4:]) - int(a[4:])


def recovery(ratio_path):
    """Recovery dates for a path that starts at 1 (wealth, real wealth, or a
    wealth ratio against T-bills or the market). "first_back" is the first
    month-end at or above 1 after the first dip below it, which can come before
    the peak for entries ahead of Mar 2000, so the guide quotes
    "durably_above_from": the month after the last month-end below 1."""
    below = [m for m, r in ratio_path[1:] if r < 1]
    if not below:
        return {"ever_below": False}
    first_dip = below[0]
    first_back = next((m for m, r in ratio_path if m > first_dip and r >= 1), None)
    last_below = below[-1]
    ends_above = ratio_path[-1][1] >= 1
    after_last = next((m for m, _ in ratio_path if m > last_below), None) if ends_above else None
    return {
        "ever_below": True,
        "first_back": first_back and label(first_back),
        "years_to_first_back": first_back and round(months_between(ratio_path[0][0], first_back) / 12, 1),
        "last_below": label(last_below),
        "durably_above_from": after_last and label(after_last),
        "years_to_durably_above": after_last and round(months_between(ratio_path[0][0], after_last) / 12, 1),
        "ends_above": ends_above,
    }


def summarize(key, entry):
    p = wealth_path(key, entry)
    t = dict(wealth_path("tbill", entry))
    mk = dict(wealth_path("market", entry))
    real = [(m, w * cpi[entry] / cpi[m]) for m, w in p]
    vs_t = [(m, w / t[m]) for m, w in p]
    vs_m = [(m, w / mk[m]) for m, w in p]
    years = months_between(entry, END) / 12
    peak, mdd, trough = 1.0, 0.0, entry
    for m, w in p:
        peak = max(peak, w)
        if w / peak - 1 < mdd:
            mdd, trough = w / peak - 1, m
    end_w, end_real = p[-1][1], real[-1][1]
    return {
        "entry": label(entry),
        "years": round(years, 2),
        "end_wealth": round(end_w, 3),
        "cagr": round(end_w ** (1 / years) - 1, 4),
        "real_end_wealth": round(end_real, 3),
        "real_cagr": round(end_real ** (1 / years) - 1, 4),
        "max_drawdown": round(mdd, 4),
        "trough": label(trough),
        "nominal_recovery": recovery(p),
        "real_recovery": recovery(real),
        "vs_tbills_end_ratio": round(vs_t[-1][1], 3),
        "vs_tbills_recovery": recovery(vs_t),
        "vs_market_end_ratio": round(vs_m[-1][1], 3),
        "vs_market_recovery": recovery(vs_m),
        "min_vs_market": round(min(r for _, r in vs_m), 3),
    }


results = {"end": label(END), "entries": {}}
for name, entry in ENTRIES.items():
    results["entries"][name] = {k: summarize(k, entry) for k in ("hitec_vw", "hitec_ew", "market")}

# Sanity check that the series are total returns: full-history annualized returns.
full = {}
for k in ("hitec_vw", "market", "tbill"):
    w = math.prod(1 + RET[k][m] for m in months if "192607" <= m <= "202512")
    full[k] = round(w ** (1 / ((months_between("192606", "202512")) / 12)) - 1, 4)
results["full_history_cagr_1926_07_to_2025_12"] = full

# Chart: growth of $1 from the close of Mar 2000, quarter-ends plus the final month.
chart_entry = "200003"
paths = {k: dict(wealth_path(k, chart_entry)) for k in ("hitec_vw", "market", "tbill")}
chart = []
for m in sorted(paths["hitec_vw"]):
    if m[4:] in ("03", "06", "09", "12") or m == END:
        row = {"m": m}
        for k in paths:
            row[k] = round(paths[k][m], 4)
        row["hitec_vw_real"] = round(paths["hitec_vw"][m] * cpi[chart_entry] / cpi[m], 4)
        chart.append(row)
results["chart_from_mar_2000"] = chart

(HERE / "results.json").write_text(json.dumps(results, indent=1) + "\n")

pct = lambda x: f"{x * 100:+.1f}%"  # noqa: E731
print(f"Window ends {results['end']}. Full-history CAGR Jul 1926-Dec 2025: {full}")
for name, block in results["entries"].items():
    print(f"\n=== Entry at close of {name} ===")
    for k, s in block.items():
        nr, rr, tr, mr = (s["nominal_recovery"], s["real_recovery"], s["vs_tbills_recovery"], s["vs_market_recovery"])
        print(
            f"{k:9s} $1 -> {s['end_wealth']:.2f} ({pct(s['cagr'])}/yr), real {s['real_end_wealth']:.2f} "
            f"({pct(s['real_cagr'])}/yr); maxDD {pct(s['max_drawdown'])} at {s['trough']}"
        )
        for tag, r in (("nominal", nr), ("real", rr), ("vs T-bills", tr), ("vs market", mr)):
            if not r["ever_below"]:
                print(f"    {tag:10s}: never below the starting line")
            elif not r["ends_above"]:
                print(f"    {tag:10s}: still below at {results['end']}")
            else:
                print(
                    f"    {tag:10s}: last month-end below {r['last_below']}; above for good from "
                    f"{r['durably_above_from']} ({r['years_to_durably_above']}y after entry)"
                )
        print(f"    end ratio vs T-bills {s['vs_tbills_end_ratio']}, vs market {s['vs_market_end_ratio']} "
              f"(low {s['min_vs_market']})")
