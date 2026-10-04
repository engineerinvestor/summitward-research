"""Volatility targeting on the US stock market, July 1926 to May 2026.

Supports https://summitward.com/learn/volatility-targeting. Standard library
only. Reads Kenneth French's daily value-weighted market return and one-month
T-bill rate (data/us_market_daily.json) and writes results.json.

Conventions: the exposure for day t uses returns through day t-1. Volatility is
the sample standard deviation of daily excess returns times sqrt(252). Sharpe
ratios use daily excess returns over the T-bill rate. Cash earns the T-bill
rate; borrowed exposure pays the T-bill rate plus a spread. Trading cost is
charged on the absolute change in exposure.
"""

import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
raw = json.loads((HERE / "data" / "us_market_daily.json").read_text())
DATES = raw["dates"]
RET = [x / 1e4 for x in raw["returns_bp"]]
RF = [x / 1e4 for x in raw["rf_bp"]]
EX = [r - f for r, f in zip(RET, RF, strict=True)]
N = len(DATES)


def idx_of(date_int):
    """First index with DATES[i] >= date_int."""
    for i, d in enumerate(DATES):
        if d >= date_int:
            return i
    return N


def idx_end(date_int):
    """One past the last index with DATES[i] <= date_int."""
    for i in range(N - 1, -1, -1):
        if DATES[i] <= date_int:
            return i + 1
    return 0


def rolling_vol(lookback):
    """Annualized vol of daily excess returns over the trailing window ending at i."""
    out = [math.nan] * N
    s = s2 = 0.0
    for i in range(N):
        s += EX[i]
        s2 += EX[i] ** 2
        if i >= lookback:
            s -= EX[i - lookback]
            s2 -= EX[i - lookback] ** 2
        if i >= lookback - 1:
            var = (s2 - s * s / lookback) / (lookback - 1)
            out[i] = math.sqrt(max(var, 0.0) * 252)
    return out


def weights(lookback=21, target=0.12, cap=1.0, rebalance="daily", band=0.10):
    vol = rolling_vol(lookback)
    raw_w = [math.nan] * N
    for i in range(1, N):
        v = vol[i - 1]
        if not math.isnan(v) and v > 0:
            raw_w[i] = min(cap, target / v)
    w = [math.nan] * N
    cur = math.nan
    for i in range(N):
        x = raw_w[i]
        if math.isnan(x):
            continue
        if math.isnan(cur):
            cur = x
        elif rebalance == "daily":
            cur = x
        elif rebalance == "monthly":
            if DATES[i] // 100 != DATES[i - 1] // 100:
                cur = x
        elif rebalance == "band" and abs(x - cur) > band:
            cur = x
        w[i] = cur
    return w


def strategy(w, i0, i1, spread=0.015, cost_bp=5.0, excess_index=False):
    """Daily returns of exposure w on the market, rest in T-bills."""
    out = []
    prev = w[i0]
    for i in range(i0, i1):
        x = w[i]
        if excess_index:
            r = x * EX[i]
        else:
            r = x * RET[i] + (1 - x) * RF[i] - max(x - 1, 0) * spread / 252
        r -= abs(x - prev) * cost_bp / 1e4
        prev = x
        out.append(r)
    return out


def static(k, i0, i1):
    return [k * RET[i] + (1 - k) * RF[i] for i in range(i0, i1)]


def mean(xs):
    return sum(xs) / len(xs)


def stdev(xs):
    m = mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def metrics(rets, i0, w=None, excess=False):
    n = len(rets)
    years = n / 252
    wealth, peak, mdd = 1.0, 1.0, 0.0
    month_ret, months, cur_m = 1.0, [], DATES[i0] // 100
    for j, r in enumerate(rets):
        d = DATES[i0 + j]
        if d // 100 != cur_m:
            months.append(month_ret - 1)
            month_ret, cur_m = 1.0, d // 100
        month_ret *= 1 + r
        wealth *= 1 + r
        peak = max(peak, wealth)
        mdd = min(mdd, wealth / peak - 1)
    months.append(month_ret - 1)
    # An excess-return index already nets out the T-bill rate.
    ex = rets if excess else [r - RF[i0 + j] for j, r in enumerate(rets)]
    # vol-of-vol: std across month ends of trailing 63-day realized vol
    rv = []
    for j in range(63, n):
        if j + 1 == n or DATES[i0 + j] // 100 != DATES[i0 + j + 1] // 100:
            rv.append(stdev(rets[j - 62 : j + 1]) * math.sqrt(252))
    out = {
        "cagr": wealth ** (1 / years) - 1,
        "vol": stdev(rets) * math.sqrt(252),
        "sharpe": mean(ex) / stdev(ex) * math.sqrt(252),
        "max_drawdown": mdd,
        "worst_month": min(months),
        "vol_of_vol": stdev(rv) if len(rv) > 2 else math.nan,
        "growth_of_1": wealth,
    }
    if w is not None:
        ws = w[i0 : i0 + n]
        out["avg_exposure"] = mean(ws)
        out["max_exposure"] = max(ws)
        out["min_exposure"] = min(ws)
        out["turnover_per_year"] = (
            sum(abs(ws[j] - ws[j - 1]) for j in range(1, n)) / years
        )
    return out


def r4(d):
    return {k: round(v, 4) for k, v in d.items()}


def compare(w, start, end, **kw):
    i0, i1 = idx_of(start), idx_end(end)
    bh = metrics(RET[i0:i1], i0)
    vt_r = strategy(w, i0, i1, **kw)
    vt = metrics(vt_r, i0, w, excess=kw.get("excess_index", False))
    k = vt["vol"] / bh["vol"]
    st = metrics(static(k, i0, i1), i0)
    st["stock_weight"] = k
    return {"buy_hold": r4(bh), "vol_target": r4(vt), "static_vol_matched": r4(st)}


def episode(w, start, end, **kw):
    i0, i1 = idx_of(start), idx_end(end)
    bh = math.prod(1 + r for r in RET[i0:i1]) - 1
    vt = math.prod(1 + r for r in strategy(w, i0, i1, **kw)) - 1
    return {
        "buy_hold": round(bh, 4),
        "vol_target": round(vt, 4),
        "exposure_start": round(w[i0], 3),
        "exposure_min": round(min(w[i0:i1]), 3),
        "exposure_end": round(w[i1 - 1], 3),
    }


def moreira_muir(start=19270101, end=20260531):
    """Monthly inverse-variance scaling, full-sample c versus real-time c."""
    months = []  # (yyyymm, excess return, variance of daily excess returns)
    cur, comp, rf_comp, days = DATES[0] // 100, 1.0, 1.0, []
    for i in range(N):
        m = DATES[i] // 100
        if m != cur:
            months.append((cur, comp - rf_comp, stdev(days) ** 2))
            cur, comp, rf_comp, days = m, 1.0, 1.0, []
        comp *= 1 + RET[i]
        rf_comp *= 1 + RF[i]
        days.append(EX[i])
    months.append((cur, comp - rf_comp, stdev(days) ** 2))
    f = [m[1] for m in months]
    inv = [math.nan] + [1 / m[2] for m in months[:-1]]
    sel = [j for j, m in enumerate(months) if start // 100 <= m[0] <= end // 100]
    scaled = [f[j] * inv[j] for j in sel]
    c_full = stdev([f[j] for j in sel]) / stdev(scaled)
    full = [c_full * x for x in scaled]
    rt, wts, raw_rt, first = [], [], [], None
    for j in sel:
        past = [k for k in range(1, j) if not math.isnan(inv[k])]
        if len(past) < 120:
            continue
        c = stdev([f[k] for k in past]) / stdev([f[k] * inv[k] for k in past])
        wts.append(c * inv[j])
        rt.append(c * inv[j] * f[j])
        raw_rt.append(f[j])
        first = first or months[j][0]

    def sr(xs):
        return mean(xs) / stdev(xs) * math.sqrt(12)

    return {
        "sharpe_unmanaged": round(sr([f[j] for j in sel]), 3),
        "sharpe_full_sample_c": round(sr(full), 3),
        "max_weight_full_sample_c": round(max(c_full * inv[j] for j in sel), 2),
        "sharpe_unmanaged_realtime_window": round(sr(raw_rt), 3),
        "sharpe_real_time_c": round(sr(rt), 3),
        "max_weight_real_time_c": round(max(wts), 2),
        "real_time_window_start": first,
    }


def main():
    end = 20260531
    base = weights(21, 0.12, 1.0)
    res = {"data": raw["_metadata"]}
    res["main"] = {
        f"{s}-{e // 10000}": compare(base, s, e)
        for s, e in [
            (19270101, end),
            (19270101, 19991231),
            (20000101, end),
            (19360101, end),
            (19900101, end),
        ]
    }
    lev = weights(21, 0.16, 1.5)
    res["levered_t16_cap150_spread150"] = compare(lev, 19270101, end)
    res["levered_t16_cap150_spread50"] = compare(lev, 19270101, end, spread=0.005)
    res["excess_return_index_style"] = {
        "t10_cap150_from1995": compare(
            weights(21, 0.10, 1.5), 19950101, end, excess_index=True
        ),
        "t10_cap150_from1995_total_return": compare(
            weights(21, 0.10, 1.5), 19950101, end
        ),
    }
    grid = {}
    for lb in (21, 63, 126):
        for t in (0.08, 0.10, 0.12, 0.15):
            w = weights(lb, t, 1.0)
            a = compare(w, 19270101, end)["vol_target"]
            b = compare(w, 20000101, end)["vol_target"]
            grid[f"lb{lb}_t{int(t * 100)}"] = {
                "sharpe_1927": a["sharpe"],
                "sharpe_2000": b["sharpe"],
                "turnover_1927": a["turnover_per_year"],
            }
    res["robustness_grid"] = grid
    res["cost_sensitivity_sharpe_1927"] = {
        str(c): compare(base, 19270101, end, cost_bp=c)["vol_target"]["sharpe"]
        for c in (0, 5, 20, 50)
    }
    res["rebalance_variants_1927"] = {
        r: compare(weights(21, 0.12, 1.0, rebalance=r), 19270101, end)["vol_target"]
        for r in ("monthly", "band")
    }
    eps = {
        "1929_crash": (19290901, 19320630),
        "oct_1987": (19871001, 19871031),
        "gfc": (20071009, 20090309),
        "recovery_2009": (20090310, 20091231),
        "covid_crash": (20200220, 20200323),
        "covid_rebound": (20200324, 20200831),
        "feb_2018": (20180126, 20180208),
        "aug_2024": (20240716, 20240805),
        "year_2022": (20220101, 20221231),
        "year_2020": (20200101, 20201231),
    }
    res["episodes_t12_cap100"] = {k: episode(base, s, e) for k, (s, e) in eps.items()}
    # share of rolling 252-day windows with realized vol between 9% and 15%
    i0 = idx_of(19270101)
    r = strategy(base, i0, N)
    inside = total = 0
    for j in range(252, len(r)):
        v = stdev(r[j - 251 : j + 1]) * math.sqrt(252)
        total += 1
        inside += 0.09 < v < 0.15
    res["share_1y_vol_within_9_15"] = round(inside / total, 3)
    ws = base[i0:N]
    res["share_days_at_full_exposure"] = round(sum(x >= 0.999 for x in ws) / len(ws), 3)
    res["share_days_below_half"] = round(sum(x < 0.5 for x in ws) / len(ws), 3)
    res["moreira_muir_monthly"] = {
        "from_1927": moreira_muir(),
        "from_1936": moreira_muir(start=19360801),
        "from_2000": moreira_muir(start=20000101),
    }
    (HERE / "results.json").write_text(json.dumps(res, indent=2) + "\n")
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
