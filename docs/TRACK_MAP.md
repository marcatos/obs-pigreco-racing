# Track map minimap (P3-07)

Peripheral race minimap using **official iRacing SVG** layers cached on your PC. Dots follow `LapDistPct` on the track path. Drawn inside Broadcast Chrome (mid-right, above Cam 2).

## Enable

1. Sync maps once (needs iRacing members credentials — local only):

```bat
copy adapters\telemetry\iracing_api.example.json adapters\telemetry\iracing_api.local.json
REM edit email/password, then:
Start-SyncTrackMaps.bat
REM or only one track:
Start-SyncTrackMaps.bat --track-id 449
```

Env alternative: `IRACING_EMAIL` + `IRACING_PASSWORD`.

2. Config: `trackMapEnabled: true` (+ telemetry running + config server `:8766`).
3. OBS: eye **ON** on **Overlay Broadcast Chrome** → Refresh cache.
4. Cache files land in `overlays/assets/tracks/iracing/{TrackID}.svg` (gitignored except mock `900001`).

## Lookup

- Tick `trackId` = numeric iRacing `TrackID` (e.g. `"449"`).
- Overlay fetches `assets/tracks/iracing/{trackId}.svg`.
- Optional `{trackId}.meta.json`: `{ "offset": 0.0, "direction": 1 }` for S/F alignment.
- Missing SVG → label `TRACK MAP — run Start-SyncTrackMaps` (no oval fallback).

## CONTRACT

`trackId`, optional `trackConfig`, `mapCars[]` (`carIdx`, `carNumber`, `distPct`, `isFocus`). See `adapters/telemetry/CONTRACT.md`.

## Notes

- Do **not** commit downloaded SVGs or `iracing_api.local.json`.
- Self-learn / open outlines are no longer the happy path (P3-07).
