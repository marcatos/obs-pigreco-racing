# Track map minimap (P3-03)

Peripheral Browser Source showing the field as dots on a track outline.

## Enable

1. Config panel / `config.values.json`: `trackMapEnabled: true` (telemetry bridge running + config server).
2. OBS: eye on **Overlay Track Map** (already in Replay / Rec 2K after regenerating the pack), or add Browser Source:

```text
http://127.0.0.1:8766/o/marcato/track-map.html
```

or `/o/overlays/track-map.html` for PiGreco. Size 1920×1080, eye on when you want the map. Default placement is bottom-right (outside center FOV).

3. Telemetry: `Start-Telemetry.bat mock` or `iracing`.

## Asset resolution

1. `overlays/assets/tracks/open/{trackId}.json` if present  
2. `overlays/assets/tracks/learned/{trackId}.json` (self-learn from bridge)  
3. Generic oval fallback  

Self-learn: while `iracing_bridge` runs, focus motion samples flush into `learned/` (and `adapters/telemetry/tracks_learned/`). First laps look rough; they improve as samples accumulate.

## CONTRACT

Ticks may include `trackId` and `mapCars[]` (`carIdx`, `carNumber`, `distPct`, `isFocus`). See `adapters/telemetry/CONTRACT.md`.
