# r-squared-trap

Supports https://summitward.com/learn/r-squared-trap and the Short
https://youtube.com/shorts/JezcUXKqTqs.

`r2_trap_render.py` simulates stock markets in which valuation has no
predictive power, regresses each market's forward 10-year return on its
starting P/E the way rolling valuation charts do, and renders the 1080x1920
video. It needs numpy and matplotlib; rendering also needs ffmpeg and looks
best with the Inter font installed. Random seeds are fixed, so every number
below reproduces exactly:

```bash
python3 r2_trap_render.py --stats-only   # numbers only, no ffmpeg needed
python3 r2_trap_render.py --preview      # six preview frames
python3 r2_trap_render.py r2_trap.mp4    # full video
```

## The simulation

- 477 months per market, matching January 1987 through September 2026, the
  span of the BofA Global Research chart (Exhibit 8, normalized trailing P/E
  vs. subsequent 10-year annualized S&P 500 return, R² = 81%).
- Monthly log price returns are i.i.d. normal with mean 0.75% and standard
  deviation 4.5%. Price is `exp(cumsum(r))`. No information at month t
  forecasts returns after t, so the population predictive R² is zero.
- Log P/E follows `lpe_t = phi * lpe_{t-1} + (r_t - mu) - e_t`: it absorbs
  each month's price shock, and `e_t ~ N(0, 1%)` adds earnings noise.
  `phi = 1` (random-walk log P/E) is the headline case; `phi = 0.997` and
  `phi = 0.99` (half-lives of about 19.2 and 5.7 years) are the sensitivity
  cases.
- 357 starting months per market, each paired with the annualized return
  over the following 120 months. R² is the squared sample correlation, which
  equals the OLS R² of a univariate regression with an intercept.
- 5,000 markets per case. The baseline uses seed 20261006 and the
  sensitivity cases use seed 7.
- The market shown in the video is picked by a rule fixed in advance: among
  markets whose P/E range is at most 3.5x, the one whose R² is closest to the
  75th percentile of all 5,000 baseline results. There is no screen on the
  slope.

The video's method line reads "i.i.d. price returns (~9%/yr, ~16% vol)". The
returns are log price returns with the monthly parameters above. The
on-screen text is left as rendered so this script reproduces the published
video.

## Output the guide quotes

```
{"median": 0.45737988874934055, "gt50": 0.4444, "ge81": 0.0422, "n81": 211, "n81_neg": 211, "neg_share": 0.9392} {"0.997": {"median": 0.39441944667976137, "ge81": 0.0142}, "0.99": {"median": 0.248704698358379, "ge81": 0.002}}
demo 1262 0.631 0.75 slope -0.004 35.8
```

| Log P/E process | Median in-sample R² | Markets with R² ≥ 81% |
| --- | --- | --- |
| Random walk (phi = 1) | 45.7% | 4.22% (211 of 5,000) |
| Half-life 19.2 years (phi = 0.997) | 39.4% | 1.42% |
| Half-life 5.7 years (phi = 0.99) | 24.9% | 0.20% |

In the baseline case, 44.4% of markets have R² above 50%. All 211 markets
at or above 81% have a negative slope, as do 93.9% of all 5,000. The market
shown in the video has R² = 63.1% (75th percentile) and a P/E range of 13x
to 35.8x.

The results depend on the assumed valuation process. A random-walk log P/E
is the most persistent case and produces the largest spurious R².

## Companion Short: R² is not a model-quality score

`r2_quality_render.py` renders a second 1080x1920 Short with four simulated
demonstrations, following Cosma Shalizi's
[lecture 10 notes](https://www.stat.cmu.edu/~cshalizi/mreg/15/lectures/10/lecture-10.pdf)
(CMU 36-401) as summarized by the UVA Library StatLab article
["Is R-squared Useless?"](https://library.virginia.edu/data/articles/is-r-squared-useless).
`r2_quality_cover.py` renders its cover. Both need numpy and matplotlib; the
video also needs ffmpeg.

```bash
python3 r2_quality_render.py --stats-only      # numbers only, no ffmpeg needed
python3 r2_quality_render.py r2_quality.mp4    # video (53.5 s); add `start end` for a slice
python3 r2_quality_cover.py                    # writes r2_quality_cover.png
```

Seeds are fixed, so the output reproduces exactly:

```
A: 0.943->0.135 rmse 0.765  B: 0.98->0.25 slope 1.52  C: 0.921  D: 0.772
```

- **A.** y = 2 + 1.2x plus the same 100 noise draws (sd 0.9). Narrowing the
  range of x from 1-10 to 1-2 drops R² from 0.94 to 0.14 while the residual
  RMSE stays at 0.765.
- **B.** The model is correctly specified and only the noise grows: R² falls
  from 0.98 at noise sd 0.5 to 0.25 at sd 8. The fitted slope at sd 8 is 1.52
  against a true 1.2.
- **C.** A straight line fit to y = x² (with multiplicative noise) gets
  R² = 0.92, while the residuals form a U-shape.
- **D.** Regressing y on x and x on y gives the same R² (0.77): with one
  regressor and an intercept, R² is the squared correlation and says nothing
  about causal direction.

MIT license, as for the rest of this repository.
