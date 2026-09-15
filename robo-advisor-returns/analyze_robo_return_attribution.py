#!/usr/bin/env python3
"""Attribute a robo-advisor's advertised historical return to its allocation.

Every number quoted in https://summitward.com/learn/robo-advisor-returns comes
from this script. It exists so those figures are auditable rather than remembered.

The question the guide asks is what part of an advertised robo-advisor return is
attributable to the service. This script answers the measurable part of it by
rebuilding the provider's own published asset allocation out of free index
returns and running it over two different eras.

Wealthfront publishes ticker-level target weights for exactly one risk score,
8.0 of 10, on its Classic portfolio page. Those weights are reproduced in
``WF_RISK8`` below. We map each sleeve to the closest long-history index series
we have committed locally, hold the weights fixed, and rebalance annually.

Three limits on what this can show, all of which the guide states:

1.  Wealthfront's advertised figure is a composite of actual client accounts,
    each compounded from its own funding date. This is a buy-and-hold CAGR of a
    fixed-weight portfolio. They are different measurement concepts and the
    difference is not a performance gap.
2.  The windows overlap but do not match. Wealthfront's runs from October 2012;
    ours runs over whole calendar years because the underlying series are annual.
3.  The published weights are risk score 8.0. The advertised headline is risk
    score 9.0, whose weights Wealthfront does not publish. We do not guess them.

So the output supports one claim only, and it is the claim the guide makes: the
same allocation, run by the same method, produces opposite verdicts against a
US-only portfolio depending on when you start. That is a fact about the era, not
about the algorithm.

Index proxies are approximate. S&P 500 stands in for a US total-market fund,
Baa corporates for an investment-grade corporate bond fund, and nominal
10-year Treasuries for a TIPS fund. Each is labelled in the printed output.

The script also summarises ``data/wealthfront_risk_ladder.json``, which is the
return Wealthfront reports at each of the twenty risk scores on its own
historical-performance page. That ladder is read from the page rather than
computed here, and it makes the same point without needing any benchmark: the
reported return climbs five percentage points as the risk score climbs, which is
what taking more equity risk in a rising market does.

Usage:
    python analyze_robo_return_attribution.py
    python analyze_robo_return_attribution.py --chart out
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"

# Wealthfront Classic portfolio, published example allocation at risk score 8.0
# of 10, medium tax level. Retrieved 2026-09-14 from
# https://www.wealthfront.com/explore/portfolios/core/classic
# VIG is counted as equity (it is a US large-cap fund and Wealthfront lists
# dividend growth among its equity asset classes). SCHP is counted as fixed
# income. That gives 82% equity / 18% fixed income.
WF_RISK8 = {
    "us": (0.48, "VTI 45% + VIG 3%", "S&P 500"),
    "dev": (0.18, "VEA 18%", "Fama-French developed ex-US"),
    "em": (0.16, "VWO 16%", "Fama-French emerging"),
    "corp": (0.12, "LQD 12%", "Baa corporate bonds"),
    "tsy": (0.06, "SCHP 6%", "10-year Treasury"),
}

# Whole calendar years. 2013 is the first full year after Wealthfront's
# October 2012 launch; 2025 is the last year our annual series cover.
WF_ERA = (2013, 2025)
# The 13 years immediately before it, chosen to be the same length so the
# comparison is not an artifact of window size.
PRIOR_ERA = (2000, 2012)


def load_series() -> dict[str, dict[str, float]]:
    """Return one dict of {year_string: annual total return} per sleeve key."""
    dam = json.loads((DATA / "damodaran_returns.json").read_text())["assets"]
    dev = json.loads((DATA / "ff_developed_annual.json").read_text())["annual"]
    em = json.loads((DATA / "ff_emerging_annual.json").read_text())["annual"]
    return {
        "us": dam["sp500"]["nominal"],
        "dev": dev,
        "em": em,
        "corp": dam["baa"]["nominal"],
        "tsy": dam["tbond"]["nominal"],
    }


def load_ladder() -> list[dict]:
    """Wealthfront's reported return at each risk score, read from its page."""
    return json.loads((DATA / "wealthfront_risk_ladder.json").read_text())["ladder"]


def cagr(returns: list[float]) -> float:
    growth = 1.0
    for r in returns:
        growth *= 1.0 + r
    return growth ** (1.0 / len(returns)) - 1.0


def blend(series: dict[str, dict[str, float]], years: list[str]) -> list[float]:
    """Annual returns of the fixed-weight portfolio, rebalanced each year."""
    return [
        sum(weight * series[key][y] for key, (weight, _, _) in WF_RISK8.items())
        for y in years
    ]


def years_in(era: tuple[int, int]) -> list[str]:
    return [str(y) for y in range(era[0], era[1] + 1)]


def run_era(series, era):
    years = years_in(era)
    port = cagr(blend(series, years))
    us_only = cagr([series["us"][y] for y in years])
    return port, us_only


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chart", metavar="OUTDIR", help="write the chart here")
    args = parser.parse_args()

    series = load_series()

    total_weight = sum(w for w, _, _ in WF_RISK8.values())
    equity = sum(w for k, (w, _, _) in WF_RISK8.items() if k in ("us", "dev", "em"))
    print("Wealthfront Classic, published risk score 8.0 weights")
    print(f"  weights sum to {total_weight:.2f}, equity share {equity:.0%}")
    for _key, (weight, holding, proxy) in WF_RISK8.items():
        print(f"  {holding:<22} {weight:>5.0%}  proxied by {proxy}")

    print("\nSame weights, free index funds, annually rebalanced:")
    header = f"  {'Era':<12}{'WF weights':>12}{'100% S&P 500':>14}{'difference':>12}"
    print(header)
    results = {}
    for era in (WF_ERA, PRIOR_ERA):
        port, us_only = run_era(series, era)
        results[era] = (port, us_only)
        label = f"{era[0]}-{era[1]}"
        print(
            f"  {label:<12}{port * 100:>11.2f}%{us_only * 100:>13.2f}%"
            f"{(port - us_only) * 100:>+11.2f}pp"
        )

    print("\nWhere the gap against 100% S&P 500 comes from:")
    print("  (82/18 with an all-US equity sleeve isolates the bond effect;")
    print("   the remainder is the international equity share)")
    for era in (WF_ERA, PRIOR_ERA):
        years = years_in(era)
        full, us_only = results[era]
        us_bond = cagr(
            [
                equity * series["us"][y]
                + WF_RISK8["corp"][0] * series["corp"][y]
                + WF_RISK8["tsy"][0] * series["tsy"][y]
                for y in years
            ]
        )
        print(
            f"  {era[0]}-{era[1]}  total {(full - us_only) * 100:+.2f}pp"
            f"  = bonds {(us_bond - us_only) * 100:+.2f}pp"
            f"  + international {(full - us_bond) * 100:+.2f}pp"
        )

    print("\nApproximate contribution to the {}-{} blend return:".format(*WF_ERA))
    years = years_in(WF_ERA)
    for key, (weight, holding, _) in WF_RISK8.items():
        sleeve = cagr([series[key][y] for y in years])
        print(
            f"  {holding:<22} weight {weight:>4.0%}"
            f"  sleeve {sleeve * 100:>6.2f}%"
            f"  contributes {weight * sleeve * 100:>5.2f}pp"
        )
    print("  (weight x sleeve CAGR; does not sum exactly to the blend because")
    print("   annual rebalancing and compounding interact)")

    ladder = load_ladder()
    best = max(ladder, key=lambda r: r["annualized_pct"])
    low = min(ladder, key=lambda r: r["annualized_pct"])
    print("\nWealthfront's own reported return by risk score (read from its page):")
    print(
        f"  lowest  risk {low['risk_score']:>4}  {low['annualized_pct']:.2f}%\n"
        f"  highest risk {best['risk_score']:>4}  {best['annualized_pct']:.2f}%\n"
        f"  spread {best['annualized_pct'] - low['annualized_pct']:.2f}pp across the scale"
    )
    top = sorted(ladder, key=lambda r: -r["annualized_pct"])[:3]
    print(
        "  best three: "
        + ", ".join(f"risk {r['risk_score']} {r['annualized_pct']:.2f}%" for r in top)
    )
    drops = [
        (ladder[i]["risk_score"], ladder[i + 1]["risk_score"])
        for i in range(len(ladder) - 1)
        if ladder[i + 1]["annualized_pct"] < ladder[i]["annualized_pct"]
    ]
    print(f"  steps where more risk reported less return: {drops}")

    if args.chart:
        write_chart(results, args.chart)
        write_ladder_chart(ladder, args.chart)


def write_chart(results, outdir: str) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    eras = [WF_ERA, PRIOR_ERA]
    labels = [f"{a}-{b}" for a, b in eras]
    wf_vals = [results[e][0] * 100 for e in eras]
    us_vals = [results[e][1] * 100 for e in eras]

    x = range(len(eras))
    width = 0.34
    fig, ax = plt.subplots(figsize=(14, 7.88), dpi=100)
    b1 = ax.bar(
        [i - width / 2 for i in x],
        wf_vals,
        width,
        label="Wealthfront's published risk-8 weights, as index funds",
        color="#0f766e",
    )
    b2 = ax.bar(
        [i + width / 2 for i in x],
        us_vals,
        width,
        label="100% S&P 500",
        color="#c2410c",
    )
    for bars in (b1, b2):
        for bar in bars:
            ax.annotate(
                f"{bar.get_height():.2f}%",
                (bar.get_x() + bar.get_width() / 2, bar.get_height()),
                textcoords="offset points",
                xytext=(0, 4),
                ha="center",
                fontsize=13,
                fontweight="bold",
            )

    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, fontsize=13)
    ax.set_ylabel("Annualized nominal return (%)", fontsize=13)
    ax.set_title(
        "The same allocation, two eras\n"
        "An 82/18 global blend trailed US stocks by 4.6pp a year in one era and "
        "led by 3.5pp in the other",
        fontsize=15,
    )
    ax.legend(fontsize=12, loc="upper right")
    ax.grid(alpha=0.3, linestyle="--", axis="y")
    ax.set_axisbelow(True)
    ax.set_ylim(0, max(wf_vals + us_vals) * 1.18)
    fig.tight_layout()

    png = f"{outdir}/robo-return-attribution.png"
    fig.savefig(png)
    webp = f"{outdir}/robo-return-attribution.webp"
    from PIL import Image

    Image.open(png).save(webp, "WEBP", quality=88, method=6)
    Path(png).unlink()
    print(f"\nchart -> {webp}")


def write_ladder_chart(ladder: list[dict], outdir: str) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    xs = [r["risk_score"] for r in ladder]
    ys = [r["annualized_pct"] for r in ladder]
    peak = max(ladder, key=lambda r: r["annualized_pct"])

    fig, ax = plt.subplots(figsize=(14, 7.88), dpi=100)
    colors = [
        "#c2410c" if r["risk_score"] == peak["risk_score"] else "#5b52b5"
        for r in ladder
    ]
    ax.bar(xs, ys, width=0.38, color=colors)
    ax.annotate(
        f"The advertised number\nrisk score {peak['risk_score']:g}, {peak['annualized_pct']:.2f}%",
        (peak["risk_score"], peak["annualized_pct"]),
        textcoords="offset points",
        xytext=(-18, 26),
        ha="center",
        fontsize=13,
        fontweight="bold",
        color="#c2410c",
        arrowprops={"arrowstyle": "->", "color": "#c2410c", "lw": 2},
    )
    ax.set_xlabel(
        "Wealthfront risk score (0.5 = most conservative, 10 = most aggressive)",
        fontsize=13,
    )
    ax.set_ylabel("Reported annualized return since 2012 (%)", fontsize=13)
    ax.set_title(
        "Wealthfront's reported return at every risk score\n"
        "Taxable Classic portfolio, as of September 13 2026, read from its own "
        "historical-performance page",
        fontsize=15,
    )
    ax.set_xticks(xs)
    ax.set_xticklabels([f"{x:g}" for x in xs], fontsize=10)
    ax.grid(alpha=0.3, linestyle="--", axis="y")
    ax.set_axisbelow(True)
    ax.set_ylim(0, max(ys) * 1.22)
    fig.tight_layout()

    png = f"{outdir}/robo-risk-score-ladder.png"
    fig.savefig(png)
    webp = f"{outdir}/robo-risk-score-ladder.webp"
    from PIL import Image

    Image.open(png).save(webp, "WEBP", quality=88, method=6)
    Path(png).unlink()
    print(f"chart -> {webp}")


if __name__ == "__main__":
    main()
