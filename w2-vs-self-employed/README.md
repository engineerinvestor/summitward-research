# w2-vs-self-employed

Supports https://summitward.com/learn/are-w2-jobs-a-scam.

`scf_wealth_by_work_status.py` compares families headed by someone who works
for someone else with families headed by a self-employed person, from the
Federal Reserve's 2025 and 2022 Surveys of Consumer Finances. It reports, by
the head's work status (`OCCAT1`): median net worth, net worth excluding
privately held business equity, financial assets and income; stock and
business ownership; the share with net worth of $1M, $3M and $10M or more;
the same medians within age bands; the work-status mix of $1M+, $3M+ and
$10M+ families; and, for employee-headed families, the $1M+ share by income
percentile.

Standard errors follow the Fed's documentation: 999 bootstrap replicate
weights (`wt1b{k} * mm{k}`, first implicate) for sampling variance, plus the
variance across the five implicates times 1.2 for imputation. Cells with fewer
than 50 sample families are suppressed. The SCF excludes the Forbes 400.

This is a cross-section. People whose businesses failed and who returned to
paid work are counted as employees, the self-employed are older, and business
equity is the owner's own valuation, so the gaps describe who holds wealth,
not the effect of choosing self-employment.

Data: the script downloads the SCF summary extracts (`scfp2025excel.zip`,
`scfp2022excel.zip`) and replicate weights (`scf2025rw1s.zip`,
`scf2022rw1s.zip`) from https://www.federalreserve.gov/econres/scfindex.htm
into a gitignored `.cache/`. Both extracts are in 2025 dollars.

```bash
pip install numpy pandas
python3 scf_wealth_by_work_status.py   # writes output/scf-wealth-by-work-status.json
```

Checks against published figures (Fed historical tables,
`scf2025_tables_internal_real_historical.xlsx`, medians by work status): the
2025 run gives $155.8k (employee) and $569.0k (self-employed) median net worth
against the Fed's $156.0k and $574.6k, and $95.7k and $92.8k median income
against $95.7k and $93.5k. The small gaps come from the median convention.

Output quoted in the guide (run 2026-10-27): `output/scf-wealth-by-work-status.txt`.
