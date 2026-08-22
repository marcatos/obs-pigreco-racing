# Session Reset Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Soft-reset telemetry continuity, Session Director sticky state, and broadcast overlays between iRacing races without restarting processes — auto on session-key change, manual via VirtualDeck scene `Reset Session`.

**Architecture:** Pure domain tracker builds a session key and decides when to emit reset; the iRacing bridge owns `reset_continuity()` + WS broadcast of `telemetry.session_reset`. Manual path: VirtualDeck → OBS scene → director sends `telemetry.command` / `session_reset` on the existing WS. Overlays clear hero/board/fight on that message.

**Tech Stack:** Python 3 (pytest, websockets, pyirsdk), OBS JSON via `tools/generate_pack.py`, Browser Source JS overlays, VirtualDeck checklist JSON.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-08-20-session-reset-design.md`
- Plane: **OBSPI-60**
- Canvas / overlays **1920×1080**; brand tokens unchanged
- Extend OBS via `tools/generate_pack.py` (correct `pos_rel`), not fragile hand JSON
- Sync new config keys to `overlays/config.example.js` and `adapters/obs_flag_director/config.example.json`
- Conventional Commits; do not commit secrets / `config.local.json`
- Close OBS before regenerating `obs/S_Marcato_42.json`
- Hexagonal: session-key / debounce logic in domain modules (no SDK/OBS IO inside domain)
- Do not yank Starting Soon / BRB / Ending on reset

---

## File map

| File | Responsibility |
|------|----------------|
| `adapters/telemetry/domain_session_reset.py` | Pure `build_session_key`, `SessionResetTracker`, envelope helpers |
| `adapters/telemetry/iracing_bridge.py` | Latch key each tick; handle `telemetry.command`; broadcast reset |
| `adapters/telemetry/mock_server.py` | Optional: honor `telemetry.command` for overlay/dev testing |
| `adapters/telemetry/CONTRACT.md` | Document `telemetry.session_reset` + `telemetry.command` |
| `adapters/obs_flag_director/domain_flag_director.py` | `on_reset_session_request` → restore scene or None |
| `adapters/obs_flag_director/director.py` | Detect Reset Session scene; send command; handle reset echo |
| `adapters/obs_flag_director/config.example.json` | `resetSessionScene`, include in `manualScenes` |
| `overlays/broadcast-director.js` | Pure `clearDirectorState` helper |
| `overlays/broadcast.js` | On `session_reset`: clear moments, board latch, fight pack |
| `tools/generate_pack.py` | Marcato scene `Reset Session` (empty aux) |
| `obs/S_Marcato_42.json` | Regenerated |
| `adapters/streamdeck/marcato-live-deck.json` | Reset button checklist |
| `docs/OBS_VIRTUALDECK.md`, `docs/SESSION_DIRECTOR.md` | Operator docs |
| `tests/test_domain_session_reset.py` | Key + tracker unit tests |
| `tests/test_flag_director.py` | Reset-session restore rules |
| `tests/test_marcato_profile.py` | Scene present in generated pack |
| `tests/test_broadcast_director_js.py` or inline Node-less: assert via reading JS / small pytest parsing — prefer extending existing pattern if any; otherwise pure Python tests only for domain and a string-presence smoke for JS handler |

---

### Task 1: Domain session key + reset tracker

**Files:**
- Create: `adapters/telemetry/domain_session_reset.py`
- Create: `tests/test_domain_session_reset.py`

**Interfaces:**
- Consumes: nothing (pure)
- Produces:
  - `build_session_key(*, unique_id: Any, track_id: Any, session_num: Any, session_kind: str | None) -> str | None`
  - `class SessionResetTracker`: `note(key: str | None, *, now_ms: int) -> dict | None` returning a reset event dict or `None`
  - `session_reset_envelope(*, reason: str, session_key: str | None, previous_key: str | None, ts: int) -> dict`
  - `RESET_DEBOUNCE_MS = 1500`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_domain_session_reset.py
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "adapters" / "telemetry"))

from domain_session_reset import (  # noqa: E402
    SessionResetTracker,
    build_session_key,
    session_reset_envelope,
)


def test_build_session_key_prefers_unique_id():
    assert (
        build_session_key(
            unique_id="UID-9",
            track_id=123,
            session_num=2,
            session_kind="race",
        )
        == "UID-9"
    )


def test_build_session_key_fallback_tuple():
    k = build_session_key(
        unique_id=None,
        track_id=42,
        session_num=1,
        session_kind="race",
    )
    assert k == "42:1:race"


def test_build_session_key_none_when_unstable():
    assert (
        build_session_key(
            unique_id=None,
            track_id=None,
            session_num=None,
            session_kind=None,
        )
        is None
    )


def test_tracker_first_latch_no_emit():
    t = SessionResetTracker(debounce_ms=1500)
    assert t.note("A", now_ms=1000) is None
    assert t.current_key == "A"


def test_tracker_key_change_emits_once():
    t = SessionResetTracker(debounce_ms=1500)
    t.note("A", now_ms=1000)
    ev = t.note("B", now_ms=3000)
    assert ev is not None
    assert ev["reason"] == "session_changed"
    assert ev["sessionKey"] == "B"
    assert ev["previousKey"] == "A"
    assert t.note("B", now_ms=3500) is None


def test_tracker_debounce_collapses_rapid_changes():
    t = SessionResetTracker(debounce_ms=1500)
    t.note("A", now_ms=1000)
    assert t.note("B", now_ms=1100) is not None
    assert t.note("C", now_ms=1200) is None  # within debounce
    assert t.current_key == "B"  # ignored flicker keeps last emitted key
    # After debounce, C can emit
    ev = t.note("C", now_ms=3000)
    assert ev is not None
    assert ev["sessionKey"] == "C"


def test_tracker_force_manual():
    t = SessionResetTracker(debounce_ms=1500)
    t.note("A", now_ms=1000)
    ev = t.force(reason="manual", now_ms=1500)
    assert ev["reason"] == "manual"
    assert ev["sessionKey"] == "A"


def test_session_reset_envelope_shape():
    msg = session_reset_envelope(
        reason="session_changed",
        session_key="B",
        previous_key="A",
        ts=99,
    )
    assert msg["type"] == "telemetry.session_reset"
    assert msg["schemaVersion"] == 1
    assert msg["ts"] == 99
    assert msg["reason"] == "session_changed"
    assert msg["sessionKey"] == "B"
    assert msg["previousKey"] == "A"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_domain_session_reset.py -v`  
Expected: FAIL (module not found)

- [ ] **Step 3: Implement domain module**

```python
# adapters/telemetry/domain_session_reset.py
"""Pure session identity + reset gating (no IO)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

RESET_DEBOUNCE_MS = 1500


def build_session_key(
    *,
    unique_id: Any,
    track_id: Any,
    session_num: Any,
    session_kind: str | None,
) -> str | None:
    if unique_id is not None and str(unique_id).strip():
        return str(unique_id).strip()
    try:
        sn = int(session_num) if session_num is not None else None
    except (TypeError, ValueError):
        sn = None
    tid = None
    if track_id is not None and str(track_id).strip():
        tid = str(track_id).strip()
    kind = (session_kind or "unknown").strip().lower() or "unknown"
    if tid is None or sn is None:
        return None
    return f"{tid}:{sn}:{kind}"


def session_reset_envelope(
    *,
    reason: str,
    session_key: str | None,
    previous_key: str | None,
    ts: int,
) -> dict[str, Any]:
    return {
        "type": "telemetry.session_reset",
        "schemaVersion": 1,
        "ts": int(ts),
        "reason": reason,
        "sessionKey": session_key,
        "previousKey": previous_key,
    }


@dataclass
class SessionResetTracker:
    debounce_ms: int = RESET_DEBOUNCE_MS
    current_key: str | None = None
    _last_emit_ms: int = field(default=-10**12, repr=False)
    _warned_missing: bool = field(default=False, repr=False)

    def note(self, key: str | None, *, now_ms: int) -> dict[str, Any] | None:
        if key is None:
            return None
        if self.current_key is None:
            self.current_key = key
            return None
        if key == self.current_key:
            return None
        if (now_ms - self._last_emit_ms) < self.debounce_ms:
            return None
        prev = self.current_key
        self.current_key = key
        self._last_emit_ms = now_ms
        return {
            "reason": "session_changed",
            "sessionKey": key,
            "previousKey": prev,
        }

    def force(self, *, reason: str, now_ms: int) -> dict[str, Any]:
        self._last_emit_ms = now_ms
        return {
            "reason": reason,
            "sessionKey": self.current_key,
            "previousKey": self.current_key,
        }

    def clear_key(self) -> None:
        """On sim disconnect — next connect re-latches without emit if same key."""
        self.current_key = None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_domain_session_reset.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add adapters/telemetry/domain_session_reset.py tests/test_domain_session_reset.py
git commit -m "feat(telemetry): domain session key and reset tracker"
```

---

### Task 2: Bridge — auto session change + `telemetry.command`

**Files:**
- Modify: `adapters/telemetry/iracing_bridge.py`
- Modify: `adapters/telemetry/CONTRACT.md`
- Modify: `tests/test_telemetry_events.py` (or new `tests/test_session_reset_bridge.py` for import-level wiring assertions)
- Optional: `adapters/telemetry/mock_server.py` — same command handler for local overlay tests

**Interfaces:**
- Consumes: `build_session_key`, `SessionResetTracker`, `session_reset_envelope`, `reset_continuity`
- Produces: WS broadcast of `telemetry.session_reset`; client command `telemetry.command` / `session_reset`

- [ ] **Step 1: Write failing wiring tests**

```python
# tests/test_session_reset_bridge.py
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_bridge_imports_session_reset_domain():
    src = (ROOT / "adapters" / "telemetry" / "iracing_bridge.py").read_text(
        encoding="utf-8"
    )
    assert "domain_session_reset" in src
    assert "SessionResetTracker" in src
    assert "telemetry.command" in src
    assert "session_reset" in src


def test_contract_documents_session_reset():
    text = (ROOT / "adapters" / "telemetry" / "CONTRACT.md").read_text(encoding="utf-8")
    assert "telemetry.session_reset" in text
    assert "telemetry.command" in text
```

- [ ] **Step 2: Run to verify fail**

Run: `python -m pytest tests/test_session_reset_bridge.py -v`  
Expected: FAIL on missing strings

- [ ] **Step 3: Wire tracker into bridge**

In `iracing_bridge.py`:

1. Import domain helpers; module-level `_session_tracker = SessionResetTracker()`.
2. Inside `build_tick_from_ir` (or right after tick built in the main loop), compute:

```python
unique = _safe_get(ir, "SessionUniqueID", None)
track_id = None
try:
    track_id = ir["WeekendInfo"].get("TrackID")
except Exception:
    pass
key = build_session_key(
    unique_id=unique,
    track_id=track_id,
    session_num=session_num,
    session_kind=session_kind,
)
```

Prefer computing in the main loop after `build_tick_from_ir` so broadcast is not buried inside tick builder. Collect pending reset events on a module list / return side channel.

Cleaner pattern:

```python
def note_session_identity(ir, *, now_ms: int) -> dict | None:
    # extract unique / track / session_num / kind; call tracker.note
    ...
```

On non-None event: `reset_continuity()` then return envelope for broadcast.

3. On disconnect path (existing `reset_continuity()`): also `_session_tracker.clear_key()` and optionally broadcast `session_reset` with `reason=sim_disconnected` (spec allows). Prefer broadcasting so overlays clear:

```python
reset_continuity()
_session_tracker.clear_key()
# broadcast session_reset envelope reason=sim_disconnected sessionKey=null
```

4. Extend WS `handler` client loop:

```python
if msg.get("type") == "telemetry.command" and msg.get("command") == "session_reset":
    ev = _session_tracker.force(
        reason=str(msg.get("reason") or "manual"),
        now_ms=int(msg.get("ts") or time.time() * 1000),
    )
    reset_continuity()
    payload = session_reset_envelope(
        reason=ev["reason"],
        session_key=ev["sessionKey"],
        previous_key=ev["previousKey"],
        ts=int(msg.get("ts") or time.time() * 1000),
    )
    # broadcast to all clients (same as ticks)
```

Unknown commands: log WARNING, continue (do not disconnect).

5. Document in `CONTRACT.md` after `telemetry.status` section — copy shapes from the spec.

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_session_reset_bridge.py tests/test_domain_session_reset.py tests/test_telemetry_events.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add adapters/telemetry/iracing_bridge.py adapters/telemetry/CONTRACT.md tests/test_session_reset_bridge.py
git commit -m "feat(telemetry): auto and command session_reset on bridge"
```

---

### Task 3: Session Director — Reset Session scene + local clear

**Files:**
- Modify: `adapters/obs_flag_director/domain_flag_director.py`
- Modify: `adapters/obs_flag_director/director.py`
- Modify: `adapters/obs_flag_director/config.example.json`
- Modify: `tests/test_flag_director.py`
- Modify: `tests/test_instant_replay_policy.py` (optional assert `reset()` already exists)

**Interfaces:**
- Consumes: InstantReplayPolicy.reset, telemetry WS send
- Produces:
  - `SessionDirectorConfig.reset_session_scene: str = "Reset Session"`
  - `SessionDirector.on_reset_session_scene(*, previous_scene: str | None) -> str | None`  
    Returns race scene to restore, or `None` if stay (manual show scene / unknown)

- [ ] **Step 1: Write failing director tests**

```python
def test_reset_session_restores_live_from_live():
    s = _session()
    s.note_obs_scene("Live")
    assert s.on_reset_session_scene(previous_scene="Live") == "Live"


def test_reset_session_restores_headcam():
    s = _session()
    s.note_obs_scene("Headcam")
    assert s.on_reset_session_scene(previous_scene="Headcam") == "Headcam"


def test_reset_session_stays_on_starting_soon():
    s = _session()
    s.note_obs_scene("Starting Soon")
    assert s.on_reset_session_scene(previous_scene="Starting Soon") is None


def test_reset_session_scene_is_manual():
    s = _session()
    # After config includes Reset Session in manual_scenes:
    s.note_obs_scene("Reset Session")
    assert (
        s.on_session_state(
            iracing_up=True, telemetry_connected=True, now_ms=5000
        )
        is None
    )
```

Update `_session()` helper to pass `manual_scenes` including `"Reset Session"` and `reset_session_scene="Reset Session"` if added as explicit field.

- [ ] **Step 2: Run fail**

Run: `python -m pytest tests/test_flag_director.py::test_reset_session_restores_live_from_live -v`  
Expected: FAIL (method missing)

- [ ] **Step 3: Domain + director wiring**

In `SessionDirectorConfig`:

```python
reset_session_scene: str = "Reset Session"
# DEFAULT_MANUAL_SCENES should include Reset Session OR merge at build time
```

```python
DEFAULT_MANUAL_SCENES = frozenset(
    {"Starting Soon", "BRB", "Ending", "Reset Session"}
)
```

```python
def on_reset_session_scene(self, *, previous_scene: str | None) -> str | None:
    prev = (previous_scene or "").strip()
    if prev in self.config.race_scenes:
        return prev
    return None
```

In `director.py` `session_poll`:

```python
prev_scene = getattr(session_poll, "_prev_prog", None)
cur = await asyncio.to_thread(obs.get_current_scene)
reset_name = str(cfg.get("resetSessionScene") or "Reset Session")
if cur == reset_name and prev_scene != reset_name:
    # local clear
    replay.policy.reset()  # or InstantReplayController method
    await hide_instant_replay_if_showing(...)
    # send command if ws available — keep a shared ws ref or queue
    restore = director.on_reset_session_scene(previous_scene=prev_scene)
    if restore:
        obs.set_scene(restore)
    else:
        # stay on Reset Session briefly is bad UX if previous was Starting Soon —
        # spec: stay on Starting Soon. So if previous was manual show, go back:
        if prev_scene and prev_scene in director.config.manual_scenes and prev_scene != reset_name:
            obs.set_scene(prev_scene)
        elif prev_scene and prev_scene != reset_name:
            obs.set_scene(prev_scene)  # Lobby etc.
# Always track previous non-reset scene
if cur and cur != reset_name:
    session_poll._prev_prog = cur
```

Also handle `telemetry.session_reset` in `ws_loop`:

```python
elif mtype == "telemetry.session_reset":
    replay.policy.reset()
    last_tick_flag = None
    # hide replay item if visible
```

For sending the command, keep `ws_send` queue:

```python
command_q: asyncio.Queue = asyncio.Queue()
# session_poll puts {"type":"telemetry.command",...}
# ws_loop: while connected, drain queue and ws.send
```

`config.example.json`:

```json
"resetSessionScene": "Reset Session",
"manualScenes": ["Starting Soon", "BRB", "Ending", "Reset Session"]
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_flag_director.py tests/test_instant_replay_policy.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add adapters/obs_flag_director/domain_flag_director.py adapters/obs_flag_director/director.py adapters/obs_flag_director/config.example.json tests/test_flag_director.py
git commit -m "feat(director): VirtualDeck Reset Session soft clear"
```

---

### Task 4: Overlay clear on `telemetry.session_reset`

**Files:**
- Modify: `overlays/broadcast-director.js`
- Modify: `overlays/broadcast.js`
- Optional twin: `overlays-marcato/` only if it vendors a copy of broadcast.js (Marcato loads shared overlays — verify; do not duplicate if shared)

**Interfaces:**
- Consumes: WS message type `telemetry.session_reset`
- Produces: `PigrecoBroadcastDirector.clearDirectorState(state) -> {hero:null, queue:[]}`

- [ ] **Step 1: Extend broadcast-director.js**

```javascript
function clearDirectorState(state) {
  return { hero: null, queue: [] };
}
// export on PigrecoBroadcastDirector
```

Add a tiny Node-free check in Python:

```python
# tests/test_broadcast_director_session_reset.py
def test_clear_director_state_in_js():
    src = Path("overlays/broadcast-director.js").read_text(encoding="utf-8")
    assert "clearDirectorState" in src
    br = Path("overlays/broadcast.js").read_text(encoding="utf-8")
    assert "telemetry.session_reset" in br
```

- [ ] **Step 2: Run fail then implement `broadcast.js` handler**

In the WS `message` listener, add:

```javascript
} else if (msg.type === "telemetry.session_reset") {
  clearMomentLayer();
  lastBoardAt = 0;
  latchedGapByKey = Object.create(null);
  latchedRelatives = null;
  lastBoardFocusIdx = null;
  fightPrevOrder = [];
  fightStickyKeys = Object.create(null);
  fightLeaveAt = Object.create(null);
  fightDroppedKeys = Object.create(null);
  fightGapHist = { ahead: null, behind: null, t: 0 };
  fightDispSeps = null;
  fightDispSide = null;
  if (elFight) {
    elFight.hidden = true;
    if (elFightRows) elFightRows.innerHTML = "";
  }
  setStatus("SESSION RESET");
  directorLog("INFO", "session_reset reason=" + (msg.reason || ""));
}
```

Also call the same clear path from `telemetry.status connected=false` (already clears moment layer — extend to board/fight for parity).

- [ ] **Step 3: Run smoke test**

Run: `python -m pytest tests/test_broadcast_director_session_reset.py -v`  
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add overlays/broadcast-director.js overlays/broadcast.js tests/test_broadcast_director_session_reset.py
git commit -m "feat(overlays): clear broadcast UI on session_reset"
```

---

### Task 5: Pack scene + VirtualDeck docs

**Files:**
- Modify: `tools/generate_pack.py` (`build_marcato_live_collection`)
- Modify: `tests/test_marcato_profile.py`
- Regenerate: `obs/S_Marcato_42.json` (and twins only if they share scene list — primary is Marcato 42)
- Modify: `adapters/streamdeck/marcato-live-deck.json`
- Modify: `docs/OBS_VIRTUALDECK.md`, `docs/SESSION_DIRECTOR.md`

**Interfaces:**
- Produces: OBS scene named exactly `Reset Session` (empty `make_scene("Reset Session", [])`)

- [ ] **Step 1: Failing pack test**

```python
def test_marcato_has_reset_session_scene():
    # after generate or against generator output
    assert any(s.get("name") == "Reset Session" for s in scenes)
```

Add assertion in existing marcato profile tests that scene_order / sources include `Reset Session`.

- [ ] **Step 2: Implement in `build_marcato_live_collection`**

```python
scene_reset = make_scene("Reset Session", [])
# append to sources list and scene_order (near end, after Ending or before)
```

Scene order suggestion:

```python
{"name": "Reset Session"},  # aux — last
```

- [ ] **Step 3: Regenerate pack**

Run (OBS closed):

```powershell
python tools/generate_pack.py --profile marcato
```

- [ ] **Step 4: Deck + docs**

`marcato-live-deck.json` button:

```json
{
  "id": "scene-reset-session",
  "label": "Reset Session",
  "action": "SetCurrentProgramScene",
  "sceneName": "Reset Session",
  "hotkeyHint": null
}
```

`OBS_VIRTUALDECK.md` table row + note: returns to Live/Headcam automatically.  
`SESSION_DIRECTOR.md` short section **Session reset** linking the spec.

- [ ] **Step 5: Run tests**

Run: `python -m pytest tests/test_marcato_profile.py tests/test_domain_session_reset.py tests/test_session_reset_bridge.py tests/test_flag_director.py tests/test_broadcast_director_session_reset.py -v`  
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add tools/generate_pack.py obs/S_Marcato_42.json adapters/streamdeck/marcato-live-deck.json docs/OBS_VIRTUALDECK.md docs/SESSION_DIRECTOR.md tests/test_marcato_profile.py
git commit -m "feat(obs): Reset Session scene and VirtualDeck button"
```

---

### Task 6: Acceptance sweep + Plane note

- [x] **Step 1: Full relevant pytest** — 87 passed (2026-08-22)

```powershell
python -m pytest tests/test_domain_session_reset.py tests/test_session_reset_bridge.py tests/test_flag_director.py tests/test_instant_replay_policy.py tests/test_telemetry_events.py tests/test_marcato_profile.py tests/test_broadcast_director_session_reset.py -v
```

Expected: all PASS

- [x] **Step 2: Manual checklist (operator)** — deferred to live stream; unit/integration coverage shipped on `main` (PRs #34–#35, commits through `6c1a6d3`)

1. OBS + Session Director + telemetry running  
2. Race A → note standings/hero  
3. Enter Race B (or change session) without restart → UI clears on key change  
4. VirtualDeck **Reset Session** → brief cut, restore Live/Headcam, UI clear  
5. From Starting Soon press Reset → state clear, return to Starting Soon (not Live)

- [x] **Step 3: Plane** — OBSPI-60 marked Done 2026-08-22

Comment on OBSPI-60 with test results; mark Done when accepted.

- [x] **Step 4: Final commit only if docs tweaks remain**

```bash
git commit -m "docs: close OBSPI-60 session reset acceptance"
```

---

## Spec coverage (self-review)

| Spec requirement | Task |
|------------------|------|
| Session key auto-detect | 1, 2 |
| `telemetry.session_reset` broadcast | 2 |
| `telemetry.command` manual | 2, 3 |
| Overlay clear hero/board/fight | 4 |
| Director replay cooldown clear | 3 |
| VirtualDeck Reset Session scene | 3, 5 |
| No yank Starting Soon/BRB/Ending | 3 |
| CONTRACT + docs | 2, 5 |
| Debounce | 1 |
| pytest | 1–5 |

No TBD placeholders. Debounce behavior on flicker: tracker ignores changes inside debounce window and keeps last committed key (documented in Task 1 tests).
