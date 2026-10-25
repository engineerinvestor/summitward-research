"""VOO, SCHD and QQQ over SCHD's full history, for the three /compare pages.

Window: SCHD's first close (2011-10-20) to 2026-09-30, plus a ten-year window
ending 2026-09-30. Total returns are built from daily closes and
distributions (dividends reinvested at the ex-date close). Prints:

- trailing 12-month distribution yields at 2026-09-30
- annualized return, volatility (monthly returns x sqrt 12), worst
  peak-to-trough decline (daily), growth of $10,000
- calendar-year returns 2012-2025 and 2026 through September
- correlations of monthly returns
- after-tax returns under the SEC method at 23.8% (all dividends qualified,
  no capital-gain distributions): after taxes on distributions, and after
  also selling at the end

Stdlib only. Run fetch_data.py first.

Usage:
    python3 analyze.py
"""

import csv
import math
from collections import defaultdict
from datetime import date
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"
FUNDS = ("VOO", "SCHD", "QQQ")


def load():
    with open(DATA / "closes.csv") as f:
        rows = list(csv.DictReader(f))
    dates = [r["date"] for r in rows]
    closes = {t: [float(r[t]) for r in rows] for t in FUNDS}
    dist = defaultdict(dict)
    with open(DATA / "distributions.csv") as f:
        for r in csv.DictReader(f):
            dist[r["ticker"]][r["ex_date"]] = float(r["amount"])
    return dates, closes, dist


def payout_fractions(dates, close, dist):
    return {
        i: dist[dates[i]] / close[i - 1]
        for i in range(1, len(dates))
        if dist.get(dates[i])
    }


def tr_index(close, q):
    idx = [1.0]
    for i in range(1, len(close)):
        idx.append(idx[-1] * (close[i] / close[i - 1] + q.get(i, 0.0)))
    return idx


def years_between(dates, i0, i1):
    a, b = (date.fromisoformat(dates[k]) for k in (i0, i1))
    return (b - a).days / 365.25


def after_tax(close, q, i0, i1, rate):
    """Return (pre-liquidation wealth, post-liquidation wealth) per $1."""
    w = b = 1.0
    for i in range(i0 + 1, i1 + 1):
        f = close[i] / close[i - 1] + q.get(i, 0.0)
        if i in q:
            d = w * q[i]
            tax = d * rate
            b += d - tax
            w = w * f - tax
        else:
            w *= f
    return w, w - max(w - b, 0.0) * rate


def month_ends(dates):
    out = []
    for i in range(len(dates)):
        if i == len(dates) - 1 or dates[i + 1][:7] != dates[i][:7]:
            out.append(i)
    return out


def corr(x, y):
    mx, my = sum(x) / len(x), sum(y) / len(y)
    sxy = sum((a - mx) * (b - my) for a, b in zip(x, y, strict=True))
    sxx = sum((a - mx) ** 2 for a in x)
    syy = sum((b - my) ** 2 for b in y)
    return sxy / math.sqrt(sxx * syy)


def main():
    dates, closes, dist = load()
    q = {t: payout_fractions(dates, closes[t], dist[t]) for t in FUNDS}
    idx = {t: tr_index(closes[t], q[t]) for t in FUNDS}
    i_end = len(dates) - 1
    end = dates[i_end]

    print(f"Window: {dates[0]} to {end}")
    y_start = f"{int(end[:4]) - 1}{end[4:]}"
    print("\nTrailing 12-month distribution yield at", end)
    for t in FUNDS:
        s = sum(a for d, a in dist[t].items() if y_start < d <= end)
        print(f"  {t}: {s / closes[t][i_end]:.2%}")

    me = month_ends(dates)
    # first month-end after inception starts the monthly series
    monthly = {
        t: [idx[t][me[k]] / idx[t][me[k - 1]] - 1 for k in range(1, len(me))]
        for t in FUNDS
    }
    print(
        f"\nMonthly series {dates[me[0]][:7]} to {dates[me[-1]][:7]}"
        f" ({len(me) - 1} months)"
    )

    def summary(i0, label):
        n = years_between(dates, i0, i_end)
        print(f"\n{label}: {dates[i0]} to {end} ({n:.2f} yrs)")
        print(
            f"{'fund':<5} {'annual':>7} {'$10k ->':>9} {'vol':>6} {'max DD':>8} {'DD trough':>10}"
        )
        k0 = next(k for k, i in enumerate(me) if i >= i0)
        for t in FUNDS:
            g = idx[t][i_end] / idx[t][i0]
            rets = [
                idx[t][me[k]] / idx[t][me[k - 1]] - 1 for k in range(k0 + 1, len(me))
            ]
            m = sum(rets) / len(rets)
            vol = math.sqrt(
                sum((r - m) ** 2 for r in rets) / (len(rets) - 1)
            ) * math.sqrt(12)
            peak, dd, trough = 0.0, 0.0, ""
            for i in range(i0, i_end + 1):
                peak = max(peak, idx[t][i])
                x = idx[t][i] / peak - 1
                if x < dd:
                    dd, trough = x, dates[i]
            print(
                f"{t:<5} {g ** (1 / n) - 1:>7.2%} {1e4 * g:>9,.0f} {vol:>6.1%} {dd:>8.1%} {trough:>10}"
            )

    summary(0, "Since SCHD inception")
    i10 = next(i for i, d in enumerate(dates) if d >= "2016-09-30")
    summary(i10, "Ten years")
    i5 = next(i for i, d in enumerate(dates) if d >= "2021-09-30")
    summary(i5, "Five years")

    print("\nCalendar-year total returns")
    print(f"{'year':<6}" + "".join(f"{t:>8}" for t in FUNDS) + "   leader")
    years = sorted({d[:4] for d in dates})
    for y in years[1:]:
        i0 = max(i for i, d in enumerate(dates) if d[:4] < y)
        i1 = max(i for i, d in enumerate(dates) if d[:4] == y)
        r = {t: idx[t][i1] / idx[t][i0] - 1 for t in FUNDS}
        lead = max(r, key=r.get)
        tag = " (YTD)" if y == end[:4] else ""
        print(f"{y:<6}" + "".join(f"{r[t]:>8.1%}" for t in FUNDS) + f"   {lead}{tag}")

    print("\nFull calendar years 2012-2025 in which the first fund beat the second")
    full = [y for y in years[1:] if y != end[:4]]
    for a, b in (("QQQ", "VOO"), ("SCHD", "VOO"), ("SCHD", "QQQ")):
        wins = []
        for y in full:
            i0 = max(i for i, d in enumerate(dates) if d[:4] < y)
            i1 = max(i for i, d in enumerate(dates) if d[:4] == y)
            if idx[a][i1] / idx[a][i0] > idx[b][i1] / idx[b][i0]:
                wins.append(y)
        print(f"  {a} over {b}: {len(wins)} of {len(full)} ({', '.join(wins)})")

    print("\nCorrelation of monthly returns")
    for a, b in (("VOO", "SCHD"), ("VOO", "QQQ"), ("SCHD", "QQQ")):
        print(f"  {a}-{b}: {corr(monthly[a], monthly[b]):.2f}")

    for label, i0 in (("Ten years", i10), ("Since SCHD inception", 0)):
        n = years_between(dates, i0, i_end)
        print(f"\nAfter-tax, SEC method at 23.8%, {label} ({n:.2f} yrs)")
        print(
            f"{'fund':<5} {'pretax':>7} {'after dist':>11} {'after sale':>11} {'dist cost':>10}"
        )
        for t in FUNDS:
            pre = idx[t][i_end] / idx[t][i0]
            w, e = after_tax(closes[t], q[t], i0, i_end, 0.238)
            a_pre, a_w, a_e = (x ** (1 / n) - 1 for x in (pre, w, e))
            print(
                f"{t:<5} {a_pre:>7.2%} {a_w:>11.2%} {a_e:>11.2%} {a_pre - a_w:>10.2%}"
            )


def long_history():
    """QQQ against SPY (S&P 500) from QQQ's March 1999 launch."""
    with open(DATA / "long_closes.csv") as f:
        rows = list(csv.DictReader(f))
    dates = [r["date"] for r in rows]
    dist = defaultdict(dict)
    with open(DATA / "long_distributions.csv") as f:
        for r in csv.DictReader(f):
            dist[r["ticker"]][r["ex_date"]] = float(r["amount"])
    print(f"\nLong history, QQQ vs SPY: {dates[0]} to {dates[-1]}")
    n = years_between(dates, 0, len(dates) - 1)
    series = {}
    for t in ("QQQ", "SPY"):
        c = [float(r[t]) for r in rows]
        ix = tr_index(c, payout_fractions(dates, c, dist[t]))
        peak, pk_date, dd, trough, dd_peak = 0.0, "", 0.0, "", ""
        for i, v in enumerate(ix):
            if v > peak:
                peak, pk_date = v, dates[i]
            if v / peak - 1 < dd:
                dd, trough, dd_peak = v / peak - 1, dates[i], pk_date
        # first date the index regains the pre-crash peak
        pk_val = ix[dates.index(dd_peak)]
        i_tr = dates.index(trough)
        rec = next(
            (dates[i] for i in range(i_tr, len(ix)) if ix[i] >= pk_val), "not yet"
        )
        print(
            f"  {t}: {ix[-1] ** (1 / n) - 1:.2%} a year over {n:.1f} yrs;"
            f" worst decline {dd:.1%} ({dd_peak} to {trough}), back to that peak {rec}"
        )
        series[t] = ix
    a, b = dates.index("2000-03-27"), dates.index("2002-10-09")
    for t in ("QQQ", "SPY"):
        print(
            f"  {t} from 2000-03-27 to 2002-10-09: {series[t][b] / series[t][a] - 1:.1%}"
        )


def holdings_overlap():
    """SCHD (Schwab, 2026-10-13) against QQQ (Invesco, 2026-10-23).

    Weights are as published on each date, not repriced to a common date.
    Invesco's expanded list showed 100 lines (99.74% of assets); cash and the
    index future are dropped and the stock weights rescaled to sum to one.
    """

    def read(name):
        with open(DATA / name) as f:
            return {r["ticker"]: float(r["weight_pct"]) for r in csv.DictReader(f)}

    schd = read("schd_holdings_2026-10-13.csv")
    qqq = {
        k: v
        for k, v in read("qqq_holdings_2026-10-23.csv").items()
        if k not in ("USD", "NQZ6")
    }
    ts, tq = sum(schd.values()), sum(qqq.values())
    shared = sorted(set(schd) & set(qqq), key=lambda k: -schd[k])
    overlap = sum(min(schd[k] / ts, qqq[k] / tq) for k in shared)
    print("\nSCHD-QQQ holdings overlap")
    print(f"  shared stocks: {len(shared)} ({', '.join(shared)})")
    print(f"  overlap by weight: {overlap:.1%}")
    print(f"  share of SCHD in shared stocks: {sum(schd[k] for k in shared) / ts:.1%}")
    print(f"  share of QQQ in shared stocks: {sum(qqq[k] for k in shared) / tq:.1%}")


if __name__ == "__main__":
    main()
    long_history()
    holdings_overlap()
