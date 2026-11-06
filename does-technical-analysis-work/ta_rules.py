"""Published moving-average trading rules on 100 years of daily US market data.

Supports https://summitward.com/learn/does-technical-analysis-work. Needs
numpy. Reads data/ (written by fetch_data.py) and writes results.json.

Data
- Market total return: Kenneth French daily Mkt-RF plus a daily T-bill rate.
- T-bill rate: French's monthly one-month T-bill return spread geometrically
  over each month's trading days. French's daily RF column is published to
  whole basis points, which misstates cash returns by up to a point a year.
- Price index for signals: total return minus Shiller's monthly S&P dividend
  yield (D/12/P) spread evenly over the month's trading days. Signals use this
  price index, as Brock, Lakonishok and LeBaron (1992) and practitioners do;
  returns use total return. A total-return-signal variant is reported too.

Rules (fixed in advance, not tuned)
- BLL's ten variable-length moving-average rules: short/long of 1/50, 1/150,
  5/150, 1/200, 2/200, each with a 0% and a 1% band. Long the market when the
  short average is above the long average by more than the band, in T-bills
  when below it by more than the band, otherwise keep the prior position.
- The 50/200-day "golden cross" (same mechanics, no band).
- Faber's 10-month rule: month-end price above its 10-month average.
- 12-month time-series momentum: trailing 12 calendar months of market return
  above the T-bill return over the same months, checked at month end.

Conventions
- A signal is computed from the close of day t. Primary ("next close"): the
  trade happens at the close of day t+1, so the first return earned is day
  t+2's. Sensitivity ("same close"): the first return earned is day t+1's.
- Trading cost is charged on the absolute change in market exposure. Primary
  cost 5 basis points; 0, 10 and 25 are also reported.
- CAGR uses calendar years. Volatility and Sharpe ratios annualize with the
  window's actual trading days per year (the data has Saturday sessions
  through May 1952, so a fixed 252 understates early annual figures).
- Moving-average lengths are counted in trading days, as BLL did.
- Benchmarks: buy and hold; a static stock/T-bill mix with the rule's average
  exposure (exposure-matched); a static mix with the rule's realized
  volatility (vol-matched). Static mixes rebalance daily at no cost and their
  weights use hindsight over the window.
- Uncertainty: stationary block bootstrap (Politis-Romano) of paired days,
  2,000 draws, mean block lengths of 63 and 250 days plus the Politis-White
  automatic choice; White's Reality Check across the rule set per window.
"""

import csv
import json
import math
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
SEED = 20261105
DRAWS = 2000
PRIMARY_COST = 0.0005
COSTS = [0.0, 0.0005, 0.0010, 0.0025]

RULES = [
    ("1-50", 1, 50, 0.0),
    ("1-50 1%", 1, 50, 0.01),
    ("1-150", 1, 150, 0.0),
    ("1-150 1%", 1, 150, 0.01),
    ("5-150", 5, 150, 0.0),
    ("5-150 1%", 5, 150, 0.01),
    ("1-200", 1, 200, 0.0),
    ("1-200 1%", 1, 200, 0.01),
    ("2-200", 2, 200, 0.0),
    ("2-200 1%", 2, 200, 0.01),
    ("50-200 golden cross", 50, 200, 0.0),
]
MONTHLY_RULES = ["Faber 10-month", "12-month trend"]
BLL = [r[0] for r in RULES[:10]]

WINDOWS = [
    ("1928-1986", 19280101, 19861231),
    ("1933-1986", 19330101, 19861231),
    ("1962-2011", 19620101, 20111231),
    ("1987-1996", 19870101, 19961231),
    ("1987-2026", 19870101, 99991231),
    ("1993-2026", 19930101, 99991231),
    ("2013-2026", 20130101, 99991231),
    ("1928-2026", 19280101, 99991231),
]

GRID_SHORT = [1, 2, 5, 10, 20]
GRID_LONG = [50, 100, 150, 200, 250, 300]

TAX_START = 19930101
TAX_RATES = {
    "32% bracket + NIIT": {"ordinary": 0.358, "ltcg": 0.188, "qdiv": 0.188},
    "24% bracket, no NIIT": {"ordinary": 0.24, "ltcg": 0.15, "qdiv": 0.15},
}


# ---------------------------------------------------------------- data


def read_french_daily():
    dates, mkt_rf, rf = [], [], []
    with (DATA / "F-F_Research_Data_Factors_daily.csv").open() as f:
        for row in csv.reader(f):
            if len(row) >= 5 and row[0].strip().isdigit() and len(row[0].strip()) == 8:
                dates.append(int(row[0]))
                mkt_rf.append(float(row[1]) / 100)
                rf.append(float(row[4]) / 100)
    return np.array(dates), np.array(mkt_rf), np.array(rf)


def read_french_monthly_rf():
    out = {}
    with (DATA / "F-F_Research_Data_Factors.csv").open() as f:
        for row in csv.reader(f):
            if not row:
                continue
            key = row[0].strip()
            if "Annual" in key:
                break
            if key.isdigit() and len(key) == 6:
                out[int(key)] = float(row[4]) / 100
    return out


def read_shiller():
    out = {}
    with (DATA / "shiller_monthly.csv").open() as f:
        for row in csv.DictReader(f):
            out[(int(row["year"]), int(row["month"]))] = (
                float(row["P"]),
                float(row["D"]),
            )
    return out


def load():
    dates, mkt_rf, _rf_rounded = read_french_daily()
    rf_m = read_french_monthly_rf()
    shiller = read_shiller()
    ym = dates // 100
    months, counts = np.unique(ym, return_counts=True)
    ndays = dict(zip(months.tolist(), counts.tolist(), strict=True))
    last_rf = max(rf_m)
    rf = np.array(
        [(1 + rf_m[m if m in rf_m else last_rf]) ** (1 / ndays[m]) - 1 for m in ym]
    )
    tr = mkt_rf + rf
    div = np.array(
        [
            shiller[(m // 100, m % 100)][1]
            / 12
            / shiller[(m // 100, m % 100)][0]
            / ndays[m]
            for m in ym
        ]
    )
    pr = (1 + tr) / (1 + div) - 1
    pydates = [date(d // 10000, d // 100 % 100, d % 100) for d in dates]
    return {
        "dates": dates,
        "pydates": pydates,
        "tr": tr,
        "rf": rf,
        "div": div,
        "pr": pr,
        "rf_months_missing": sorted({int(m) for m in ym if m not in rf_m}),
    }


# ---------------------------------------------------------------- signals


def sma(x, n):
    c = np.concatenate([[0.0], np.cumsum(x)])
    out = np.full(len(x), np.nan)
    out[n - 1 :] = (c[n:] - c[:-n]) / n
    return out


def ma_signal(level, short, long, band):
    """1 = long the market after the close of day t, 0 = T-bills."""
    a, b = sma(level, short), sma(level, long)
    sig = np.ones(len(level), dtype=np.int8)
    state = 1
    for t in range(len(level)):
        if not math.isnan(b[t]):
            if a[t] > b[t] * (1 + band):
                state = 1
            elif a[t] < b[t] * (1 - band):
                state = 0
        sig[t] = state
    return sig


def month_end_index(dates):
    ym = dates // 100
    return np.flatnonzero(np.r_[ym[1:] != ym[:-1], True])


def faber_signal(level, dates):
    me = month_end_index(dates)
    lv = level[me]
    avg = sma(lv, 10)
    sig = np.ones(len(level), dtype=np.int8)
    state = 1
    for k, t in enumerate(me):
        if not math.isnan(avg[k]):
            state = 1 if lv[k] > avg[k] else 0
        end = me[k + 1] if k + 1 < len(me) else len(level) - 1
        sig[t : end + 1] = state
    return sig


def trend_signal(tr_level, cash_level, dates):
    me = month_end_index(dates)
    sig = np.ones(len(tr_level), dtype=np.int8)
    state = 1
    for k, t in enumerate(me):
        if k >= 12:
            j = me[k - 12]
            mkt = tr_level[t] / tr_level[j]
            cash = cash_level[t] / cash_level[j]
            state = 1 if mkt > cash else 0
        end = me[k + 1] if k + 1 < len(me) else len(tr_level) - 1
        sig[t : end + 1] = state
    return sig


def position(sig, lag):
    """Exposure earning day t's return. lag=1: next close; lag=0: same close."""
    shift = 1 + lag
    pos = np.ones(len(sig), dtype=np.float64)
    pos[shift:] = sig[:-shift]
    return pos


def all_signals(d, signal_level):
    sigs = {}
    for name, s, l_, b in RULES:
        sigs[name] = ma_signal(signal_level, s, l_, b)
    sigs["Faber 10-month"] = faber_signal(signal_level, d["dates"])
    tr_level = np.cumprod(1 + d["tr"])
    cash_level = np.cumprod(1 + d["rf"])
    sigs["12-month trend"] = trend_signal(tr_level, cash_level, d["dates"])
    return sigs


def strat_returns(pos, d, cost):
    trade = np.abs(np.diff(pos, prepend=pos[0]))
    return pos * d["tr"] + (1 - pos) * d["rf"] - cost * trade


# ---------------------------------------------------------------- metrics


def years_between(d0, d1):
    return ((d1 - d0).days + 1) / 365.25


def cagr(r, yrs):
    return float(np.exp(np.sum(np.log1p(r)) / yrs) - 1)


def max_dd(r):
    w = np.cumprod(1 + r)
    peak = np.maximum.accumulate(w)
    return float(np.min(w / peak - 1))


def spells(pos, pydates):
    """Holding spells (entry index, exit index exclusive) where pos == 1."""
    out = []
    start = None
    for t, p in enumerate(pos):
        if p == 1 and start is None:
            start = t
        elif p == 0 and start is not None:
            out.append((start, t))
            start = None
    if start is not None:
        out.append((start, len(pos)))
    return out


def metrics(r, rf, pos, pydates):
    n = len(r)
    yrs = years_between(pydates[0], pydates[-1])
    per_year = n / yrs
    ex = r - rf
    sp = spells(pos, pydates)
    exits = sum(1 for _, e in sp if e < n)
    closed = [(s, e) for s, e in sp if e < n]
    short = sum(1 for s, e in closed if (pydates[e - 1] - pydates[s]).days + 1 <= 365)
    return {
        "cagr": cagr(r, yrs),
        "vol": float(np.std(r, ddof=1) * math.sqrt(per_year)),
        "sharpe": float(np.mean(ex) / np.std(ex, ddof=1) * math.sqrt(per_year)),
        "max_dd": max_dd(r),
        "exposure": float(np.mean(pos)),
        "exits_per_year": exits / yrs,
        "short_spell_share": (short / len(closed)) if closed else None,
        "years": yrs,
        "days": n,
    }


def vol_match_weight(target_vol, tr, rf):
    lo, hi = 0.0, 2.0
    for _ in range(60):
        mid = (lo + hi) / 2
        v = np.std(mid * tr + (1 - mid) * rf, ddof=1)
        if v < target_vol:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


# ---------------------------------------------------------------- bootstrap


def sb_indices(rng, n, block):
    starts = rng.random(n) < 1.0 / block
    starts[0] = True
    rand_pos = rng.integers(0, n, size=n)
    ar = np.arange(n)
    last = np.maximum.accumulate(np.where(starts, ar, 0))
    return (rand_pos[last] + (ar - last)) % n


def politis_white(x):
    """Politis-White (2004) automatic mean block length for the stationary
    bootstrap, with the Patton-Politis-White (2009) correction."""
    x = np.asarray(x, dtype=float)
    n = len(x)
    x = x - x.mean()
    kn = max(5, int(math.ceil(math.sqrt(math.log10(n)))))
    mmax = int(math.ceil(math.sqrt(n))) + kn
    crit = 2.0 * math.sqrt(math.log10(n) / n)
    acov = np.array([np.dot(x[: n - k], x[k:]) / n for k in range(mmax + 1)])
    rho = acov[1:] / acov[0]
    mhat = mmax - kn
    for m in range(0, mmax - kn + 1):
        if np.all(np.abs(rho[m : m + kn]) < crit):
            mhat = m
            break
    big_m = min(2 * max(mhat, 1), mmax)
    ks = np.arange(-big_m, big_m + 1)
    t = np.abs(ks / big_m)
    lam = np.where(t <= 0.5, 1.0, np.where(t <= 1.0, 2 * (1 - t), 0.0))
    r_k = acov[np.abs(ks)]
    g = np.sum(lam * np.abs(ks) * r_k)
    d_sb = 2 * np.sum(lam * r_k) ** 2
    b = (2 * g**2 / d_sb) ** (1 / 3) * n ** (1 / 3)
    bmax = math.ceil(min(3 * math.sqrt(n), n / 3))
    return float(min(max(b, 1.0), bmax))


def bootstrap_window(rets, pos, tr, rf, yrs, block, rng):
    """90% intervals on CAGR edge vs buy and hold and vs the exposure-matched
    mix, plus White's Reality Check p-values against each benchmark."""
    names = list(rets)
    r = np.vstack([rets[k] for k in names])
    p = np.vstack([pos[k] for k in names])
    n = r.shape[1]
    lr = np.log1p(r)
    lbh = np.log1p(tr)
    w_full = p.mean(axis=1, keepdims=True)
    lmix_full = np.log1p(w_full * tr + (1 - w_full) * rf)
    f_bh = lr - lbh
    f_mix = lr - lmix_full
    v_bh = math.sqrt(n) * f_bh.mean(axis=1).max()
    v_mix = math.sqrt(n) * f_mix.mean(axis=1).max()
    sub = np.array([names.index(k) for k in BLL])
    v_bh_sub = math.sqrt(n) * f_bh[sub].mean(axis=1).max()
    v_mix_sub = math.sqrt(n) * f_mix[sub].mean(axis=1).max()
    mu_bh = f_bh.mean(axis=1)
    mu_mix = f_mix.mean(axis=1)
    e_bh = np.empty((DRAWS, len(names)))
    e_mix = np.empty((DRAWS, len(names)))
    e_vol = np.empty((DRAWS, len(names)))
    rc_bh = np.empty(DRAWS)
    rc_mix = np.empty(DRAWS)
    rc_bh_sub = np.empty(DRAWS)
    rc_mix_sub = np.empty(DRAWS)
    for b in range(DRAWS):
        idx = sb_indices(rng, n, block)
        s_rule = lr[:, idx].sum(axis=1)
        s_bh = lbh[idx].sum()
        w = p[:, idx].mean(axis=1, keepdims=True)
        s_mix = np.log1p(w * tr[idx] + (1 - w) * rf[idx]).sum(axis=1)
        g_rule = np.exp(s_rule / yrs) - 1
        e_bh[b] = g_rule - (math.exp(s_bh / yrs) - 1)
        e_mix[b] = g_rule - (np.exp(s_mix / yrs) - 1)
        wv = (r[:, idx].std(axis=1, ddof=1) / tr[idx].std(ddof=1))[:, None]
        s_vmix = np.log1p(wv * tr[idx] + (1 - wv) * rf[idx]).sum(axis=1)
        e_vol[b] = g_rule - (np.exp(s_vmix / yrs) - 1)
        d_bh = f_bh[:, idx].mean(axis=1) - mu_bh
        d_mix = f_mix[:, idx].mean(axis=1) - mu_mix
        rc_bh[b] = math.sqrt(n) * d_bh.max()
        rc_mix[b] = math.sqrt(n) * d_mix.max()
        rc_bh_sub[b] = math.sqrt(n) * d_bh[sub].max()
        rc_mix_sub[b] = math.sqrt(n) * d_mix[sub].max()
    out = {}
    for i, k in enumerate(names):
        out[k] = {
            "bh": [
                float(np.percentile(e_bh[:, i], 5)),
                float(np.percentile(e_bh[:, i], 95)),
            ],
            "exp": [
                float(np.percentile(e_mix[:, i], 5)),
                float(np.percentile(e_mix[:, i], 95)),
            ],
            "vol": [
                float(np.percentile(e_vol[:, i], 5)),
                float(np.percentile(e_vol[:, i], 95)),
            ],
        }
    pvals = {
        "bh": float(np.mean(rc_bh >= v_bh)),
        "exp": float(np.mean(rc_mix >= v_mix)),
        "bh_bll": float(np.mean(rc_bh_sub >= v_bh_sub)),
        "exp_bll": float(np.mean(rc_mix_sub >= v_mix_sub)),
    }
    return out, pvals


# ---------------------------------------------------------------- tax


def after_tax(pos, d, i0, i1, cost, rates, start_value=100_000.0):
    """Single-lot taxable account in a total-market fund, T-bills when out.

    Exits realize the gain (short-term if held 365 days or less, counting any
    holding period carried over by a wash sale). A loss exit followed by
    re-entry within 30 days is a wash sale: the loss is disallowed, added to
    the new basis, and the old holding period carries over. Dividends are
    reinvested; dividends earned in a holding spell shorter than 61 days are
    taxed as ordinary income. T-bill interest is ordinary income. Each year's
    tax is paid on the first trading day of April the next year, out of the
    position (a pro-rata reduction of value and basis; the small gain such a
    sale would realize is ignored). Capital losses net short against long and
    carry forward; the $3,000 ordinary-income offset is ignored."""
    pyd = d["pydates"]
    pr, dv, rf = d["pr"], d["div"], d["rf"]
    p = pos[i0:i1]
    n = i1 - i0
    sp = spells(p, None)
    spell_len = np.zeros(n)
    for s, e in sp:
        end_day = pyd[i0 + e - 1]
        spell_len[s:e] = (end_day - pyd[i0 + s]).days + 1
    book = {}

    def yr(y):
        return book.setdefault(
            y, {"st": 0.0, "lt": 0.0, "qdiv": 0.0, "odiv": 0.0, "int": 0.0}
        )

    cf = {"st": 0.0, "lt": 0.0}
    paid_years = set()
    value = basis = 0.0
    cash = 0.0
    entry = None
    pending = None
    wash_n = 0
    wash_amt = 0.0
    loss_exits = 0
    taxes_paid = 0.0
    gains_st = gains_lt = 0.0
    if p[0] == 1:
        value = basis = start_value
        entry = pyd[i0] - timedelta(days=1)
    else:
        cash = start_value

    def net_tax(st, lt):
        st += cf["st"]
        lt += cf["lt"]
        st_t = lt_t = 0.0
        new_cf = {"st": 0.0, "lt": 0.0}
        if st >= 0 and lt >= 0:
            st_t, lt_t = st, lt
        elif st < 0 and lt < 0:
            new_cf = {"st": st, "lt": lt}
        elif st < 0:
            net = lt + st
            if net >= 0:
                lt_t = net
            else:
                new_cf["st"] = net
        else:
            net = st + lt
            if net >= 0:
                st_t = net
            else:
                new_cf["lt"] = net
        return st_t, lt_t, new_cf

    def settle(y):
        nonlocal value, basis, cash, taxes_paid
        if y in paid_years:
            return
        paid_years.add(y)
        b = yr(y)
        st_t, lt_t, new_cf = net_tax(b["st"], b["lt"])
        cf.update(new_cf)
        tax = (
            st_t * rates["ordinary"]
            + lt_t * rates["ltcg"]
            + b["qdiv"] * rates["qdiv"]
            + (b["odiv"] + b["int"]) * rates["ordinary"]
        )
        taxes_paid += tax
        if value > 0:
            frac = max(0.0, 1 - tax / value)
            value *= frac
            basis *= frac
        else:
            cash -= tax

    def book_loss(pl):
        yr(pl["year"])[pl["term"]] += pl["loss"]

    for t in range(n):
        today = pyd[i0 + t]
        prev = pyd[i0 + t - 1] if i0 + t - 1 >= 0 else today
        if pending is not None and (prev - pending["date"]).days > 30:
            book_loss(pending)
            pending = None
        if t > 0 and p[t] != p[t - 1]:
            if p[t] == 0:
                proceeds = value * (1 - cost)
                gain = proceeds - basis
                held = (prev - entry).days
                term = "lt" if held > 365 else "st"
                if gain >= 0:
                    yr(prev.year)[term] += gain
                    if term == "st":
                        gains_st += gain
                    else:
                        gains_lt += gain
                else:
                    loss_exits += 1
                    pending = {
                        "loss": gain,
                        "term": term,
                        "date": prev,
                        "year": prev.year,
                        "held": held,
                    }
                cash = proceeds
                value = basis = 0.0
                entry = None
            else:
                amount = cash * (1 - cost)
                value = basis = amount
                cash = 0.0
                entry = prev
                if pending is not None and (prev - pending["date"]).days <= 30:
                    basis += -pending["loss"]
                    entry = prev - timedelta(days=pending["held"])
                    wash_n += 1
                    wash_amt += -pending["loss"]
                    pending = None
        if (
            today.month >= 4
            and (today.year - 1) not in paid_years
            and today.year - 1 >= pyd[i0].year
        ):
            settle(today.year - 1)
        if p[t] == 1:
            dvd = value * dv[i0 + t]
            key = "qdiv" if spell_len[t] >= 61 else "odiv"
            yr(today.year)[key] += dvd
            value = value * (1 + pr[i0 + t]) + dvd
            basis += dvd
        else:
            interest = cash * rf[i0 + t]
            yr(today.year)["int"] += interest
            cash += interest
    last = pyd[i1 - 1]
    if pending is not None:
        book_loss(pending)
    for y in sorted(book):
        if y not in paid_years:
            settle(y)
    unliquidated = value + cash
    liquidated = unliquidated
    if value > 0:
        gain = value - basis
        held = (last - entry).days
        term = "lt" if held > 365 else "st"
        st_t, lt_t, _ = net_tax(
            gain if term == "st" else 0.0, gain if term == "lt" else 0.0
        )
        liquidated = value + cash - st_t * rates["ordinary"] - lt_t * rates["ltcg"]
    total_gains = gains_st + gains_lt
    return {
        "unliquidated": unliquidated,
        "liquidated": liquidated,
        "taxes_paid": taxes_paid,
        "wash_sales": wash_n,
        "loss_exits": loss_exits,
        "wash_sale_losses_deferred": wash_amt,
        "short_term_share_of_realized_gains": (gains_st / total_gains)
        if total_gains > 0
        else None,
    }


# ---------------------------------------------------------------- main


def window_idx(dates, start, end):
    i0 = int(np.searchsorted(dates, start, side="left"))
    i1 = int(np.searchsorted(dates, end, side="right"))
    return i0, i1


def r4(x):
    if isinstance(x, dict):
        return {k: r4(v) for k, v in x.items()}
    if isinstance(x, list):
        return [r4(v) for v in x]
    if isinstance(x, float):
        return round(x, 6)
    return x


def evaluate(d, pos_by_rule, cost, windows, with_bootstrap=False, rng=None):
    out = {}
    tr, rf, pyd, dates = d["tr"], d["rf"], d["pydates"], d["dates"]
    for wname, ws, we in windows:
        i0, i1 = window_idx(dates, ws, we)
        trw, rfw, pyw = tr[i0:i1], rf[i0:i1], pyd[i0:i1]
        bh = metrics(trw, rfw, np.ones(i1 - i0), pyw)
        rows = {}
        rets_w, pos_w = {}, {}
        for name, pos in pos_by_rule.items():
            r = strat_returns(pos, d, cost)[i0:i1]
            pw = pos[i0:i1]
            m = metrics(r, rfw, pw, pyw)
            w_exp = m["exposure"]
            mix = w_exp * trw + (1 - w_exp) * rfw
            w_vol = vol_match_weight(np.std(r, ddof=1), trw, rfw)
            vmix = w_vol * trw + (1 - w_vol) * rfw
            m["edge_bh"] = m["cagr"] - bh["cagr"]
            m["edge_exp"] = m["cagr"] - cagr(mix, m["years"])
            m["edge_vol"] = m["cagr"] - cagr(vmix, m["years"])
            m["vol_match_weight"] = w_vol
            m["exp_mix_max_dd"] = max_dd(mix)
            m["vol_mix_max_dd"] = max_dd(vmix)
            m["sharpe_minus_bh"] = m["sharpe"] - bh["sharpe"]
            rows[name] = m
            rets_w[name] = r
            pos_w[name] = pw
        entry = {"buy_hold": bh, "rules": rows}
        if with_bootstrap:
            diff = np.log1p(rets_w["1-200"]) - np.log1p(trw)
            pw_len = politis_white(diff)
            entry["pw_block"] = pw_len
            entry["ci"] = {}
            entry["reality_check"] = {}
            for label, block in (("63", 63), ("250", 250), ("pw", pw_len)):
                ci, pvals = bootstrap_window(
                    rets_w, pos_w, trw, rfw, bh["years"], block, rng
                )
                entry["ci"][label] = ci
                entry["reality_check"][label] = pvals
        out[wname] = entry
    return out


def autocorr(d):
    out = {}
    for name, s, e in (
        ("1928-1961", 19280101, 19611231),
        ("1962-1986", 19620101, 19861231),
        ("1987-2026", 19870101, 99991231),
    ):
        i0, i1 = window_idx(d["dates"], s, e)
        x = d["tr"][i0:i1] - d["tr"][i0:i1].mean()
        out[name] = {
            "lag1": float(np.dot(x[:-1], x[1:]) / np.dot(x, x)),
            "lag2": float(np.dot(x[:-2], x[2:]) / np.dot(x, x)),
        }
    return out


def grid_check(d, level):
    i0, i1 = window_idx(d["dates"], 19280101, 19861231)
    j0, j1 = window_idx(d["dates"], 19870101, 99991231)
    tr, rf, pyd = d["tr"], d["rf"], d["pydates"]
    bh_in = cagr(tr[i0:i1], years_between(pyd[i0], pyd[i1 - 1]))
    yrs_out = years_between(pyd[j0], pyd[j1 - 1])
    bh_out = cagr(tr[j0:j1], yrs_out)
    cells = []
    for s in GRID_SHORT:
        for l_ in GRID_LONG:
            pos = position(ma_signal(level, s, l_, 0.0), 1)
            r = strat_returns(pos, d, PRIMARY_COST)
            yrs_in = years_between(pyd[i0], pyd[i1 - 1])
            e_in = cagr(r[i0:i1], yrs_in) - bh_in
            w = float(np.mean(pos[j0:j1]))
            mix = w * tr[j0:j1] + (1 - w) * rf[j0:j1]
            e_out = cagr(r[j0:j1], yrs_out) - bh_out
            e_out_exp = cagr(r[j0:j1], yrs_out) - cagr(mix, yrs_out)
            cells.append(
                {
                    "short": s,
                    "long": l_,
                    "edge_in": e_in,
                    "edge_out": e_out,
                    "edge_out_exp": e_out_exp,
                }
            )
    best = max(cells, key=lambda c: c["edge_in"])
    return {
        "cells": cells,
        "winner": best,
        "median_edge_in": float(np.median([c["edge_in"] for c in cells])),
        "median_edge_out": float(np.median([c["edge_out"] for c in cells])),
        "median_edge_out_exp": float(np.median([c["edge_out_exp"] for c in cells])),
        "best_out": max(cells, key=lambda c: c["edge_out"]),
        "winner_rank_out": 1
        + sorted([c["edge_out"] for c in cells], reverse=True).index(best["edge_out"]),
    }


def rolling_edges(d, pos_by_rule, years=10):
    """Trailing 10-year CAGR edge vs buy and hold and vs an exposure-matched
    mix (weight = the rule's average exposure in that window), at month ends
    from 1938, for the 1-200 rule and the median of BLL's ten rules."""
    dates, pyd, tr, rf = d["dates"], d["pydates"], d["tr"], d["rf"]
    me = month_end_index(dates)
    names = BLL
    r = np.vstack([strat_returns(pos_by_rule[k], d, PRIMARY_COST) for k in names])
    p = np.vstack([pos_by_rule[k] for k in names])
    lr = np.log1p(r)
    lbh = np.log1p(tr)
    i200 = names.index("1-200")
    out = []
    for t in me:
        if dates[t] < 19371231:
            continue
        start = date(pyd[t].year - years, pyd[t].month, 1)
        i0 = int(np.searchsorted(dates, int(start.strftime("%Y%m%d")), side="left"))
        yrs = years_between(pyd[i0], pyd[t])
        g_rule = np.exp(lr[:, i0 : t + 1].sum(axis=1) / yrs) - 1
        g_bh = math.exp(lbh[i0 : t + 1].sum() / yrs) - 1
        w = p[:, i0 : t + 1].mean(axis=1, keepdims=True)
        g_mix = (
            np.exp(
                np.log1p(w * tr[i0 : t + 1] + (1 - w) * rf[i0 : t + 1]).sum(axis=1)
                / yrs
            )
            - 1
        )
        e_bh = g_rule - g_bh
        e_exp = g_rule - g_mix
        out.append(
            {
                "date": int(dates[t] // 100),
                "rule200_bh": round(float(e_bh[i200]), 5),
                "rule200_exp": round(float(e_exp[i200]), 5),
                "median_bh": round(float(np.median(e_bh)), 5),
                "median_exp": round(float(np.median(e_exp)), 5),
            }
        )
    return out


EPISODES = [
    ("1987 crash", 19870825, 19871204),
    ("2000-02 bear market", 20000324, 20021009),
    ("2008-09 bear market", 20071009, 20090309),
    ("2020 COVID crash", 20200219, 20200323),
    ("2022 bear market", 20220103, 20221012),
]


def episodes(d, pos_by_rule):
    """Market peak-to-trough windows: buy-and-hold vs rule return over the
    decline and over the 12 months after the trough (primary conventions)."""
    out = []
    dates, pyd = d["dates"], d["pydates"]
    names = ["1-200", "50-200 golden cross", "Faber 10-month", "12-month trend"]
    rets = {k: strat_returns(pos_by_rule[k], d, PRIMARY_COST) for k in names}
    for label, a, b in EPISODES:
        i0, i1 = window_idx(dates, a + 1, b)
        after_end = int(
            (date(pyd[i1 - 1].year + 1, pyd[i1 - 1].month, pyd[i1 - 1].day)).strftime(
                "%Y%m%d"
            )
        )
        j0, j1 = window_idx(dates, b + 1, after_end)
        row = {
            "episode": label,
            "start": a,
            "end": b,
            "bh_decline": float(np.prod(1 + d["tr"][i0:i1]) - 1),
            "bh_next_12m": float(np.prod(1 + d["tr"][j0:j1]) - 1),
        }
        for k in names:
            row[k] = {
                "decline": float(np.prod(1 + rets[k][i0:i1]) - 1),
                "next_12m": float(np.prod(1 + rets[k][j0:j1]) - 1),
            }
        out.append(row)
    return out


def web_export(res):
    """Compact subset for web/src/data/technical-analysis-results.json."""
    main = [
        "1928-1986",
        "1933-1986",
        "1962-2011",
        "1987-1996",
        "1987-2026",
        "1993-2026",
        "2013-2026",
    ]
    eras = {}
    for w in main:
        e = res["primary"][w]
        rules = e["rules"]
        bll = [rules[k] for k in BLL]
        eras[w] = {
            "bh_cagr": e["buy_hold"]["cagr"],
            "bll_median_edge_bh": float(np.median([m["edge_bh"] for m in bll])),
            "bll_median_edge_exp": float(np.median([m["edge_exp"] for m in bll])),
            "bll_median_edge_vol": float(np.median([m["edge_vol"] for m in bll])),
            "bll_min_edge_bh": min(m["edge_bh"] for m in bll),
            "bll_max_edge_bh": max(m["edge_bh"] for m in bll),
            "bll_positive_exp": sum(1 for m in bll if m["edge_exp"] > 0),
            "bll_ci_exp_above_zero": sum(
                1 for k in BLL if e["ci"]["63"][k]["exp"][0] > 0
            ),
            "bll_ci_exp_below_zero": sum(
                1 for k in BLL if e["ci"]["63"][k]["exp"][1] < 0
            ),
            "bll_median_edge_bh_same_close": float(
                np.median([res["same_close"][w]["rules"][k]["edge_bh"] for k in BLL])
            ),
            "rc_exp": e["reality_check"]["63"]["exp_bll"],
            "rc_bh": e["reality_check"]["63"]["bh_bll"],
            "rc_exp_all13": e["reality_check"]["63"]["exp"],
            "rc_bh_all13": e["reality_check"]["63"]["bh"],
            "rules": {
                k: {
                    "cagr": rules[k]["cagr"],
                    "exposure": rules[k]["exposure"],
                    "exits_per_year": rules[k]["exits_per_year"],
                    "edge_bh": rules[k]["edge_bh"],
                    "edge_exp": rules[k]["edge_exp"],
                    "edge_vol": rules[k]["edge_vol"],
                    "ci_bh": e["ci"]["63"][k]["bh"],
                    "ci_exp": e["ci"]["63"][k]["exp"],
                    "ci_vol": e["ci"]["63"][k]["vol"],
                    "max_dd": rules[k]["max_dd"],
                    "exp_mix_max_dd": rules[k]["exp_mix_max_dd"],
                    "vol_mix_max_dd": rules[k]["vol_mix_max_dd"],
                    "sharpe": rules[k]["sharpe"],
                }
                for k in [
                    "1-200",
                    "50-200 golden cross",
                    "Faber 10-month",
                    "12-month trend",
                    "1-50",
                ]
            },
            "bh": {
                "max_dd": e["buy_hold"]["max_dd"],
                "sharpe": e["buy_hold"]["sharpe"],
            },
        }
    tax = res["tax"]["after_tax"]["32% bracket + NIIT"]
    return r4(
        {
            "_metadata": {
                "source": "summitward-research/does-technical-analysis-work/ta_rules.py",
                "first_day": res["_metadata"]["first_day"],
                "last_day": res["_metadata"]["last_day"],
                "conventions": res["_metadata"]["primary"],
            },
            "autocorr": res["autocorr"],
            "eras": eras,
            "grid": {k: v for k, v in res["grid"].items() if k != "cells"},
            "tax": {
                k: {
                    "pre_tax": res["tax"]["pre_tax"][k],
                    "after_tax": tax[k]["liquidated"],
                    "after_tax_cagr": tax[k]["after_tax_cagr"],
                    "after_tax_alt": res["tax"]["after_tax"]["24% bracket, no NIIT"][k][
                        "liquidated"
                    ],
                    "wash_sales": tax[k]["wash_sales"],
                    "loss_exits": tax[k]["loss_exits"],
                    "st_share": tax[k]["short_term_share_of_realized_gains"],
                }
                for k in [
                    "Buy and hold",
                    "1-200",
                    "50-200 golden cross",
                    "Faber 10-month",
                    "12-month trend",
                    "1-50",
                ]
            },
            "episodes": res["episodes"],
            "rolling": [x for x in res["rolling"] if x["date"] % 100 in (3, 6, 9, 12)],
        }
    )


def gspc_check(d, sigs_price, sigs_tr):
    path = HERE / ".cache" / "gspc_daily.csv"
    if not path.exists():
        return None
    g = {}
    with path.open() as f:
        for row in csv.DictReader(f):
            g[int(row["date"])] = float(row["close"])
    common = [i for i, dt in enumerate(d["dates"]) if dt in g]
    lv = np.array([g[d["dates"][i]] for i in common])
    gs = ma_signal(lv, 1, 200, 0.0)
    idx = np.array(common)
    keep = slice(250, None)
    return {
        "days": int(len(common) - 250),
        "agree_price_signal": float(
            np.mean(gs[keep] == sigs_price["1-200"][idx][keep])
        ),
        "agree_tr_signal": float(np.mean(gs[keep] == sigs_tr["1-200"][idx][keep])),
    }


def main():
    quick = "--quick" in sys.argv
    d = load()
    rng = np.random.default_rng(SEED)
    price_level = np.cumprod(1 + d["pr"])
    tr_level = np.cumprod(1 + d["tr"])
    sigs = all_signals(d, price_level)
    sigs_tr = all_signals(d, tr_level)
    pos1 = {k: position(v, 1) for k, v in sigs.items()}
    pos0 = {k: position(v, 0) for k, v in sigs.items()}
    pos_tr = {k: position(v, 1) for k, v in sigs_tr.items()}

    res = {
        "_metadata": {
            "guide": "https://summitward.com/learn/does-technical-analysis-work",
            "first_day": int(d["dates"][0]),
            "last_day": int(d["dates"][-1]),
            "rf_months_missing_filled_with_last": d["rf_months_missing"],
            "primary": "next-close execution, 5 bp per unit of exposure traded, price-index signals",
            "draws": DRAWS,
            "seed": SEED,
        },
        "autocorr": autocorr(d),
    }
    res["primary"] = evaluate(
        d, pos1, PRIMARY_COST, WINDOWS, with_bootstrap=not quick, rng=rng
    )
    res["costs"] = {f"{round(c * 1e4)}bp": evaluate(d, pos1, c, WINDOWS) for c in COSTS}
    res["same_close"] = evaluate(d, pos0, PRIMARY_COST, WINDOWS)
    res["same_close_zero_cost"] = evaluate(d, pos0, 0.0, WINDOWS)
    res["tr_signal"] = evaluate(d, pos_tr, PRIMARY_COST, WINDOWS)
    res["grid"] = grid_check(d, price_level)
    res["gspc_check"] = gspc_check(d, sigs, sigs_tr)

    i0, i1 = window_idx(d["dates"], TAX_START, 99991231)
    tax = {}
    for label, rates in TAX_RATES.items():
        rows = {
            "Buy and hold": after_tax(
                np.ones(len(d["tr"])), d, i0, i1, PRIMARY_COST, rates
            )
        }
        for name, pos in pos1.items():
            rows[name] = after_tax(pos, d, i0, i1, PRIMARY_COST, rates)
        tax[label] = rows
    pre = {"Buy and hold": float(np.prod(1 + d["tr"][i0:i1]) * 100_000)}
    for name, pos in pos1.items():
        pre[name] = float(
            np.prod(1 + strat_returns(pos, d, PRIMARY_COST)[i0:i1]) * 100_000
        )
    yrs_tax = years_between(d["pydates"][i0], d["pydates"][i1 - 1])
    for rows in tax.values():
        for v in rows.values():
            v["after_tax_cagr"] = (v["liquidated"] / 100_000) ** (1 / yrs_tax) - 1
    res["tax"] = {
        "window_start": TAX_START,
        "years": yrs_tax,
        "pre_tax": pre,
        "after_tax": tax,
    }
    res["rolling"] = rolling_edges(d, pos1)
    res["episodes"] = episodes(d, pos1)

    (HERE / "results.json").write_text(json.dumps(r4(res), indent=1))
    if not quick:
        (HERE / "web_results.json").write_text(
            json.dumps(web_export(res), separators=(",", ":"))
        )
    report(res)


def pct(x, nd=1):
    return "   n/a" if x is None else f"{x * 100:+.{nd}f}"


def report(res):
    md = res["_metadata"]
    print(f"Data {md['first_day']} to {md['last_day']}. Primary: {md['primary']}.")
    print("\nLag-1 / lag-2 autocorrelation of daily market returns:")
    for k, v in res["autocorr"].items():
        print(f"  {k}: {v['lag1']:+.3f} / {v['lag2']:+.3f}")
    for wname, w in res["primary"].items():
        bh = w["buy_hold"]
        print(
            f"\n== {wname}  buy-and-hold CAGR {bh['cagr'] * 100:.2f}%  vol {bh['vol'] * 100:.1f}%  Sharpe {bh['sharpe']:.2f}  maxDD {bh['max_dd'] * 100:.0f}%"
        )
        if "reality_check" in w:
            rc = w["reality_check"]
            print(
                f"   PW block {w['pw_block']:.1f} d; Reality Check p vs B&H (63/250/pw): {rc['63']['bh']:.3f}/{rc['250']['bh']:.3f}/{rc['pw']['bh']:.3f}; vs exposure-matched: {rc['63']['exp']:.3f}/{rc['250']['exp']:.3f}/{rc['pw']['exp']:.3f}; BLL ten only vs B&H / vs exposure-matched (63): {rc['63']['bh_bll']:.3f} / {rc['63']['exp_bll']:.3f}"
            )
        print(
            f"   {'rule':22s} {'CAGR':>6s} {'expo':>5s} {'exit/y':>6s} {'vsBH':>6s} {'vsExp':>6s} {'vsVol':>6s} {'sameCl':>6s} {'TRsig':>6s}  CI63 vsBH        CI63 vsExp       CI250 vsExp"
        )
        for name, m in w["rules"].items():
            sc = res["same_close"][wname]["rules"][name]["edge_bh"]
            ts = res["tr_signal"][wname]["rules"][name]["edge_bh"]
            line = f"   {name:22s} {m['cagr'] * 100:6.2f} {m['exposure'] * 100:5.0f} {m['exits_per_year']:6.1f} {pct(m['edge_bh'])} {pct(m['edge_exp'])} {pct(m['edge_vol'])} {pct(sc)} {pct(ts)}"
            if "ci" in w:
                c63 = w["ci"]["63"][name]
                c250 = w["ci"]["250"][name]
                line += f"  [{pct(c63['bh'][0])},{pct(c63['bh'][1])}] [{pct(c63['exp'][0])},{pct(c63['exp'][1])}] [{pct(c250['exp'][0])},{pct(c250['exp'][1])}]"
            print(line)
    print("\nCost sensitivity, edge vs exposure-matched mix (0/5/10/25 bp):")
    for wname in ("1928-1986", "1993-2026"):
        for name in ("1-200", "1-50", "50-200 golden cross", "12-month trend"):
            vals = [
                res["costs"][k][wname]["rules"][name]["edge_exp"] for k in res["costs"]
            ]
            print(f"  {wname} {name:22s} " + " ".join(pct(v, 2) for v in vals))
    g = res["grid"]
    wn = g["winner"]
    print(
        f"\nGrid: in-sample winner {wn['short']}-{wn['long']} edge vs B&H 1928-86 {pct(wn['edge_in'], 2)} (grid median {pct(g['median_edge_in'], 2)}); 1987-2026 {pct(wn['edge_out'], 2)} vs B&H, {pct(wn['edge_out_exp'], 2)} vs exposure-matched (grid median {pct(g['median_edge_out'], 2)} / {pct(g['median_edge_out_exp'], 2)}); out-of-sample rank {g['winner_rank_out']} of {len(g['cells'])}"
    )
    if res["gspc_check"]:
        gc = res["gspc_check"]
        print(
            f"^GSPC 1-200 signal agreement over {gc['days']} days: price-index signal {gc['agree_price_signal'] * 100:.1f}%, total-return signal {gc['agree_tr_signal'] * 100:.1f}%"
        )
    print(
        "\nEpisodes (decline / next 12 months): buy and hold vs 1-200, golden cross, Faber, 12-month trend"
    )
    for e in res["episodes"]:
        cells = " | ".join(
            f"{pct(e[k]['decline'], 0)}/{pct(e[k]['next_12m'], 0)}"
            for k in (
                "1-200",
                "50-200 golden cross",
                "Faber 10-month",
                "12-month trend",
            )
        )
        print(
            f"  {e['episode']:22s} B&H {pct(e['bh_decline'], 0)}/{pct(e['bh_next_12m'], 0)} | {cells}"
        )
    t = res["tax"]
    print(f"\nAfter tax from {t['window_start']}, $100,000, 5 bp:")
    for label, rows in t["after_tax"].items():
        print(f"  {label}")
        for name, v in rows.items():
            print(
                f"    {name:22s} pre-tax ${t['pre_tax'][name]:>12,.0f}  after-tax liquidated ${v['liquidated']:>12,.0f}  after-tax CAGR {v['after_tax_cagr'] * 100:5.2f}%  wash sales {v['wash_sales']:3d} of {v['loss_exits']:3d} loss exits  ST share {pct(v['short_term_share_of_realized_gains'], 0)}"
            )


if __name__ == "__main__":
    main()
