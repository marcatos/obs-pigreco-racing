# ADR-001: Local HTML Browser Sources (not cloud overlays)

## Status

Accepted — 2026-07-31

## Context

Need branded overlays shareable offline inside the team.

## Decision

Use OBS **Browser Source** pointing at local `file:///` HTML/CSS/JS in `overlays/`.

## Consequences

- Works offline; zip-friendly.
- Paths must be regenerated per machine (`setup_streamer` / `generate_pack`).
- No server dependency for core pack.
