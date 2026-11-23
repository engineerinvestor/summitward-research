"""Micron's trailing P/E at each fiscal year end, and what earnings did next.

Diluted EPS for each fiscal year comes from Micron's 10-K filings (SEC XBRL
companyconcept, cached by fetch_fundamentals.py's cache directory); prices are
Yahoo closes on each fiscal year-end date (Micron has not split since 2000,
so split adjustment does not matter). A P/E is computed only for profitable
years.

This is a description of one company's history, not a forecast: three
episodes are an anecdote, and the guide says so.

Writes output/micron_history.json.

Usage:
    SEC_USER_AGENT="..." python3 micron_history.py
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import fetch_fundamentals as ff
import yfinance as yf

HERE = Path(__file__).resolve().parent
OUT = HERE / "output"
MU_CIK = 723125
SNAPSHOT = "2026-11-20"


def annual_eps() -> dict[str, float]:
    rows = ff.concept(MU_CIK, "us-gaap", "EarningsPerShareDiluted")
    out = {}
    for r in ff.latest_filed(rows).values():
        if not r.get("start"):
            continue
        days = (date.fromisoformat(r["end"]) - date.fromisoformat(r["start"])).days
        if 350 <= days <= 380:
            out[r["end"]] = float(r["val"])
    return dict(sorted(out.items()))


def main() -> None:
    ff.CACHE.mkdir(parents=True, exist_ok=True)
    eps = {e: v for e, v in annual_eps().items() if e >= "2009-01-01"}
    px = yf.download(
        "MU", start="2009-08-01", end="2026-11-22", auto_adjust=False, progress=False
    )["Close"]
    px = px["MU"] if hasattr(px, "columns") else px

    def close(day: str) -> float:
        return float(px.loc[:day].iloc[-1])

    years = []
    ends = list(eps)
    for i, e in enumerate(ends):
        p = close(e)
        nxt = eps[ends[i + 1]] if i + 1 < len(ends) else None
        years.append(
            {
                "fy_end": e,
                "eps": eps[e],
                "price": round(p, 2),
                "trailing_pe": round(p / eps[e], 1) if eps[e] > 0 else None,
                "next_eps": nxt,
                "next_change_pct": (
                    round(100 * (nxt / eps[e] - 1), 0)
                    if nxt is not None and eps[e] > 0
                    else None
                ),
            }
        )
    last = ends[-1]
    snap = {
        "date": SNAPSHOT,
        "price": round(close(SNAPSHOT), 2),
        "trailing_eps": eps[last],
        "trailing_pe": round(close(SNAPSHOT) / eps[last], 1),
        "peak_close_fy2026_end": round(close(last), 2),
        "drawdown_from_fy_end_pct": round(100 * (close(SNAPSHOT) / close(last) - 1), 1),
    }
    low = [y for y in years if y["trailing_pe"] and y["trailing_pe"] < 8 and y["next_eps"]]
    res = {"years": years, "snapshot": snap, "pe_under_8_with_next_year": low}
    OUT.mkdir(exist_ok=True)
    (OUT / "micron_history.json").write_text(json.dumps(res, indent=1) + "\n")
    for y in years:
        print(y)
    print(snap)
    print("P/E under 8 at a fiscal year end, and the next year's EPS change:")
    for y in low:
        print(f"  FY end {y['fy_end']}: P/E {y['trailing_pe']} -> EPS {y['next_change_pct']}%")


if __name__ == "__main__":
    main()
