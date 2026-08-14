# Broadcast Director + Enriched Telemetry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enrich `telemetry.tick`, add `telemetry.event` detection in the bridge/mock, and drive a hybrid auto/manual broadcast director in the HTML overlay without covering center gameplay.

**Architecture:** Pure domain helpers (`domain_enrich.py`, `domain_events.py`) compute tick extras and events from tick deltas. Mock + iRacing adapters fill/emit CONTRACT messages. Overlay `broadcast.js` keeps a base layer + moment layer state machine gated by `broadcastDirector` and existing widget allow-list toggles.

**Tech Stack:** Python 3 (stdlib + existing `websockets`/`pyirsdk`), Browser Source HTML/CSS/JS, pytest, OBS pack conventions from `AGENTS.md`.

## Global Constraints

- Canvas / overlays **1920×1080**; never cover center FOV (`docs/DESIGN_SYSTEM.md`).
- Brand tokens: green `#00C400`, blue `#009FE5`, bg `#080A0C` (Marcato pack keeps carbon/steel — no PiGreco green forced onto Marcato theme tokens beyond shared `broadcast.css` variables already used).
- `schemaVersion` stays **1**; all new fields/events are additive/optional.
- Overlay reads CONTRACT only — no sim SDK from Browser Source JS.
- Config keys synced to `overlays/config.example.js`, both `config.values.json`, `config-panel.html`.
- Conventional Commits; one commit per task; Windows-first; do not reverse ADR-005.
- Claim roadmap **P3-06** (new) under Phase 3 — do not expand into P3-03/P3-04.
- Spec: `docs/superpowers/specs/2026-08-14-broadcast-director-enrichment-design.md`.

## File map

| Path | Responsibility |
|------|----------------|
| `adapters/telemetry/domain_enrich.py` | Pure: `delta_best_ms`, `apply_pos_change`, `SENSITIVITY` constants shared with events |
| `adapters/telemetry/domain_events.py` | Pure: `EventDetector` → list of event dicts from consecutive ticks |
| `adapters/telemetry/mock_server.py` | Fill enrich fields; run detector; broadcast events |
| `adapters/telemetry/iracing_bridge.py` | Same + SDK fields (`inPit`, temps, iRating when available) |
| `adapters/telemetry/CONTRACT.md` | Document enrich + `telemetry.event` |
| `overlays/broadcast.js` | Director SM + moment layer + enriched focus/LB UI |
| `overlays/assets/broadcast.css` | Moment chip/banner keyframes |
| `overlays/broadcast-chrome.html` + `overlays-marcato/broadcast-chrome.html` | Moment mount node |
| `overlays/config.example.js`, `*/config.values.json`, `config-panel.html` | `broadcastDirector`, `broadcastDirectorSensitivity` |
| `tests/test_telemetry_enrich.py` | Enrich helpers |
| `tests/test_telemetry_events.py` | Event detector |
| `docs/TELEMETRY_BROADCAST.md` | Operator guide |
| `docs/ROADMAP.md` | P3-06 claim → done at end |

---

### Task 1: Claim P3-06 + enrich domain helpers (TDD)

**Files:**
- Modify: `docs/ROADMAP.md` (add P3-06 `in_progress`)
- Create: `adapters/telemetry/domain_enrich.py`
- Create: `tests/test_telemetry_enrich.py`

**Interfaces:**
- Produces:
  - `delta_best_ms(last_lap_ms: float | None, best_lap_ms: float | None) -> int | None`
  - `apply_pos_change(standings: list[dict], prev_pos_by_car: dict[Any, int] | None) -> tuple[list[dict], dict[Any, int]]` — mutates copies with `posChange` ∈ {-1,0,1,null}; returns (rows, new_map)
  - `SENSITIVITY: dict[str, dict]` with keys `calm|normal|hype` each having `battle_ms: int`, `battle_ticks: int`, `debounce_ms: int`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_telemetry_enrich.py
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "adapters" / "telemetry"))

from domain_enrich import SENSITIVITY, apply_pos_change, delta_best_ms


def test_delta_best_ms():
    assert delta_best_ms(90100, 90000) == 100
    assert delta_best_ms(89900, 90000) == -100
    assert delta_best_ms(None, 90000) is None
    assert delta_best_ms(90000, None) is None


def test_apply_pos_change_gain_and_loss():
    prev = {1: 3, 2: 1}
    rows = [
        {"carIdx": 1, "pos": 2},
        {"carIdx": 2, "pos": 1},
    ]
    out, new_map = apply_pos_change(rows, prev)
    assert out[0]["posChange"] == 1   # 3 → 2 improved
    assert out[1]["posChange"] == 0   # still P1
    assert new_map[1] == 2


def test_sensitivity_keys():
    assert set(SENSITIVITY) == {"calm", "normal", "hype"}
    assert SENSITIVITY["normal"]["battle_ms"] == 1200
    assert SENSITIVITY["calm"]["battle_ms"] > SENSITIVITY["normal"]["battle_ms"]
    assert SENSITIVITY["hype"]["battle_ms"] < SENSITIVITY["normal"]["battle_ms"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_telemetry_enrich.py -v`  
Expected: FAIL (`ModuleNotFoundError: domain_enrich`)

- [ ] **Step 3: Implement `domain_enrich.py`**

```python
"""Pure tick enrichment helpers (no IO)."""
from __future__ import annotations
from typing import Any

SENSITIVITY: dict[str, dict[str, int]] = {
    "calm": {"battle_ms": 1800, "battle_ticks": 8, "debounce_ms": 4000},
    "normal": {"battle_ms": 1200, "battle_ticks": 5, "debounce_ms": 3000},
    "hype": {"battle_ms": 800, "battle_ticks": 3, "debounce_ms": 2000},
}


def delta_best_ms(last_lap_ms: float | None, best_lap_ms: float | None) -> int | None:
    if last_lap_ms is None or best_lap_ms is None:
        return None
    try:
        return int(round(float(last_lap_ms) - float(best_lap_ms)))
    except (TypeError, ValueError):
        return None


def apply_pos_change(
    standings: list[dict[str, Any]],
    prev_pos_by_car: dict[Any, int] | None,
) -> tuple[list[dict[str, Any]], dict[Any, int]]:
    prev = prev_pos_by_car or {}
    out: list[dict[str, Any]] = []
    new_map: dict[Any, int] = {}
    for row in standings:
        r = dict(row)
        key = r.get("carIdx")
        if key is None:
            key = r.get("carNumber")
        pos = r.get("pos")
        change = None
        if key is not None and isinstance(pos, (int, float)):
            pos_i = int(pos)
            new_map[key] = pos_i
            if key in prev:
                delta = prev[key] - pos_i  # positive = gained places
                if delta > 0:
                    change = 1
                elif delta < 0:
                    change = -1
                else:
                    change = 0
        r["posChange"] = change
        out.append(r)
    return out, new_map
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `python -m pytest tests/test_telemetry_enrich.py -v`

- [ ] **Step 5: Claim roadmap ID**

In `docs/ROADMAP.md` Phase 3 table add:

```markdown
| P3-06 | Broadcast director + tick enrichment | in_progress | spec 2026-08-14; hybrid auto/manual moments |
```

Update suggested claims to mention P3-06.

- [ ] **Step 6: Commit**

```bash
git add adapters/telemetry/domain_enrich.py tests/test_telemetry_enrich.py docs/ROADMAP.md
git commit -m "$(cat <<'EOF'
feat(telemetry): add enrich helpers and claim P3-06

EOF
)"
```

---

### Task 2: Wire enrich fields into mock + standings rows

**Files:**
- Modify: `adapters/telemetry/domain_standings.py` (`mock_standings` add `inPit: False`, optional `iRating`)
- Modify: `adapters/telemetry/mock_server.py` (`build_tick` + module-level prev map)
- Modify: `adapters/telemetry/CONTRACT.md`
- Modify: `tests/test_telemetry_broadcast.py`

**Interfaces:**
- Consumes: `delta_best_ms`, `apply_pos_change`
- Produces: tick fields `deltaBestMs`, `inPit`, `iRating`, `airTempC`, `trackTempC`, `sof`; standings rows may include `posChange`, `inPit`, `iRating`

- [ ] **Step 1: Extend failing assertion in existing test**

Add to `tests/test_telemetry_broadcast.py`:

```python
def test_build_tick_enrichment_fields():
    tick = build_tick(5.0)
    assert "deltaBestMs" in tick
    assert tick["deltaBestMs"] == tick["lastLapMs"] - tick["bestLapMs"]
    assert isinstance(tick.get("inPit"), bool)
    assert tick["standings"][0].get("posChange") in (-1, 0, 1, None)
    # second call should populate posChange from prev
    tick2 = build_tick(6.0)
    assert any(r.get("posChange") is not None for r in tick2["standings"])
```

- [ ] **Step 2: Run — expect FAIL** on missing keys

Run: `python -m pytest tests/test_telemetry_broadcast.py::test_build_tick_enrichment_fields -v`

- [ ] **Step 3: Update `mock_server.build_tick`**

Keep a module-level `_prev_pos_by_car: dict = {}`.

After building `standings` from `mock_standings`:

```python
from domain_enrich import apply_pos_change, delta_best_ms

# inside build_tick, after standings = mock_standings(...):
global _prev_pos_by_car
standings, _prev_pos_by_car = apply_pos_change(standings, _prev_pos_by_car)
# force a brief battle / pos flip already exists via wave — optional:
# at elapsed_s windows where position flips 3↔4, posChange will appear

# add to _envelope(...):
deltaBestMs=delta_best_ms(last_lap, best_lap),
inPit=False,
iRating=1850,
airTempC=24.0,
trackTempC=32.0,
sof=2100,
```

Also set each mock standings row `inPit=False`, `iRating=1700 + pos * 10` inside `mock_standings`.

- [ ] **Step 4: Document in CONTRACT.md** under optional broadcast fields (new subsection “P3-06 enrichment”) matching the design spec tables + note consumers ignore unknowns.

- [ ] **Step 5: Run full broadcast tests**

Run: `python -m pytest tests/test_telemetry_broadcast.py tests/test_telemetry_enrich.py -v`  
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add adapters/telemetry/domain_standings.py adapters/telemetry/mock_server.py adapters/telemetry/CONTRACT.md tests/test_telemetry_broadcast.py
git commit -m "$(cat <<'EOF'
feat(telemetry): enrich mock ticks with delta and posChange

EOF
)"
```

---

### Task 3: Enrich iRacing bridge ticks

**Files:**
- Modify: `adapters/telemetry/iracing_bridge.py`

**Interfaces:**
- Consumes: `delta_best_ms`, `apply_pos_change`
- Produces: same enrich fields; `inPit` from `OnPitRoad` / `CarIdxOnPitRoad[focus]`; temps from `AirTemp`/`TrackTemp` when present; `iRating` from DriverInfo when present

- [ ] **Step 1: Add module state + imports**

```python
from domain_enrich import apply_pos_change, delta_best_ms

_prev_pos_by_car: dict = {}
```

- [ ] **Step 2: After `standings_from_cars(...)`**

```python
global _prev_pos_by_car
standings, _prev_pos_by_car = apply_pos_change(standings, _prev_pos_by_car)
```

Also, when building each car dict, set `inPit` from `CarIdxOnPitRoad` if available, and pass through onto standing rows (extend `standings_from_cars` **or** post-process rows by carIdx map — prefer post-process to avoid widening `standings_from_cars` signature):

```python
pit_by_idx = {}  # filled while scanning cars
for r in standings:
    idx = r.get("carIdx")
    if idx in pit_by_idx:
        r["inPit"] = pit_by_idx[idx]
```

- [ ] **Step 3: Add focus enrich fields on `_envelope` return**

```python
last_ms = focus_row.get("lastLapMs") if focus_row else None
best_ms = focus_row.get("bestLapMs") if focus_row else None
# ...
deltaBestMs=delta_best_ms(last_ms, best_ms),
inPit=pit_by_idx.get(focus_idx),
iRating=focus_info.get("iRating"),  # parse from DriverInfo when building drivers map
airTempC=_num_or_none(_safe_get(ir, "AirTemp", None)),
trackTempC=_num_or_none(_safe_get(ir, "TrackTemp", None) or _safe_get(ir, "TrackTempCrew", None)),
sof=None,  # leave null unless WeekendInfo Sof clearly available
```

Add small helper:

```python
def _num_or_none(v: Any) -> float | None:
    try:
        if v is None:
            return None
        return float(v)
    except (TypeError, ValueError):
        return None
```

When parsing DriverInfo drivers, if `IRating` / `IRating` key exists, store as int on `drivers[idx]["iRating"]`.

- [ ] **Step 4: Manual smoke (optional if sim open)** — else rely on unit tests from Task 2.

Run: `python -m pytest tests/test_telemetry_broadcast.py tests/test_telemetry_enrich.py -v`

- [ ] **Step 5: Commit**

```bash
git add adapters/telemetry/iracing_bridge.py
git commit -m "$(cat <<'EOF'
feat(telemetry): enrich iRacing bridge ticks for P3-06

EOF
)"
```

---

### Task 4: Overlay surfaces for enrich fields (E1 UI)

**Files:**
- Modify: `overlays/broadcast.js`
- Modify: `overlays/assets/broadcast.css`
- Modify: `overlays/broadcast-chrome.html` (no structural change required if focus HTML is built in JS)
- Modify: `overlays-marcato/broadcast-chrome.html` only if it duplicates focus markup (it shares `../overlays/broadcast.js`)

**Interfaces:**
- Consumes: tick `deltaBestMs`, `fuelPct`, `speedKph`, `inPit`; row `posChange`

- [ ] **Step 1: Extend focus meta in `render()`**

After existing LAST/BEST/GAP spans, append:

```javascript
(tick.deltaBestMs != null
  ? "<span>Δ BEST <strong class=\"" +
    (Number(tick.deltaBestMs) <= 0 ? "is-purple" : "is-slow") +
    "\">" +
    fmtMs(tick.deltaBestMs) +
    "</strong></span>"
  : "") +
(tick.fuelPct != null
  ? "<span>FUEL <strong>" + Number(tick.fuelPct).toFixed(0) + "%</strong></span>"
  : "") +
(tick.inPit
  ? "<span class=\"bc-pit-tag\">PIT</span>"
  : "")
```

- [ ] **Step 2: Standings row posChange marker**

In LB row HTML, after pos:

```javascript
(r.posChange === 1
  ? '<span class="bc-pos-up" aria-label="gained">▲</span>'
  : r.posChange === -1
    ? '<span class="bc-pos-down" aria-label="lost">▼</span>'
    : "")
```

Use text triangles (not emoji storms); style with brand green/red.

- [ ] **Step 3: CSS**

```css
.bc-focus-meta .is-purple { color: #c084fc; } /* lap improvement only; not UI chrome glow */
.bc-focus-meta .is-slow { color: var(--muted, #9aa3ad); }
.bc-pit-tag {
  color: #080a0c;
  background: #009fe5;
  font-size: 11px;
  font-weight: 700;
  padding: 2px 6px;
  letter-spacing: 0.06em;
}
.bc-pos-up { color: #00c400; font-size: 10px; margin-left: 2px; }
.bc-pos-down { color: #e5484d; font-size: 10px; margin-left: 2px; }
```

Note: `#c084fc` is only for Δ-best improvement signal (motorsport “purple”), not ambient glow stacks.

- [ ] **Step 4: Smoke**

Run mock: `python adapters/telemetry/mock_server.py`  
Open `http://127.0.0.1:8766/o/marcato/broadcast-chrome.html` (config server + telemetryEnabled). Confirm Δ BEST / FUEL / ▲▼ appear.

- [ ] **Step 5: Commit**

```bash
git add overlays/broadcast.js overlays/assets/broadcast.css
git commit -m "$(cat <<'EOF'
feat(overlay): show delta, fuel, and posChange on broadcast chrome

EOF
)"
```

---

### Task 5: `EventDetector` domain (TDD) — E2 core

**Files:**
- Create: `adapters/telemetry/domain_events.py`
- Create: `tests/test_telemetry_events.py`

**Interfaces:**
- Produces:
  - `PRIORITIES = {"flag_change": 100, "session_end": 90, "overtake": 80, "battle": 60, "fast_lap": 50, "pit": 40}`
  - `DEFAULT_TTL_MS = 4000`
  - `class EventDetector:`
    - `__init__(self, *, sensitivity: str = "normal")`
    - `set_sensitivity(self, name: str) -> None`
    - `feed(self, tick: dict, *, now_ms: int | None = None) -> list[dict]`
  - Each event: `{type:"telemetry.event", schemaVersion:1, ts, eventId, kind, priority, ttlMs, payload}`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_telemetry_events.py
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "adapters" / "telemetry"))

from domain_events import EventDetector, PRIORITIES


def _tick(**kw):
    base = {
        "type": "telemetry.tick",
        "schemaVersion": 1,
        "ts": 1_000_000,
        "flag": "green",
        "position": 4,
        "gapAheadMs": 2500,
        "gapBehindMs": 2500,
        "lastLapMs": 91000,
        "bestLapMs": 90000,
        "inPit": False,
        "focusCarNumber": "42",
    }
    base.update(kw)
    return base


def test_flag_change_emits_once():
    d = EventDetector(sensitivity="normal")
    assert d.feed(_tick(flag="green", ts=1)) == []
    ev = d.feed(_tick(flag="yellow", ts=2))
    assert len(ev) == 1
    assert ev[0]["kind"] == "flag_change"
    assert ev[0]["priority"] == PRIORITIES["flag_change"]
    assert ev[0]["payload"]["flag"] == "yellow"
    assert ev[0]["payload"]["prev"] == "green"
    assert d.feed(_tick(flag="yellow", ts=3)) == []


def test_battle_requires_streak():
    d = EventDetector(sensitivity="hype")  # battle_ticks=3
    assert d.feed(_tick(gapAheadMs=500, ts=10)) == []
    assert d.feed(_tick(gapAheadMs=500, ts=11)) == []
    ev = d.feed(_tick(gapAheadMs=500, ts=12))
    assert any(e["kind"] == "battle" for e in ev)


def test_overtake_on_position_improve():
    d = EventDetector()
    d.feed(_tick(position=5, ts=20))
    ev = d.feed(_tick(position=4, ts=21))
    assert any(e["kind"] == "overtake" and e["payload"]["fromPos"] == 5 for e in ev)


def test_fast_lap_when_last_le_best():
    d = EventDetector()
    d.feed(_tick(lastLapMs=91000, bestLapMs=90000, ts=30))
    ev = d.feed(_tick(lastLapMs=89900, bestLapMs=89900, ts=31))
    assert any(e["kind"] == "fast_lap" for e in ev)


def test_debounce_suppresses_repeat_battle():
    d = EventDetector(sensitivity="hype")
    for t in range(3):
        d.feed(_tick(gapAheadMs=400, ts=100 + t))
    # first battle likely at ts=102; immediate re-feed should debounce
    more = []
    for t in range(3, 6):
        more.extend(d.feed(_tick(gapAheadMs=400, ts=100 + t)))
    assert not any(e["kind"] == "battle" for e in more)
```

- [ ] **Step 2: Run — expect FAIL**

Run: `python -m pytest tests/test_telemetry_events.py -v`

- [ ] **Step 3: Implement `domain_events.py`**

```python
"""Pure telemetry.event detection from consecutive ticks (no IO)."""
from __future__ import annotations

from typing import Any

from domain_enrich import SENSITIVITY

PRIORITIES = {
    "flag_change": 100,
    "session_end": 90,
    "overtake": 80,
    "battle": 60,
    "fast_lap": 50,
    "pit": 40,
}
DEFAULT_TTL_MS = 4000


class EventDetector:
    def __init__(self, *, sensitivity: str = "normal") -> None:
        self.set_sensitivity(sensitivity)
        self._prev: dict[str, Any] | None = None
        self._battle_streak = 0
        self._last_emit_ms: dict[str, int] = {}
        self._seq = 0

    def set_sensitivity(self, name: str) -> None:
        key = name if name in SENSITIVITY else "normal"
        self._sens_name = key
        self._cfg = SENSITIVITY[key]

    def feed(self, tick: dict[str, Any], *, now_ms: int | None = None) -> list[dict[str, Any]]:
        ts = int(now_ms if now_ms is not None else tick.get("ts") or 0)
        out: list[dict[str, Any]] = []
        prev = self._prev

        if prev is not None:
            out.extend(self._detect(prev, tick, ts))

        self._prev = dict(tick)
        return out

    def _debounced(self, kind: str, ts: int) -> bool:
        last = self._last_emit_ms.get(kind)
        if last is not None and (ts - last) < self._cfg["debounce_ms"]:
            return True
        return False

    def _emit(self, kind: str, ts: int, payload: dict[str, Any]) -> dict[str, Any] | None:
        if self._debounced(kind, ts):
            return None
        self._last_emit_ms[kind] = ts
        self._seq += 1
        return {
            "type": "telemetry.event",
            "schemaVersion": 1,
            "ts": ts,
            "eventId": f"evt-{self._seq}",
            "kind": kind,
            "priority": PRIORITIES[kind],
            "ttlMs": DEFAULT_TTL_MS,
            "payload": payload,
        }

    def _detect(self, prev: dict[str, Any], tick: dict[str, Any], ts: int) -> list[dict[str, Any]]:
        found: list[dict[str, Any]] = []
        pf = (prev.get("flag") or "none").lower()
        cf = (tick.get("flag") or "none").lower()
        if cf != pf:
            e = self._emit("flag_change", ts, {"flag": cf, "prev": pf})
            if e:
                found.append(e)
            if cf in ("checkered", "white"):
                e2 = self._emit("session_end", ts, {"flag": cf})
                if e2:
                    found.append(e2)

        # battle streak
        thr = self._cfg["battle_ms"]
        ga = tick.get("gapAheadMs")
        gb = tick.get("gapBehindMs")
        close = False
        gap_val = None
        if isinstance(ga, (int, float)) and 0 < ga <= thr:
            close, gap_val = True, int(ga)
        if isinstance(gb, (int, float)) and 0 < gb <= thr:
            if gap_val is None or gb < gap_val:
                close, gap_val = True, int(gb)
        if close:
            self._battle_streak += 1
        else:
            self._battle_streak = 0
        if self._battle_streak >= self._cfg["battle_ticks"]:
            e = self._emit(
                "battle",
                ts,
                {"gapMs": gap_val, "withCarNumber": None},
            )
            if e:
                found.append(e)
                self._battle_streak = 0

        pp, cp = prev.get("position"), tick.get("position")
        if isinstance(pp, (int, float)) and isinstance(cp, (int, float)) and int(cp) < int(pp):
            e = self._emit(
                "overtake",
                ts,
                {"fromPos": int(pp), "toPos": int(cp)},
            )
            if e:
                found.append(e)

        pl, pb = prev.get("lastLapMs"), prev.get("bestLapMs")
        cl, cb = tick.get("lastLapMs"), tick.get("bestLapMs")
        if (
            isinstance(cl, (int, float))
            and isinstance(cb, (int, float))
            and cl <= cb
            and (pl != cl or pb != cb)
        ):
            e = self._emit("fast_lap", ts, {"lapMs": int(cl)})
            if e:
                found.append(e)

        # pit enter/exit — implemented fully in Task 8; stub hook OK if tests don't cover yet
        return found
```

Adjust tests if debounce timing needs `now_ms` far apart for multi-kind cases.

- [ ] **Step 4: Run — expect PASS**

Run: `python -m pytest tests/test_telemetry_events.py -v`

- [ ] **Step 5: Commit**

```bash
git add adapters/telemetry/domain_events.py tests/test_telemetry_events.py
git commit -m "$(cat <<'EOF'
feat(telemetry): add EventDetector for broadcast moments

EOF
)"
```

---

### Task 6: Emit events from mock + bridge (+ CONTRACT)

**Files:**
- Modify: `adapters/telemetry/mock_server.py`
- Modify: `adapters/telemetry/iracing_bridge.py`
- Modify: `adapters/telemetry/CONTRACT.md`
- Modify: `tests/test_telemetry_events.py` (optional integration: feed two `build_tick` samples)

**Interfaces:**
- Produces: WS clients receive `telemetry.event` JSON frames interleaved with ticks
- CLI optional: `--sensitivity normal` (default)

- [ ] **Step 1: Mock WS loop**

Module-level `detector = EventDetector(sensitivity="normal")`.

In `_run_ws_loop` after building `tick`:

```python
events = detector.feed(tick)
# send tick first, then each event
for ws in list(clients):
    await ws.send(payload)  # tick
    for ev in events:
        await ws.send(json.dumps(ev, separators=(",", ":")))
```

Mirror for file mode: write only latest tick to file (events are WS-only; document that).

Add argparse `--sensitivity` choices calm|normal|hype.

Log at INFO when an event is emitted: `log.info("event kind=%s id=%s", ev["kind"], ev["eventId"])`.

- [ ] **Step 2: iRacing bridge same pattern** in the main loop after `tick = build_tick_from_ir(ir)`.

- [ ] **Step 3: CONTRACT.md** — add full `telemetry.event` section from the design spec (fields + kinds table).

- [ ] **Step 4: Test**

```python
def test_mock_tick_sequence_can_yield_flag_event():
    from domain_events import EventDetector
    from mock_server import build_tick
    d = EventDetector(sensitivity="normal")
    # find yellow window: int(elapsed) % 47 in (12,13,14)
    d.feed(build_tick(11.0))
    ev = d.feed(build_tick(12.0))
    assert any(e["kind"] == "flag_change" for e in ev)
```

Run: `python -m pytest tests/test_telemetry_events.py -v`

- [ ] **Step 5: Commit**

```bash
git add adapters/telemetry/mock_server.py adapters/telemetry/iracing_bridge.py adapters/telemetry/CONTRACT.md tests/test_telemetry_events.py
git commit -m "$(cat <<'EOF'
feat(telemetry): broadcast telemetry.event from mock and bridge

EOF
)"
```

---

### Task 7: Overlay director state machine + animations (E2 UI)

**Files:**
- Modify: `overlays/broadcast-chrome.html` — add `<div class="bc-moment" data-bc-moment hidden></div>`
- Modify: `overlays-marcato/broadcast-chrome.html` — same node
- Modify: `overlays/broadcast.js`
- Modify: `overlays/assets/broadcast.css`
- Modify: `overlays/config.example.js`, `overlays/config.values.json`, `overlays-marcato/config.values.json`, `overlays/config-panel.html`
- Regenerate configs via existing `python tools/write_config_js.py` (both roots if needed)

**Interfaces:**
- Config: `broadcastDirector: "auto"|"manual"|"off"` (default `"auto"`), `broadcastDirectorSensitivity: "calm"|"normal"|"hype"` (default `"normal"` — client-side only for future; detection already on bridge; overlay uses mode for UI policy)
- Produces: moment layer shows one hero at a time; queue max 2

- [ ] **Step 1: Config keys**

In `config.example.js`:

```js
broadcastDirector: "auto",
broadcastDirectorSensitivity: "normal",
```

Same defaults in both `config.values.json`. Panel: select inputs for director + sensitivity; add names to checkbox/select lists in `config-panel.html` (`BOOL` vs select — use `<select name="broadcastDirector">` and `<select name="broadcastDirectorSensitivity">`; extend `fill`/`readForm` to handle selects).

- [ ] **Step 2: HTML moment mount**

```html
<div class="bc-moment" data-bc-moment hidden aria-live="polite"></div>
```

Place after flag banner, before status.

- [ ] **Step 3: Director logic in `broadcast.js`**

```javascript
const director = cfg.broadcastDirector || "auto"; // auto|manual|off
const elMoment = root.querySelector("[data-bc-moment]");
let hero = null; // {kind, priority, until, payload}
let queue = [];

function enqueueEvent(ev) {
  if (director !== "auto") return;
  if (!ev || !ev.kind) return;
  const item = {
    kind: ev.kind,
    priority: Number(ev.priority) || 0,
    ttlMs: Number(ev.ttlMs) || 4000,
    payload: ev.payload || {},
  };
  if (hero && item.priority <= hero.priority) {
    if (queue.length < 2) queue.push(item);
    queue.sort(function (a, b) { return b.priority - a.priority; });
    return;
  }
  if (hero && item.priority > hero.priority) {
    queue.unshift(hero);
    if (queue.length > 2) queue.length = 2;
  }
  showHero(item);
}

function showHero(item) {
  hero = item;
  hero.until = Date.now() + item.ttlMs;
  if (!elMoment) return;
  elMoment.hidden = false;
  elMoment.dataset.kind = item.kind;
  elMoment.classList.remove("is-exit");
  elMoment.classList.add("is-enter");
  var label = item.kind.replace("_", " ").toUpperCase();
  if (item.kind === "flag_change") label = String(item.payload.flag || "").toUpperCase();
  if (item.kind === "overtake") label = "OVERTAKE P" + (item.payload.toPos || "");
  if (item.kind === "fast_lap") label = "FASTEST";
  if (item.kind === "battle") label = "BATTLE";
  if (item.kind === "pit") label = "PIT " + String(item.payload.state || "").toUpperCase();
  if (item.kind === "session_end") label = String(item.payload.flag || "FINISH").toUpperCase();
  elMoment.innerHTML = '<div class="bc-moment-chip">' + label + "</div>";
}

function tickHero() {
  if (!hero) return;
  if (Date.now() < hero.until) return;
  if (elMoment) {
    elMoment.classList.remove("is-enter");
    elMoment.classList.add("is-exit");
  }
  hero = null;
  window.setTimeout(function () {
    if (queue.length) showHero(queue.shift());
    else if (elMoment) {
      elMoment.hidden = true;
      elMoment.innerHTML = "";
    }
  }, 200);
}
window.setInterval(tickHero, 100);
```

In message handler:

```javascript
if (msg.type === "telemetry.tick") {
  render(msg);
} else if (msg.type === "telemetry.event") {
  enqueueEvent(msg);
}
```

**Director policy for base widgets (auto):** keep current toggle allow-list (`no-leaderboard` etc.). Do not auto-hide session/focus in v1 (spec: preferred on). `manual`: ignore events. `off`: ignore events (same as manual for moments).

When `director === "off" || director === "manual"`, leave existing flag banner behavior as today (tick-driven). When `auto`, prefer event-driven flag_change for banner pulse; still update session strip from ticks.

- [ ] **Step 4: CSS motion**

```css
.bc-moment {
  position: absolute;
  left: 50%;
  top: 120px;
  transform: translate(-50%, -8px);
  z-index: 40;
  pointer-events: none;
  opacity: 0;
}
.bc-moment.is-enter {
  animation: bcMomentIn 300ms ease-out forwards;
}
.bc-moment.is-exit {
  animation: bcMomentOut 200ms ease-in forwards;
}
.bc-moment-chip {
  font-family: inherit;
  font-weight: 800;
  letter-spacing: 0.12em;
  font-size: 28px;
  padding: 10px 22px;
  background: rgba(8, 10, 12, 0.88);
  border: 2px solid #00c400;
  color: #fff;
}
.bc-moment[data-kind="flag_change"] .bc-moment-chip { border-color: #f5d90a; }
.bc-moment[data-kind="overtake"] .bc-moment-chip { border-color: #00c400; }
.bc-moment[data-kind="fast_lap"] .bc-moment-chip { border-color: #c084fc; }
@keyframes bcMomentIn {
  from { opacity: 0; transform: translate(-50%, -16px); }
  to { opacity: 1; transform: translate(-50%, 0); }
}
@keyframes bcMomentOut {
  from { opacity: 1; }
  to { opacity: 0; }
}
```

Keep chip **above** session strip / below top edge — not center FOV.

- [ ] **Step 5: Regenerate config.js**

```powershell
python tools/write_config_js.py
python tools/write_config_js.py --overlay-root overlays-marcato
```

(Use whatever CLI the tool actually exposes — if only `overlay_root=` kw in Python, call accordingly.)

- [ ] **Step 6: Smoke**

1. `broadcastDirector: auto`, mock running  
2. Wait for yellow window (~12s) → moment chip + existing banner  
3. Set `manual` → refresh → no chips on flag change  

- [ ] **Step 7: Commit**

```bash
git add overlays/broadcast.js overlays/assets/broadcast.css overlays/broadcast-chrome.html overlays-marcato/broadcast-chrome.html overlays/config.example.js overlays/config.values.json overlays-marcato/config.values.json overlays/config.js overlays-marcato/config.js overlays/config-panel.html
git commit -m "$(cat <<'EOF'
feat(overlay): add auto broadcast director moment layer

EOF
)"
```

---

### Task 8: Pit + session_end polish (E3)

**Files:**
- Modify: `adapters/telemetry/domain_events.py` (pit enter/exit)
- Modify: `tests/test_telemetry_events.py`
- Modify: `overlays/broadcast.js` / `broadcast.css` if session_end needs stronger banner
- Modify: `docs/TELEMETRY_BROADCAST.md`
- Modify: `docs/ROADMAP.md` → P3-06 `done`

- [ ] **Step 1: Tests for pit**

```python
def test_pit_enter_exit():
    d = EventDetector()
    d.feed(_tick(inPit=False, ts=50))
    ev = d.feed(_tick(inPit=True, ts=51))
    assert any(e["kind"] == "pit" and e["payload"]["state"] == "enter" for e in ev)
    ev2 = d.feed(_tick(inPit=False, ts=52 + 5000))  # past debounce if needed
    # use now_ms to bypass debounce:
    ev2 = d.feed(_tick(inPit=False, ts=60), now_ms=60_000)
    assert any(e["kind"] == "pit" and e["payload"]["state"] == "exit" for e in ev2)
```

- [ ] **Step 2: Implement in `_detect`**

```python
ppit = bool(prev.get("inPit"))
cpit = bool(tick.get("inPit"))
if cpit and not ppit:
    e = self._emit("pit", ts, {"state": "enter"})
    if e:
        found.append(e)
elif ppit and not cpit:
    e = self._emit("pit", ts, {"state": "exit"})
    if e:
        found.append(e)
```

Ensure mock occasionally sets `inPit=True` for a few seconds (e.g. `int(elapsed_s) % 80 in range(40, 45)`).

- [ ] **Step 3: Docs**

Update `docs/TELEMETRY_BROADCAST.md`:

- Director modes table  
- New config keys  
- Note events are WS-only  
- Smoke checklist for auto vs manual  

- [ ] **Step 4: Mark P3-06 done in ROADMAP**

- [ ] **Step 5: Full test suite**

Run: `python -m pytest tests/test_telemetry_enrich.py tests/test_telemetry_events.py tests/test_telemetry_broadcast.py -v`  
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add adapters/telemetry/domain_events.py adapters/telemetry/mock_server.py tests/test_telemetry_events.py docs/TELEMETRY_BROADCAST.md docs/ROADMAP.md overlays/broadcast.js overlays/assets/broadcast.css
git commit -m "$(cat <<'EOF'
feat(telemetry): pit events and finish P3-06 broadcast director

EOF
)"
```

---

## Spec coverage checklist

| Spec item | Task |
|-----------|------|
| Enrich tick fields | 1–3 |
| Overlay delta/fuel/posChange | 4 |
| `telemetry.event` + detector | 5–6 |
| Director auto/manual/off + animations | 7 |
| Pit / session_end + docs | 8 |
| Mock scripted moments | 2, 6, 8 |
| Unit tests without SDK | 1, 5 |
| Config sync | 7 |
| Non-goals (map/cameras/IBT) | not scheduled |

## Placeholder / consistency notes

- Sensitivity for **detection** lives in the bridge/mock (`--sensitivity`); overlay config `broadcastDirectorSensitivity` is stored for future client-side filters — v1 may log it only; do not dual-detect in JS.
- Purple `#c084fc` only for Δ-best / fastest chip accent, not ambient glow.
- File mode does not persist events (documented).
