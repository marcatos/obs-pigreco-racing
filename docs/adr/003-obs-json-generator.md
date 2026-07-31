# ADR-003: Generate OBS JSON; never rely on hand-tuned relative transforms

## Status

Accepted — 2026-07-31

## Context

OBS 32 rewrites `pos_rel`; incorrect values pin sources to canvas center.

## Decision

All scene item placement goes through `tools/generate_pack.py` helpers (`pos_rel`, `scale_rel`).

## Consequences

- Agents must extend the generator for new sources.
- After edits, reinstall JSON with OBS closed.
