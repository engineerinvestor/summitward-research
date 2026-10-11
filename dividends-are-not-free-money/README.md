# dividends-are-not-free-money

Supports https://summitward.com/learn/dividends-are-not-free-money and the
Short https://youtube.com/shorts/kjpjg-X76_k ("Dividends Aren't Free Money").

`div_short_render.py` renders the 1080x1920, 30 fps video. It needs numpy and
matplotlib, plus ffmpeg for video, and looks best with the Inter font
installed. Every number in it is a worked example, checked by asserts when
the script starts.

```bash
python3 div_short_render.py --stats-only           # worked-example figures, no ffmpeg needed
python3 div_short_render.py div_short.mp4          # untimed video (58.5 s)
python3 div_short_render.py --vo hank div.mp4      # timed to one voiceover read (69.5 s)
python3 div_short_render.py --vo jessica div.mp4   # timed to another read (67.0 s)
```

Any render also takes `start end` in seconds to render one slice.

## Worked examples

- A $100 stock pays a $2 dividend. On the ex-dividend date the price drops
  to about $98, and the $2 is owed to the holder, so value moves from the
  stock to cash and is not created.
- Investor A owns 50 shares and takes the dividend. Investor B owns 50 shares
  of an otherwise identical stock that pays none and sells 1 share for the
  same $100 of cash. Both end with $4,900 of stock and $100 of cash before
  tax.
- With a $60 cost basis and a 15% rate on qualified dividends and long-term
  gains, A owes $15 this year (the whole dividend is income) and B owes $6
  (only the $40 gain on the share sold). If both later sell everything at
  unchanged prices and tax rates, each pays $300 in total. The difference is
  timing and control, and it mostly disappears in an IRA, 401(k) or Roth.

## Output

```
after the dividend: A stock 4,900 + cash 100; B stock 4,900 + cash 100
tax now: A 15.00, B 6.00; tax on selling the rest: A 285.00, B 294.00; total 300.00 vs 300.00
```

## Adding a voiceover

`--vo` maps audio time to scene time with two lists per voice, `A` (seconds
in the audio) and `V` (seconds in the scene timeline), anchored at sentence
starts. Without `--vo`, a fixed map stretches the scene timeline to the final
pacing. To retime for a new read, find its pauses:

```bash
ffmpeg -i voiceover.mp3 -af silencedetect=noise=-35dB:d=0.3 -f null - 2>&1 | grep silence_
```

then add an entry to `ANCHORS` (both lists must stay increasing and the same
length), and mux:

```bash
ffmpeg -i div.mp4 -i voiceover.mp3 -filter_complex "[1:a]apad=pad_dur=3[a]" \
  -map 0:v -map "[a]" -c:v copy -c:a aac -b:a 192k -t 69.5 div_vo.mp4
```

MIT license, as for the rest of this repository.
