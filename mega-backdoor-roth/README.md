# mega-backdoor-roth

Supports https://summitward.com/learn/mega-backdoor-roth and the Short
https://youtube.com/shorts/tMMjkk9Z1V4 ("Why I Max Out My Mega Backdoor Roth
($254K Example)").

`mbr_model.py` compares the same after-tax 401(k) room invested for 25 years
in a Roth (through the mega backdoor) and in a taxable brokerage account. It is
stdlib only. `render_mbr.py` imports it and renders the 1080x1920, 30 fps
video; it needs numpy and matplotlib, plus ffmpeg for video, and looks best
with the Inter font installed.

```bash
python3 mbr_model.py                    # every figure the guide quotes
python3 render_mbr.py --stats-only      # the figures the video shows
python3 render_mbr.py mbr.mp4           # silent video, timed to the published voiceover (61 s)
python3 render_mbr.py test.mp4 20 30    # one slice, in seconds
```

## Method

- 2026 limits, under age 50 (IRS Notice 2025-67): $72,000 annual additions
  from all sources, $24,500 employee deferral. Employer contribution is 4% of a
  $200,000 salary, $8,000. After-tax room: $72,000 - $24,500 - $8,000 = $39,500.
- $39,500 contributed at the end of each year for 25 years, limits held flat.
- Both accounts earn a 7% annual total return. In the taxable account, 1.5% of
  that is a qualified dividend taxed at 15% each year; the rest is reinvested
  and added to basis. Nothing else is sold until year 25, when the remaining
  gain is taxed at 15%. No state tax. Roth withdrawals are qualified.
- Results are in future dollars. The real figure deflates by 2.5% a year.

The renderer's taxable bar follows the pre-sale path and then drops by the
capital gains tax, so its year-by-year path is `run()` stepped one year at a
time, not `series()`, which assumes a sale in every year.

## Output

```
room: 72,000 - 24,500 - 8,000 employer = 39,500
contributed             987,500
Roth                  2,498,337
taxable pre-sale      2,419,089
taxable after sale    2,244,763
advantage               253,574
  dividend taxes paid          47,544
  growth on those taxes        31,704
  capital gains tax at sale   174,326
never sold (or step-up)        79,248
in today's dollars at 2.5%: 136,776
backdoor Roth IRA (7,500/yr): 48,147  ratio 5.27 vs contribution ratio 5.27
return:  5% $150K  7% $254K  9% $398K
tax:     0.0% $0K  10.0% $170K  15.0% $254K  18.8% $316K  23.8% $398K
horizon: 15y $64K  25y $254K  35y $726K
```

The advantage is linear in the contribution, so the backdoor Roth IRA figure
is the mega backdoor figure scaled by 7,500 / 39,500. "Never sold" also covers
a step-up in basis at death or donating the shares: the capital gains tax is
never paid and only the dividend drag remains.

MIT license, as for the rest of this repository.
