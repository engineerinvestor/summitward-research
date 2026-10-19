# millionaire-renter

Supports https://summitward.com/learn/millionaire-renter.

`scf_wealthy_renters.py` estimates how many wealthy U.S. families rent their
home, from the Federal Reserve's 2025 and 2022 Surveys of Consumer Finances.
For net worth thresholds of $1M, $3M, $5M and $10M it reports the share of
families who do not own their home and the share who pay rent, under three
wealth definitions: net worth, net worth excluding primary-residence equity,
and financial assets. It also profiles millionaire renters against millionaire
owners (age, income, assets, stock share, business and other real estate
ownership) and breaks the renter share out by age.

Standard errors follow the Fed's documentation: 999 bootstrap replicate weights
(`wt1b{k} * mm{k}`, first implicate) for sampling variance, plus the variance
across the five implicates times 1.2 for imputation. Cells with fewer than 50
sample families are suppressed. The SCF excludes the Forbes 400.

`user_cost_example.py` computes the year-one economic cost of owning a $1.5M
home for one modeled high-income couple (Himmelberg, Mayer and Sinai 2005 user
cost), with 2026 federal tax rules and mid-October 2026 rates. It is stdlib
only. Every input is an assumption stated at the top of the file.

Data: the scripts download the SCF summary extracts (`scfp2025excel.zip`,
`scfp2022excel.zip`) and replicate weights (`scf2025rw1s.zip`,
`scf2022rw1s.zip`) from https://www.federalreserve.gov/econres/scfindex.htm
into a gitignored `.cache/`. The Fed distributes both extracts in 2025 dollars.

```bash
pip install numpy pandas
python3 scf_wealthy_renters.py      # writes output/scf-wealthy-renters.json
python3 user_cost_example.py
```

Checks against published figures: the 2025 run reproduces the Fed's 65.6%
homeownership rate and $215,900 median net worth, and the 2022 run its 66.1%
homeownership rate. The 21.5% millionaire share and 96.1% millionaire
homeownership rate match the People's Policy Project chart posted by Matt
Bruenig on October 13, 2026.

Output quoted in the guide (run 2026-10-18): `output/scf-wealthy-renters.txt`
and `output/user-cost-example.txt`.
