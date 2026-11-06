# more-buyers-than-sellers

Supports https://summitward.com/learn/more-buyers-than-sellers.

`sec_order_metrics.py` averages two SEC market structure metrics for corporate
stocks and exchange-traded products (ETPs):

- **Trade-Order Volume (%)**: shares traded during continuous trading divided
  by the share volume of every displayed limit order, at any price level,
  across the exchange feeds the SEC processes. Opening and closing crosses are
  excluded. Definition: SEC Data Highlight 2013-01,
  https://www.sec.gov/about/trade-order-volume-ratios
- **Cancel-Trade Ratio**: number of cancel events (full and partial) divided by
  number of trade events. The SEC notes it "does not provide an exact
  numerical representation of what actually happens to orders."
  https://www.sec.gov/featured-topics/market-structure-analytics/market-activity-report-methodology

Run with Python 3.10+ and the standard library only:

```
python sec_order_metrics.py            # committed CSV
python sec_order_metrics.py --refresh  # re-download from the SEC
```

Output quoted by the guide (Q2 2026 row):

```
File: etp_stock_timeseries3.csv, 20120103 to 20260630, 3642 days
Period     days  stock T/O %  ETP T/O %  stock C/T  ETP C/T
2012        249         3.18       0.18       19.8     92.3
2019        252         3.23       0.41       18.0     90.3
2025        250         4.17       0.20       15.1    147.4
Q2 2026      62         4.30       0.21       17.0    138.8
```

Caveats:

- Averages are simple means of daily values, computed here. The SEC file has
  no quarterly averages.
- Exchange order books only. Off-exchange executions (wholesalers, ATSs) are
  not in either the numerator or the denominator.
- Exchanges that publish level-based rather than order-based feeds can
  overstate the cancel-to-trade ratio; the trade-to-order volume ratio is less
  affected. See the SEC methodology page above.

Data: `data/etp_stock_timeseries3.csv`, extracted unchanged from
https://www.sec.gov/files/opa/data/market-structure/summary-metrics-exchange/metrics_by_exchange_q2_2026.zip
("Market Structure Metrics by Exchange", 2012 Q1 to 2026 Q2, page updated
June 30, 2026). U.S. government work, public domain.
