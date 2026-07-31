# Stinger transition — PiGreco Racing

Short branded wipe (~**0.8 s**) for OBS **Stinger** scene transitions: dark panel `#080A0C`, leading edge `#00C400` → `#009FE5`, official π mark.

## Assets

| Path | Use |
|------|-----|
| [`overlays/stinger/pigreco-stinger.webm`](../overlays/stinger/pigreco-stinger.webm) | **Preferred** — VP9 + alpha for OBS Stinger |
| [`overlays/stinger/index.html`](../overlays/stinger/index.html) | Preview / re-export helper (Browser Source) |
| `python tools/generate_stinger.py` | Regenerate WebM from logo + wipe math |

Preview in a browser:

`overlays/stinger/index.html?preview=1`  
(optional `&loop=1` to repeat)

## OBS setup (exact steps)

1. Open OBS → **Settings** → **Scene Transitions** (or the Transitions dock).
2. Click **+** → choose **Stinger**.
3. Name it e.g. `PiGreco Stinger`.
4. **Video File**: browse to  
   `…\obs-pigreco-racing\overlays\stinger\pigreco-stinger.webm`  
   (full path on your machine after Setup / clone).
5. **Transition Point**: set **~50–70%** (start at **55%**).  
   The cut should happen while the frame is fully covered (π visible), before the reveal wipe.
6. **Audio**: leave unset unless you add a whoosh later (optional; pack ships silent).
7. Set this transition as the **default** scene transition, or pick it per switch.
8. Test: switch Starting Soon ↔ Live Race — you should see the green-edged wipe + π, then the new scene.

### Tips

- Canvas must stay **1920×1080** (pack default).
- If the cut feels early/late, nudge Transition Point a few percent (earlier = lower %, later = higher %).
- Close OBS before regenerating pack JSON; stinger media is independent of `PiGreco_Racing.json`.

## Regenerate WebM

Requires **ffmpeg** on `PATH` and Pillow (`PIL`).

```powershell
python tools/generate_stinger.py
# frames only:
python tools/generate_stinger.py --skip-encode --keep-frames
```

## Alternate: record from HTML

If you need a custom length or want to avoid the shipped WebM:

1. OBS → add a temporary scene with a **Browser Source** → local file  
   `overlays/stinger/index.html` (1920×1080, **Shutdown source when not visible** off while recording).
2. Record a few seconds (simple output), trim to one sting cycle (~0.8 s).
3. Prefer exporting **WebM with alpha** if your tool supports it; otherwise opaque black cover still works if Transition Point is mid-cover.
4. Point the Stinger transition at that file (same steps as above).

## Do not

- Do not put the stinger Browser Source on the Live Race scene as a permanent overlay — use the **Transitions → Stinger** media path.
- Do not cover gameplay with a looping sting; one-shot per scene change only.
