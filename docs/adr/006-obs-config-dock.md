# ADR-006: OBS Custom Browser Dock + local config server

## Status

Accepted — 2026-07-31

## Context

Piloti non tecnici devono cambiare username/sessione/sponsor senza aprire editor di testo. OBS non può scrivere `file://` dalla UI.

## Decision

1. Canonical config: `overlays/config.values.json`
2. Generated `overlays/config.js` = JSON + `config.runtime.js`
3. Local stdlib HTTP server `tools/config_server.py` on `127.0.0.1:8766`
4. UI: Custom Browser Dock → that URL
5. Optional OBS script to refresh Browser Source caches

## Consequences

- Server must run while using the panel. Autostart stack:
  1. **OBS Lua script** `obs/scripts/pigreco_config_autostart.lua` (+ `tools/ensure_config_server.py`) — preferred; Lua is always available inside OBS (Python scripting often fails with system Python 3.12+/3.14).
  2. Optional **Windows Startup** shortcut via `tools/install_config_autostart.ps1`.
  3. Manual fallback: `Start-ConfigPanel.bat`.
- Legacy Python OBS script `pigreco_config_autostart.py` remains for machines with a compatible OBS Python (e.g. 3.10) but is no longer wired into generated collections.
- No cloud dependency.
- Future: could add obs-websocket push refresh without script button.
