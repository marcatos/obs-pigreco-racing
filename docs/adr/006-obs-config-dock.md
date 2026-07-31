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

- Server must run while using the panel.
- No cloud dependency.
- Future: could add obs-websocket push refresh without script button.
