# social-security-discount-rate

Supports https://summitward.com/learn/social-security-discount-rate, and the
summary figures in https://summitward.com/learn/fact-checking-mr-money-mustache
and https://summitward.com/learn/gateway-finance-fact-check.

`ss_claiming_pv.py` computes the present value at age 62, per dollar of full
retirement age benefit, of claiming at 62, 67 or 70, at a range of real
discount rates, weighting each year by the probability of being alive to
collect it. Benefit factors are the statutory ones for a full retirement age
of 67 (70%, 100%, 124%). Mortality is SSA's 2023 period life table as used in
the 2026 Trustees Report, embedded in the script.

Three crossovers are printed for each sex: the highest real rate at which 70
still beats 62, at which 70 still beats 67, and at which 67 still beats 62.
"70 has the highest present value" requires the second, not the first.

```bash
python3 ss_claiming_pv.py                    # scheduled benefits, plus a 78%-from-69 scenario
python3 ss_claiming_pv.py --haircut 0.83:70  # a different trust-fund scenario
```

Output quoted in the guide (run 2026-09-14, annual payments):

```
  mortality-weighted, male     70 beats 62 below 2.27%   70 beats 67 below 1.43%   67 beats 62 below 2.77%
  mortality-weighted, female   70 beats 62 below 3.39%   70 beats 67 below 2.67%   67 beats 62 below 3.80%
  78% from 69, male            70 beats 62 below 0.54%   70 beats 67 below 0.00%   67 beats 62 below 0.99%
  78% from 69, female          70 beats 62 below 1.67%   70 beats 67 below 1.06%   67 beats 62 below 2.04%
  monthly, male                70 beats 62 below 2.12%   70 beats 67 below 1.24%   67 beats 62 below 2.63%
  monthly, female              70 beats 62 below 3.25%   70 beats 67 below 2.51%   67 beats 62 below 3.69%
```

Limits stated in the guide: annual payments in advance, no taxation of
benefits, no spousal or survivor benefits, no earnings test, a period rather
than cohort table, population rather than higher-earner mortality.
