# mortgage-rate-below-ten-percent

Supports https://summitward.com/learn/mortgage-rate-below-ten-percent.

`guaranteed_vs_equity_windows.py` counts, for each guaranteed rate and
holding period, the share of overlapping historical windows in which buying
and holding the S&P 500 (dividends reinvested, nominal) ended above a
guaranteed return compounded over the same window.

Data: `data/sp500_returns.json`, annual S&P 500 total returns 1928 to 2025,
from Aswath Damodaran's `histretSP.xls` (NYU Stern), rounded to four decimals.

```bash
python3 guaranteed_vs_equity_windows.py
```

Output quoted in the guide (run 2026-09-14):

```
  guaranteed      5yr     10yr     20yr     30yr
         3%      80%      90%      99%     100%
         5%      74%      85%      96%     100%
         6%      72%      81%      94%     100%
         7%      70%      73%      87%     100%
         8%      69%      66%      78%      97%
         9%      65%      56%      67%      96%

  9% guaranteed, 10-year windows: stocks won 50 of 89 (56%), lost 39 (44%)
  9% guaranteed, 20-year windows: stocks won 53 of 79 (67%), lost 26 (33%)
  9% guaranteed, 30-year windows: stocks won 66 of 69 (96%), lost 3 (4%)
```

Windows overlap, so they are not independent observations. Taxes, the
mortgage interest deduction and the repayment schedule are not modelled.
