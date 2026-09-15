# robo-advisor-returns

Supports https://summitward.com/learn/robo-advisor-returns.

`analyze_robo_return_attribution.py` rebuilds Wealthfront's published Classic
allocation at risk score 8.0 (45% VTI, 18% VEA, 16% VWO, 12% LQD, 6% SCHP,
3% VIG) out of long-history index series, rebalanced annually with no advisory
fee, over 2013 to 2025 and 2000 to 2012, and compares each era to 100% S&P
500. It also summarises `data/wealthfront_risk_ladder.json`, the annualized
return Wealthfront's historical performance page reported at each of its
twenty risk scores on 2026-09-13.

Data:

- `data/damodaran_returns.json`: S&P 500, Baa corporate and 10-year Treasury
  annual nominal returns, Aswath Damodaran (NYU Stern).
- `data/ff_developed_annual.json`, `data/ff_emerging_annual.json`: developed
  ex-US and emerging market annual returns in USD, Kenneth R. French Data
  Library (Mkt-RF plus RF).
- `data/wealthfront_risk_ladder.json`: read from Wealthfront's page; the
  file's `_metadata` records the method and dates.

```bash
python3 analyze_robo_return_attribution.py
python3 analyze_robo_return_attribution.py --chart out   # needs matplotlib and Pillow
```

Output quoted in the guide (run 2026-09-14):

```
  Era           WF weights  100% S&P 500  difference
  2013-2025         10.12%        14.75%      -4.63pp
  2000-2012          5.09%         1.63%      +3.46pp
```

Index proxies are approximate and the rebuild is a buy-and-hold figure, which
is a different measurement from a composite of client accounts funded on many
dates. The guide states both limits.
