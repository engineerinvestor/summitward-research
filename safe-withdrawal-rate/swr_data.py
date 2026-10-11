"""Annual real returns from Shiller's monthly U.S. data, and a 4%-rule backtest.

Stocks: S&P composite, price + dividends, compounded monthly.
Bonds: 10-year Treasury, approximated as a par bond bought each January and
sold a year later as a 9-year bond at the new yield (coupon + price change).
Inflation: CPI, January to January. Annual rebalancing, withdrawals at the
start of each year, constant real spending, no fees, no taxes.
"""
import numpy as np
import pandas as pd

import pathlib
d = pd.read_csv(pathlib.Path(__file__).resolve().parent / "data" / "shiller.csv", parse_dates=["Date"])
d = d[(d["Consumer Price Index"] > 0) & (d["Dividend"] > 0) & (d["Long Interest Rate"] > 0)].reset_index(drop=True)
P, D, CPI, Y = (d[c].values for c in ["SP500", "Dividend", "Consumer Price Index", "Long Interest Rate"])
Y = Y / 100

# monthly stock total return, then Jan->Jan annual
r_m = (P[1:] + D[:-1] / 12) / P[:-1]
jan = np.where(d.Date.dt.month.values == 1)[0]
jan = jan[jan + 12 < len(d)]
years = d.Date.dt.year.values[jan]
stock_nom = np.array([np.prod(r_m[i:i + 12]) - 1 for i in jan])
y0, y1 = Y[jan], Y[jan + 12]
bond_nom = y0 + (y0 * (1 - (1 + y1) ** -9) / y1 + (1 + y1) ** -9) - 1
infl = CPI[jan + 12] / CPI[jan] - 1
stock_real = (1 + stock_nom) / (1 + infl) - 1
bond_real = (1 + bond_nom) / (1 + infl) - 1


def portfolio_real(eq):
    return eq * stock_real + (1 - eq) * bond_real


def run(start_idx, wr, horizon, eq=0.6, rets=None):
    """Real portfolio value path starting at 1.0; withdraw wr (real) at the start of each year."""
    r = portfolio_real(eq) if rets is None else rets
    v = [1.0]
    for k in range(horizon):
        x = v[-1] - wr
        if x <= 0:
            v += [0.0] * (horizon - k)
            break
        v.append(x * (1 + r[start_idx + k]))
    return np.array(v)


def starts(horizon):
    return [i for i in range(len(years)) if i + horizon <= len(years)]


def success(wr, horizon, eq=0.6):
    s = starts(horizon)
    return np.mean([run(i, wr, horizon, eq)[-1] > 0 for i in s]), len(s)


if __name__ == "__main__":
    print("years", years[0], "-", years[-1], "(last return year starts Jan", years[-1], ")")
    print("mean real stock %.3f bond %.3f infl %.3f" % (stock_real.mean(), bond_real.mean(), infl.mean()))
    for H in (30, 50):
        for wr in (0.03, 0.035, 0.04, 0.045, 0.05):
            p, n = success(wr, H)
            print(f"H={H} wr={wr:.3f} success={p:.3f} n={n}")
    s = starts(30)
    ends = np.array([run(i, 0.04, 30)[-1] for i in s])
    fails = [years[i] for i in s if run(i, 0.04, 30)[-1] <= 0]
    print("4% 30y 60/40 failures:", fails)
    print("ending real multiple: median %.2f, p10 %.2f, min %.2f, frac >= 1x start %.2f" % (np.median(ends), np.percentile(ends, 10), ends.min(), np.mean(ends >= 1)))
    worst = s[int(np.argmin(ends))]
    print("worst start", years[worst], "end", ends.min())
    # max sustainable rate per start year
    def maxrate(i, H=30):
        lo, hi = 0.0, 0.2
        for _ in range(40):
            m = (lo + hi) / 2
            lo, hi = (m, hi) if run(i, m, H)[-1] > 0 else (lo, m)
        return lo
    mr = np.array([maxrate(i) for i in s])
    print("SAFEMAX 30y 60/40: min %.4f (%d), median %.4f" % (mr.min(), years[s[int(mr.argmin())]], np.median(mr)))
