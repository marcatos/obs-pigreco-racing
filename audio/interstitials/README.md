# Interstitial background music (OBS)

Royalty-free bed loops for scenes where game audio is not the focus:
**Starting Soon**, **BRB**, **Ending**.

| File | Source | License notes |
|------|--------|----------------|
| `starting-soon.mp3` | Pixabay CDN ambient bed (trimmed/normalized) | [Pixabay Content License](https://pixabay.com/service/license-summary/) — free for commercial use / streaming |
| `brb.mp3` | SoundHelix Song 8 (trimmed/normalized) | Free for commercial use — [soundhelix.com](https://www.soundhelix.com/) |
| `ending.mp3` | SoundHelix Song 15 (trimmed/normalized) | Free for commercial use — [soundhelix.com](https://www.soundhelix.com/) |

Processed with ffmpeg (~90s, fade in/out, loudnorm −16 LUFS). OBS Media Source uses **looping** + restart on scene activate.

Replace any file with your own loop (same filename) and re-run:

```bat
python tools\generate_pack.py --profile marcato
```

Then re-import / refresh the scene collection in OBS.
