"""Count proposed sports team ETFs on EDGAR and work out how much of an NBA
team index is zero-sum across the league.

Supports https://summitward.com/learn/sports-team-etfs

Part 1 searches EDGAR full-text search for 485APOS filings that mention the
CME FutureSports Performance Indexes ("FSPI" or "FutureSports"), opens each
filing's index page and counts the new fund series it registers, by issuer,
league and leverage. It then checks that no 485BPOS, 497 or 497K mentioning
FSPI exists, i.e. that no sports team fund has an effective prospectus.

Part 2 uses only the scoring rules stated in the LeagueShares NBA 485APOS of
November 24, 2026 (no index values) to compute how much the sum of all 30 NBA
team indexes can change in a season from the game-result and postseason
constituents. No FutureSports index data is read or stored: its data terms
of use bar compiling or analyzing index values without written consent.

Standard library only. Set SEC_USER_AGENT="Name email" to identify yourself
to the SEC, as its fair-access policy asks.

    python analyze.py            # writes output/sports-team-etfs.json
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

UA = {"User-Agent": os.environ.get("SEC_USER_AGENT", "summitward-research research@example.com")}
START, END = "2026-06-01", "2026-11-25"
OUT = Path(__file__).parent / "output" / "sports-team-etfs.json"

ISSUERS = {
    "1122649": "LeagueShares",
    "1884021": "Volatility Shares",
    "1976517": "Roundhill",
    "2043954": "REX (Alpha Sports)",
}


def get(url: str) -> str:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        body = r.read().decode("utf-8", "replace")
    time.sleep(0.25)  # stay well under the SEC's 10 requests/second
    return body


def fts(query: str, forms: str) -> list[dict]:
    hits, frm = [], 0
    while True:
        url = "https://efts.sec.gov/LATEST/search-index?" + urllib.parse.urlencode(
            {"q": query, "forms": forms, "dateRange": "custom",
             "startdt": START, "enddt": END, "from": frm})
        d = json.loads(get(url))
        page = d["hits"]["hits"]
        hits += page
        frm += len(page)
        if not page or frm >= d["hits"]["total"]["value"]:
            return hits


def league_of(names: list[str]) -> str:
    text = " ".join(names)
    if re.search(r"Basketball|Hawks.*On-Court|Celtics|Lakers|Knicks", text):
        return "NBA"
    if re.search(r"Diamondbacks|Yankees|Dodgers|Mariners|Baseball", text):
        return "MLB"
    if re.search(r"Ducks|Bruins|Kraken|Oilers|Hockey", text):
        return "NHL"
    raise ValueError(f"cannot classify league: {names[:2]}")


def count_filings() -> dict:
    filings = {}
    for q in ('"FSPI"', '"FutureSports"'):
        for h in fts(q, "485APOS"):
            s = h["_source"]
            acc = h["_id"].split(":")[0]
            filings[acc] = {"date": s["file_date"], "cik": s["ciks"][0].lstrip("0")}
    rows = []
    for acc, f in sorted(filings.items(), key=lambda x: (x[1]["date"], x[0])):
        cik = f["cik"]
        idx = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc.replace('-', '')}/{acc}-index.htm"
        html = get(idx)
        series = re.findall(
            r'class="seriesName">Series <a[^>]*>(S\d{9})</a></td>\s*<td[^>]*>([^<]*)</td>\s*<td[^>]*>([^<]*)</td>',
            html)
        names = [n for _, status, n in series if status.strip() == "new"]
        leveraged = sum(bool(re.search(r"Leveraged|\b2x\b", n)) for n in names)
        rows.append({
            "date": f["date"], "accession": acc, "issuer": ISSUERS.get(cik, cik),
            "league": league_of(names), "newSeries": len(names),
            "leveragedSeries": leveraged, "indexUrl": idx,
        })
    by_issuer, by_league = Counter(), Counter()
    for r in rows:
        by_issuer[r["issuer"]] += r["newSeries"]
        by_league[r["league"]] += r["newSeries"]
    effective = {f: len(fts('"FSPI"', f)) + len(fts('"FutureSports"', f))
                 for f in ("485BPOS", "497", "497K")}
    return {
        "filings": rows,
        "total": sum(by_issuer.values()),
        "leveraged": sum(r["leveragedSeries"] for r in rows),
        "byIssuer": dict(by_issuer),
        "byLeague": dict(by_league),
        "effectiveFilingHits": effective,
    }


def nba_league_sum() -> dict:
    """Range of the change in the sum of all 30 NBA indexes from the
    game-result and postseason constituents in the Nov 24, 2026 filing."""
    teams, base = 30, 7500
    win, loss = 10, -10                 # every regular-season game: nets to 0
    qualify, miss = 80, -80             # 16 teams reach round one (incl. play-in)
    qualifiers = 16
    po_win, po_loss = 20, -5            # replaces the regular win/loss values
    champion = 250
    series = 15                         # 8 + 4 + 2 + 1 best-of-seven series
    regular = win + loss
    qual = qualifiers * qualify + (teams - qualifiers) * miss
    per_po_game = po_win + po_loss
    lo_games, hi_games = series * 4, series * 7
    lo = regular + qual + per_po_game * lo_games + champion
    hi = regular + qual + per_po_game * hi_games + champion
    total_base = teams * base
    return {
        "teams": teams, "baseTotal": total_base,
        "qualificationNet": qual, "pointsPerPlayoffGame": per_po_game,
        "playoffGames": [lo_games, hi_games], "champion": champion,
        "changeRange": [lo, hi],
        "changePctRange": [round(100 * lo / total_base, 2), round(100 * hi / total_base, 2)],
        "excluded": "free throws missed (no listed counterpart; weight not "
                    "disclosed) and the in-season tournament final bonus",
    }


def main() -> None:
    out = {"asOf": END, "edgar": count_filings(), "nbaLeagueSum": nba_league_sum()}
    e = out["edgar"]
    assert e["total"] == sum(e["byLeague"].values())
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps({k: v for k, v in e.items() if k != "filings"}, indent=2))
    print(json.dumps(out["nbaLeagueSum"], indent=2))


if __name__ == "__main__":
    main()
