# tals-leverage-simulator

Supports https://summitward.com/learn/tals-leverage-simulator, with the
renderer for a short video on tax-aware long-short (TALS) investing.

`tals_short_render.py` renders the 1080x1920, 30 fps video from the result
CSVs that [talsim](https://github.com/engineerinvestor/talsim) v0.5.0
generates in pinned CI. It needs numpy, pandas and matplotlib, plus ffmpeg
for video, and looks best with the Inter font installed.

```bash
git clone --branch v0.5.0 https://github.com/engineerinvestor/talsim
python3 tals_short_render.py talsim/docs/results --stats-only       # figures only, no ffmpeg needed
python3 tals_short_render.py talsim/docs/results tals_short.mp4     # video (58.5 s)
```

A render also takes `start end` in seconds after the output path to render one
slice. The script asserts the v0.5.0 headline figures, so it stops on result
files from any other release.

## What the video shows

- **Leverage sweep** (`leverage_sweep.csv`): median gross losses realized and
  median tax benefit used for 100/0, 130/30, 150/50, 200/100 and 250/150
  books. $1M, 10 years, 200 common-random-number paths, seed 7, zero alpha,
  $100k a year of outside short-term gains, full liquidation at the end.
- **Scenario comparison** (`scenario_comparison.csv`): the median paired
  difference in after-tax wealth against the 100/0 book, with zero alpha and
  with the "+75 bps alpha" scenario, over 100 paired paths. talsim scales
  alpha linearly with active gross exposure, with 150/50 as the reference, so
  that scenario gives 130/30 about 45 bps a year, 200/100 about 150 bps and
  250/150 about 225 bps. The on-screen label "+0.75%/yr alpha" is left as
  rendered.
- Tax rates are talsim's defaults: 40.8% short-term and 23.8% long-term (top
  2026 federal rates with the 3.8% NIIT).

All results come from a synthetic market and depend on talsim's stated
assumptions. They are not evidence about any real strategy.

## Output

```
losses 8.58x  tax benefit 2.14x  (250/150 vs 100/0)
  130/30  zero alpha    -62,762  +75bp alpha    -27,419  P(beats 100/0) 0.39
  150/50  zero alpha    -80,240  +75bp alpha    -11,266  P(beats 100/0) 0.46
 200/100  zero alpha   -123,436  +75bp alpha      2,916  P(beats 100/0) 0.52
 250/150  zero alpha   -197,325  +75bp alpha    -14,874  P(beats 100/0) 0.48
```

The 250/150 book realizes 8.6 times the gross losses of long-only but uses
only 2.1 times the tax benefit. With zero alpha, every levered book trails
long-only at the median. With the alpha scenario, only 200/100 comes out ahead
at the median ($2,916), and the levered books beat long-only in 39% to 52% of
paths. P(beats 100/0) is for the alpha scenario.

**The guide quotes earlier figures.** The guide's 7.2x losses for 2.4x tax
benefit, and its $427k median shortfall, come from talsim v0.4 results, which
the [v0.5.0 release notes](https://github.com/engineerinvestor/talsim/releases/tag/v0.5.0)
say to discard. Among other changes, v0.5.0 widened the synthetic universe
from 36 to 500 names, which cut the tracking error that had dragged on the
levered medians, and made portfolio margin the default. The video uses
v0.5.0.

MIT license, as for the rest of this repository.
