# most-stocks-lose-to-tbills

Supports https://summitward.com/learn/most-stocks-lose-to-tbills and the
Short https://youtube.com/shorts/z7ExMJ8qIrU ("Most Stocks Lose to T-Bills.
The Market Still Wins.").

`skew_short_render.py` renders the 1080x1920, 30 fps video. `skew_cover.py`
renders its cover image. Both need numpy and matplotlib; the video also needs
ffmpeg, and both look best with the Inter font installed.

```bash
python3 skew_short_render.py --stats-only    # simulation figures, no ffmpeg needed
python3 skew_short_render.py skew_short.mp4  # untimed video (58.5 s)
python3 skew_short_render.py --vo skew.mp4   # timed to the published voiceover (67.6 s)
python3 skew_cover.py                        # writes skew_cover.png
```

Any render also takes `start end` in seconds to render one slice.

## Historical figures

Hardcoded from Hendrik Bessembinder (2026), "One Hundred Years in the U.S.
Stock Markets," [SSRN 6438198](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6438198),
covering U.S. common stocks from 1926 through 2025:

- 29,754 stocks; 59% had lifetime buy-and-hold returns below one-month
  Treasury bills over the same months.
- The median stock's lifetime return was -6.9% (total over its listed life,
  not annualized).
- Shareholders' net wealth creation above T-bills was $91 trillion. 46 of
  29,081 firms account for half of it, and 1,082 firms (3.7%) for all of it.

## Simulation

The second half of the video shows how skew arises from compounding alone:

- 1,000 identical stocks, each with a 10% expected annual return and 40%
  annual volatility, i.i.d. normal monthly returns (floored at -99%), for 20
  years. No stock has an edge over another.
- T-bills earn 3% a year.
- The portfolio holds equal dollars in every stock at the start, then buys
  and holds with no rebalancing.
- Seed 1 is the first seed tried. Across seeds 1 to 100, an average of 56.4%
  of stocks finish below T-bills (range 52.8% to 60.1%), and in all 100 the
  portfolio beats T-bills while the median stock does not.

The simulation shows that compounding produces skew. It does not explain why
stocks beat cash on average, which is the 10% expected return assumed here.

## Output

```
below 0.588 median 1.27 port 6.07 tb 1.81 max 206 med_idx_end 1.27
```

58.8% of the simulated stocks finish below T-bills. The median stock turns $1
into $1.27 against $1.81 for T-bills, the equal-weight portfolio ends at
$6.07, and the best stock ends at $206.

## Adding a voiceover

`--vo` maps audio time to scene time with two lists, `A` (seconds in the
audio) and `V` (seconds in the scene timeline), anchored at sentence starts.
To retime for a new read, find its pauses:

```bash
ffmpeg -i voiceover.mp3 -af silencedetect=noise=-35dB:d=0.3 -f null - 2>&1 | grep silence_
```

then edit `A` so each anchor lands on its sentence (both lists must stay
increasing and the same length), and mux:

```bash
ffmpeg -i skew.mp4 -i voiceover.mp3 -filter_complex "[1:a]apad=pad_dur=2[a]" \
  -map 0:v -map "[a]" -c:v copy -c:a aac -b:a 192k -t 67.6 skew_vo.mp4
```

MIT license, as for the rest of this repository.
