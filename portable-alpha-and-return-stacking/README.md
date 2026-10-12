# portable-alpha-and-return-stacking

Supports https://summitward.com/learn/portable-alpha-and-return-stacking.

`stacking_returns.py` measures the live record of capital-efficient ETFs from
Yahoo Finance auto-adjusted daily closes (dividends reinvested; market-price
returns, not NAV returns) and writes `results.json`:

1. Calendar-year returns, 2019 to date, for NTSX, RSSB, RSST, SPLS, SPY, VT,
   AOR, VBIAX, AGG, IEF, DBMF, KMLM and BIL. A ticker's first year is partial,
   measured from its first close (marked `*`).
2. 2022 returns and drawdowns for NTSX, SPY, VBIAX, AGG and a costless 90/60
   built from ETFs (0.9 SPY + 0.6 IEF - 0.5 BIL, rebalanced daily).
3. RSST against SPY by year and since its first close (2023-09-06), with DBMF
   and KMLM excess returns over BIL for context, and the worst trailing
   252-day gap between RSST and SPY.
4. RSSB against VT and a costless daily-rebalanced VT + IEF - BIL 100/100
   since its first close (2023-12-05), with volatility and drawdown.
5. Daily correlation with SPY and annualized volatility since RSST's first
   close for RSST minus SPY, DBMF, KMLM, IEF and RSST.
6. Calendar-year correlation of SPY and IEF daily returns from 2002, and the
   2003-2021 figure.

The guide quotes the run with `--end 2026-10-09`:

```bash
pip install numpy pandas yfinance
python3 stacking_returns.py --end 2026-10-09
```

Like `minimum-volatility-investing`, this folder needs third-party packages.
Yahoo data is downloaded at run time and not redistributed here.

## Figures the guide quotes

| Figure | Value |
|---|---|
| NTSX 2022 return / max drawdown | -25.8% / -30.9% |
| Costless 90/60, 2022 | -24.8% / -30.1% |
| SPY 2022 | -18.2% / -24.5% |
| VBIAX 2022 | -16.9% / -21.3% |
| DBMF, KMLM 2022 | +21.6%, +24.2% |
| DBMF, KMLM 2023 | -8.9%, -5.7% |
| RSST vs SPY, 2023-09-06 to 2026-10-09 | +83.9% vs +81.6% |
| DBMF minus BIL, same window | +23.2 points |
| Worst 252-day RSST minus SPY | -23.4 points (2024-05-20 to 2025-05-22; RSST -12.0%, SPY +11.4%) |
| Best 252-day RSST minus SPY | +30.7 points (2025-05-12 to 2026-05-13) |
| RSSB / costless 100/100 / VT, 2023-12-05 to 2026-10-09 | +58.0% / +59.2% / +71.4% |
| Volatility: RSSB / VT | 16.5% / 14.6% |
| RSST minus SPY: correlation with SPY / volatility | 0.35 / 13.6% |
| IEF volatility since RSST launch | 6.3% |
| SPY-IEF daily correlation 2003-2021 / 2022 / 2026 YTD | -0.39 / +0.19 / +0.41 |

