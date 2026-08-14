# Audio-aware Scene Transitions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make S.Marcato 42 scene changes dissolve the full scene audio mix by default (Dissolvenza 900 ms), and use S.Marcato Stinger + whoosh when switching to Live or Ending.

**Architecture:** Keep OBS-native behaviour only. Change `build_transitions` defaults for profile `marcato`, set scene `private_settings.transition` overrides on Live/Ending, tune stinger whoosh volume and bed Media Source flags so fades are not hard-cut. Docs + pack regenerate; no Session Director volume scripting.

**Tech Stack:** Python (`tools/generate_pack.py`), OBS 32.x scene collection JSON, pytest, existing `marcato-stinger.webm` (VP9 + Opus whoosh).

## Global Constraints

- Canvas / overlays remain **1920×1080**.
- No Advanced Scene Switcher; no WebSocket volume ramps in Session Director.
- Default transition for Marcato: **Dissolvenza**, duration **900** ms.
- Highlight overrides: switching **to Live** and **to Ending** → **S.Marcato Stinger**.
- Stinger `audio_fade_style` remains **crossfade** (`1`).
- Conventional Commits; commit after each task.
- Spec: `docs/superpowers/specs/2026-08-14-audio-scene-transitions-design.md`.

## File map

| File | Responsibility |
|------|----------------|
| `tools/generate_pack.py` | `build_transitions`, `make_scene` / override helper, Marcato Live (+ Replay via shared builder) wiring, bed media settings, quick transitions |
| `tests/test_pack_transitions.py` | Unit tests for default transition + override private_settings (no OBS) |
| `docs/TRANSITIONS.md` | Operator-facing transition defaults |
| `docs/SESSION_DIRECTOR.md` / `docs/S_MARCATO_42.md` | Short audio/transition notes |
| `obs/S_Marcato_*.json` | Regenerated artifacts |

---

### Task 1: Unit tests for Marcato transition defaults + scene override helper

**Files:**
- Create: `tests/test_pack_transitions.py`
- Modify: `tools/generate_pack.py` (minimal helpers in Task 2 — this task writes failing tests first)

**Interfaces:**
- Consumes: nothing yet (tests define expected API)
- Produces: failing tests that expect:
  - `build_transitions(overlays_dir=..., profile="marcato")` → `("Dissolvenza", 900)` as current name + duration
  - `apply_scene_transition_override(scene, transition_name, duration_ms)` sets `scene["private_settings"]["transition"]` and `transition_duration`

- [ ] **Step 1: Write the failing tests**

```python
"""Pack transition defaults (no OBS)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import generate_pack as gp  # noqa: E402


def test_marcato_default_is_dissolvenza_900():
    overlays = ROOT / "overlays-marcato"
    transitions, current, duration = gp.build_transitions(
        overlays_dir=overlays, profile="marcato"
    )
    assert current == "Dissolvenza"
    assert duration == 900
    names = [t["name"] for t in transitions]
    assert "Dissolvenza" in names
    assert "S.Marcato Stinger" in names
    assert "S.Marcato Move" in names
    stinger = next(t for t in transitions if t["name"] == "S.Marcato Stinger")
    assert stinger["settings"]["audio_fade_style"] == 1
    assert stinger["volume"] <= 0.55


def test_apply_scene_transition_override_sets_private_settings():
    scene = gp.make_scene("Live", [])
    gp.apply_scene_transition_override(
        scene, transition_name="S.Marcato Stinger", duration_ms=850
    )
    assert scene["private_settings"]["transition"] == "S.Marcato Stinger"
    assert scene["private_settings"]["transition_duration"] == 850
```

- [ ] **Step 2: Run tests — expect FAIL**

```powershell
python -m pytest tests/test_pack_transitions.py -v
```

Expected: FAIL (`apply_scene_transition_override` missing and/or wrong `current`/`duration`/`volume`).

- [ ] **Step 3: Commit tests only**

```powershell
git add tests/test_pack_transitions.py
git commit -m "test(transitions): expect Dissolvenza default and scene override helper"
```

---

### Task 2: Implement `build_transitions` Marcato defaults + override helper

**Files:**
- Modify: `tools/generate_pack.py` (`build_transitions` ~707–777, add helper near `make_scene` ~780)

**Interfaces:**
- Consumes: existing `transition_source`, stinger path for marcato
- Produces:
  - `build_transitions(*, overlays_dir: Path, profile: str) -> tuple[list[dict], str, int]`
  - For `profile=="marcato"`: `current="Dissolvenza"`, `duration=900`
  - For other profiles: keep Move default + `_MOVE_DURATION_MS` (unchanged)
  - Stinger `volume=0.45` (whoosh under mix)
  - `def apply_scene_transition_override(scene: dict, *, transition_name: str, duration_ms: int) -> None`

- [ ] **Step 1: Add helper after `make_scene`**

```python
def apply_scene_transition_override(
    scene: dict,
    *,
    transition_name: str,
    duration_ms: int,
) -> None:
    """OBS stores per-scene overrides in private_settings (websocket SetSceneSceneTransitionOverride)."""
    ps = scene.setdefault("private_settings", {})
    ps["transition"] = transition_name
    ps["transition_duration"] = int(duration_ms)
```

- [ ] **Step 2: Change Marcato branch of `build_transitions`**

After building `transitions` list (including stinger insert), set:

```python
    if profile == "marcato":
        current = "Dissolvenza"
        duration = 900
        log.info("marcato default transition: Dissolvenza (%d ms)", duration)
    else:
        current = move_name
        duration = _MOVE_DURATION_MS
        log.info("move transition default: %s (%d ms)", move_name, duration)
```

Remove the old unconditional `current = move_name` / `duration = _MOVE_DURATION_MS` assignment that runs before the stinger block.

Pass `volume=0.45` into `transition_source(...)` for the stinger (replace `volume=1.0`).

- [ ] **Step 3: Run tests — expect PASS**

```powershell
python -m pytest tests/test_pack_transitions.py -v
```

Expected: 2 passed.

- [ ] **Step 4: Commit**

```powershell
git add tools/generate_pack.py tests/test_pack_transitions.py
git commit -m "feat(transitions): Dissolvenza 900ms default for Marcato + override helper"
```

---

### Task 3: Wire Live/Ending overrides + quick transitions + bed fade-friendly settings

**Files:**
- Modify: `tools/generate_pack.py` — `build_marcato_live_collection` (after `scene_live` / `scene_end` created; quick_transitions block ~1658–1670)
- Modify: bed `music()` settings in Marcato live (and Replay beds that share the same pattern) if cuts persist — start with:
  - `close_when_inactive`: `False` for interstitial beds only on Marcato live (keeps decoder warm through fade; CPU cost small for 4 loops)
  - keep `restart_on_activate`: `True`

**Interfaces:**
- Consumes: `apply_scene_transition_override`, stinger name `"S.Marcato Stinger"`
- Produces: Live + Ending scenes with private_settings overrides; quick dock = Dissolvenza / Stinger / Taglio

- [ ] **Step 1: After `scene_live` and `scene_end` are built in `build_marcato_live_collection`**

```python
    apply_scene_transition_override(
        scene_live, transition_name="S.Marcato Stinger", duration_ms=850
    )
    apply_scene_transition_override(
        scene_end, transition_name="S.Marcato Stinger", duration_ms=850
    )
```

- [ ] **Step 2: Replace Marcato live `quick_transitions` with**

```python
    collection["quick_transitions"] = [
        {"name": "Dissolvenza", "duration": tr_dur, "hotkeys": [], "id": 1, "fade_to_black": False},
        {"name": "S.Marcato Stinger", "duration": 850, "hotkeys": [], "id": 2, "fade_to_black": False},
        {"name": "Taglio", "duration": 0, "hotkeys": [], "id": 3, "fade_to_black": False},
    ]
```

(Only include Stinger entry if that transition exists in `transitions`; if missing, omit id 2 and renumber.)

- [ ] **Step 3: In Marcato live `music()` ffmpeg settings, set**

```python
                "close_when_inactive": False,
                "restart_on_activate": True,
```

Apply the same bed flags in Replay’s `music()` if it still uses `close_when_inactive: True` (same file, Replay builder).

- [ ] **Step 4: Extend unit test**

```python
def test_marcato_live_live_and_ending_have_stinger_override(tmp_path, monkeypatch):
    # Optional: call build_marcato_live_collection only if mic/monitor helpers are safe;
    # otherwise assert by grepping written JSON after generate in Task 4.
    pass
```

Prefer **not** calling full collection build in unit tests (monitor/mic side effects). Instead add:

```python
def test_override_helper_idempotent():
    scene = gp.make_scene("Ending", [])
    gp.apply_scene_transition_override(
        scene, transition_name="S.Marcato Stinger", duration_ms=850
    )
    gp.apply_scene_transition_override(
        scene, transition_name="S.Marcato Stinger", duration_ms=850
    )
    assert scene["private_settings"]["transition"] == "S.Marcato Stinger"
```

- [ ] **Step 5: Run pytest**

```powershell
python -m pytest tests/test_pack_transitions.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add tools/generate_pack.py tests/test_pack_transitions.py
git commit -m "feat(obs): stinger overrides on Live/Ending and fade-friendly beds"
```

---

### Task 4: Regenerate Marcato pack + assert JSON

**Files:**
- Modify (generated): `obs/S_Marcato_42.json`, `obs/S_Marcato_Replay.json` (and Rec 2K if it calls `build_transitions`)

- [ ] **Step 1: Regenerate**

```powershell
python tools/generate_pack.py --profile marcato
```

Expected: logs `marcato default transition: Dissolvenza (900 ms)`; collections installed.

- [ ] **Step 2: Assert JSON (PowerShell)**

```powershell
python -c @"
import json
from pathlib import Path
c=json.loads(Path('obs/S_Marcato_42.json').read_text(encoding='utf-8'))
assert c['current_transition']=='Dissolvenza'
assert c['transition_duration']==900
by={s['name']:s for s in c['sources']}
assert by['Live']['private_settings']['transition']=='S.Marcato Stinger'
assert by['Ending']['private_settings']['transition']=='S.Marcato Stinger'
assert by['Lobby']['private_settings'].get('transition') in (None, '')
st=next(t for t in c['transitions'] if t['name']=='S.Marcato Stinger')
assert st['volume']<=0.55
print('S_Marcato_42 transition assertions OK')
"@
```

Expected: `S_Marcato_42 transition assertions OK`.

- [ ] **Step 3: Commit artifacts**

```powershell
git add obs/S_Marcato_42.json obs/S_Marcato_Replay.json obs/S_Marcato_Rec_2K.json
git commit -m "chore(obs): regenerate Marcato collections with audio-aware transitions"
```

---

### Task 5: Docs

**Files:**
- Modify: `docs/TRANSITIONS.md`
- Modify: `docs/SESSION_DIRECTOR.md` (one short subsection)
- Modify: `docs/S_MARCATO_42.md` (replace Move-default wording)

- [ ] **Step 1: Rewrite Marcato section of `docs/TRANSITIONS.md` to state**

- Default: **Dissolvenza 900 ms** (full mix crossfade)
- Overrides: **Live** / **Ending** → **S.Marcato Stinger** + whoosh
- Move remains optional
- Quick: Dissolvenza · Stinger · Taglio
- Note: judge fades from stream/recording; Monitor Alone may differ

- [ ] **Step 2: Add checklist lines to SESSION_DIRECTOR / S_MARCATO_42** matching the spec verification table (Soon→Lobby fade; Lobby→Live stinger; Live→BRB fade; BRB→Ending stinger).

- [ ] **Step 3: Commit**

```powershell
git add docs/TRANSITIONS.md docs/SESSION_DIRECTOR.md docs/S_MARCATO_42.md
git commit -m "docs(transitions): Dissolvenza default and Live/Ending stinger overrides"
```

---

### Task 6: Manual OBS verification (operator)

**Files:** none (checklist only)

- [ ] **Step 1:** Restart OBS if generate_pack did not; collection **S.Marcato 42**.

- [ ] **Step 2:** Dock Transizioni → **Dissolvenza** selected, duration **900**.

- [ ] **Step 3:** Right-click **Live** / **Ending** → Transition Override → **S.Marcato Stinger**.

- [ ] **Step 4:** Record a short take while switching: Starting Soon → Lobby → Live → BRB → Ending. Confirm bed/Desktop/mic dissolve on Dissolvenza; whoosh + wipe on Live/Ending; no hard music cut mid-fade.

- [ ] **Step 5:** If beds still hard-cut, flip `close_when_inactive` experiment (document result in `TRANSITIONS.md`) and regenerate — do not add Advanced Scene Switcher.

---

## Spec coverage (self-review)

| Spec requirement | Task |
|------------------|------|
| Dissolvenza 900 default | 1–2, 4 |
| Full mix crossfade via native Fade | 2–3 (beds), 6 |
| Stinger+whoosh to Live/Ending | 3–4 |
| Taglio emergency | 3 quick list |
| No ASS / no WS volume | Global + Task 3 non-goals |
| Docs | 5 |
| Verification checklist | 5–6 |
| Stinger volume under mix | 2 (`0.45`) |
| OBS private_settings override shape | 2–3 (websocket-documented keys) |

## Placeholder / consistency scan

- No TBD steps; helper name `apply_scene_transition_override` used consistently.
- Stinger display name always `S.Marcato Stinger`.
- Duration override `850` matches ~stinger length; default Fade `900`.
