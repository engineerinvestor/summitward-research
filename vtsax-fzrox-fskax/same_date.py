"""Same-date holdings comparison of FZROX, FSKAX and VTSAX at August 31, 2026.

The SEC N-PORT filings that analyze.py reads have different period ends for
each fund, so their overlap figures mix index differences with timing. This
script uses holdings files that share one date instead:

- Fidelity's "Monthly Holdings Report" PDFs for FZROX and FSKAX, as of
  August 31, 2026 (fund document pages on fundresearch.fidelity.com, posted
  September 30, 2026).
- Vanguard's "Export full holdings" CSV for VTI, as of August 31, 2026
  (advisors.vanguard.com VTI portfolio page, date selector set to
  08/31/2026). VTI is the ETF share class of the fund VTSAX belongs to, so
  its holdings are VTSAX's.

These files are the issuers' and are not redistributed here. Save them as

    .cache/fzrox_2026-08-31.pdf
    .cache/fskax_2026-08-31.pdf
    .cache/vti_2026-08-31.csv

Needs `pdftotext` (poppler) on the PATH; otherwise standard library only.

Holdings are grouped by issuer: positions that share a SEDOL, a ticker root
(BRK.B and BRK/A both become BRK) or a cleaned name are linked, so share
classes collapse together. Futures and other derivatives are dropped. The
output gives each pair's active share, 1/2 * sum |w_A - w_B|, and the weight
each fund has in issuers the other does not hold.
"""

import csv
import re
import subprocess
from pathlib import Path

CACHE = Path(__file__).resolve().parent / ".cache"
FILES = {
    "FZROX": "fzrox_2026-08-31.pdf",
    "FSKAX": "fskax_2026-08-31.pdf",
    "VTSAX": "vti_2026-08-31.csv",
}

ROW = re.compile(r"^(?P<name>\S.*?)\s{2,}\$(?P<val>[\d,]+)\s+-?[\d.]+%\s*(?P<rest>.*)$")
SECTIONS = (
    "Domestic Equities",
    "Developed Markets",
    "Emerging Markets",
    "Tax-Advantaged Domiciles",
    "Cash and Other Securities",
)
FUTURES_TICKER = re.compile(r"^[A-Z]{2,3}[FGHJKMNQUVXZ]\d$")  # e.g. ESU6, RTYU6
SUFFIXES = (
    r"\b(INC|CORP|CORPORATION|CO|COS|LTD|PLC|NV|SA|AG|LLC|LP|HOLDINGS?|GROUP|"
    r"THE|CLASS [A-Z]|CL [A-Z]|COM|NEW|INCORPORATED|COMPANY|TRUST|REIT|SHS)\b"
)


def fidelity(path: Path):
    text = subprocess.run(
        ["pdftotext", "-layout", str(path), "-"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    section, rows = None, []
    for line in text.splitlines():
        s = line.strip()
        if s in SECTIONS:
            section = s
            continue
        if section in (None, "Cash and Other Securities") or "Total:" in s:
            continue
        m = ROW.match(s)
        if not m:
            continue
        rest = m["rest"].split()
        isin = next((t for t in rest if re.fullmatch(r"[A-Z]{2}[0-9A-Z]{9}\d", t)), "")
        sedol = rest[-1] if rest and re.fullmatch(r"[0-9B-Z][0-9A-Z]{6}", rest[-1]) else ""
        ticker = rest[0] if rest and rest[0] not in (isin, sedol) else ""
        if re.fullmatch(r"[0-9A-Z]{9}", ticker) and any(c.isdigit() for c in ticker):
            ticker = ""  # a CUSIP in the ticker column
        if FUTURES_TICKER.match(ticker) and not isin:
            continue  # index futures, which wrap onto two lines in the PDF
        rows.append(
            {"name": m["name"], "value": float(m["val"].replace(",", "")), "sedol": sedol, "ticker": ticker}
        )
    return rows


def vanguard(path: Path):
    rows, in_equity = [], False
    with path.open(encoding="utf-8-sig") as f:
        for r in csv.reader(f):
            if r and r[0]:
                in_equity = r[0].startswith("Equity")
                continue
            if not in_equity or len(r) < 10 or r[1] == "SEDOL":
                continue
            rows.append(
                {
                    "name": r[2],
                    "value": float(r[8].replace("$", "").replace(",", "")),
                    "sedol": r[1].strip(),
                    "ticker": r[3].strip(),
                }
            )
    return rows


def clean_name(name: str) -> str:
    n = re.sub(r"\(.*?\)", " ", name.upper())
    n = re.sub(r"[^A-Z0-9 ]", " ", n)
    n = re.sub(SUFFIXES, " ", n)
    return " ".join(n.split())


def is_derivative(name: str) -> bool:
    return bool(re.search(r"E-MINI|FUTURE|INDEX CON|SWAP", name.upper()))


def main():
    funds = {
        "FZROX": fidelity(CACHE / FILES["FZROX"]),
        "FSKAX": fidelity(CACHE / FILES["FSKAX"]),
        "VTSAX": vanguard(CACHE / FILES["VTSAX"]),
    }

    parent = {}

    def find(x):
        while parent.setdefault(x, x) != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for rows in funds.values():
        for r in rows:
            keys = ["N" + clean_name(r["name"])]
            if r["sedol"]:
                keys.append("S" + r["sedol"])
            if r["ticker"] and r["ticker"] != "---":
                keys.append("T" + re.split(r"[./]", r["ticker"])[0])
            r["key"] = keys[0]
            for k in keys[1:]:
                parent[find(keys[0])] = find(k)

    weights, names = {}, {}
    print("Holdings as of August 31, 2026, grouped by issuer")
    for fund, rows in funds.items():
        rows = [r for r in rows if r["value"] > 0 and not is_derivative(r["name"])]
        total = sum(r["value"] for r in rows)
        w = {}
        for r in rows:
            g = find(r["key"])
            w[g] = w.get(g, 0) + r["value"] / total
            names.setdefault(g, r["name"])
        weights[fund] = w
        print(f"   {fund}: {len(rows)} positions, {len(w)} issuers")

    print("\nPairs: active share, and weight in issuers the other fund does not hold")
    for a, b in (("FZROX", "VTSAX"), ("FZROX", "FSKAX"), ("FSKAX", "VTSAX")):
        wa, wb = weights[a], weights[b]
        active = 0.5 * sum(abs(wa.get(k, 0) - wb.get(k, 0)) for k in set(wa) | set(wb))
        only_b = sorted((k for k in wb if k not in wa), key=lambda k: -wb[k])
        only_a = sorted((k for k in wa if k not in wb), key=lambda k: -wa[k])
        print(f"   {a} vs {b}: active share {100 * active:.2f}%, overlap {100 * (1 - active):.2f}%")
        print(
            f"      {b} in issuers {a} lacks: {100 * sum(wb[k] for k in only_b):.2f}% "
            f"({len(only_b)} issuers); largest: "
            + "; ".join(f"{names[k][:30]} {100 * wb[k]:.3f}%" for k in only_b[:5])
        )
        print(
            f"      {a} in issuers {b} lacks: {100 * sum(wa[k] for k in only_a):.2f}% "
            f"({len(only_a)} issuers); largest: "
            + "; ".join(f"{names[k][:30]} {100 * wa[k]:.3f}%" for k in only_a[:5])
        )

    n = len(weights["FZROX"])
    print(f"\nWeight in issuers ranked below FZROX's issuer count ({n})")
    for fund in ("VTSAX", "FSKAX"):
        s = sorted(weights[fund].values(), reverse=True)
        print(f"   {fund}: {len(s) - n} issuers, {100 * sum(s[n:]):.3f}%")


if __name__ == "__main__":
    main()
