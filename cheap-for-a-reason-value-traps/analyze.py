"""Value traps in Ken French's book-to-market x operating-profitability portfolios.

Reads monthly returns in data/ (Ken French Data Library, files built from the
202608 CRSP database) and prints every research-portfolio figure quoted in the
Summitward guide https://summitward.com/learn/cheap-for-a-reason-value-traps .
Writes results.json next to this script. With --chart PATH it also writes the
year-end growth-of-$1 series the guide's chart reads.

Portfolios (independent sorts at the end of each June, NYSE breakpoints):
  cheap_unprofitable   = 5x5 "HiBM LoOP"  (highest BE/ME quintile, lowest OP quintile)
  cheap_profitable     = 5x5 "HiBM HiOP"
  expensive_profitable = 5x5 "LoBM HiOP"
  expensive_junk       = 5x5 "LoBM LoOP"
  small/big splits     = 2x4x4 ME x BE/ME x OP quartile corners
  market = Mkt-RF + RF, tbill = RF.
OP is operating profits (revenue minus cost of goods sold, SG&A and interest
expense) over book equity. "Low OP" is the bottom quintile or quartile, which
holds low-margin firms as well as money-losers.

Annualized returns are geometric unless labelled arithmetic. Research
portfolios carry no fees, trading costs or taxes, so they are not investable
returns. Standard library only.

    python3 analyze.py
    python3 analyze.py --chart ../path/to/value-trap-corners.json
"""

import csv
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).parent
DATA = HERE / "data"
VW = "Average Value Weighted Returns -- Monthly"
EW = "Average Equal Weighted Returns -- Monthly"
FIRMS = "Number of Firms in Portfolios"


def read_block(path, title, scale=0.01):
    """Monthly block under a title line, or under a column-header line when
    title starts with a comma -> {yyyymm: {col: value}}."""
    lines = path.read_text(errors="ignore").splitlines()
    start = next(i for i, ln in enumerate(lines) if ln.strip().startswith(title.strip()))
    if not title.startswith(","):
        start += 1
    cols = [c.strip() for c in lines[start].split(",")][1:]
    out = {}
    for row in csv.reader(lines[start + 1 :]):
        key = row[0].strip() if row else ""
        if len(key) != 6 or not key.isdigit():
            break
        vals = [float(v) for v in row[1:]]
        if scale and any(v <= -99.99 for v in vals):
            raise ValueError(f"missing value in {path.name} {key}")
        out[key] = {c: v * scale if scale else v for c, v in zip(cols, vals)}
    return out


P25 = DATA / "25_Portfolios_BEME_OP_5x5.csv"
P32 = DATA / "32_Portfolios_ME_BEME_OP_2x4x4.csv"
t25 = read_block(P25, VW)
t25_ew = read_block(P25, EW)
n25 = read_block(P25, FIRMS, scale=None)
t32 = read_block(P32, VW)
n32 = read_block(P32, FIRMS, scale=None)
ff5 = read_block(DATA / "F-F_Research_Data_5_Factors_2x3.csv", ",Mkt-RF")
ff3 = read_block(DATA / "F-F_Research_Data_Factors.csv", ",Mkt-RF")

months = sorted(set(t25) & set(t32) & set(ff5))
LAST = months[-1]

CORNERS = {
    "cheap_unprofitable": "HiBM LoOP",
    "cheap_profitable": "HiBM HiOP",
    "expensive_profitable": "LoBM HiOP",
    "expensive_junk": "LoBM LoOP",
}
SPLITS = {
    "small_cheap_unprofitable": "SMALL HiBM LoOP",
    "small_cheap_profitable": "SMALL HiBM HiOP",
    "big_cheap_unprofitable": "BIG HiBM LoOP",
    "big_cheap_profitable": "BIG HiBM HiOP",
    "small_expensive_junk": "SMALL LoBM LoOP",
}

S = {k: [t25[m][c] for m in months] for k, c in CORNERS.items()}
S |= {k + "_ew": [t25_ew[m][c] for m in months] for k, c in CORNERS.items()}
S |= {k: [t32[m][c] for m in months] for k, c in SPLITS.items()}
S["market"] = [ff5[m]["Mkt-RF"] + ff5[m]["RF"] for m in months]
S["tbill"] = [ff5[m]["RF"] for m in months]

PERIODS = [
    ("full", months[0], LAST),
    ("1963-1990", months[0], "199012"),
    ("1991-2006", "199101", "200612"),
    ("2007-2020", "200701", "202012"),
    (f"2021-{LAST[:4]}", "202101", LAST),
]


def idx(a, b):
    return [i for i, m in enumerate(months) if a <= m <= b]


def geo(r):
    return math.exp(sum(math.log1p(x) for x in r) * 12 / len(r)) - 1


def arith(r):
    return sum(r) / len(r) * 12


def vol(r):
    mu = sum(r) / len(r)
    return math.sqrt(sum((x - mu) ** 2 for x in r) / (len(r) - 1) * 12)


def growth(r):
    return math.exp(sum(math.log1p(x) for x in r))


def max_drawdown(r, labels):
    level, peak, peak_at, worst = 1.0, 1.0, labels[0], (0.0, None, None)
    for x, m in zip(r, labels):
        level *= 1 + x
        if level > peak:
            peak, peak_at = level, m
        dd = level / peak - 1
        if dd < worst[0]:
            worst = (dd, peak_at, m)
    return {"depth": worst[0], "peak": worst[1], "trough": worst[2], "now_below_peak": level / peak - 1}


def ols(y, cols):
    """OLS with intercept via normal equations; returns (coefs, t-stats)."""
    X = [[1.0, *row] for row in zip(*cols)]
    k, n = len(X[0]), len(X)
    xtx = [[sum(r[i] * r[j] for r in X) for j in range(k)] for i in range(k)]
    xty = [sum(r[i] * yy for r, yy in zip(X, y)) for i in range(k)]
    inv = invert(xtx)
    b = [sum(inv[i][j] * xty[j] for j in range(k)) for i in range(k)]
    resid = [yy - sum(bi * xi for bi, xi in zip(b, r)) for r, yy in zip(X, y)]
    s2 = sum(e * e for e in resid) / (n - k)
    se = [math.sqrt(s2 * inv[i][i]) for i in range(k)]
    ybar = sum(y) / n
    r2 = 1 - sum(e * e for e in resid) / sum((yy - ybar) ** 2 for yy in y)
    return b, [bi / si for bi, si in zip(b, se)], r2


def invert(a):
    n = len(a)
    m = [row[:] + [float(i == j) for j in range(n)] for i, row in enumerate(a)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(m[r][c]))
        m[c], m[p] = m[p], m[c]
        piv = m[c][c]
        m[c] = [v / piv for v in m[c]]
        for r in range(n):
            if r != c:
                f = m[r][c]
                m[r] = [vr - f * vc for vr, vc in zip(m[r], m[c])]
    return [row[n:] for row in m]


def pct(x, d=2):
    return f"{100 * x:{7}.{d}f}%"


results = {"data_through": LAST, "start": months[0], "periods": {}, "firms": {}}

print(f"Data {months[0]} to {LAST}, {len(months)} months. Value-weighted unless marked _ew.")
print("\nAnnualized geometric return by period")
keys = [*CORNERS, "market", "tbill", *[k + "_ew" for k in CORNERS], *SPLITS]
names = [p[0] for p in PERIODS]
print(f"  {'':26}" + "".join(f"{n:>11}" for n in names))
for k in keys:
    row = []
    for name, a, b in PERIODS:
        r = [S[k][i] for i in idx(a, b)]
        stats = {"geo": geo(r), "arith": arith(r), "vol": vol(r), "growth": growth(r)}
        results["periods"].setdefault(name, {})[k] = stats
        row.append(stats["geo"])
    print(f"  {k:26}" + "".join(pct(g, 1).rjust(11) for g in row))

print("\nFull sample: arithmetic mean, volatility, growth of $1, max drawdown")
for k in [*CORNERS, "market", "tbill", *SPLITS]:
    st = results["periods"]["full"][k]
    dd = max_drawdown(S[k], months)
    st["max_drawdown"] = dd
    print(
        f"  {k:26} arith {pct(st['arith'])} vol {pct(st['vol'], 1)}"
        f"  $1 -> ${st['growth']:>9,.2f}  maxDD {pct(dd['depth'], 1)} ({dd['peak']}-{dd['trough']})"
    )

print("\nAverage number of firms per month")
for k, c in CORNERS.items():
    counts = [n25[m][c] for m in months]
    results["firms"][k] = {"mean": sum(counts) / len(counts), "min": min(counts)}
for k, c in SPLITS.items():
    counts = [n32[m][c] for m in months]
    results["firms"][k] = {"mean": sum(counts) / len(counts), "min": min(counts)}
for k, v in results["firms"].items():
    print(f"  {k:26} mean {v['mean']:6.0f}  min {v['min']:4.0f}")

print("\n5x5 grid, full-sample annualized geometric return (rows BE/ME low->high, cols OP low->high)")
grid = []
for bm in range(1, 6):
    row = []
    for op in range(1, 6):
        col = list(t25[months[0]])[(bm - 1) * 5 + (op - 1)]
        row.append(geo([t25[m][col] for m in months]))
    grid.append(row)
    print(f"  BM{bm} " + "".join(pct(g, 1).rjust(9) for g in row))
results["grid_5x5_geo"] = grid

print("\nFive-factor regressions of monthly excess returns (alpha annualized)")
fac = ["Mkt-RF", "SMB", "HML", "RMW", "CMA"]
X = [[ff5[m][f] for m in months] for f in fac]
results["ff5"] = {}
for k in [*CORNERS, *[k + "_ew" for k in CORNERS]]:
    y = [r - rf for r, rf in zip(S[k], S["tbill"])]
    b, t, r2 = ols(y, X)
    results["ff5"][k] = {
        "alpha": b[0] * 12,
        "alpha_t": t[0],
        **{f: b[i + 1] for i, f in enumerate(fac)},
        **{f + "_t": t[i + 1] for i, f in enumerate(fac)},
        "r2": r2,
    }
    print(
        f"  {k:26} alpha {pct(b[0] * 12)} (t {t[0]:5.2f})  "
        + "  ".join(f"{f} {bi:5.2f}" for f, bi in zip(fac, b[1:]))
        + f"  R2 {r2:.2f}"
    )

print("\nRolling 10-year windows, full sample")
results["rolling_10y"] = {}
for a, bkey in [("cheap_unprofitable", "market"), ("expensive_junk", "tbill"), ("small_cheap_profitable", "small_cheap_unprofitable")]:
    wins = total = 0
    for s in range(len(months) - 119):
        wins += growth(S[a][s : s + 120]) > growth(S[bkey][s : s + 120])
        total += 1
    results["rolling_10y"][f"{a}_beats_{bkey}"] = wins / total
    print(f"  {a} beat {bkey} in {wins} of {total} windows ({100 * wins / total:.0f}%)")

print("\nHML and RMW")
hm = sorted(ff3)
hml_all = [ff3[m]["HML"] for m in hm]
results["hml"] = {
    "since": hm[0],
    "arith_all": arith(hml_all),
    "drawdown": max_drawdown(hml_all, hm),
    "by_period": {n: arith([ff5[m]["HML"] for m in months if a <= m <= b]) for n, a, b in PERIODS},
}
results["rmw"] = {"by_period": {n: arith([ff5[m]["RMW"] for m in months if a <= m <= b]) for n, a, b in PERIODS}}
d = results["hml"]["drawdown"]
print(f"  HML mean since {hm[0]}: {pct(results['hml']['arith_all'])} per year")
print(f"  HML worst drawdown {pct(d['depth'], 1)} ({d['peak']} to {d['trough']}); now {pct(d['now_below_peak'], 1)} from that peak")
for n in names:
    print(f"  {n:12} HML {pct(results['hml']['by_period'][n])}  RMW {pct(results['rmw']['by_period'][n])}")

(HERE / "results.json").write_text(json.dumps(results, indent=1) + "\n")
print("\nWrote results.json")

if "--chart" in sys.argv:
    out = Path(sys.argv[sys.argv.index("--chart") + 1])
    series = ["cheap_unprofitable", "expensive_profitable", "expensive_junk", "market", "tbill"]
    level = dict.fromkeys(series, 1.0)
    # t is fractional years at month end, so the start point sits at mid-1963.
    t0 = int(months[0][:4]) + (int(months[0][4:]) - 1) / 12
    points = [{"t": round(t0, 4), **dict.fromkeys(series, 1.0)}]
    for i, m in enumerate(months):
        for k in series:
            level[k] *= 1 + S[k][i]
        if m.endswith("12") or m == LAST:
            t = int(m[:4]) + int(m[4:]) / 12
            points.append({"t": round(t, 4), **{k: round(level[k], 4) for k in series}})
    chart = {"start": months[0], "end": LAST, "points": points}
    out.write_text(json.dumps(chart, indent=1) + "\n")
    print(f"Wrote chart series ({len(points)} points)")
