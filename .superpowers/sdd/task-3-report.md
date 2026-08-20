# Task 3 report — Gate fight panel in broadcast.js

**Status:** done  
**Branch:** `feat/p3-12-cam-flag-battle`  
**Roadmap:** P3-12 (left `in_progress`; flag strip + ROADMAP close are later tasks)  
**Commit:** `fcde2e9` `feat(broadcast): gate battle panel on battleEligible / session`  
**Pushed:** no

## What shipped

- Helper `battleEligibleFromTick(tick)` at the top of the battle section in `overlays/broadcast.js`.
- `updateFightPanel` now returns before gap/arm logic when ineligible: if the panel was on, it hides and logs; if off, it only clears `battleStreak`.
- `docs/TELEMETRY_BROADCAST.md` documents the session rule under the battle-panel config bullets.

### Eligibility (client)

| Input | Result |
|-------|--------|
| `tick.battleEligible` is a boolean | that value (bridge / Task 2 wins) |
| missing bool + `session` quali / cooldown / unknown / empty | `false` |
| missing bool + `session` race | `true` iff `lap` is finite and `>= 1` |
| missing bool + `session` practice | `true` iff `tick.standings.length >= 2` |
| missing / null tick, or other session | `false` |

After Task 2 the bool is always on the tick; the session/lap/standings path is legacy-only.

## Files

| Path | Change |
|------|--------|
| `overlays/broadcast.js` | helper + gate at start of `updateFightPanel` |
| `docs/TELEMETRY_BROADCAST.md` | battle pack eligibility bullet |

## Tests

- No JS unit tests for `broadcast.js` fight-panel logic (N/A).
- Isolated Node copy of the helper: 11/11 matrix cases OK (bool true/false, race lap 0/1, practice solo/2, quali, cooldown, unknown, empty session, null tick).
- `node --check overlays/broadcast.js` → OK.
- `python -m pytest tests/test_broadcast_director.py -q` → 8 passed, **1 failed** (`test_overlay_runtime_director_policies_via_node`): harness `ReferenceError: location is not defined` in pre-existing `flagAssetBase()`. Same `location.pathname` exists on HEAD; not introduced by this gate. Not fixed (out of scope).

## Constraints / notes

- Overlay stays an IIFE in `broadcast.js` (existing pack). No new hexagonal tree.
- Logging uses existing `directorLog` (INFO when an active panel is forced off).
- Did not touch flag strip, director `battle` hero chips, `generate_pack.py`, or ROADMAP status.
- Marcato chrome already loads shared `overlays/broadcast.js`.

## Concerns

1. Director `telemetry.event` `battle` chips are **not** gated here (brief: only `updateFightPanel`). A quali/formation fight chip could still play if the producer emits `battle`.
2. Fallback practice check uses `tick.standings.length >= 2`, not “≥1 other car vs focus”. Harmless after Task 2 (bool always present).
3. Pre-existing overlay runtime harness crash (`location` missing) — Task 7 review lock, unrelated to this change.

## Critical dependency fix — 2026-08-20

- Reviewed the untracked instant-replay policy and focused tests against `InstantReplayController`; the module provides the imported config parser and all policy methods used by the director, including `reset()`.
- Committed `adapters/obs_flag_director/domain_instant_replay.py` and `tests/test_instant_replay_policy.py` as `752a6bd` (`feat(director): add instant replay policy module (session-reset dep)`).
- `python -m pytest tests/test_flag_director.py tests/test_instant_replay_policy.py -v` passed: 28 tests in 0.04s.
- `python -m py_compile adapters/obs_flag_director/domain_instant_replay.py tests/test_instant_replay_policy.py` passed; IDE diagnostics reported no errors.
- Unrelated dirty overlay, telemetry, OBS pack, documentation, and generator WIP remained unstaged.
