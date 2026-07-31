# ADR-004: Windows-first setup with optional elevated Python install

## Status

Accepted — 2026-07-31

## Context

Pilots may lack Python; asking them to install manually fails.

## Decision

`Setup.ps1` detects Python; if missing, re-launches elevated and installs via **winget** (`Python.Python.3.12`), then runs `setup_streamer.py`.

## Consequences

- UAC prompt is expected once.
- Non-Windows is out of scope for setup automation.
