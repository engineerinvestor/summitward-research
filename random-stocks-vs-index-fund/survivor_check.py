"""Two checks that use actual returns of current S&P 500 members.

Supports https://summitward.com/learn/random-stocks-vs-index-fund.

1. Spread check. Random equal-weight, buy-and-hold portfolios of N current
   members over November 2021 to October 2026, ending wealth relative to SPY,
   compared with the same statistic from the baseline model in simulate.py
   over five years. Only the width of the distribution is informative; its
   level is biased by survivorship (see 2).
2. Survivorship illustration. Equal-weighting today's members over the past
   five years (bought and held, and rebalanced quarterly as RSP is), against
   the live equal-weight fund (RSP, which held the members of each date) over
   the same months.

Reads .cache/monthly_closes.csv and .cache/rsp_spy_monthly.csv (written by
calibrate.py and ew_vs_cw.py) and output/per_stock.csv and
output/calibration.json. Needs numpy, pandas. Writes output/survivor_check.json.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
CACHE = HERE / ".cache"
OUT = HERE / "output"
SEED = 20261118
DRAWS = 20000
MODEL_PATHS = 5000


def main() -> None:
    closes = pd.read_csv(CACHE / "monthly_closes.csv", index_col=0, parse_dates=True)
    rets = closes.pct_change(fill_method=None).loc["2021-11":"2026-10"]
    per = pd.read_csv(OUT / "per_stock.csv")
    tickers = [t.replace(".", "-") for t in per["ticker"]]
    R = rets[tickers].to_numpy()
    m = rets["SPY"].to_numpy()
    G = np.prod(1 + R, axis=0)
    Gm = float(np.prod(1 + m))
    cal = json.loads((OUT / "calibration.json").read_text())
    s = cal["idiosyncratic_vol"]["rms"] / np.sqrt(12)
    sm = cal["spy_annualized_vol"] / np.sqrt(12)
    rng = np.random.default_rng(SEED)

    spread = {}
    for N in (1, 10, 30, 100):
        idx = np.array([rng.choice(len(tickers), N, replace=False) for _ in range(DRAWS)])
        actual = G[idx].mean(axis=1) / Gm
        model = np.empty(MODEL_PATHS)
        for p in range(MODEL_PATHS):
            rm = rng.normal(0.09 / 12, sm, 60)
            r = rm[:, None] + rng.normal(0, s, (60, N))
            model[p] = np.prod(1 + r, axis=0).mean() / np.prod(1 + rm)
        spread[str(N)] = {
            "actual_sd_log": round(float(np.log(actual).std()), 3),
            "model_sd_log": round(float(np.log(model).std()), 3),
            "actual_p5_p95_ratio": round(float(np.percentile(actual, 95) / np.percentile(actual, 5)), 2),
            "model_p5_p95_ratio": round(float(np.percentile(model, 95) / np.percentile(model, 5)), 2),
        }

    port = 1.0
    w = np.ones(len(tickers))
    for i, row in enumerate(1 + R):
        if i % 3 == 0:  # reset to equal weights at the start of each quarter
            w = np.full(len(tickers), port / len(tickers))
        w = w * row
        port = float(w.sum())
    quarterly = port / Gm

    px = pd.read_csv(CACHE / "rsp_spy_monthly.csv", index_col=0, parse_dates=True)
    fr = px.pct_change(fill_method=None).loc["2021-11":"2026-10"]
    rsp_rel = float(np.prod(1 + fr["RSP"]) / np.prod(1 + fr["SPY"]))
    out = {
        "window": "2021-11 to 2026-10",
        "stocks": len(tickers),
        "spread_check": spread,
        "survivorship": {
            "todays_members_equal_weight_vs_spy": round(float(G.mean() / Gm), 4),
            "todays_members_quarterly_rebalanced_vs_spy": round(float(quarterly), 4),
            "rsp_vs_spy": round(rsp_rel, 4),
        },
    }
    (OUT / "survivor_check.json").write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
