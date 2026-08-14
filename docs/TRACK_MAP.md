# Track map minimap (P3-03)

A peripheral race minimap for viewers: the field as dots on a track outline, drawn inside broadcast chrome so center gameplay stays clear. Open assets and self-learned outlines improve as you drive.

## Enable

1. Config: `trackMapEnabled: true` (+ telemetry running).
2. OBS: eye **ON** only on **Overlay Broadcast Chrome** — the minimap is drawn **inside** that page (middle-right, above Cam 2).
3. Optional separate source **Overlay Track Map** can stay eye-off (legacy / standalone).
4. Refresh cache on the Broadcast Browser Source after updates.

## Asset resolution

1. `overlays/assets/tracks/open/{trackId}.json` if present  
2. `overlays/assets/tracks/learned/{trackId}.json` (self-learn from bridge)  
3. Generic oval fallback  

Self-learn: while `iracing_bridge` runs, focus motion samples flush into `learned/` (and `adapters/telemetry/tracks_learned/`). First laps look rough; they improve as samples accumulate.

## CONTRACT

Ticks may include `trackId` and `mapCars[]` (`carIdx`, `carNumber`, `distPct`, `isFocus`). See `adapters/telemetry/CONTRACT.md`.
