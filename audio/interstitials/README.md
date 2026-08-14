# Interstitial background music (OBS)

Original **melodic motif loops** for **Starting Soon**, **Lobby**, **BRB**, **Ending**.

Composed by `tools/generate_interstitial_music.py` (algorithmic melody + chords +
bass + light drums — not ambient pads, not third-party libraries). Kept in-repo
so Twitch Content ID does not match Pixabay / SoundHelix / stock catalogs.

| File | Motif |
|------|--------|
| `starting-soon.mp3` | *Grid Call* — minor waiting hook |
| `lobby.mp3` | *Paddock Walk* — soft dorian lounge |
| `brb.mp3` | *Hold Lane* — cool mixolydian hold |
| `ending.mp3` | *Checkered Warm* — major resolve |

License: original to this repo — free to use for your streams/VODs with this pack.

Regenerate:

```powershell
python tools\generate_interstitial_music.py
```

OBS Media Source uses **looping** + restart on scene activate. Volume: Mixer → `Music …`.

If you prefer silence instead, delete the MP3s and re-run `generate_pack.py`
(the Music sources are skipped when files are missing).
