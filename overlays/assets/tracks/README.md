# Track assets (P3-03)

## Layout

- `open/` — curated redistributable path JSON (`{trackId}.json`)
- `learned/` — written by the iRacing bridge while you drive/replay (gitignored except `.gitkeep`)

## JSON shape

```json
{
  "trackId": "monza-gp",
  "points": [{ "x": 0.12, "y": 0.40 }, { "x": 0.20, "y": 0.38 }],
  "source": "optional-note"
}
```

Coordinates are normalized roughly to `0..1` (SVG viewBox scaled in the overlay).

## Naming

`trackId` is a slug from iRacing weekend name / id (e.g. `Monza GP` → `monza-gp`). Match the file name to that slug.

## Copyright

Do **not** copy proprietary iRacing / game HUD track maps. Prefer self-learn or clearly open/public-domain outlines.
