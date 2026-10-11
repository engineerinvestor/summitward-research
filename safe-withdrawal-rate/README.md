# safe-withdrawal-rate

Supports https://summitward.com/learn/safe-withdrawal-rate and the Short
https://youtube.com/shorts/bjOHsWfVhk0 ("The 4% Rule Isn't a Rule").

`swr_data.py` builds annual real returns from Robert Shiller's monthly U.S.
data and backtests a constant-real withdrawal from a 60/40 portfolio.
`swr_short_render.py` imports it and renders the 1080x1920, 30 fps video.
Both need numpy and pandas; the renderer also needs matplotlib, plus ffmpeg
for video, and it looks best with the Inter font installed.

```bash
python3 swr_data.py                         # backtest table, no ffmpeg needed
python3 swr_short_render.py --stats-only    # the figures the video shows
python3 swr_short_render.py swr_short.mp4   # untimed video (58.5 s)
python3 swr_short_render.py --vo swr.mp4    # timed to the published voiceover (75 s)
```

Any render also takes `start end` in seconds to render one slice, for example
`python3 swr_short_render.py test.mp4 25 35`.

## Method

- Stocks: S&P Composite price plus dividends (dividend / 12 each month),
  compounded monthly, then January to January.
- Bonds: the 10-year Treasury, modeled as a par bond bought each January at
  that month's yield and sold a year later as a 9-year bond at the new yield
  (coupon plus price change).
- Inflation: CPI, January to January. Returns are deflated by it.
- Portfolio: 60/40, rebalanced annually. Withdrawals are taken at the start of
  each year and held constant in real terms. No fees, no taxes.
- A start year succeeds if the balance stays above zero for the whole horizon.

Shiller's prices are monthly averages of daily closes, so these January
"returns" are average-to-average, which smooths them slightly compared with
month-end data.

## Data

`data/shiller.csv` is the
[datasets/s-and-p-500](https://github.com/datasets/s-and-p-500) CSV of
Shiller's [monthly data](https://shillerdata.com/), dedicated to the public
domain (ODC PDDL) by its maintainer, with credit to Shiller. That mirror's
Shiller rows end in June 2023; later rows carry only the FRED price, with
dividends, CPI and yields set to zero. The script drops those rows, so **the
last annual return runs January 2022 to January 2023** even though prices in
the file run to September 2026. The file is committed as used so the video's
numbers reproduce.

The Trinity Study bars in the video (98%, 100%, 95%, 74% and 19% success for
100/0 through 0/100 at 4% over 30 years, 1926-1997) are copied from Cooley,
Hubbard and Walz (1999), *Financial Counseling and Planning* 10(1), Table 2,
and are not computed here.

## Output

```
years 1871 - 2022 (last return year starts Jan 2022 )
mean real stock 0.084 bond 0.027 infl 0.023
H=30 wr=0.030 success=1.000 n=123
H=30 wr=0.035 success=1.000 n=123
H=30 wr=0.040 success=0.959 n=123
H=30 wr=0.045 success=0.894 n=123
H=30 wr=0.050 success=0.748 n=123
H=50 wr=0.030 success=1.000 n=103
H=50 wr=0.035 success=0.961 n=103
H=50 wr=0.040 success=0.796 n=103
H=50 wr=0.045 success=0.602 n=103
H=50 wr=0.050 success=0.417 n=103
4% 30y 60/40 failures: [np.int32(1965), np.int32(1966), np.int32(1967), np.int32(1968), np.int32(1969)]
ending real multiple: median 1.31, p10 0.37, min 0.00, frac >= 1x start 0.61
worst start 1965 end 0.0
SAFEMAX 30y 60/40: min 0.0369 (1966), median 0.0615
```

At 4% for 30 years, 118 of 123 start years (95.9%) succeed; the five
failures start in 1965 through 1969. Over 50 years the rate drops to 79.6%.
The lowest rate that survived every 30-year window is 3.69%, set by the 1966
start. The 1966 sequence runs out in year 26, while the same 30 annual returns
in reverse order end at 1.58 times the starting balance.

The guide's 95-100% figure is the Trinity Study's. This backtest is a separate
calculation on different data (1871 onward, a modeled bond return) and lands
in the same range.

## Adding a voiceover

The `--vo` timing maps audio time to scene time with two lists, `A` (seconds
in the audio) and `V` (seconds in the scene timeline), anchored at sentence
starts. The published audio has 3 s of silence inserted at 58.95 s, before
"My take". To retime for a new read, find its pauses:

```bash
ffmpeg -i voiceover.mp3 -af silencedetect=noise=-35dB:d=0.3 -f null - 2>&1 | grep silence_
```

then edit `A` so each anchor lands on its sentence (both lists must stay
increasing and the same length), and mux:

```bash
ffmpeg -i swr.mp4 -i voiceover.wav -map 0:v -map 1:a -c:v copy -c:a aac -shortest swr_vo.mp4
```

MIT license, as for the rest of this repository.
