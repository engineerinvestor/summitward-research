"""Value spread: how cheap value stocks are relative to growth stocks.

Powers the public /markets/value-spread page and the "Is the value premium
back?" Learn guide. Every series is computed from portfolio-level
characteristics that Eugene Fama and Kenneth French publish in their data
library, so the whole history is reproducible from free files.

Definition
----------
The spread is the book-to-market ratio of the value portfolio divided by the
book-to-market ratio of the growth portfolio. Because B/M is the inverse of
P/B, this equals growth's price-to-book multiple divided by value's. A reading
of 6.0 means growth stocks trade at six times the price-to-book multiple of
value stocks. The same construction is applied to earnings-to-price and
cash-flow-to-price sorts as a check on how much the result depends on book
value, which understates the capital of firms that invest in intangibles.

Series
------
* ``small`` and ``large``: the six size/book-to-market portfolios (2x3).
  Value is the top 30% of B/M within each size half, growth the bottom 30%.
  French's "BE_FYt-1/ME_June t" block gives each portfolio's value-weighted
  B/M at June prices when the portfolios are formed. Value weighting with the
  same market equity that sits in the denominator makes this the aggregate
  ratio, sum of book equity over sum of market equity.
* Monthly readings between June formations are rolled forward with the
  portfolios' value-weighted returns *without dividends* (price change per
  share), holding book equity per share at its fiscal-year value. This is the
  usual "current price, lagged book" convention. Each June the portfolios are
  re-sorted with new book values and the rolled estimate is replaced by the
  next published reading; :func:`annual_revisions` measures how far that moves
  the number.
* ``small_op`` and ``large_op``: the 32 size/B/M/profitability portfolios
  (2x4x4, from 1963). Within each size half and each operating-profitability
  quartile, the highest B/M quartile is divided by the lowest; the four
  ratios are averaged geometrically. This compares cheap and expensive firms
  of similar profitability.
* ``allcap_bm``, ``allcap_ep``, ``allcap_cfp``: univariate sorts, top 30% over
  bottom 30%, from the "Sum of X / Sum of ME" annual blocks (December prices
  of the prior year).

Pure functions only; no network or file I/O. ``scripts/extract_value_spread.py``
downloads the files and writes the JSON the site reads.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

Rows = dict[str, dict[str, float]]


# --------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Section:
    title: str
    rows: Rows  # key "YYYYMM" or "YYYY" -> {column: value}


def parse_sections(text: str) -> list[Section]:
    """Split a Kenneth French CSV into its titled tables.

    A table starts at a header line that begins with a comma; its title is the
    run of non-blank, non-numeric lines immediately above it (French wraps the
    longer titles over several lines). Rows run until the first line whose
    first field is not all digits.
    """
    lines = text.splitlines()
    sections: list[Section] = []
    i = 0
    while i < len(lines):
        if lines[i].strip().startswith(",") and i > 0:
            j = i - 1
            title_lines: list[str] = []
            while j >= 0:
                s = lines[j].strip()
                if not s or s.startswith(",") or s.split(",")[0].strip().isdigit():
                    break
                title_lines.insert(0, s)
                j -= 1
            header = [h.strip() for h in lines[i].split(",")]
            rows: Rows = {}
            k = i + 1
            while k < len(lines):
                parts = [p.strip() for p in lines[k].split(",")]
                if not parts[0].isdigit():
                    break
                rows[parts[0]] = dict(zip(header[1:], map(float, parts[1:])))
                k += 1
            sections.append(Section(" ".join(title_lines), rows))
            i = k
        else:
            i += 1
    return sections


def find_section(sections: list[Section], *needles: str) -> Section:
    """Return the first section whose whitespace-free title contains every needle."""
    for sec in sections:
        flat = sec.title.replace(" ", "").lower()
        if all(n.replace(" ", "").lower() in flat for n in needles):
            return sec
    raise KeyError(f"no section matching {needles!r}")


def crsp_cut(text: str) -> str:
    """The data vintage stated on the first line, e.g. ``"202609"``."""
    first = text.splitlines()[0]
    for tok in first.split():
        if tok.isdigit() and len(tok) == 6:
            return tok
    raise ValueError(f"no YYYYMM vintage in {first!r}")


# --------------------------------------------------------------------------
# Spreads
# --------------------------------------------------------------------------


def ratio(rows: Rows, value_col: str, growth_col: str) -> dict[str, float]:
    """value/growth for each row where both entries are positive."""
    out = {}
    for key, r in rows.items():
        v, g = r.get(value_col, -99.99), r.get(growth_col, -99.99)
        if v > 0 and g > 0:
            out[key] = v / g
    return out


def geometric_mean_ratio(rows: Rows, pairs: list[tuple[str, str]]) -> dict[str, float]:
    """Geometric mean of value/growth across several column pairs."""
    out = {}
    for key, r in rows.items():
        logs = []
        for v_col, g_col in pairs:
            v, g = r[v_col], r[g_col]
            if v <= 0 or g <= 0:
                break
            logs.append(math.log(v / g))
        else:
            out[key] = math.exp(sum(logs) / len(logs))
    return out


def june_readings(monthly_block: Rows) -> Rows:
    """Formation readings: the July row of each year, re-dated to June.

    French reports the June-price characteristic on every month of the
    portfolio year (only the weights move). The July row is the first month
    of the year the portfolio is held, so it is the reading at formation.
    """
    return {f"{k[:4]}06": v for k, v in monthly_block.items() if k.endswith("07")}


def next_month(ym: str) -> str:
    y, m = int(ym[:4]), int(ym[4:])
    return f"{y + (m == 12)}{(m % 12) + 1:02d}"


def roll_forward(
    readings: Rows, exdiv_returns: Rows, columns: list[str]
) -> dict[str, Rows]:
    """Monthly B/M for each column, rolled from each June reading.

    ``readings`` maps ``YYYY06`` to the formation B/M; ``exdiv_returns`` maps
    ``YYYYMM`` to value-weighted returns without dividends, in percent. The
    month-end B/M after month m is the June reading divided by the cumulative
    price relative from July through m. The roll stops at the next reading or
    at the last month with returns.

    Returns ``{"YYYYMM": {"col": bm, ..., "_estimate": 0 or 1}}`` where
    ``_estimate`` is 1 for rolled months and 0 for published readings.
    """
    out: dict[str, Rows] = {}
    june_keys = sorted(readings)
    last_ret = max(exdiv_returns)
    for idx, jk in enumerate(june_keys):
        stop = june_keys[idx + 1] if idx + 1 < len(june_keys) else None
        base = readings[jk]
        out[jk] = {c: base[c] for c in columns} | {"_estimate": 0.0}
        growth = dict.fromkeys(columns, 1.0)
        m = next_month(jk)
        while (stop is None or m < stop) and m <= last_ret:
            r = exdiv_returns.get(m)
            if r is None:
                break
            for c in columns:
                growth[c] *= 1 + r[c] / 100
            out[m] = {c: base[c] / growth[c] for c in columns} | {"_estimate": 1.0}
            m = next_month(m)
    return out


def rolled_to(readings: Rows, exdiv_returns: Rows, columns: list[str], june: str):
    """B/M of the vintage formed at ``june``, rolled through the next May.

    Used to compare against the next June's published reading.
    """
    base = readings[june]
    growth = dict.fromkeys(columns, 1.0)
    m = next_month(june)
    stop = f"{int(june[:4]) + 1}06"
    while m <= stop:
        r = exdiv_returns.get(m)
        if r is None:
            return None
        for c in columns:
            growth[c] *= 1 + r[c] / 100
        m = next_month(m)
    return {c: base[c] / growth[c] for c in columns}


def annual_revisions(
    readings: Rows,
    exdiv_returns: Rows,
    value_col: str,
    growth_col: str,
) -> list[float]:
    """Log change in the spread at each June re-sort.

    Compares the spread rolled 12 months through June t+1 with the reading
    French publishes for the portfolios re-formed at June t+1. The gap comes
    from new book values and new portfolio membership, not from arithmetic
    error, and tells a reader how much the next annual update typically moves
    a monthly estimate.
    """
    keys = sorted(readings)
    out = []
    for a, b in zip(keys, keys[1:]):
        rolled = rolled_to(readings, exdiv_returns, [value_col, growth_col], a)
        if rolled is None:
            continue
        s_rolled = rolled[value_col] / rolled[growth_col]
        s_next = readings[b][value_col] / readings[b][growth_col]
        out.append(math.log(s_next / s_rolled))
    return out


# --------------------------------------------------------------------------
# Statistics
# --------------------------------------------------------------------------


def percentile_rank(history: list[float], value: float) -> float:
    """Share of ``history`` at or below ``value`` (empirical, no distribution assumed)."""
    if not history:
        raise ValueError("empty history")
    return sum(h <= value for h in history) / len(history)


def quantile(xs: list[float], q: float) -> float:
    s = sorted(xs)
    pos = (len(s) - 1) * q
    lo, hi = math.floor(pos), math.ceil(pos)
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


def forward_spread_return(
    monthly_returns: Rows, start: str, months: int, value_col: str, growth_col: str
) -> float | None:
    """Annualized value-minus-growth total return over ``months`` from ``start``."""
    keys = sorted(k for k in monthly_returns if k >= start)[:months]
    if len(keys) < months or keys[0] != start:
        return None
    gv = math.prod(1 + monthly_returns[k][value_col] / 100 for k in keys)
    gg = math.prod(1 + monthly_returns[k][growth_col] / 100 for k in keys)
    return gv ** (12 / months) - gg ** (12 / months)


def ols_newey_west(x: list[float], y: list[float], lags: int) -> dict[str, float]:
    """Univariate OLS y = a + b x with Newey-West (Bartlett) standard error on b."""
    n = len(x)
    mx, my = sum(x) / n, sum(y) / n
    sxx = sum((xi - mx) ** 2 for xi in x)
    b = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y)) / sxx
    a = my - b * mx
    e = [yi - a - b * xi for xi, yi in zip(x, y)]
    u = [(xi - mx) * ei for xi, ei in zip(x, e)]
    s = sum(ui * ui for ui in u)
    for lag in range(1, lags + 1):
        w = 1 - lag / (lags + 1)
        s += 2 * w * sum(u[t] * u[t - lag] for t in range(lag, n))
    se = math.sqrt(s) / sxx
    sst = sum((yi - my) ** 2 for yi in y)
    r2 = 1 - sum(ei * ei for ei in e) / sst
    return {"slope": b, "intercept": a, "se_nw": se, "t_nw": b / se, "r2": r2}


def oos_r2(
    x: list[float], y: list[float], horizon_years: int, min_train: int
) -> tuple[float, int]:
    """Campbell-Thompson out-of-sample R-squared against the historical mean.

    Observations are annual and in time order; ``y[i]`` is only known
    ``horizon_years`` after ``x[i]``. For each forecast origin i, both the
    regression and the benchmark mean are fit on observations j with
    j + horizon_years <= i, so no forecast uses an outcome that had not yet
    happened. Positive values mean the spread beat the running mean.
    """
    sse_model = sse_mean = 0.0
    count = 0
    for i in range(len(x)):
        train = [j for j in range(i) if j + horizon_years <= i]
        if len(train) < min_train:
            continue
        tx, ty = [x[j] for j in train], [y[j] for j in train]
        mx, my = sum(tx) / len(tx), sum(ty) / len(ty)
        sxx = sum((v - mx) ** 2 for v in tx)
        b = sum((v - mx) * (w - my) for v, w in zip(tx, ty)) / sxx
        pred = my + b * (x[i] - mx)
        sse_model += (y[i] - pred) ** 2
        sse_mean += (y[i] - my) ** 2
        count += 1
    return 1 - sse_model / sse_mean, count
