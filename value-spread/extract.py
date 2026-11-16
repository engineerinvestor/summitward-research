"""Build the value-spread dataset from the Kenneth French Data Library.

Supports https://summitward.com/markets/value-spread and
https://summitward.com/learn/is-the-value-premium-back. The math lives in
``value_spread.py`` next to this file (pure functions, standard library only);
this script reads the French CSVs in ``data/``, calls those functions, and
writes JSON.

What it computes (definitions in ``value_spread.py``):

  * monthly small-cap and large-cap value spreads since June 1926, from the
    six size/book-to-market portfolios, with the months between June
    formations rolled forward on ex-dividend returns;
  * profitability-controlled small and large spreads since 1963, from the 32
    size/B/M/profitability portfolios;
  * all-cap spreads on book, earnings and cash flow (annual, December prices);
  * empirical percentiles of the latest readings, full history and since 1963;
  * what each June reading was followed by: value-minus-growth total returns
    over the next 5 and 10 years, by tercile of the starting spread, with an
    in-sample slope (Newey-West t-stat) and a Campbell-Thompson out-of-sample
    R-squared against the running historical mean;
  * the typical move at each June re-sort, so a reader knows how much the
    next annual update tends to revise a monthly estimate;
  * trailing 12-month and year-to-date returns of the four corner portfolios
    and of HML and SMB.

Usage:  python3 extract.py [--refresh]
Writes: output/value_spread.json

The French CSVs in ``data/`` are the 202609 vintage the published figures use;
``--refresh`` downloads the current files over them. Each monthly French update extends every
series and can revise history (CRSP and Compustat restatements), so a page or
guide that quotes these numbers should name the CRSP vintage stored in
``_metadata.crsp_cut``. The guide's figures are frozen at the 202609 vintage.
"""

from __future__ import annotations

import argparse
import io
import json
import math
import sys
import urllib.request
import zipfile
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))

import value_spread as vs  # noqa: E402

OUTPUTS = [REPO_ROOT / "output" / "value_spread.json"]
DATA = REPO_ROOT / "data"
# The library's HTTPS endpoint has intermittently returned 404 for the zip
# files while HTTP works; try HTTPS first and fall back.
FRENCH = "mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp"
LIBRARY_URL = (
    "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html"
)

SMALL_V, SMALL_G = "SMALL HiBM", "SMALL LoBM"
BIG_V, BIG_G = "BIG HiBM", "BIG LoBM"
HORIZONS = (5, 10)
OOS_MIN_TRAIN = 20


def _get(name: str, refresh: bool) -> str:
    path = DATA / f"{name}.csv"
    if refresh or not path.exists():
        body = None
        for scheme in ("https", "http"):
            url = f"{scheme}://{FRENCH}/{name}_CSV.zip"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    body = resp.read()
                break
            except OSError:
                continue
        if body is None:
            raise RuntimeError(f"could not download {name}")
        with zipfile.ZipFile(io.BytesIO(body)) as zf:
            path.write_bytes(zf.read(zf.namelist()[0]))
    return path.read_text(encoding="latin-1")


def _ym(key: str) -> str:
    return f"{key[:4]}-{key[4:]}"


def _r(x: float, d: int = 4) -> float:
    return round(x, d)


def _col32(cols: list[str], size: int, bm: int, op: int) -> str:
    """Resolve a 32-portfolio column; corners carry names like 'SMALL HiBM LoOP'."""
    plain = f"ME{size} BM{bm} OP{op}"
    if plain in cols:
        return plain
    s = {1: "SMALL", 2: "BIG"}[size]
    b = {1: "LoBM", 4: "HiBM"}[bm]
    o = {1: "LoOP", 4: "HiOP"}[op]
    name = f"{s} {b} {o}"
    if name not in cols:
        raise KeyError(name)
    return name


def _annual_dec(rows: vs.Rows, v: str, g: str) -> dict[str, float]:
    """Univariate 'Sum of X / Sum of ME' rows keyed YYYY, re-keyed to Dec of YYYY-1."""
    return {f"{int(k) - 1}12": s for k, s in vs.ratio(rows, v, g).items()}


def _percentiles(series: dict[str, float], key: str) -> dict:
    vals = list(series.values())
    since63 = [s for k, s in series.items() if k >= "196306"]
    x = series[key]
    return {
        "full": _r(vs.percentile_rank(vals, x), 3),
        "since_1963": _r(vs.percentile_rank(since63, x), 3),
        "median_full": _r(vs.quantile(vals, 0.5)),
        "median_since_1963": _r(vs.quantile(since63, 0.5)),
        "first": _ym(min(series)),
        "n": len(vals),
    }


def _peak(series: dict[str, float], lo: str, hi: str) -> dict:
    window = {k: s for k, s in series.items() if lo <= k <= hi}
    k = max(window, key=window.get)
    return {"date": _ym(k), "value": _r(window[k], 3)}


def _forward(readings: dict[str, float], totals: vs.Rows, v: str, g: str) -> dict:
    keys = sorted(readings)
    out = {}
    latest_key = keys[-1]
    latest = readings[latest_key]
    for h in HORIZONS:
        xs, ys, starts = [], [], []
        for k in keys:
            start = vs.next_month(k)  # returns of the year formed at June k
            fwd = vs.forward_spread_return(totals, start, 12 * h, v, g)
            if fwd is None:
                continue
            xs.append(math.log(readings[k]))
            ys.append(fwd)
            starts.append(k[:4])
        fit = vs.ols_newey_west(xs, ys, lags=h)
        oos, n_oos = vs.oos_r2(xs, ys, horizon_years=h, min_train=OOS_MIN_TRAIN)
        ranked = sorted(zip(xs, ys, starts))
        third = len(ranked) // 3
        groups = {
            "narrowest third": ranked[:third],
            "middle third": ranked[third : len(ranked) - third],
            "widest third": ranked[len(ranked) - third :],
        }
        terciles = []
        for label, grp in groups.items():
            gy = [y for _, y, _ in grp]
            terciles.append(
                {
                    "label": label,
                    "n": len(grp),
                    "spread_low": _r(math.exp(grp[0][0]), 2),
                    "spread_high": _r(math.exp(grp[-1][0]), 2),
                    "mean": _r(sum(gy) / len(gy)),
                    "median": _r(vs.quantile(gy, 0.5)),
                    "share_negative": _r(sum(y < 0 for y in gy) / len(gy), 3),
                    "worst": _r(min(gy)),
                    "best": _r(max(gy)),
                }
            )
        at_least = [y for x, y, _ in ranked if math.exp(x) >= latest]
        out[f"{h}y"] = {
            "n": len(xs),
            "first_start": starts[0],
            "last_start": starts[-1],
            "non_overlapping_windows": len(xs) // h,
            "slope_log_spread": _r(fit["slope"]),
            "t_newey_west": _r(fit["t_nw"], 2),
            "r2_in_sample": _r(fit["r2"], 3),
            "oos_r2": _r(oos, 3),
            "oos_forecasts": n_oos,
            "terciles": terciles,
            "starts_at_least_as_wide_as_latest": {
                "threshold": _r(latest, 2),
                "n": len(at_least),
                "mean": _r(sum(at_least) / len(at_least)) if at_least else None,
                "share_negative": (
                    _r(sum(y < 0 for y in at_least) / len(at_least), 3)
                    if at_least
                    else None
                ),
            },
        }
    return out


def _compound(rows: vs.Rows, col: str, keys: list[str]) -> float:
    return math.prod(1 + rows[k][col] / 100 for k in keys) - 1


def _span(june: str) -> list[str]:
    """The 12 months from the July after ``june`` through the next June."""
    out, m = [], vs.next_month(june)
    for _ in range(12):
        out.append(m)
        m = vs.next_month(m)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--refresh", action="store_true", help="re-download French files")
    args = ap.parse_args()

    files = {
        "six": "6_Portfolios_2x3",
        "six_exdiv": "6_Portfolios_2x3_Wout_Div",
        "p32": "32_Portfolios_ME_BEME_OP_2x4x4",
        "p32_exdiv": "32_Portfolios_ME_BEME_OP_2x4x4_Wout_Div",
        "bm": "Portfolios_Formed_on_BE-ME",
        "ep": "Portfolios_Formed_on_E-P",
        "cfp": "Portfolios_Formed_on_CF-P",
        "ff3": "F-F_Research_Data_Factors",
    }
    text = {k: _get(v, args.refresh) for k, v in files.items()}
    cuts = {files[k]: vs.crsp_cut(t) for k, t in text.items()}
    if len(set(cuts.values())) != 1:
        raise SystemExit(f"French files are from different vintages: {cuts}")
    cut = next(iter(cuts.values()))
    secs = {k: vs.parse_sections(t) for k, t in text.items()}

    # --- small and large, monthly -------------------------------------------
    six_june = vs.june_readings(vs.find_section(secs["six"], "BE_FYt-1/ME_June").rows)
    six_tot = vs.find_section(
        secs["six"], "Average Value Weighted Returns", "Monthly"
    ).rows
    six_exd = vs.find_section(
        secs["six_exdiv"], "Average Value Weighted Returns", "Monthly"
    ).rows
    cols = [SMALL_V, SMALL_G, BIG_V, BIG_G]
    monthly = vs.roll_forward(six_june, six_exd, cols)
    small_m = {k: r[SMALL_V] / r[SMALL_G] for k, r in monthly.items()}
    large_m = {k: r[BIG_V] / r[BIG_G] for k, r in monthly.items()}
    small_june = vs.ratio(six_june, SMALL_V, SMALL_G)
    large_june = vs.ratio(six_june, BIG_V, BIG_G)
    last_m = max(monthly)
    last_june = max(six_june)

    # --- profitability-controlled (32 portfolios) -----------------------------
    p32_june = vs.june_readings(vs.find_section(secs["p32"], "BE_FYt-1/ME_June").rows)
    cols32 = list(next(iter(p32_june.values())).keys())
    pairs = {
        size: [
            (_col32(cols32, size, 4, o), _col32(cols32, size, 1, o))
            for o in (1, 2, 3, 4)
        ]
        for size in (1, 2)
    }
    small_op = vs.geometric_mean_ratio(p32_june, pairs[1])
    large_op = vs.geometric_mean_ratio(p32_june, pairs[2])
    p32_exd = vs.find_section(
        secs["p32_exdiv"], "Average Value Weighted Returns", "Monthly"
    ).rows
    flat_cols = sorted({c for pr in pairs.values() for p in pr for c in p})
    p32_roll = vs.roll_forward({last_june: p32_june[last_june]}, p32_exd, flat_cols)
    small_op_est = vs.geometric_mean_ratio({last_m: p32_roll[last_m]}, pairs[1])[last_m]
    large_op_est = vs.geometric_mean_ratio({last_m: p32_roll[last_m]}, pairs[2])[last_m]

    # --- all-cap univariate sorts (annual, Dec prices) ------------------------
    allcap = {
        "allcap_bm": _annual_dec(
            vs.find_section(secs["bm"], "Sum of BE / Sum of ME").rows, "Hi 30", "Lo 30"
        ),
        "allcap_ep": _annual_dec(
            vs.find_section(secs["ep"], "Sum of E / Sum of ME").rows, "Hi 30", "Lo 30"
        ),
        "allcap_cfp": _annual_dec(
            vs.find_section(secs["cfp"], "Sum of CF / Sum of ME").rows, "Hi 30", "Lo 30"
        ),
    }

    # --- revisions at each June re-sort ---------------------------------------
    revisions = {}
    for label, (v, g) in {"small": (SMALL_V, SMALL_G), "large": (BIG_V, BIG_G)}.items():
        logs = vs.annual_revisions(six_june, six_exd, v, g)
        absolute = [abs(math.exp(x) - 1) for x in logs]
        revisions[label] = {
            "n": len(logs),
            "median_abs_pct": _r(100 * vs.quantile(absolute, 0.5), 1),
            "p90_abs_pct": _r(100 * vs.quantile(absolute, 0.9), 1),
            "mean_signed_pct": _r(100 * (math.exp(sum(logs) / len(logs)) - 1), 1),
        }
        # The most recent re-sort: last year's portfolios held fixed and rolled
        # to this June, against this June's published reading.
        prev = sorted(six_june)[-2]
        rolled = vs.rolled_to(six_june, six_exd, [v, g], prev)
        revisions[label]["latest"] = {
            "from": _ym(prev),
            "to": _ym(last_june),
            "prior_reading": _r(six_june[prev][v] / six_june[prev][g], 3),
            "rolled_fixed_portfolios": _r(rolled[v] / rolled[g], 3),
            "new_reading": _r(six_june[last_june][v] / six_june[last_june][g], 3),
            "value_exdiv_return": _r(_compound(six_exd, v, _span(prev)), 4),
            "growth_exdiv_return": _r(_compound(six_exd, g, _span(prev)), 4),
        }

    # --- recent returns -------------------------------------------------------
    ff3 = secs["ff3"][0].rows  # first table is monthly
    assert all(len(k) == 6 for k in ff3), "expected monthly factor rows"
    months = sorted(k for k in six_tot if len(k) == 6)
    trailing = months[-12:]
    ytd = [k for k in months if k[:4] == months[-1][:4]]
    recent = {}
    for label, keys in {"trailing_12m": trailing, "ytd": ytd}.items():
        recent[label] = {
            "start": _ym(keys[0]),
            "end": _ym(keys[-1]),
            "small_value": _r(_compound(six_tot, SMALL_V, keys)),
            "small_growth": _r(_compound(six_tot, SMALL_G, keys)),
            "large_value": _r(_compound(six_tot, BIG_V, keys)),
            "large_growth": _r(_compound(six_tot, BIG_G, keys)),
            "hml": _r(_compound(ff3, "HML", keys)),
            "smb": _r(_compound(ff3, "SMB", keys)),
        }

    def headline(series_m: dict, series_june: dict) -> dict:
        prev_june = sorted(series_june)[-2]
        return {
            "latest": {
                "date": _ym(last_m),
                "value": _r(series_m[last_m], 3),
                "estimate": bool(monthly[last_m]["_estimate"]),
            },
            "last_reading": {
                "date": _ym(last_june),
                "value": _r(series_june[last_june], 3),
            },
            "prior_reading": {
                "date": _ym(prev_june),
                "value": _r(series_june[prev_june], 3),
            },
            "percentile_monthly": _percentiles(series_m, last_m),
            "percentile_june": _percentiles(series_june, last_june),
            "peak_dotcom": _peak(series_m, "199701", "200212"),
            "peak_2020": _peak(series_m, "201801", "202212"),
            "trough_2007": {
                "date": _ym(
                    min(
                        (k for k in series_m if "200301" <= k <= "200912"),
                        key=series_m.get,
                    )
                ),
                "value": _r(
                    min(s for k, s in series_m.items() if "200301" <= k <= "200912"), 3
                ),
            },
        }

    annual_series = {
        "small_op": small_op,
        "large_op": large_op,
        **allcap,
    }
    annual_out = {}
    for name, series in annual_series.items():
        last = max(series)
        entry = {
            "points": [[_ym(k), _r(s, 3)] for k, s in sorted(series.items())],
            "latest": {"date": _ym(last), "value": _r(series[last], 3)},
            "percentile": _percentiles(series, last),
        }
        if name in ("allcap_bm", "allcap_ep", "allcap_cfp"):
            entry["peak_dotcom"] = _peak(series, "199701", "200212")
            entry["peak_2020"] = _peak(series, "201801", "202212")
        annual_out[name] = entry
    annual_out["small_op"]["estimate"] = {
        "date": _ym(last_m),
        "value": _r(small_op_est, 3),
    }
    annual_out["large_op"]["estimate"] = {
        "date": _ym(last_m),
        "value": _r(large_op_est, 3),
    }

    payload = {
        "_metadata": {
            "title": "Value spread (value B/M divided by growth B/M)",
            "source": "Kenneth R. French Data Library",
            "source_url": LIBRARY_URL,
            "crsp_cut": cut,
            "files": sorted(files.values()),
            "generated": date.today().isoformat(),
            "method": (
                "Spread = value portfolio book-to-market / growth portfolio "
                "book-to-market (equivalently growth P/B over value P/B). "
                "small/large: 2x3 size-B/M portfolios, top vs bottom 30% of B/M "
                "within each size half, June-price readings at each formation, "
                "months between formations rolled forward on value-weighted "
                "returns without dividends (book per share held fixed). "
                "small_op/large_op: 2x4x4 size-B/M-OP portfolios, geometric mean "
                "of highest/lowest B/M quartile within each OP quartile. "
                "allcap_*: univariate sorts, top/bottom 30%, December prices. "
                "Percentiles are empirical ranks (share of observations at or "
                "below the latest), computed over the full history shown."
            ),
            "computed_by": "Summitward calculations (summitward-research/value-spread/extract.py)",
        },
        "headline": {
            "small": headline(small_m, small_june),
            "large": headline(large_m, large_june),
        },
        "monthly": {
            "dates": [_ym(k) for k in sorted(monthly)],
            "small": [_r(small_m[k], 3) for k in sorted(monthly)],
            "large": [_r(large_m[k], 3) for k in sorted(monthly)],
            "estimate": [int(monthly[k]["_estimate"]) for k in sorted(monthly)],
        },
        "annual": annual_out,
        "forward": {
            "small": _forward(small_june, six_tot, SMALL_V, SMALL_G),
            "large": _forward(large_june, six_tot, BIG_V, BIG_G),
            "note": (
                "x = log spread at each June formation; y = annualized total "
                "return of value minus growth (same size half) over the next "
                "5 or 10 years starting that July. Windows overlap, so the "
                "Newey-West lag equals the horizon in years. Terciles are "
                "ranked on the full sample (hindsight). The out-of-sample "
                "R-squared fits each forecast only on outcomes already known "
                "at that date and compares it with the running mean."
            ),
        },
        "revisions": revisions,
        "recent_returns": recent,
    }

    for out in OUTPUTS:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, separators=(",", ":")) + "\n")
        print(
            f"Saved {out.relative_to(REPO_ROOT)} ({out.stat().st_size / 1024:.0f} KB)"
        )

    h = payload["headline"]
    for size in ("small", "large"):
        hd = h[size]
        print(
            f"{size}: {hd['latest']['date']} {hd['latest']['value']} "
            f"(June reading {hd['last_reading']['value']}, prior {hd['prior_reading']['value']}); "
            f"monthly pct full {hd['percentile_monthly']['full']}, "
            f"since 1963 {hd['percentile_monthly']['since_1963']}; "
            f"peaks {hd['peak_dotcom']} {hd['peak_2020']}"
        )
    for name, entry in annual_out.items():
        print(name, entry["latest"], entry["percentile"], entry.get("estimate", ""))
    for size in ("small", "large"):
        for hz, f in payload["forward"][size].items():
            print(
                size,
                hz,
                {
                    k: f[k]
                    for k in (
                        "n",
                        "slope_log_spread",
                        "t_newey_west",
                        "r2_in_sample",
                        "oos_r2",
                        "oos_forecasts",
                    )
                },
            )
            for t in f["terciles"]:
                print("   ", t)
            print("    at least as wide:", f["starts_at_least_as_wide_as_latest"])
    print("revisions", revisions)
    print("recent", json.dumps(recent))


if __name__ == "__main__":
    main()
