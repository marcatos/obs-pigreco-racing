# S.Marcato 42 — overlay pack

Broadcast overlays and transitions for pilot **S.Marcato** (car **42**): carbon/steel theme under `overlays-marcato/`. Full collection setup is documented in later tasks; this page starts with the stinger.

## Stinger transition (steel wipe)

Short wipe (~**0.8 s**) for OBS **Stinger** scene changes: dark panel, steel/white leading edge, center mark **42** (Syne, no PiGreco green flash or π logo).

### Assets

| Path | Use |
|------|-----|
| [`overlays-marcato/stinger/index.html`](../overlays-marcato/stinger/index.html) | Preview / record-from-browser helper |
| PiGreco reference timing | Same ~800 ms keyframes as [`overlays/stinger/`](../overlays/stinger/) — see [`docs/STINGER.md`](STINGER.md) |

Preview in a browser:

`overlays-marcato/stinger/index.html?preview=1`  
(optional `&loop=1` to repeat, **Replay** button in preview mode)

### OBS setup

1. Open OBS → **Settings** → **Scene Transitions** (or the Transitions dock).
2. Click **+** → **Stinger**.
3. Name it e.g. `S.Marcato 42 Stinger`.
4. **Video file** (recommended after you record/export one cycle from the HTML preview), **or** use a temporary **Browser Source** on a record scene pointing at  
   `…\obs-pigreco-racing\overlays-marcato\stinger\index.html`  
   (1920×1080, transparent background).
5. **Transition point**: start at **~50%** (~**400 ms** on an 800 ms clip) — cut while the frame is fully covered (`42` visible), before the reveal wipe.
6. **Audio**: unset unless you add a whoosh later.
7. Set as default or pick per scene switch; test Starting Soon ↔ Live (or your marcato scenes).

### Tips

- Canvas **1920×1080** (pack default).
- Nudge transition point a few percent if the cut feels early (lower %) or late (higher %).
- Do not leave the stinger as a permanent overlay on race scenes — use **Transitions → Stinger** only.

### Do not

- Do not use PiGreco green stinger media for the marcato collection.
- Do not loop the sting on-air; one shot per scene change.
