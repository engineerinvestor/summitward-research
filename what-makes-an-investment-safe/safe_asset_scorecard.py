"""Score the same assets against different bills: the "safe for what?" scorecard.

An asset is only safe relative to something. This module asks one question
over every historical window in Damodaran's annual US data (1928 onward):
money set aside at the start of a window, invested in a strategy, did it reach
the bill at the end? The bill is either the same number of dollars (a
fixed-dollar liability) or the same purchasing power (a CPI-linked one).

Conventions (mirrored by the Summitward calculator on the guide page;
the site checks the two against shared parity vectors):

- Calendar-year returns. A window that starts in year ``s`` with horizon ``h``
  invests at the end of ``s - 1`` and compounds the returns of years
  ``s .. s + h - 1``. Start years run from the first data year to the last
  year that completes the window.
- Real returns are ``(1 + nominal) / (1 + CPI inflation) - 1``, using the
  CPI-U December-to-December inflation in the same file.
- ``sixty_forty`` is 60% S&P 500 and 40% 10-year Treasury, rebalanced yearly.
- ``tbill_after_tax`` taxes each year's bill interest at ``tax_rate``:
  ``nominal * (1 - tax_rate)``. Only interest is taxed here. Stocks and the
  rolling bond are shown pre-tax, because their tax depends on turnover,
  account type and holding period.
- ``held_10y`` buys a 10-year Treasury at the prior year-end yield and holds it
  to maturity, approximated as a zero-coupon bond: it pays
  ``(1 + y) ** 10`` nominal. It exists only for a 10-year horizon.
- Flexibility: a window counts as funded if the strategy reaches
  ``1 - can_cut`` of the bill at any year-end from ``h`` to ``h + can_delay``.
  When ``can_delay > 0``, only start years that complete ``h + can_delay``
  are scored, so the same windows can be compared with ``can_delay = 0`` by
  passing ``window_years``.

US data only, before fees, and overlapping windows: a 20-year horizon over
98 years has 79 windows but about five independent periods.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"

STRATEGIES = (
    "tbill",
    "tbill_after_tax",
    "tbond",
    "held_10y",
    "sp500",
    "sixty_forty",
)
LABELS = {
    "tbill": "T-bills, rolled",
    "tbill_after_tax": "T-bills, rolled, after tax",
    "tbond": "10-year Treasury, rolled",
    "held_10y": "10-year Treasury, held to maturity",
    "sp500": "S&P 500",
    "sixty_forty": "60/40 stocks/10-year Treasury",
}
BASES = ("nominal", "real")


@lru_cache(maxsize=1)
def load_data(data_dir: str | None = None) -> dict:
    """Annual returns, inflation and year-end 10-year yields, keyed by int year."""
    base = Path(data_dir) if data_dir else DATA_DIR
    d = json.loads((base / "damodaran_returns.json").read_text())
    y = json.loads((base / "treasury_10y_yields.json").read_text())

    def ints(m: dict) -> dict[int, float]:
        return {int(k): float(v) for k, v in m.items()}

    assets = d["assets"]
    return {
        "first_year": int(d["_metadata"]["first_year"]),
        "last_year": int(d["_metadata"]["last_year"]),
        "inflation": ints(d["inflation"]),
        "sp500": ints(assets["sp500"]["nominal"]),
        "tbill": ints(assets["tbill"]["nominal"]),
        "tbond": ints(assets["tbond"]["nominal"]),
        "yield10": ints(y["yields"]),
    }


def nominal_return(
    data: dict, strategy: str, year: int, tax_rate: float = 0.0
) -> float:
    """One calendar year's nominal return for a rolling strategy."""
    if strategy == "tbill":
        return data["tbill"][year]
    if strategy == "tbill_after_tax":
        return data["tbill"][year] * (1 - tax_rate)
    if strategy == "tbond":
        return data["tbond"][year]
    if strategy == "sp500":
        return data["sp500"][year]
    if strategy == "sixty_forty":
        return 0.6 * data["sp500"][year] + 0.4 * data["tbond"][year]
    raise ValueError(f"no annual return series for {strategy!r}")


def start_years(data: dict, horizon: int, extra: int = 0) -> list[int]:
    """Start years whose window of ``horizon + extra`` years is in the data."""
    first, last = data["first_year"], data["last_year"]
    return list(range(first, last - horizon - extra + 2))


def _cpi_growth(data: dict, start: int, years: int) -> float:
    g = 1.0
    for yr in range(start, start + years):
        g *= 1 + data["inflation"][yr]
    return g


def path(
    data: dict,
    strategy: str,
    start: int,
    years: int,
    basis: str = "real",
    tax_rate: float = 0.0,
) -> list[float]:
    """Value of $1 at the end of each year 1..years of a window starting ``start``."""
    if basis not in BASES:
        raise ValueError(f"basis must be one of {BASES}")
    out: list[float] = []
    if strategy == "held_10y":
        if years != 10:
            raise ValueError("held_10y exists only for a 10-year horizon")
        nominal = (1 + data["yield10"][start - 1]) ** 10
        value = nominal / _cpi_growth(data, start, 10) if basis == "real" else nominal
        return [value]
    w = 1.0
    for yr in range(start, start + years):
        r = nominal_return(data, strategy, yr, tax_rate)
        w *= 1 + r
        if basis == "real":
            w /= 1 + data["inflation"][yr]
        out.append(w)
    return out


def shortfall(
    data: dict,
    strategy: str,
    horizon: int,
    basis: str = "real",
    can_delay: int = 0,
    can_cut: float = 0.0,
    tax_rate: float = 0.0,
    window_years: list[int] | None = None,
) -> dict:
    """How often, and how badly, a strategy missed the bill.

    Returns the window count, the number and share that fell short, the worst
    outcome (value at the due date or, with flexibility, the best value reached
    inside the grace period, minus one), the median outcome at the due date,
    and the start years that fell short.
    """
    if strategy == "held_10y" and (horizon != 10 or can_delay):
        raise ValueError("held_10y is scored only at 10 years with no delay")
    target = 1.0 - can_cut
    years = window_years or start_years(data, horizon, can_delay)
    short_years: list[int] = []
    outcomes: list[float] = []
    at_due: list[float] = []
    for s in years:
        p = path(data, strategy, s, horizon + can_delay, basis, tax_rate)
        grace = p[horizon - 1 :] if strategy != "held_10y" else p
        best = max(grace)
        at_due.append(grace[0])
        outcomes.append(best)
        if best < target - 1e-12:
            short_years.append(s)
    n = len(years)
    srt = sorted(at_due)
    mid = n // 2
    median = srt[mid] if n % 2 else (srt[mid - 1] + srt[mid]) / 2
    return {
        "strategy": strategy,
        "horizon": horizon,
        "basis": basis,
        "can_delay": can_delay,
        "can_cut": can_cut,
        "tax_rate": tax_rate,
        "windows": n,
        "short": len(short_years),
        "share_short": len(short_years) / n if n else 0.0,
        "worst": min(outcomes) - 1.0 if n else 0.0,
        "median": median - 1.0 if n else 0.0,
        "short_years": short_years,
        "first_start": years[0] if n else None,
        "last_start": years[-1] if n else None,
    }


def underwater_spells(data: dict, strategy: str, basis: str = "real") -> list[dict]:
    """Every spell below a prior year-end high, longest first.

    ``years`` runs from the peak year-end to the recovery year-end (or to the
    last data year if the spell is still open). Year-end resolution misses
    intra-year peaks and troughs.
    """
    first, last = data["first_year"], data["last_year"]
    w, peak, peak_year = 1.0, 1.0, first - 1
    spells: list[dict] = []
    cur: dict | None = None
    for yr in range(first, last + 1):
        w *= 1 + nominal_return(data, strategy, yr)
        if basis == "real":
            w /= 1 + data["inflation"][yr]
        if w >= peak:
            if cur:
                cur["recovery_year"] = yr
                cur["years"] = yr - cur["peak_year"]
                spells.append(cur)
                cur = None
            peak, peak_year = w, yr
        else:
            depth = w / peak - 1
            if cur is None:
                cur = {"peak_year": peak_year, "trough_year": yr, "depth": depth}
            elif depth < cur["depth"]:
                cur["trough_year"], cur["depth"] = yr, depth
    if cur:
        cur["recovery_year"] = None
        cur["years"] = last - cur["peak_year"]
        cur["depth_now"] = w / peak - 1
        spells.append(cur)
    return sorted(spells, key=lambda s: -s["years"])
