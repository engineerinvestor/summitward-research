"""Do trailing 3- and 5-year factor returns predict the next 3 or 5 years?

Tests the third peeve in Cliff Asness, "My Top 10 Peeves" (Financial Analysts
Journal, 2014): that judging strategies on trailing three- to five-year
returns uses the data "backwards," because returns at that horizon tend, if
weakly, to mean revert.

Data: Kenneth R. French Data Library, monthly US factors
(F-F_Research_Data_Factors: Mkt-RF, SMB, HML; F-F_Momentum_Factor: Mom).
Download the two CSV zips into ./data/ and unzip them first:
  https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_Factors_CSV.zip
  https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Momentum_Factor_CSV.zip

Method, for each factor and horizon h (36 or 60 months):
  1. Compound monthly returns into the trailing-h and following-h return at
     every month-end where both windows are complete.
  2. Correlation of trailing vs following, using every month (overlapping
     windows, so neighbouring observations share up to h-1 months and the
     effective sample is far smaller than the row count) and using only
     non-overlapping origins spaced h months apart (median and range over
     every possible starting offset).
  3. Chasing test: each January, rank factors by rank factors by
     trailing-h return; report how often the trailing loser beat the trailing
     winner over the next h months, and the average gap.

Standard library only.
"""

import csv
import math
from pathlib import Path

DATA = Path(__file__).parent / "data"
FACTORS = ["Mkt-RF", "SMB", "HML", "Mom"]
HORIZONS = [36, 60]


def read_monthly(path):
    """Return {yyyymm: {col: decimal return}} from a French CSV's monthly block."""
    rows, header = {}, None
    with open(path, newline="") as f:
        for rec in csv.reader(f):
            if not rec:
                if header and rows:
                    break  # end of monthly block
                continue
            first = rec[0].strip()
            if header is None and len(rec) > 1 and first == "":
                header = [c.strip() for c in rec[1:]]
                continue
            if header and len(first) == 6 and first.isdigit():
                rows[first] = {
                    h: float(v) / 100 for h, v in zip(header, rec[1:], strict=False)
                }
            elif header and rows:
                break
    return rows


def compound(rs):
    p = 1.0
    for r in rs:
        p *= 1 + r
    return p - 1


def corr(xs, ys):
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    return sxy / math.sqrt(sxx * syy)


def main():
    ff = read_monthly(DATA / "F-F_Research_Data_Factors.csv")
    mom = read_monthly(DATA / "F-F_Momentum_Factor.csv")
    months = sorted(set(ff) & set(mom))
    series = {f: [ff[m][f] for m in months] for f in ["Mkt-RF", "SMB", "HML"]}
    series["Mom"] = [mom[m]["Mom"] for m in months]
    n = len(months)
    print(f"Sample: {months[0]} to {months[-1]} ({n} months)\n")

    print("1) Correlation of trailing-h with following-h compounded return")
    print("   'all months' uses every month-end (overlapping windows).")
    print("   Non-overlapping origins are spaced h months apart; the result depends")
    print("   on the starting month, so the median and range over all h offsets")
    print("   are shown.")
    print(
        f"{'factor':8}{'h':>4}{'all months':>12}{'non-overlap median':>20}"
        f"{'min':>7}{'max':>7}{'offsets < 0':>13}{'n per offset':>14}"
    )
    for h in HORIZONS:
        for fac in FACTORS:
            r = series[fac]
            trail = [compound(r[t - h : t]) for t in range(h, n - h + 1)]
            fwd = [compound(r[t : t + h]) for t in range(h, n - h + 1)]
            c_all = corr(trail, fwd)
            cs = []
            for off in range(h):
                idx = range(off, len(trail), h)
                cs.append(corr([trail[i] for i in idx], [fwd[i] for i in idx]))
            cs.sort()
            neg = sum(c < 0 for c in cs) / len(cs)
            print(
                f"{fac:8}{h:>4}{c_all:>12.2f}{cs[len(cs) // 2]:>20.2f}"
                f"{cs[0]:>7.2f}{cs[-1]:>7.2f}{neg:>13.0%}{len(trail) // h:>14}"
            )
    print()

    for label, pool in [
        ("all four factors", FACTORS),
        ("SMB, HML, Mom only", FACTORS[1:]),
    ]:
        print(f"2) Chasing test, {label}: each January, best vs worst trailing-h")
        print(
            f"{'h':>4}{'decisions':>11}{'loser beat winner':>19}"
            f"{'avg next-h (winner)':>21}{'avg next-h (loser)':>20}"
        )
        for h in HORIZONS:
            wins = 0
            w_ret, l_ret = [], []
            for t in range(h, n - h + 1):
                if months[t][-2:] != "01":  # forward window starts in January
                    continue
                trail = {f: compound(series[f][t - h : t]) for f in pool}
                fwd = {f: compound(series[f][t : t + h]) for f in pool}
                best = max(trail, key=trail.get)
                worst = min(trail, key=trail.get)
                w_ret.append(fwd[best])
                l_ret.append(fwd[worst])
                wins += fwd[worst] > fwd[best]
            k = len(w_ret)
            print(
                f"{h:>4}{k:>11}{wins / k:>18.0%} {sum(w_ret) / k:>20.1%}"
                f"{sum(l_ret) / k:>20.1%}"
            )
        print()


if __name__ == "__main__":
    main()
