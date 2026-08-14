# Interstitial background music (OBS)

Original melodic loops for **Starting Soon**, **Lobby**, **BRB**, **Ending**.

| File | Mood | Motif |
|------|------|--------|
| `starting-soon.mp3` | **Upbeat** | *Lights Out* — four-on-the-floor pre-show |
| `lobby.mp3` | **Upbeat** | *Formation Lap* — paddock / pre-race energy |
| `brb.mp3` | **Calm** | *Pit Lane Quiet* — soft hold |
| `ending.mp3` | **Calm** | *Cool Down Lap* — gentle resolve |

Composed by `tools/generate_interstitial_music.py` (original algorithmic music —
not stock libraries, so Twitch Content ID is unlikely to mute them).

```powershell
python tools\generate_interstitial_music.py
```

OBS: Mixer → `Music …` volumes. Refresh media sources after regenerating.
