# cliff-asness-investing-pet-peeves

Supports https://summitward.com/learn/cliff-asness-investing-pet-peeves.

`trailing_vs_forward.py` tests the third peeve in Cliff Asness, "My Top 10
Peeves" (Financial Analysts Journal 70(1), 2014): that judging strategies on
trailing three- to five-year returns uses the data "backwards." For the US
market excess return (Mkt-RF), size (SMB), value (HML) and momentum (Mom), it
prints:

1. The correlation between every trailing 36- and 60-month compounded return
   and the following 36 or 60 months, using all month-ends (overlapping
   windows) and using non-overlapping origins at every possible starting
   offset (median, min, max, share negative).
2. A chasing test: each January, compare the factor with the best trailing
   return against the one with the worst over the next window, for all four
   factors and for the three long-short factors alone.

Overlapping windows share up to h-1 months, so the effective sample is about
31 independent three-year pairs and 17 five-year pairs. Treat the
correlations as descriptive. Research factors carry no fees, trading costs or
taxes.

Data (Kenneth R. French,
[Data Library](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html),
files built from the 202608 CRSP database, downloaded 2026-10-03; used with
attribution):

- `data/F-F_Research_Data_Factors.csv`
- `data/F-F_Momentum_Factor.csv`

Standard library only.

```bash
python3 trailing_vs_forward.py
```

Output quoted in the guide (run 2026-10-03):

```
Sample: 192701 to 202608 (1196 months)

1) Correlation of trailing-h with following-h compounded return
   'all months' uses every month-end (overlapping windows).
   Non-overlapping origins are spaced h months apart; the result depends
   on the starting month, so the median and range over all h offsets
   are shown.
factor     h  all months  non-overlap median    min    max  offsets < 0  n per offset
Mkt-RF    36       -0.19               -0.20  -0.41   0.21          81%            31
SMB       36       -0.05               -0.06  -0.16   0.06          78%            31
HML       36       -0.09               -0.07  -0.21   0.13          83%            31
Mom       36       -0.07               -0.06  -0.24   0.32          78%            31
Mkt-RF    60       -0.10                0.02  -0.52   0.41          43%            17
SMB       60       -0.26               -0.24  -0.42  -0.02         100%            17
HML       60       -0.20               -0.16  -0.55   0.20          87%            17
Mom       60        0.30                0.42  -0.10   0.66           7%            17

2) Chasing test, all four factors: each January, best vs worst trailing-h
   h  decisions  loser beat winner  avg next-h (winner)  avg next-h (loser)
  36         94               47%                19.5%               18.0%
  60         90               47%                37.0%               26.7%

2) Chasing test, SMB, HML, Mom only: each January, best vs worst trailing-h
   h  decisions  loser beat winner  avg next-h (winner)  avg next-h (loser)
  36         94               48%                16.4%               13.9%
  60         90               48%                32.5%               22.2%

```
