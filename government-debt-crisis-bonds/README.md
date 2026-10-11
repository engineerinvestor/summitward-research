# government-debt-crisis-bonds

Supports https://summitward.com/learn/government-debt-crisis-bonds.

`france_refinancing.py` rolls France's nominal State debt forward from the
Agence France Trésor (AFT) line table of October 2026 and asks how quickly
higher market yields reach the interest bill. Each year, bonds that mature plus
new net borrowing are refinanced at a scenario yield; every other bond keeps
its coupon. It compares that path with the shortcut of repricing the whole
stock at today's yields at once, and checks the model against the French
government's own published sensitivity.

```bash
python3 france_refinancing.py          # prints the tables below
python3 france_refinancing.py --json   # also writes effective_rate_paths.json (the guide's chart)
```

## Data

- `data/france_lines.csv`: 103 lines of negotiable State debt (58 nominal OATs,
  5 OATi, 13 OAT€i, 27 BTFs) transcribed from the AFT detailed-outstanding pages
  (`aft.gouv.fr/en/encours-detaille-oat`, `-oati`, `-oatei`, `-btf`), read
  2026-10-11. The pages carry no date; the OAT pages include the 1 October 2026
  auction (settled 5 October), so lines are dated 2026-10-05, and BTFs
  2026-10-09. The matured OAT 2.50% 24 September 2026 is excluded. Linker
  indexed amounts use AFT's own index coefficients. Nominal OAT face includes
  EUR 20bn of securities created on 31 August 2026 for the Caisse de la dette
  publique, due to be cancelled by year-end. Face-value sums: nominal OATs EUR
  2,393.0bn, linkers EUR 242.7bn (EUR 317.6bn indexed), BTFs EUR 216.3bn. These
  sit EUR 16.3bn above AFT's EUR 2,896.2bn headline for 30 September after the
  October auction is netted out; we could not reconcile the difference from
  published pages (candidate causes: the CDP securities, or a September buyback
  not yet reflected). Face-weighted average remaining life computed from this
  table is 8 years 154 days, against AFT's 8 years 158 days.
- `data/bdf_tec_yields.csv`: Banque de France constant-maturity OAT yields
  (TEC 1, 2, 5, 10, 30), source Euronext, read 2026-10-11. The script uses
  9 October 2026: 3.251%, 3.602%, 4.111%, 4.795%, 5.357%.
- Constants in the script, with sources in comments: nominal GDP growth from the
  PLF 2027 debt annex (Rapport sur la dette des administrations publiques, Table
  1); net new borrowing of EUR 160.5bn a year from the 2027 ceiling on the net
  change in nominal negotiable debt (AFT press release, 29 September 2026);
  Maastricht debt of 119.3% of GDP for 2026 (PLF 2027 annex).

## Assumptions

- Scope is nominal debt only (OATs and BTFs, about 91% of face). Inflation-linked
  bonds are left out: their cost depends on real yields and realized inflation.
- New medium/long-term issuance is split 20/30/35/15 across 2-, 5-, 10- and
  30-year maturities (average 9.9 years, close to AFT's 9y33d average life of the
  medium/long-term stock). At the 9 October curve that mix yields 4.435%.
- The BTF stock is held at its October level and reprices to the one-year rate
  within the first year.
- Net borrowing is held at EUR 160.5bn a year in every scenario, with no
  feedback from higher interest to higher borrowing.
- Mid-year convention for redemptions and new issuance. Coupon accrual only: no
  issue premiums or discounts, which move the budgetary charge.

## Validation

For a permanent +100bp shift, the model adds EUR 3.1bn, 7.7bn and 19.1bn of
interest in years 1, 2 and 5. The PLF 2027 debt annex gives +3.4bn, +8.1bn and
about +19.2bn for all negotiable debt including linkers. The 2027 nominal-debt
bill of EUR 65.4bn plus roughly EUR 8bn of linker coupons and indexation is
close to the annex's EUR 74.9bn State debt charge (general accounting).

## Output quoted in the guide (run 2026-10-11)

```
Nominal OATs: EUR 2,393.0bn, face-weighted coupon 2.144%
BTF stock: EUR 216.3bn
Issuance-mix yield at 9 Oct 2026 curve: 4.435%

Share of October 2026 OAT face still at its old coupon, end of year:
  2027:  91.6%
  2028:  82.0%
  2029:  71.6%
  2031:  55.4%
  2036:  27.2%

Effective rate on nominal debt (%), interest bill (EUR bn):
  year                curve -100bp    curve held at 9 Oct 2026                curve +100bp      shortcut (all at once)
  2027          2.32%       62.3bn          2.43%       65.4bn          2.55%       68.5bn          4.34%      116.7bn
  2028          2.50%       71.1bn          2.77%       78.9bn          3.04%       86.6bn          4.35%      123.9bn
  2029          2.69%       81.0bn          3.08%       92.7bn          3.47%      104.4bn          4.35%      131.0bn
  2030          2.83%       89.7bn          3.32%      105.3bn          3.81%      120.8bn          4.35%      138.1bn
  2031          2.96%       98.7bn          3.54%      117.8bn          4.11%      136.9bn          4.36%      145.2bn
  2032          3.07%      107.1bn          3.71%      129.7bn          4.36%      152.3bn          4.36%      152.3bn
  2033          3.11%      113.7bn          3.81%      139.3bn          4.52%      164.9bn          4.37%      159.4bn
  2034          3.15%      120.1bn          3.89%      148.5bn          4.64%      176.9bn          4.37%      166.6bn
  2035          3.18%      126.3bn          3.97%      157.6bn          4.75%      188.9bn          4.37%      173.7bn
  2036          3.20%      132.3bn          4.03%      166.5bn          4.86%      200.8bn          4.37%      180.8bn

Extra interest from a permanent +100bp shift vs held curve (EUR bn):
  year 1 (2027): +3.1
  year 2 (2028): +7.7
  year 5 (2031): +19.1
  AFT/DG Tresor, PLF 2027 debt annex: +3.4 (year 1), +8.1 (year 2), ~+19.2 (year 5), all negotiable debt incl. linkers

Debt-stabilizing primary balance, all debt at the 5-year OAT yield (4.11%), Maastricht debt 119.3% of GDP:
  nominal growth 2.0%: primary surplus 2.47% of GDP
  nominal growth 2.5%: primary surplus 1.88% of GDP
  nominal growth 2.7%: primary surplus 1.64% of GDP
  at the stock's 2.14% average OAT coupon and 2.7% growth: -0.65% of GDP
```

The "shortcut" column reprices every nominal bond at the 4.435% issuance-mix
yield on day one. It is a steady-state answer reached only after the whole
stock has rolled, roughly a decade at France's average maturity.
