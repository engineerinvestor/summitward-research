"""After-tax cost of SCHD's dividend yield in a taxable account.

Three studies, each printed as a table the guide quotes:

A. Controlled model. Two funds earn the same constant pretax total return;
   only the share paid out as dividends differs. Dividends are taxed when
   paid and the rest reinvested; the deferred gain is taxed (or not) at the
   end. Reported for three end states: hold (no sale), sell everything, and
   step-up at death or donation (deferred gain never taxed).

B. SCHD's actual payouts. SCHD's own daily total-return path from its
   distributions and closes, with two payout schedules laid on top of it:
   SCHD's actual distributions, and VTI's actual distribution yield on VTI's
   ex-dates. Same pretax return by construction, so the gap is the tax cost of
   SCHD's payout policy alone. Also reports each fund's own after-tax return
   over the same window, which mixes in their different pretax returns.

C. Retiree spending. Tax owed to fund the same after-tax spending from
   dividends versus from share sales at several basis ratios.

Assumptions shared by A and B: all dividends qualified (SCHD reported 98.5%
qualified for 2025), no capital-gain distributions (SCHD paid none in fiscal
2021-2025), taxes paid from the dividend and the remainder reinvested on the
ex-date, no state tax, no fees beyond those already in fund returns.

Stdlib only. Run fetch_data.py first.

Usage:
    python3 analyze.py
"""

import csv
import math
from collections import defaultdict
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"

RATES = [0.0, 0.15, 0.188, 0.238]


# --------------------------------------------------------------------------
# Study A
# --------------------------------------------------------------------------


def model(y, r, div_rate, sale_rate, years, start=100_000.0):
    """Annual-step accumulation. Returns (value before sale, basis)."""
    w = b = start
    for _ in range(years):
        d = w * y
        tax = d * div_rate
        w = w * (1 + r) - tax
        b += d - tax
    return w, b


def end_value(w, b, sale_rate):
    return w - max(w - b, 0.0) * sale_rate


def cagr(v, start, years):
    return (v / start) ** (1 / years) - 1


def study_a(y_hi, y_lo, r=0.07, start=100_000.0):
    print("=" * 78)
    print(
        f"STUDY A  controlled model: ${start:,.0f}, {r:.0%} pretax total return,"
        f" yields {y_hi:.2%} vs {y_lo:.2%}"
    )
    print("=" * 78)
    print("\nYear-1 dividend tax per $100,000")
    print(f"{'rate':>7} {'high yield':>11} {'low yield':>10} {'extra':>8}")
    for t in RATES:
        a, b = start * y_hi * t, start * y_lo * t
        print(f"{t:>7.1%} {a:>11,.0f} {b:>10,.0f} {a - b:>8,.0f}")

    def row(label, div_rate, sale_rate, years):
        wa, ba = model(y_hi, r, div_rate, sale_rate, years, start)
        wb, bb = model(y_lo, r, div_rate, sale_rate, years, start)
        hold = wb - wa
        hold_bp = (cagr(wb, start, years) - cagr(wa, start, years)) * 1e4
        ea, eb = end_value(wa, ba, sale_rate), end_value(wb, bb, sale_rate)
        sale = eb - ea
        sale_bp = (cagr(eb, start, years) - cagr(ea, start, years)) * 1e4
        # extra dividend tax paid by the high-yield fund, undiscounted sum
        paid = 0.0
        w1 = w2 = start
        for _ in range(years):
            paid += (w1 * y_hi - w2 * y_lo) * div_rate
            w1 = w1 * (1 + r) - w1 * y_hi * div_rate
            w2 = w2 * (1 + r) - w2 * y_lo * div_rate
        print(
            f"{label:<26} {years:>3} {paid:>10,.0f} {hold:>10,.0f} {hold_bp:>6.1f}"
            f" {sale:>10,.0f} {sale_bp:>6.1f}"
        )

    print(
        "\nLow-yield advantage. 'extra tax' = sum of extra dividend tax the"
        " high-yield fund paid;\n'no sale' = gap if never sold, which is also the"
        " step-up/donation result; 'full sale' = gap after selling and paying"
        " gains tax at the sale rate. bp = annualized."
    )
    hdr = (
        f"{'dividend rate / sale rate':<26} {'yrs':>3} {'extra tax':>10}"
        f" {'no sale $':>10} {'bp':>6} {'full sale $':>10} {'bp':>6}"
    )
    print(hdr)
    for t in RATES[1:]:
        for n in (10, 20, 30):
            row(f"{t:.1%} / {t:.1%}", t, t, n)
    print("Rate changes between now and the sale (20 years):")
    for dr, sr in ((0.15, 0.238), (0.238, 0.15), (0.0, 0.15), (0.15, 0.0)):
        row(f"{dr:.1%} / {sr:.1%}", dr, sr, 20)


# --------------------------------------------------------------------------
# Study B
# --------------------------------------------------------------------------


def load():
    with open(DATA / "closes.csv") as f:
        rows = list(csv.DictReader(f))
    dates = [r["date"] for r in rows]
    closes = {t: [float(r[t]) for r in rows] for t in ("SCHD", "VTI", "VOO")}
    dist = defaultdict(dict)
    with open(DATA / "distributions.csv") as f:
        for r in csv.DictReader(f):
            dist[r["ticker"]][r["ex_date"]] = float(r["amount"])
    return dates, closes, dist


def payout_fractions(dates, close, dist):
    """Map index -> dividend / prior close on each ex-date."""
    out = {}
    for i in range(1, len(dates)):
        amt = dist.get(dates[i])
        if amt:
            out[i] = amt / close[i - 1]
    return out


def tr_factors(close, payouts):
    """Daily total-return factors: (close + dividend) / prior close."""
    f = [1.0]
    for i in range(1, len(close)):
        q = payouts.get(i, 0.0)
        f.append(close[i] / close[i - 1] + q)
    return f


def run(factors, payouts, i0, i1, div_rate, start=10_000.0):
    """Hold from close i0 to close i1. Returns (value, basis, tax paid)."""
    w = b = start
    paid = 0.0
    for i in range(i0 + 1, i1 + 1):
        q = payouts.get(i, 0.0)
        if q:
            # Value just before the ex-date move is w; the day's total return
            # includes the payout, which is taxed and the rest reinvested.
            d = w * q
            tax = d * div_rate
            paid += tax
            b += d - tax
            w = w * factors[i] - tax
        else:
            w *= factors[i]
    return w, b, paid


def study_b():
    dates, closes, dist = load()
    q = {t: payout_fractions(dates, closes[t], dist[t]) for t in closes}
    f = {t: tr_factors(closes[t], q[t]) for t in closes}
    i_end = len(dates) - 1
    print("\n" + "=" * 78)
    print(f"STUDY B  SCHD's actual payouts, closes to {dates[i_end]}")
    print("=" * 78)

    # Trailing-12-month yields at the end date
    end = dates[i_end]
    y_start = f"{int(end[:4]) - 1}{end[4:]}"
    ttm = {}
    for t in closes:
        s = sum(a for d, a in dist[t].items() if y_start < d <= end)
        ttm[t] = s / closes[t][i_end]
        print(f"{t} trailing-12-month distribution yield at {end}: {ttm[t]:.2%}")

    def years_between(i0, i1):
        from datetime import date

        a, b = (date.fromisoformat(dates[k]) for k in (i0, i1))
        return (b - a).days / 365.25

    print(
        "\nSame SCHD pretax path, two payout schedules: SCHD's actual payouts vs"
        " VTI's payout yield.\nValues per $10,000. 'hold' = before any sale;"
        " 'sale' = after selling everything at the same rate.\nbp = annualized"
        " advantage of the low-payout schedule."
    )
    print(
        f"{'start':<11} {'yrs':>5} {'rate':>6} {'pretax':>8} {'tax paid S/V':>15}"
        f" {'hold bp':>8} {'sale bp':>8} {'sale $':>7}"
    )
    starts = [y for y in range(2012, 2022)]
    for t_rate in (0.15, 0.238):
        for yr in starts:
            i0 = next(i for i, d in enumerate(dates) if d >= f"{yr}-01-01") - 1
            if yr == 2012:
                i0 = 0  # first close after inception (2011-10-20)
            n = years_between(i0, i_end)
            pre, _, _ = run(f["SCHD"], q["SCHD"], i0, i_end, 0.0)
            ws, bs, ps = run(f["SCHD"], q["SCHD"], i0, i_end, t_rate)
            # Counterfactual: SCHD's total-return path, VTI's payout fraction
            # on VTI's ex-dates.
            wv, bv, pv = run(f["SCHD"], q["VTI"], i0, i_end, t_rate)
            hold_bp = (cagr(wv, 1e4, n) - cagr(ws, 1e4, n)) * 1e4
            es, ev = end_value(ws, bs, t_rate), end_value(wv, bv, t_rate)
            sale_bp = (cagr(ev, 1e4, n) - cagr(es, 1e4, n)) * 1e4
            print(
                f"{dates[i0]:<11} {n:>5.1f} {t_rate:>6.1%} {pre:>8,.0f}"
                f" {ps:>7,.0f}/{pv:<7,.0f} {hold_bp:>8.1f} {sale_bp:>8.1f}"
                f" {ev - es:>7,.0f}"
            )

    print(
        "\nEach fund's own after-tax return (different pretax returns; this is"
        " investor experience,\nnot the tax effect). Annualized, 100% qualified,"
        " sale at the end at the same rate."
    )
    i10 = next(i for i, d in enumerate(dates) if d >= "2016-09-30")
    for label, i0 in (("10 yr", i10), ("since SCHD inception", 0)):
        n = years_between(i0, i_end)
        print(f"\n{label}: {dates[i0]} to {dates[i_end]} ({n:.1f} yrs)")
        print(
            f"{'fund':<6} {'rate':>6} {'pretax':>7} {'after div':>10} {'after sale':>11}"
        )
        for t_rate in (0.20, 0.238):
            for t in ("SCHD", "VTI", "VOO"):
                pre, _, _ = run(f[t], q[t], i0, i_end, 0.0)
                w, b, _ = run(f[t], q[t], i0, i_end, t_rate)
                e = end_value(w, b, t_rate)
                print(
                    f"{t:<6} {t_rate:>6.1%} {cagr(pre, 1e4, n):>7.2%}"
                    f" {cagr(w, 1e4, n):>10.2%} {cagr(e, 1e4, n):>11.2%}"
                )
    return ttm


# --------------------------------------------------------------------------
# Study C
# --------------------------------------------------------------------------


def study_c(spend=40_000.0):
    print("\n" + "=" * 78)
    print(f"STUDY C  tax to fund ${spend:,.0f} of after-tax spending")
    print("=" * 78)
    print(
        "Dividends are fully taxable; a share sale is taxable only on the gain"
        "\n(sale price minus basis). Basis ratio = basis / market value of the"
        " shares sold."
    )
    print(
        f"{'rate':>6} {'dividends':>10} {'sell b=100%':>12} {'b=70%':>8} {'b=50%':>8} {'b=30%':>8}"
    )
    for t in (0.0, 0.15, 0.188):
        div_tax = spend / (1 - t) * t
        cells = []
        for br in (1.0, 0.7, 0.5, 0.3):
            g = 1 - br
            s = spend / (1 - g * t)
            cells.append(s * g * t)
        print(
            f"{t:>6.1%} {div_tax:>10,.0f} {cells[0]:>12,.0f} {cells[1]:>8,.0f}"
            f" {cells[2]:>8,.0f} {cells[3]:>8,.0f}"
        )


def main():
    ttm = study_b()
    study_a(round(ttm["SCHD"], 4), round(ttm["VTI"], 4))
    study_c()
    assert math.isclose(end_value(110, 100, 0.15), 108.5)


if __name__ == "__main__":
    main()
