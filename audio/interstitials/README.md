# Interstitial music (OBS) — Pixabay loops

Replace the four MP3s below with **Pixabay** royalty-free loops (Content License).
Automated download is blocked by Pixabay Cloudflare — drop files here manually.

| OBS file | Mood | Suggested Pixabay search / track |
|----------|------|----------------------------------|
| `starting-soon.mp3` | **Upbeat** pre-show | [upbeat loop](https://pixabay.com/music/search/upbeat%20loop/) → e.g. *Good Vibes - Upbeat Loop* (Sonican) or *Loop Seamless Groove Bed* |
| `lobby.mp3` | **Upbeat** pre-race | same search → e.g. *Upbeat Loop - Motivational Joy* or *Positive Loop* (The_Mountain) |
| `brb.mp3` | **Calm** hold | [calm loop](https://pixabay.com/music/search/calm%20loop/) → e.g. *Soft Loop* (The_Mountain) |
| `ending.mp3` | **Calm** close | [ambient calm](https://pixabay.com/music/search/ambient%20calm/) → soft ambient / chill loop |

Note: the link you sent ([videos looping](https://pixabay.com/videos/search/looping/)) is **video**. For stream beds we need **Music** MP3s (links above).

## Install steps

1. Open `Open-Pixabay-Music.bat` (same folder) — opens the four searches in your browser.
2. On each track page click **Free download** → save as MP3.
3. Rename / overwrite into this folder with the exact names above.
4. **Normalize beds** (Pixabay masters often peak at 0 dBFS):

```powershell
# from repo root — drop ~14 dB so beds sit under voice/game
foreach ($f in 'starting-soon','lobby','brb','ending') {
  ffmpeg -y -i "audio/interstitials/$f.mp3" -af "volume=-14dB" -codec:a libmp3lame -b:a 256k "audio/interstitials/$f.norm.mp3"
  Move-Item -Force "audio/interstitials/$f.norm.mp3" "audio/interstitials/$f.mp3"
}
```

5. In OBS: refresh Media Sources `Music …` (or re-run `python tools/generate_pack.py --profile marcato`). Pack mixer defaults are ~0.15–0.18 (beds, not foreground).

## License

[Pixabay Content License](https://pixabay.com/service/license-summary/) — free for streams; **Twitch Content ID** may still mute some Pixabay tracks. If muted, pick a less popular loop from the same searches.

Fill `ATTRIBUTION.txt` with the four track titles + author + Pixabay URL after download.
