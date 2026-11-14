"""SPAXX vs. FDRXX (and FDLXX): where the yield gap comes from.

Reads data/nmfp_monthly.csv and data/nmfp_composition.csv (written by
fetch_data.py from SEC Form N-MFP2/N-MFP3) and prints:

1. Gross and net 7-day yield spreads, FDRXX minus SPAXX, Oct 2016-Oct 2026.
2. The net spread by gross-yield level, and the implied expense ratio
   (gross minus net 7-day yield) by calendar year.
3. Calendar-year total returns from the funds' prospectuses, for comparison.
4. Portfolio composition in the latest month and the range of repo shares.
5. After-tax yields for the three funds under three state-tax cases, for 2024
   and 2025 actual returns and for the Nov 13, 2026 seven-day yields.

Standard library only. Also writes out/chart_monthly.json for the guide's chart.
"""

import csv
import json
import statistics as st
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
OUT = HERE / "out"

# Calendar-year total returns (%), from the bar charts in the SPAXX/FDLXX
# prospectus dated June 29, 2026 and the FDRXX prospectus dated Jan 29, 2026.
RETURNS = {
    "SPAXX": [0.04, 0.51, 1.47, 1.84, 0.26, 0.01, 1.31, 4.78, 4.92, 3.95],
    "FDRXX": [0.09, 0.56, 1.52, 1.90, 0.27, 0.01, 1.34, 4.79, 4.95, 4.01],
    "FDLXX": [0.01, 0.47, 1.47, 1.81, 0.26, 0.01, 1.26, 4.65, 4.90, 3.90],
}
YEARS = list(range(2016, 2026))

# Share of income from U.S. government securities (%) and whether the fund
# met the California/Connecticut/New York minimum, from Fidelity's
# TY24GSESupplementalLetter.pdf and ty25-gse-supplemental-letter.pdf.
GOV_INCOME = {
    2024: {"SPAXX": (55.09, True), "FDRXX": (57.19, True), "FDLXX": (97.00, True)},
    2025: {"SPAXX": (50.90, False), "FDRXX": (52.17, False), "FDLXX": (98.67, True)},
}

# Seven-day yields (%) on Nov 13, 2026, Fidelity daily money market pricing.
YIELDS_NOV13 = {"SPAXX": 3.55, "FDRXX": 3.61, "FDLXX": 3.62}

# SPAXX's Sep 2017 filing reports a 0.98% net yield on a 1.09% gross yield,
# which would mean 0.11% of expenses in a year when every other month implies
# 0.42%, and SPAXX's 2017 calendar return trailed FDRXX's. Treated as a filing
# error: kept in the CSV, excluded from the statistics and the chart.
ANOMALIES = {"2017-09"}

FEDERAL = 0.24
STATE = 0.05  # a state that exempts the government share pro rata, no asset test
STATE_CA = 0.093  # California's 9.3% bracket; CA applies the 50% asset test
BALANCE = 100_000


def load() -> dict[str, dict[str, dict]]:
    by: dict[str, dict[str, dict]] = {}
    for r in csv.DictReader((DATA / "nmfp_monthly.csv").open()):
        by.setdefault(r["ticker"], {})[r["report_month"]] = r
    return by


def pct(x: str) -> float:
    return float(x) * 100


def bp(x: float) -> str:
    """Format a difference given in percentage points as basis points."""
    return f"{x * 100:+.1f}bp"


def after_tax(y: float, gov: float, passed: bool, case: str) -> float:
    """Annual after-tax yield (%), all income federally taxable as ordinary
    income, fixed marginal rates, no federal deduction for state tax."""
    if case == "none":
        state = 0.0
    elif case == "other":  # exemption applies pro rata, no asset test
        state = STATE * (1 - gov / 100)
    elif case == "ca":  # CA/CT/NY: exemption only if the fund met the minimum
        state = STATE_CA * ((1 - gov / 100) if passed else 1.0)
    elif case == "hsa":  # federal tax-free; nothing at the state level
        return y
    elif case == "hsa_ca":  # California taxes HSA earnings in the year earned
        return y * (1 - STATE_CA * ((1 - gov / 100) if passed else 1.0))
    else:
        raise ValueError(case)
    return y * (1 - FEDERAL - state)


def main() -> None:
    by = load()
    months = sorted(by["SPAXX"])
    print(f"Excluded as filing errors: SPAXX {', '.join(sorted(ANOMALIES))}\n")
    rows = []
    for m in months:
        if m in ANOMALIES:
            continue
        s, f, t = by["SPAXX"][m], by["FDRXX"][m], by["FDLXX"][m]
        rows.append(
            {
                "month": m,
                "gross_spaxx": pct(s["gross_last"]),
                "gross_fdrxx": pct(f["gross_last"]),
                "gross_fdlxx": pct(t["gross_last"]),
                "net_spaxx": pct(s["net_last"]),
                "net_fdrxx": pct(f["net_last"]),
                "net_fdlxx": pct(t["net_last"]),
            }
        )
    for r in rows:
        r["gross_spread"] = r["gross_fdrxx"] - r["gross_spaxx"]
        r["net_spread"] = r["net_fdrxx"] - r["net_spaxx"]
        r["exp_spaxx"] = r["gross_spaxx"] - r["net_spaxx"]
        r["exp_fdrxx"] = r["gross_fdrxx"] - r["net_fdrxx"]
        r["exp_gap"] = r["exp_spaxx"] - r["exp_fdrxx"]

    print("1. FDRXX minus SPAXX, month-end 7-day yields,", months[0], "to", months[-1])
    gs = [r["gross_spread"] for r in rows]
    ns = [r["net_spread"] for r in rows]
    print(f"   months: {len(rows)}")
    print(
        f"   gross spread: mean {bp(st.mean(gs))}, median {bp(st.median(gs))},"
        f" min {bp(min(gs))}, max {bp(max(gs))}"
    )
    within1 = sum(abs(g) <= 0.0101 for g in gs)
    within2 = sum(abs(g) <= 0.0201 for g in gs)
    print(
        f"   gross spread within 1bp: {within1}/{len(gs)}; within 2bp: {within2}/{len(gs)}"
    )
    wide = [
        f"{r['month']} {bp(r['gross_spread'])}"
        for r in rows
        if abs(r["gross_spread"]) > 0.0101
    ]
    print(f"   months with |gross spread| > 1bp: {', '.join(wide)}")
    last12 = rows[-12:]
    print(
        f"   last 12 months ({last12[0]['month']}..{last12[-1]['month']}): mean net spread {bp(st.mean(r['net_spread'] for r in last12))}, mean gross spread {bp(st.mean(r['gross_spread'] for r in last12))}"
    )
    print(
        f"   net spread: mean {bp(st.mean(ns))}, median {bp(st.median(ns))},"
        f" min {bp(min(ns))}, max {bp(max(ns))}"
    )
    fdrxx_ahead = sum(n > 0.0001 for n in ns)
    tied = sum(abs(n) <= 0.0001 for n in ns)
    print(
        f"   FDRXX net ahead: {fdrxx_ahead} months, tied: {tied}, behind: {len(ns) - fdrxx_ahead - tied}"
    )
    # How much of the net spread the gross spread explains
    resid = [r["net_spread"] - r["gross_spread"] - r["exp_gap"] for r in rows]
    print(
        f"   identity check (net = gross + expense gap), max residual: {max(map(abs, resid)):.6f}"
    )

    print("\n2. Net spread by SPAXX gross-yield level (month-end)")
    buckets = [
        ("waiver floor: SPAXX net <= 0.02%", lambda r: r["net_spaxx"] <= 0.02),
        ("gross 0.25-1%", lambda r: r["net_spaxx"] > 0.02 and r["gross_spaxx"] < 1),
        ("gross 1-3%", lambda r: r["net_spaxx"] > 0.02 and 1 <= r["gross_spaxx"] < 3),
        ("gross 3-4.5%", lambda r: 3 <= r["gross_spaxx"] < 4.5),
        ("gross 4.5%+", lambda r: r["gross_spaxx"] >= 4.5),
    ]
    for label, cond in buckets:
        sel = [r for r in rows if cond(r)]
        if not sel:
            continue
        print(
            f"   {label:34s} n={len(sel):3d}  net spread mean {bp(st.mean(r['net_spread'] for r in sel))}"
            f"  gross spread mean {bp(st.mean(r['gross_spread'] for r in sel))}"
            f"  implied exp SPAXX {st.mean(r['exp_spaxx'] for r in sel):.2f}%"
            f" FDRXX {st.mean(r['exp_fdrxx'] for r in sel):.2f}%"
        )
    print(
        "\n   Implied expense ratio (gross minus net 7-day yield), calendar-year mean of month-ends"
    )
    print(
        "   year   SPAXX  FDRXX  FDLXX   gap(SPAXX-FDRXX)  mean net spread  mean SPAXX gross"
    )
    for y in range(2016, 2027):
        sel = [r for r in rows if r["month"].startswith(str(y))]
        if not sel:
            continue
        print(
            f"   {y}   {st.mean(r['exp_spaxx'] for r in sel):.2f}   {st.mean(r['exp_fdrxx'] for r in sel):.2f}"
            f"   {st.mean(r['gross_fdlxx'] - r['net_fdlxx'] for r in sel):.2f}"
            f"   {bp(st.mean(r['exp_gap'] for r in sel)):>10s}"
            f"        {bp(st.mean(r['net_spread'] for r in sel)):>9s}"
            f"        {st.mean(r['gross_spaxx'] for r in sel):.2f}%  (n={len(sel)})"
        )
    unwaived = [r for r in rows if r["net_spaxx"] > 0.02 and r["gross_spaxx"] >= 1]
    xs = [r["gross_spaxx"] for r in unwaived]
    ys = [r["net_spread"] for r in unwaived]
    print(
        f"\n   Correlation of net spread with gross yield, months with gross >= 1% and no waiver floor"
        f" (n={len(unwaived)}): {st.correlation(xs, ys):+.2f}"
    )
    slope = st.linear_regression(xs, ys).slope
    print(f"   OLS slope: {slope * 100:+.2f}bp of spread per 1 point of gross yield")

    print("\n3. Calendar-year total returns from the prospectuses (%)")
    print("   year  SPAXX  FDRXX  FDLXX  FDRXX-SPAXX  FDLXX-FDRXX")
    for i, y in enumerate(YEARS):
        s, f, t = (RETURNS[k][i] for k in ("SPAXX", "FDRXX", "FDLXX"))
        print(
            f"   {y}  {s:5.2f}  {f:5.2f}  {t:5.2f}   {round((f - s) * 100):+3d}bp       {round((t - f) * 100):+3d}bp"
        )
    last10 = [(RETURNS["FDRXX"][i] - RETURNS["SPAXX"][i]) for i in range(10)]
    print(
        f"   FDRXX ahead in {sum(d > 0.0001 for d in last10)} of 10 years, tied {sum(abs(d) <= 0.0001 for d in last10)}"
    )

    print("\n4. Composition, % of net assets (SEC investment categories)")
    comp = {}
    for r in csv.DictReader((DATA / "nmfp_composition.csv").open()):
        comp.setdefault(r["ticker"], {})[r["report_month"]] = {
            k: float(v) * 100
            for k, v in r.items()
            if k not in ("ticker", "report_month")
        }
    last = months[-1]
    months = [m for m in months if m not in ANOMALIES]
    for t in ("SPAXX", "FDRXX", "FDLXX"):
        c = comp[t][last]
        repo = c.get("treasury_repo", 0) + c.get("agency_repo", 0)
        agency = c.get("agency_debt", 0)
        fhlb_ffcb = c.get("agency_fhlb", 0) + c.get("agency_farm_credit", 0)
        print(
            f"   {t} {last}: Treasury debt {c.get('treasury_debt', 0):.2f}, agency debt {agency:.2f}"
            f" (FHLB+Farm Credit {fhlb_ffcb:.2f}, Fannie+Freddie"
            f" {c.get('agency_fannie_mae', 0) + c.get('agency_freddie_mac', 0):.2f}),"
            f" repo {repo:.2f} (Treasury repo {c.get('treasury_repo', 0):.2f}, agency repo"
            f" {c.get('agency_repo', 0):.2f}), other {c.get('other', 0):.2f}"
        )
    for t in ("SPAXX", "FDRXX"):
        reps = {
            m: comp[t][m].get("treasury_repo", 0) + comp[t][m].get("agency_repo", 0)
            for m in comp[t]
            if m >= "2024-01"
        }
        lo, hi = min(reps, key=reps.get), max(reps, key=reps.get)
        print(
            f"   {t} repo share Jan 2024-{last}: {reps[lo]:.1f}% ({lo}) to {reps[hi]:.1f}% ({hi})"
        )
    diff = [
        (
            comp["FDRXX"][m].get("treasury_repo", 0)
            + comp["FDRXX"][m].get("agency_repo", 0)
        )
        - (
            comp["SPAXX"][m].get("treasury_repo", 0)
            + comp["SPAXX"][m].get("agency_repo", 0)
        )
        for m in months
        if m >= "2024-01"
    ]
    print(
        f"   FDRXX minus SPAXX repo share since Jan 2024: mean {st.mean(diff):+.1f} points, range {min(diff):+.1f} to {max(diff):+.1f}"
    )

    print(f"\n5. After-tax yield (%), {FEDERAL:.0%} federal; dollars per ${BALANCE:,}")
    cases = [
        ("none", "no state income tax"),
        ("other", "5% state, pro rata exemption"),
        ("ca", "California 9.3%, 50% asset test"),
        ("hsa", "HSA, no state tax"),
        ("hsa_ca", "HSA in California (9.3%)"),
    ]
    sources = [
        (
            "2024 total return",
            2024,
            {k: RETURNS[k][YEARS.index(2024)] for k in RETURNS},
        ),
        (
            "2025 total return",
            2025,
            {k: RETURNS[k][YEARS.index(2025)] for k in RETURNS},
        ),
        ("Nov 13, 2026 7-day yield, 2025 tax data", 2025, YIELDS_NOV13),
    ]
    for label, tax_year, ylds in sources:
        print(f"   {label}")
        for case, case_label in cases:
            vals = {
                k: after_tax(ylds[k], *GOV_INCOME[tax_year][k], case)
                for k in ("SPAXX", "FDRXX", "FDLXX")
            }
            best = max(vals, key=vals.get)
            print(
                f"     {case_label:30s} SPAXX {vals['SPAXX']:.3f}  FDRXX {vals['FDRXX']:.3f}  FDLXX {vals['FDLXX']:.3f}"
                f"  | FDRXX-SPAXX ${(vals['FDRXX'] - vals['SPAXX']) * BALANCE / 100:,.0f}"
                f"  FDLXX-FDRXX ${(vals['FDLXX'] - vals['FDRXX']) * BALANCE / 100:,.0f}  best {best}"
            )
    g25 = GOV_INCOME[2025]
    extra = (g25["FDRXX"][0] - g25["SPAXX"][0]) / 100
    print(
        f"\n   Value of FDRXX's extra 2025 exempt share ({extra * 100:.2f} points) at its Nov 13 yield and a 5% state rate:"
        f" ${BALANCE * YIELDS_NOV13['FDRXX'] / 100 * extra * STATE:.2f} per ${BALANCE:,} a year"
    )
    for bal in (25_000, 100_000):
        pre = bal * (YIELDS_NOV13["FDRXX"] - YIELDS_NOV13["SPAXX"]) / 100
        print(
            f"   Nov 13 gap on ${bal:,}: ${pre:.0f} before tax, ${pre * (1 - FEDERAL):.0f} after {FEDERAL:.0%} federal,"
            f" ${pre * (1 - 0.32):.0f} after 32% federal"
        )

    OUT.mkdir(exist_ok=True)
    chart = [
        {
            "m": r["month"],
            "grossSpaxx": round(r["gross_spaxx"], 2),
            "grossFdrxx": round(r["gross_fdrxx"], 2),
            "netSpread": round(r["net_spread"] * 100, 1),
            "grossSpread": round(r["gross_spread"] * 100, 1),
            "expGap": round(r["exp_gap"] * 100, 1),
        }
        for r in rows
    ]
    (OUT / "chart_monthly.json").write_text(json.dumps(chart))
    print("\nwrote out/chart_monthly.json")


if __name__ == "__main__":
    main()
