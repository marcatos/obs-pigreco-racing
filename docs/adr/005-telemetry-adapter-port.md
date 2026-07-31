# ADR-005: Telemetry via adapter port (future)

## Status

Proposed — 2026-07-31

## Context

Phase 3 needs iRacing/ACC/SimHub data without coupling HTML to one SDK.

## Decision

Introduce `adapters/telemetry/` that exposes a **local** contract (WebSocket or JSON file). Overlays subscribe to that contract only.

## Consequences

- No direct sim SDK imports inside `overlays/*.js`.
- First milestone is contract + mock producer, then real SimHub bridge.
