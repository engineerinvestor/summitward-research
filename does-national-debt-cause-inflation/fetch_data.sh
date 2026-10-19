#!/usr/bin/env bash
# Download the source data into .cache/ (gitignored; not redistributed here).
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p .cache
UA='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'
# JST Macrohistory Database, release 6 (Stata file; the site serves it under this link).
curl -sL -A "$UA" -o .cache/JSTdatasetR6.dta \
  'https://www.macrohistory.net/app/download/9834512469/JSTdatasetR6.dta?t=1720600177'
# OMB Historical Tables, FY2027 Budget (April 2026).
for t in 01z1 03z1 07z1 10z1; do
  curl -sL -A "$UA" -o ".cache/hist${t}_fy2027.xlsx" \
    "https://www.whitehouse.gov/wp-content/uploads/2026/04/hist${t}_fy2027.xlsx"
done
ls -la .cache
