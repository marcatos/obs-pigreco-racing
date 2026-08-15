# Task 3 Report — Live/Ending overrides + quick transitions + bed fade settings

**Branch:** `feat/audio-scene-transitions`  
**Date:** 2026-08-14  
**Status:** ✅ Complete

## Summary

Wired per-scene stinger transition overrides on Marcato Live and Ending scenes, replaced the Marcato live quick-transition dock with Dissolvenza / Stinger / Taglio, and set interstitial bed `ffmpeg_source` settings to keep decoders warm through scene fades.

## Changes

### `tools/generate_pack.py`

#### 1. Live + Ending stinger overrides (`build_marcato_live_collection`)

After `scene_live` and `scene_end` are built:

```python
apply_scene_transition_override(
    scene_live, transition_name="S.Marcato Stinger", duration_ms=850
)
apply_scene_transition_override(
    scene_end, transition_name="S.Marcato Stinger", duration_ms=850
)
```

Each scene’s `private_settings` now carries `transition: "S.Marcato Stinger"` and `transition_duration: 850`.

#### 2. Quick transitions dock

Replaced the old 5-entry dock (Taglio, current_tr, Swipe Racing, Flash Carbon, Dissolvenza 350) with:

| id | name | duration |
|----|------|----------|
| 1 | Dissolvenza | `tr_dur` (900 ms Marcato default) |
| 2 | S.Marcato Stinger | 850 ms *(only if transition exists)* |
| 3 | Taglio | 0 ms |

If `S.Marcato Stinger` is absent from `transitions`, id 2 is omitted and Taglio is renumbered to id 2.

#### 3. Fade-friendly interstitial beds

**Marcato live** `music()` helper:

- `close_when_inactive`: `False` (was `True`)
- `restart_on_activate`: `True` (unchanged)

**Replay** `music()` helper (same pattern):

- `close_when_inactive`: `False` (was `True`)
- `restart_on_activate`: `True` (unchanged)

Rationale: keeps ffmpeg decoders warm through 850–900 ms dissolves/stingers so bed audio does not cut abruptly when scenes deactivate.

### `tests/test_pack_transitions.py`

Added `test_override_helper_idempotent` — calls `apply_scene_transition_override` twice on the same scene and asserts stable `private_settings`.

Existing tests retained:

- `test_marcato_default_is_dissolvenza_900`
- `test_apply_scene_transition_override_sets_private_settings`

## Test results

```
python -m pytest tests/test_pack_transitions.py -v
```

```
tests/test_pack_transitions.py::test_marcato_default_is_dissolvenza_900 PASSED
tests/test_pack_transitions.py::test_apply_scene_transition_override_sets_private_settings PASSED
tests/test_pack_transitions.py::test_override_helper_idempotent PASSED

3 passed in 0.05s
```

## Commit

```
feat(obs): stinger overrides on Live/Ending and fade-friendly beds
```

Staged files only:

- `tools/generate_pack.py`
- `tests/test_pack_transitions.py`

## Out of scope (deferred)

- **Task 4:** Regenerate `obs/S_Marcato_42.json` (and siblings) — JSON on disk still reflects pre-Task-3 quick_transitions until regen.
- **Task 5:** `TRANSITIONS.md` documentation update.
- Full-collection integration test for Live/Ending overrides (brief recommends helper-level test only; monitor/mic side effects avoided).

## Notes / concerns

1. **JSON drift:** Until Task 4 runs `generate_pack.py`, committed OBS JSON files may not match generator output. Expected per task split.
2. **CPU cost:** `close_when_inactive: False` keeps up to 4 loop decoders resident on Marcato live; brief accepts this tradeoff for smoother fades.
3. **Stinger conditional:** Quick dock omits Stinger entry only if `build_transitions(profile="marcato")` ever drops it; current Marcato profile always includes it.
