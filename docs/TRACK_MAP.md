# Track map minimap (P3-07)

Peripheral race minimap using **official iRacing track outlines** cached on your PC. Dots follow `LapDistPct` on the track path. Drawn inside Broadcast Chrome (mid-right, above Cam 2).

## Enable

1. Sync maps once:

```bat
Start-SyncTrackMaps.bat
```

Default source is **`paths-dump`**: downloads official `activePath` geometry (no login).  
iRacing retired legacy email/password API auth (Dec 2025) and paused new OAuth client IDs — so this is the reliable path today.

Optional API mode (when you already have OAuth `client_id` / `client_secret`):

```bat
REM adapters\telemetry\iracing_api.local.json:
REM   email, password, client_id, client_secret
Start-SyncTrackMaps.bat --source api
```

2. Config: `trackMapEnabled: true` (+ telemetry + config server `:8766`).
3. OBS: eye **ON** on **Overlay Broadcast Chrome** → Refresh cache.
4. Cache: `overlays/assets/tracks/iracing/{TrackID}.svg` (gitignored except mock `900001`).

## Lookup

- Tick `trackId` = numeric iRacing `TrackID` (e.g. `"449"`).
- Overlay fetches `assets/tracks/iracing/{trackId}.svg`.
- Calibration `{trackId}.meta.json` from sync (`offset` / `direction` — aligns LapDistPct to SVG).
- Optional config `trackMapLeadPct` (default `0.016`) + `trackMapPredictSec` (default `0.05`) advance dots for replay/WS lag.
- Missing SVG → `TRACK MAP — run Start-SyncTrackMaps`.

## CONTRACT

`trackId`, optional `trackConfig`, `mapCars[]`. See `adapters/telemetry/CONTRACT.md`.

## Notes

- Do **not** commit downloaded SVGs or `iracing_api.local.json`.
- Self-learn / oval are not the happy path.
