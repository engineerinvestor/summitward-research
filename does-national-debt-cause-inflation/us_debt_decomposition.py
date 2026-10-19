"""What moved US federal debt held by the public as a share of GDP, FY1946-2025.

Each fiscal year's change in the debt ratio b = B/Y splits exactly into

    db = PD/Y + NI/Y - b0 * pi/(1+g) - b0 * gamma*(1+pi)/(1+g) + SF/Y

where PD is the primary deficit, NI net interest outlays, pi the GDP-price
inflation rate, gamma real GDP growth, 1+g = (1+gamma)(1+pi) nominal growth,
and SF the stock-flow residual (debt change not explained by the deficit:
cash balance changes, credit programs, the 1976 transition quarter).

Nominal interest plus the inflation term is the real interest cost of the
debt; Hall and Sargent (2011) report that net figure for 1945-74.

    python3 us_debt_decomposition.py           # prints the tables
    python3 us_debt_decomposition.py --json    # also writes output/us_debt_decomposition.json

Data: OMB Historical Tables, FY2027 Budget (April 2026): Table 1.1 (deficit),
3.1 (net interest), 7.1 (debt held by the public), 10.1 (GDP and the GDP
chained price index, fiscal years). Run fetch_data.sh first.
"""

import json
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).parent
C = HERE / ".cache"

ERAS = [
    ("FY1946-1974", 1946, 1974),
    ("FY1975-2007", 1975, 2007),
    ("FY2008-2019", 2008, 2019),
    ("FY2020-2025", 2020, 2025),
    ("FY2021-2023", 2021, 2023),
    ("FY1946-2025", 1946, 2025),
]


def _num(x):
    try:
        return float(str(x).replace(",", ""))
    except ValueError:
        return None


def load() -> pd.DataFrame:
    t1 = pd.read_excel(C / "hist01z1_fy2027.xlsx", header=None)
    t3 = pd.read_excel(C / "hist03z1_fy2027.xlsx", header=None)
    t7 = pd.read_excel(C / "hist07z1_fy2027.xlsx", header=None)
    t10 = pd.read_excel(C / "hist10z1_fy2027.xlsx", header=None)

    deficit = {}  # millions, positive = deficit
    for _, r in t1.iterrows():
        k, v = str(r[0]).strip(), _num(r[3])
        if v is not None and (k.isdigit() or k == "TQ"):
            deficit[k] = -v

    row = t3.index[t3[0].astype(str).str.strip() == "Net interest"][0]  # $m row
    interest = {}
    for col in t3.columns[1:]:
        k = str(t3.iloc[1, col]).strip()
        v = _num(t3.iloc[row, col])
        if v is not None and (k.isdigit() or k == "TQ"):
            interest[k] = v

    debt = {}  # held by the public, millions, end of fiscal year
    for _, r in t7.iterrows():
        k, v = str(r[0]).strip(), _num(r[3])
        if v is not None and (k.isdigit() or k == "TQ"):
            debt[k] = v

    gdp, price = {}, {}
    for _, r in t10.iterrows():
        k = str(r[0]).strip()
        if k.isdigit():
            gdp[k], price[k] = 1000 * _num(r[1]), _num(r[2])

    rows = []
    for y in range(1946, 2026):
        k, k0 = str(y), str(y - 1)
        pd_ = deficit[k] - interest[k]
        ni = interest[k]
        if y == 1977:  # FY1977 step also covers the July-Sept 1976 transition quarter
            pd_ += deficit["TQ"] - interest["TQ"]
            ni += interest["TQ"]
        Y, Y0 = gdp[k], gdp[k0]
        b0, b1 = debt[k0] / Y0, debt[k] / Y
        g = Y / Y0 - 1
        pi = price[k] / price[k0] - 1
        gamma = (1 + g) / (1 + pi) - 1
        parts = {
            "primary_deficit": pd_ / Y,
            "interest": ni / Y,
            "inflation": -b0 * pi / (1 + g),
            "real_growth": -b0 * gamma * (1 + pi) / (1 + g),
        }
        parts["residual"] = (b1 - b0) - sum(parts.values())
        rows.append(
            {
                "fy": y,
                "b_start": b0,
                "b_end": b1,
                "change": b1 - b0,
                "pi": pi,
                "gamma": gamma,
                **parts,
            }
        )
    return pd.DataFrame(rows).set_index("fy")


COMPONENTS = ["primary_deficit", "interest", "inflation", "real_growth", "residual"]


def main() -> None:
    d = load()
    out = {"eras": {}, "annual": {}}
    print("Debt held by the public, % of GDP; contributions in percentage points.\n")
    hdr = (
        f"{'era':12s} {'start':>6s} {'end':>6s} {'change':>7s} "
        + " ".join(f"{c[:9]:>9s}" for c in COMPONENTS)
        + f" {'real int':>8s}"
    )
    print(hdr)
    for name, lo, hi in ERAS:
        s = d.loc[lo:hi]
        tot = {c: 100 * s[c].sum() for c in COMPONENTS}
        rec = {
            "start": 100 * s["b_start"].iloc[0],
            "end": 100 * s["b_end"].iloc[-1],
            "change": 100 * s["change"].sum(),
            **tot,
            "real_interest": tot["interest"] + tot["inflation"],
            "avg_inflation": 100 * ((1 + s["pi"]).prod() ** (1 / len(s)) - 1),
            "avg_real_growth": 100 * ((1 + s["gamma"]).prod() ** (1 / len(s)) - 1),
        }
        out["eras"][name] = {k: round(v, 2) for k, v in rec.items()}
        print(
            f"{name:12s} {rec['start']:6.1f} {rec['end']:6.1f} {rec['change']:+7.1f} "
            + " ".join(f"{tot[c]:+9.1f}" for c in COMPONENTS)
            + f" {rec['real_interest']:+8.1f}"
        )
    print("\nAverage GDP-price inflation and real growth by era (%/yr):")
    for name, v in out["eras"].items():
        print(
            f"  {name:12s} inflation {v['avg_inflation']:.2f}  real growth {v['avg_real_growth']:.2f}"
        )
    print("\nFY2019-2025 by year (pp):")
    print(
        (100 * d.loc[2019:2025, ["b_end", "change", *COMPONENTS, "pi"]])
        .round(2)
        .to_string()
    )
    out["annual"] = {
        int(y): {k: round(100 * v, 3) for k, v in r.items()} for y, r in d.iterrows()
    }
    if "--json" in sys.argv:
        (HERE / "output").mkdir(exist_ok=True)
        (HERE / "output" / "us_debt_decomposition.json").write_text(
            json.dumps(out, indent=2)
        )


if __name__ == "__main__":
    main()
