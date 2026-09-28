"""Small-cap value vs. small-cap growth, from Ken French's size/book-to-market portfolios.

Reads the monthly value-weighted returns in data/ (Ken French Data Library,
file built from the 202608 CRSP database) and prints every research-portfolio
figure quoted in the Summitward guide
https://summitward.com/learn/small-cap-value-vs-small-cap-growth .
Writes results.json next to this script.

Definitions (Fama-French 2x3 sort: NYSE median size breakpoint, 30th and 70th
NYSE book-to-market percentiles, rebalanced each June):
  small growth = SMALL LoBM, small value = SMALL HiBM,
  large growth = BIG LoBM,   large value = BIG HiBM,
  small = mean of the three small portfolios, big = mean of the three big ones
  (the averages whose difference is SMB), market = Mkt-RF + RF.
The "tiny" corners come from the 5x5 sort: smallest size quintile, lowest
(tiny growth) and highest (tiny value) book-to-market quintile.

Annualized returns are geometric. The full window is calendar 1927-2025.
Research portfolios carry no fees, trading costs or taxes.

The optional --funds flag adds the index-fund comparison, which needs yfinance.

    python3 analyze.py
    python3 analyze.py --funds
"""

import csv
import json
import math
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).parent
DATA = HERE / "data"


def read_block(path, header):
    """Monthly block under a title line (or starting at a column-header line
    beginning with a comma) -> {yyyymm: {col: return}}."""
    lines = path.read_text(errors="ignore").splitlines()
    start = next(i for i, ln in enumerate(lines) if ln.strip().startswith(header.strip()))
    cols = [c.strip() for c in lines[start].split(",")][1:] if header.startswith(",") else None
    if cols is None:
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


VW = "Average Value Weighted Returns -- Monthly"
six = read_block(DATA / "6_Portfolios_2x3.csv", VW)
t25 = read_block(DATA / "25_Portfolios_5x5.csv", VW)
ff = read_block(DATA / "F-F_Research_Data_Factors.csv", ",Mkt-RF")  # first block is monthly

months = sorted(set(six) & set(t25) & set(ff))
S = {
    "small_growth": [six[m]["SMALL LoBM"] for m in months],
    "small_value": [six[m]["SMALL HiBM"] for m in months],
    "large_growth": [six[m]["BIG LoBM"] for m in months],
    "large_value": [six[m]["BIG HiBM"] for m in months],
    "small": [(six[m]["SMALL LoBM"] + six[m]["ME1 BM2"] + six[m]["SMALL HiBM"]) / 3 for m in months],
    "big": [(six[m]["BIG LoBM"] + six[m]["ME2 BM2"] + six[m]["BIG HiBM"]) / 3 for m in months],
    "market": [ff[m]["Mkt-RF"] + ff[m]["RF"] for m in months],
    "tbill": [ff[m]["RF"] for m in months],
    "tiny_growth": [t25[m]["SMALL LoBM"] for m in months],
    "tiny_value": [t25[m]["SMALL HiBM"] for m in months],
}


def window(key, a, b):
    """Returns for months a..b inclusive (yyyymm strings)."""
    return [x for m, x in zip(months, S[key]) if a <= m <= b]


def growth(xs):
    return math.prod(1 + x for x in xs)


def ann(xs):
    return growth(xs) ** (12 / len(xs)) - 1


def vol(xs):
    return statistics.stdev(xs) * math.sqrt(12)


def max_drawdown(xs):
    w, peak, worst = 1.0, 1.0, 0.0
    for x in xs:
        w *= 1 + x
        peak = max(peak, w)
        worst = min(worst, w / peak - 1)
    return worst


def pct(v, d=1):
    return round(100 * v, d)


A, B = "192701", "202512"
full_months = [m for m in months if A <= m <= B]
out = {"data_through": months[-1], "window": "1927-01 to 2025-12", "months": len(full_months), "full": {}}
print(f"Data through {months[-1]}. Full window 1927-2025, {len(full_months)} months")
for k in S:
    xs = window(k, A, B)
    f = {"ann": pct(ann(xs), 2), "vol": pct(vol(xs)), "maxdd": pct(max_drawdown(xs)), "growth_of_1": round(growth(xs))}
    out["full"][k] = f
    print(f"  {k:13s} ann {f['ann']:6.2f}%  vol {f['vol']:5.1f}%  maxDD {f['maxdd']:6.1f}%  $1 -> ${f['growth_of_1']:,}")

print("\nBy decade (annualized %): small value, small growth, spread, small, big, market")
out["decades"] = []
for start in range(1930, 2030, 10):
    end = min(start + 9, 2025)
    a, b = f"{start}01", f"{end}12"
    row = {"label": f"{start}s" if end == start + 9 else f"{start}-{end}"}
    for k in ("small_value", "small_growth", "small", "big", "market"):
        row[k] = pct(ann(window(k, a, b)))
    row["spread"] = round(row["small_value"] - row["small_growth"], 1)
    out["decades"].append(row)
    print(f"  {row['label']:10s} {row['small_value']:6.1f} {row['small_growth']:6.1f} {row['spread']:6.1f} {row['small']:6.1f} {row['big']:6.1f} {row['market']:6.1f}")

print("\nSub-periods (annualized %)")
out["subperiods"] = {}
keys = ("small_value", "small_growth", "market", "small", "big", "tiny_value", "tiny_growth", "tbill")
for a, b in [("1927", "1962"), ("1963", "2025"), ("1990", "2025"), ("2000", "2025"), ("2010", "2025")]:
    s = {k: pct(ann(window(k, a + "01", b + "12"))) for k in keys}
    out["subperiods"][f"{a}-{b}"] = s
    print(f"  {a}-{b}: " + "  ".join(f"{k} {v}" for k, v in s.items()))

ytd = [m for m in months if m >= "202601"]
out["ytd_2026"] = {"through": ytd[-1], **{k: pct(growth(window(k, "202601", ytd[-1])) - 1) for k in ("small_value", "small_growth", "market")}}
print(f"\n2026 through {ytd[-1]}: {out['ytd_2026']}")

print("\nRolling windows (monthly steps): share in which small value beat small growth")
out["rolling"] = {}
lv = [math.log1p(x) for x in window("small_value", A, B)]
lg = [math.log1p(x) for x in window("small_growth", A, B)]
for yrs in (1, 5, 10, 20):
    n = 12 * yrs
    diffs = []
    for i in range(n, len(lv) + 1):
        d = math.exp(sum(lv[i - n : i]) / yrs) - math.exp(sum(lg[i - n : i]) / yrs)
        diffs.append((d, full_months[i - 1]))
    vals = [d for d, _ in diffs]
    worst = min(diffs)
    x = {
        "windows": len(diffs),
        "share_value_won": pct(sum(v > 0 for v in vals) / len(vals)),
        "median_spread": pct(statistics.median(vals)),
        "worst_spread": pct(worst[0]),
        "worst_window_end": worst[1],
        "best_spread": pct(max(vals)),
    }
    out["rolling"][f"{yrs}y"] = x
    print(f"  {yrs:2d}y: {x['windows']} windows, value won {x['share_value_won']}%, median {x['median_spread']}pp, worst {x['worst_spread']}pp (ending {x['worst_window_end']}), best {x['best_spread']}pp")

# Longest stretch the small value / small growth wealth ratio spent below its prior high
ratio, peak, run, run_start, best = 1.0, 1.0, 0, None, (0, None, None)
for m, v, g in zip(full_months, window("small_value", A, B), window("small_growth", A, B)):
    ratio *= (1 + v) / (1 + g)
    if ratio < peak:
        run += 1
        run_start = run_start or m
        if run > best[0]:
            best = (run, run_start, m)
    else:
        peak, run, run_start = ratio, 0, None
out["longest_relative_drawdown"] = {"months": best[0], "from": best[1], "to": best[2]}
print(f"\nLongest stretch with the SV/SG wealth ratio below its prior high: {best[0]} months, {best[1]} to {best[2]}")

years = sorted({m[:4] for m in full_months})
won = sum(
    growth(window("small_value", y + "01", y + "12")) > growth(window("small_growth", y + "01", y + "12")) for y in years
)
out["calendar_years_value_won"], out["calendar_years"] = won, len(years)
print(f"Calendar years small value beat small growth: {won} of {len(years)}")

# Index funds against the research portfolios over matching windows. Fund total
# returns (dividends reinvested, net of expense ratio) from Yahoo Finance
# adjusted closes, month end to month end.
FUND_WINDOWS = [
    ("200008", "202512", ["IWN", "IWO"]),
    ("200402", "202512", ["VBR", "VBK", "IJS", "IJT"]),
    ("201910", "202512", ["AVUV", "VBR", "VBK", "IWN", "IWO"]),
]
if "--funds" in sys.argv:
    import yfinance as yf

    tickers = sorted({t for *_, ts in FUND_WINDOWS for t in ts})
    px = yf.download(tickers, start="2000-07-01", end="2026-01-01", auto_adjust=True, progress=False)["Close"]
    me = px.resample("ME").last()
    fret = {t: {} for t in tickers}
    for t in tickers:
        s = me[t]
        for (d0, p0), (d1, p1) in zip(s.items(), list(s.items())[1:]):
            if p0 == p0 and p1 == p1:  # skip NaN
                fret[t][d1.strftime("%Y%m")] = p1 / p0 - 1
    out["funds"] = []
    print("\nIndex funds vs. research portfolios, same months (annualized %)")
    for a, b, ts in FUND_WINDOWS:
        row = {"window": f"{a[:4]}-{a[4:]} to {b[:4]}-{b[4:]}"}
        row["funds"] = {t: pct(ann([r for m, r in sorted(fret[t].items()) if a <= m <= b]), 2) for t in ts}
        for k in ("small_value", "small_growth", "tiny_growth"):
            row["ff_" + k] = pct(ann(window(k, a, b)), 2)
        out["funds"].append(row)
        print(f"  {row['window']}: {row['funds']}  FF small value {row['ff_small_value']}  small growth {row['ff_small_growth']}  tiny growth {row['ff_tiny_growth']}")
else:
    prior = HERE / "results.json"
    if prior.exists() and "funds" in json.loads(prior.read_text()):
        out["funds"] = json.loads(prior.read_text())["funds"]

(HERE / "results.json").write_text(json.dumps(out, indent=2) + "\n")
print("\nwrote results.json")
