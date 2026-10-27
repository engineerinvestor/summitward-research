# athletes-go-broke-paul-pierce

Supports https://summitward.com/learn/athletes-go-broke-paul-pierce.

`income_cliff.py` reproduces every computed figure in the guide. It is
standard library only, and every input is a constant at the top of the file
with its source:

- Cash runway under two readings of Paul Pierce's reported monthly outflows
  (TMZ, October 27, 2026). The figures are one party's claims in a contested
  support case, not a verified balance sheet.
- Invested assets needed to fund a spending level at a 3.9% starting
  withdrawal rate (Morningstar retirement income research, December 2025).
- Shares of long-tenured displaced workers reemployed full time at lower pay,
  from BLS Worker Displacement Table 7 (January 2026 survey, released
  August 27, 2026), computed over those who reported earnings.
- Ratios of the NFL bankruptcy hazard in Carlson, Kim, Lusardi and Camerer
  (2015, NBER w21085) to the two general-population benchmarks the paper
  reports.
- Outputs of the guide's peak-window calculator for its three illustrative
  presets. The Python model mirrors `web/src/lib/peak-window-math.ts` in the
  Summitward app: constant real spending that exhausts assets plus the present
  value of after-tax income at the end of the plan, with end-of-year cash flows.

```bash
python3 income_cliff.py
```

Output:

```
Cash runway, months (cash / (outflows - income)):
  bills are in addition to support   outflows $ 96,000 income $     0  gap $ 96,000  runway   3.1
  bills are in addition to support   outflows $ 96,000 income $23,000  gap $ 73,000  runway   4.1
  bills include support              outflows $ 48,000 income $     0  gap $ 48,000  runway   6.2
  bills include support              outflows $ 48,000 income $23,000  gap $ 25,000  runway  12.0
  itemized bill lines sum to $27,700 of $48,000; $20,300 unitemized
  eating out $7,000 closes 9.6% of a $73,000 gap; runway 4.1 -> 4.5 months

Invested assets needed at a 3.9% starting withdrawal rate:
  $10,000/mo = $  120,000/yr -> $  3.08M
  $25,000/mo = $  300,000/yr -> $  7.69M
  $48,000/mo = $  576,000/yr -> $ 14.77M
  $96,000/mo = $1,152,000/yr -> $ 29.54M

BLS DWS Jan 2026, reemployed full time (earnings reported):
  reported 1,342k of 1,593k full-time reemployed
  earn less than before:   51.1%
  earn 20%+ less:          27.5%
  earn as much or more:    48.9%

Carlson et al. hazard comparisons:
  NFL / STW ages 25-34: 1.02x
  NFL / NLSY97 men:     3.1x

Career NBA salary:
  Basketball-Reference $198,120,632
  Spotrac              $195,132,032
  difference           $2,988,600

Peak-window presets at a 3% real return (illustrative households):
  tech engineer, 10 peak years: sustainable $192,768/yr, peak savings rate 36%, spending $230,000 -> $176,180/yr after 45 (23% cut), unchanged spending runs out age 72
  pro athlete, 5-year career: sustainable $160,438/yr, peak savings rate 77%, spending $350,000 -> $125,412/yr after 28 (64% cut), unchanged spending runs out age 35
  pro athlete, 15-year career: sustainable $1,702,545/yr, peak savings rate 57%, spending $2,000,000 -> $1,500,126/yr after 37 (25% cut), unchanged spending runs out age 68
```
