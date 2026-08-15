# Marcato Cam + Flag Strip + Battle Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix Marcato PiP camera device IDs, add a FIELD-like top flag strip (10s for checkered/white/debris), and gate the battle panel by session (race from lap 1, practice with others, never quali).

**Architecture:** Refresh DirectShow IDs in `generate_pack.py` and regenerate Marcato OBS JSON. Correct iRacing `SessionFlags` bits and emit `battleEligible` from a pure domain helper via the bridge. Replace the thin flag banner + flag moment chips with a top strip choreographed like the field ticker in shared `overlays/broadcast.js` / `broadcast.css` (Marcato already loads these).

**Tech Stack:** Python 3 (pytest, iracing bridge, generate_pack), OBS scene JSON, Browser Source HTML/CSS/JS overlays.

## Global Constraints

- Canvas / overlays target **1920×1080** (Rec 2K nests scale from 1080 design space).
- Brand tokens remain pack-specific; Marcato chrome uses shared `../overlays/broadcast.*`.
- Extend OBS layouts via `tools/generate_pack.py`, not fragile hand JSON.
- Sync new config keys to `overlays/config.example.js` (and Marcato `config.values.json` / example if present).
- Conventional Commits; local git only unless asked to push.
- Close OBS before rewriting scene collection JSON when regenerating.
- Spec: `docs/superpowers/specs/2026-08-15-marcato-cam-flag-battle-design.md`.
- Roadmap ID: **P3-12** (claim `in_progress` then `done`); note P1-04 cam ID follow-up.

---

## File map

| File | Responsibility |
|------|----------------|
| `tools/generate_pack.py` | `STREAMCAM_ID` / `USBCAM_ID` constants |
| `obs/S_Marcato_42.json`, `S_Marcato_Replay.json`, `S_Marcato_Rec_2K.json` | Regenerated collections |
| `adapters/telemetry/domain_battle.py` | Pure `battle_panel_eligible(...)` |
| `adapters/telemetry/iracing_bridge.py` | Flag bits, `debris`, `battleEligible` on tick |
| `adapters/telemetry/mock_server.py` | Emit `battleEligible` + `debris` in mock ticks when useful |
| `adapters/telemetry/CONTRACT.md` | Document `debris` + `battleEligible` |
| `overlays/broadcast-chrome.html` | Flag strip markup; remove/keep banner inert |
| `overlays-marcato/broadcast-chrome.html` | Same markup twin |
| `overlays/broadcast.js` | Strip controller; battle gate; stop flag banner/chips |
| `overlays/assets/broadcast.css` | Strip + debris styles |
| `overlays/config.example.js` | `broadcastFlagStripMs` |
| `docs/CAMERAS.md`, `docs/TELEMETRY_BROADCAST.md`, `docs/ROADMAP.md` | Docs |
| `tests/test_domain_battle.py` | Battle eligibility matrix |
| `tests/test_flag_bits.py` | `_flag_name` bit coverage |
| `tests/test_pack_cameras.py` | Device ID format assertions |

---

### Task 1: Claim roadmap + fix SessionFlags / debris

**Files:**
- Modify: `docs/ROADMAP.md`
- Modify: `adapters/telemetry/iracing_bridge.py` (flag constants + `_flag_name`)
- Modify: `adapters/telemetry/CONTRACT.md`
- Create: `tests/test_flag_bits.py`

**Interfaces:**
- Consumes: irsdk SessionFlags bit layout from spec
- Produces: `_flag_name(flags: int | None) -> str` returning `"debris"` for `0x40`; `"blue"` for `0x20`

- [ ] **Step 1: Claim P3-12 in ROADMAP**

Add under Phase 3:

```markdown
| P3-12 | Flag strip + battle session gate + cam ID refresh | in_progress | spec 2026-08-15-marcato-cam-flag-battle-design |
```

Update Suggested next agent claims if needed. Note on P1-04 row: `cam device ID refresh 2026-08-15`.

- [ ] **Step 2: Write failing flag-bit tests**

Create `tests/test_flag_bits.py`:

```python
"""SessionFlags → flag name mapping."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "adapters" / "telemetry"))

import iracing_bridge as br  # noqa: E402


def test_debris_is_0x40_not_blue():
    assert br._flag_name(0x00000040) == "debris"


def test_blue_is_0x20():
    assert br._flag_name(0x00000020) == "blue"


def test_black_and_meatball_bits():
    assert br._flag_name(0x00010000) == "black"
    assert br._flag_name(0x00100000) == "meatball"


def test_checkered_beats_debris():
    assert br._flag_name(0x00000001 | 0x00000040) == "checkered"


def test_white_flag():
    assert br._flag_name(0x00000002) == "white"
```

- [ ] **Step 3: Run tests — expect FAIL**

Run: `python -m pytest tests/test_flag_bits.py -v`

Expected: FAIL (`debris` currently maps as `blue`, black/meatball wrong).

- [ ] **Step 4: Fix flag constants and `_flag_name`**

In `adapters/telemetry/iracing_bridge.py` replace the SessionFlags subset with:

```python
_FLAG_CHECKERED = 0x00000001
_FLAG_WHITE = 0x00000002
_FLAG_GREEN = 0x00000004
_FLAG_YELLOW = 0x00000008
_FLAG_RED = 0x00000010
_FLAG_BLUE = 0x00000020
_FLAG_DEBRIS = 0x00000040
_FLAG_BLACK = 0x00010000
_FLAG_MEATBALL = 0x00100000
```

Update `_flag_name` priority:

```python
def _flag_name(session_flags: int | None) -> str:
    if not session_flags:
        return "none"
    f = int(session_flags)
    if f & _FLAG_CHECKERED:
        return "checkered"
    if f & _FLAG_RED:
        return "red"
    if f & _FLAG_YELLOW:
        return "yellow"
    if f & _FLAG_DEBRIS:
        return "debris"
    if f & _FLAG_WHITE:
        return "white"
    if f & _FLAG_BLUE:
        return "blue"
    if f & _FLAG_BLACK:
        return "black"
    if f & _FLAG_MEATBALL:
        return "meatball"
    if f & _FLAG_GREEN:
        return "green"
    return "none"
```

Update CONTRACT `flag` enum to include `debris`.

- [ ] **Step 5: Run tests — expect PASS**

Run: `python -m pytest tests/test_flag_bits.py -v`

Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add docs/ROADMAP.md adapters/telemetry/iracing_bridge.py adapters/telemetry/CONTRACT.md tests/test_flag_bits.py
git commit -m "fix(telemetry): correct SessionFlags bits and add debris"
```

---

### Task 2: Domain `battleEligible` + bridge field

**Files:**
- Create: `adapters/telemetry/domain_battle.py`
- Create: `tests/test_domain_battle.py`
- Modify: `adapters/telemetry/iracing_bridge.py` (emit `battleEligible` on tick)
- Modify: `adapters/telemetry/mock_server.py` (set `battleEligible` sensibly)
- Modify: `adapters/telemetry/CONTRACT.md`

**Interfaces:**
- Consumes: `race_live_order_ready` from `domain_grid`
- Produces:

```python
def battle_panel_eligible(
    session_kind: str,
    *,
    live_order_ready: bool,
    other_cars: int,
) -> bool:
    ...
```

- Tick field: `battleEligible: bool`

- [ ] **Step 1: Write failing domain tests**

Create `tests/test_domain_battle.py`:

```python
"""Battle panel session eligibility."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "adapters" / "telemetry"))

from domain_battle import battle_panel_eligible  # noqa: E402


def test_quali_always_off():
    assert battle_panel_eligible("quali", live_order_ready=True, other_cars=10) is False


def test_cooldown_unknown_off():
    assert battle_panel_eligible("cooldown", live_order_ready=True, other_cars=5) is False
    assert battle_panel_eligible("unknown", live_order_ready=True, other_cars=5) is False


def test_practice_requires_others():
    assert battle_panel_eligible("practice", live_order_ready=True, other_cars=0) is False
    assert battle_panel_eligible("practice", live_order_ready=True, other_cars=1) is True


def test_race_requires_live_order():
    assert battle_panel_eligible("race", live_order_ready=False, other_cars=20) is False
    assert battle_panel_eligible("race", live_order_ready=True, other_cars=20) is True
```

- [ ] **Step 2: Run — expect FAIL (import error)**

Run: `python -m pytest tests/test_domain_battle.py -v`

Expected: FAIL — `domain_battle` missing.

- [ ] **Step 3: Implement domain helper**

Create `adapters/telemetry/domain_battle.py`:

```python
"""Battle panel session gating (pure, no IO)."""

from __future__ import annotations


def battle_panel_eligible(
    session_kind: str,
    *,
    live_order_ready: bool,
    other_cars: int,
) -> bool:
    """Whether the broadcast battle pack may arm.

    - race: only after live order ready (formation / pace / pre-lap1 blocked)
    - practice: only when at least one other car is present
    - quali / cooldown / unknown: never
    """
    kind = (session_kind or "unknown").lower()
    if kind in ("quali", "cooldown", "unknown"):
        return False
    if kind == "practice":
        return int(other_cars) >= 1
    if kind == "race":
        return bool(live_order_ready)
    return False
```

- [ ] **Step 4: Run domain tests — expect PASS**

Run: `python -m pytest tests/test_domain_battle.py -v`

Expected: PASS.

- [ ] **Step 5: Wire bridge + mock + CONTRACT**

In `iracing_bridge.py` where the tick dict is built (near `session=session_kind`, after `live_order` / standings are known):

```python
from domain_battle import battle_panel_eligible

other_cars = max(0, len(standings_rows) - 1)  # or count cars with carIdx != focus
battle_eligible = battle_panel_eligible(
    session_kind,
    live_order_ready=(session_kind != "race") or bool(live_order),
    # For race, live_order True means race_live_order_ready already passed.
    # Prefer: live_order_ready=live_order if session_kind=="race" else True
    other_cars=other_cars,
)
```

Use this exact call shape:

```python
live_ready = True
if session_kind == "race":
    live_ready = bool(live_order)  # same flag already used for grid hold
battle_eligible = battle_panel_eligible(
    session_kind,
    live_order_ready=live_ready,
    other_cars=max(0, sum(1 for r in standings if r.get("carIdx") is not None) - 1),
)
```

Add `battleEligible=battle_eligible` to the tick envelope fields.

In `mock_server.py`, set `battleEligible` True for default race mock after lap>=1; False for early laps if mocked; for practice/quali scenarios if any.

CONTRACT: document under optional broadcast fields:

```markdown
| `battleEligible` | boolean | When false, battle pack must not arm (formation / quali / solo practice) |
```

And add `debris` to the `flag` enum line if not done in Task 1.

- [ ] **Step 6: Run related tests**

Run: `python -m pytest tests/test_domain_battle.py tests/test_flag_bits.py tests/test_domain_grid.py -v`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add adapters/telemetry/domain_battle.py adapters/telemetry/iracing_bridge.py adapters/telemetry/mock_server.py adapters/telemetry/CONTRACT.md tests/test_domain_battle.py
git commit -m "feat(telemetry): emit battleEligible for session-gated fight panel"
```

---

### Task 3: Gate fight panel in broadcast.js

**Files:**
- Modify: `overlays/broadcast.js` (`updateFightPanel`)
- Modify: `docs/TELEMETRY_BROADCAST.md` (battle session rules)

**Interfaces:**
- Consumes: `tick.battleEligible` (bool; missing → fail closed: treat as false when `session` is present and not clearly eligible — prefer: if `battleEligible === false` OR (`battleEligible` absent and session is quali/cooldown) → off; if absent and race/practice → keep legacy until bridge ships, but after Task 2 always present)
- Produces: fight panel never arms when ineligible

- [ ] **Step 1: Add eligibility helper at top of battle section in `broadcast.js`**

```javascript
  function battleEligibleFromTick(tick) {
    if (!tick) return false;
    if (typeof tick.battleEligible === "boolean") return tick.battleEligible;
    // Fail closed for known non-race/practice if bridge old:
    var s = String(tick.session || "").toLowerCase();
    if (s === "quali" || s === "cooldown" || s === "unknown" || !s) return false;
    if (s === "race") {
      var lap = Number(tick.lap);
      return Number.isFinite(lap) && lap >= 1;
    }
    if (s === "practice") {
      var rows = Array.isArray(tick.standings) ? tick.standings : [];
      return rows.length >= 2;
    }
    return false;
  }
```

- [ ] **Step 2: Gate `updateFightPanel`**

At the start of `updateFightPanel`:

```javascript
  function updateFightPanel(tick, standings) {
    if (!battlePanelEnabled || !elFight) return;
    if (!battleEligibleFromTick(tick)) {
      if (battleActive) {
        battleActive = false;
        battleStreak = 0;
        hideFightPanel();
        directorLog("INFO", "fight panel off (session not eligible)");
      } else {
        battleStreak = 0;
      }
      return;
    }
    // ... existing logic
```

- [ ] **Step 3: Document in TELEMETRY_BROADCAST.md**

Add under battle panel bullets:

```markdown
- Battle pack arms only when `battleEligible` is true: **race** after live order (lap ≥ 1, not formation/pace); **practice** with ≥1 other car; **never** in quali/cooldown.
```

- [ ] **Step 4: Commit**

```bash
git add overlays/broadcast.js docs/TELEMETRY_BROADCAST.md
git commit -m "feat(broadcast): gate battle panel on battleEligible / session"
```

---

### Task 4: Top flag strip markup + CSS

**Files:**
- Modify: `overlays/broadcast-chrome.html`
- Modify: `overlays-marcato/broadcast-chrome.html`
- Modify: `overlays/assets/broadcast.css`
- Modify: `overlays/config.example.js`
- Modify: `overlays/config.js` only if it must mirror new key defaults (prefer example + values JSON)

**Interfaces:**
- Produces DOM:
  - `[data-bc-flag-strip]`
  - `[data-bc-flag-strip-label]`
  - `[data-bc-flag-strip-text]`
- CSS classes: `.bc-flag-strip`, `.is-up`, `.is-expanded`, `[data-flag=…]`
- Config: `broadcastFlagStripMs` default `10000`

- [ ] **Step 1: Replace banner with strip in both HTML files**

Remove (or leave unused) `<div class="bc-flag-banner" …>`. Insert after `broadcast-root` opens (before moment):

```html
      <div class="bc-flag-strip" data-bc-flag-strip hidden aria-hidden="true">
        <div class="bc-flag-strip-label" data-bc-flag-strip-label>FLAG</div>
        <div class="bc-flag-strip-body">
          <span data-bc-flag-strip-text></span>
        </div>
      </div>
```

Apply identically in `overlays-marcato/broadcast-chrome.html`.

- [ ] **Step 2: Add CSS (mirror field ticker, top-anchored)**

In `overlays/assets/broadcast.css`, add (near ticker styles):

```css
/* Top flag strip — FIELD-like accordion (P3-12) */
.bc-flag-strip {
  position: absolute;
  left: 0;
  top: 0;
  z-index: 14;
  height: 40px;
  max-width: 100%;
  display: grid;
  grid-template-columns: auto 0fr;
  width: max-content;
  align-items: stretch;
  background: color-mix(in srgb, var(--panel, #111) 94%, transparent);
  border-bottom: 2px solid var(--accent, #00c400);
  pointer-events: none;
  overflow: hidden;
  transform: translate3d(0, -110%, 0);
  opacity: 0;
  visibility: hidden;
  transition:
    grid-template-columns 480ms cubic-bezier(0.22, 1, 0.36, 1),
    width 480ms cubic-bezier(0.22, 1, 0.36, 1),
    transform 420ms cubic-bezier(0.22, 1, 0.36, 1),
    opacity 320ms ease,
    visibility 0s linear 420ms;
}
.bc-flag-strip.is-up {
  transform: translate3d(0, 0, 0);
  opacity: 1;
  visibility: visible;
  transition:
    grid-template-columns 480ms cubic-bezier(0.22, 1, 0.36, 1),
    width 480ms cubic-bezier(0.22, 1, 0.36, 1),
    transform 420ms cubic-bezier(0.22, 1, 0.36, 1),
    opacity 280ms ease,
    visibility 0s linear 0s;
}
.bc-flag-strip.is-expanded {
  grid-template-columns: auto 1fr;
  width: 100%;
}
.bc-flag-strip-label {
  display: flex;
  align-items: center;
  padding: 0 0.85rem;
  font-family: var(--font-display);
  font-size: 0.62rem;
  letter-spacing: 0.2em;
  text-transform: uppercase;
  color: #080a0c;
  background: var(--accent, #00c400);
  white-space: nowrap;
}
.bc-flag-strip-body {
  min-width: 0;
  display: flex;
  align-items: center;
  padding: 0 1rem;
  font-size: 0.85rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  overflow: hidden;
  white-space: nowrap;
}
.bc-flag-strip[data-flag="yellow"] .bc-flag-strip-label { background: #f5d000; }
.bc-flag-strip[data-flag="red"] .bc-flag-strip-label { background: #e10600; color: #fff; }
.bc-flag-strip[data-flag="white"] .bc-flag-strip-label { background: #f7fafc; }
.bc-flag-strip[data-flag="debris"] .bc-flag-strip-label {
  background: repeating-linear-gradient(90deg, #e10600 0 12px, #f5d000 12px 24px);
  color: #080a0c;
}
.bc-flag-strip[data-flag="checkered"] .bc-flag-strip-label {
  background: repeating-conic-gradient(#111 0% 25%, #f7fafc 0% 50%) 0 0 / 12px 12px;
  color: #fff;
  text-shadow: 0 0 4px #000;
}
.bc-flag-strip[data-flag="blue"] .bc-flag-strip-label { background: #009fe5; color: #fff; }
```

Deprecate visual use of `.bc-flag-banner` (can leave rules; JS will stop toggling it).

- [ ] **Step 3: Config key**

In `overlays/config.example.js`:

```javascript
  broadcastFlagStripMs: 10000, // timed flags: white / debris / checkered
```

- [ ] **Step 4: Commit**

```bash
git add overlays/broadcast-chrome.html overlays-marcato/broadcast-chrome.html overlays/assets/broadcast.css overlays/config.example.js
git commit -m "feat(broadcast): add top flag strip markup and styles"
```

---

### Task 5: Flag strip controller in broadcast.js

**Files:**
- Modify: `overlays/broadcast.js`
- Modify: `docs/TELEMETRY_BROADCAST.md`
- Modify: `overlays/broadcast-director.js` only if needed to suppress flag heroes (prefer filtering in `enqueueEvent` caller)

**Interfaces:**
- Consumes: `tick.flag`, `telemetry.event` flag_change/session_end, `cfg.broadcastFlagStripMs`
- Produces: strip show/hide; no `.bc-flag-banner`; no moment chips for `flag_change` / `session_end` when flag is white|debris|checkered|yellow|red (strip owns flag UX)

Timed flags: `white`, `debris`, `checkered` — hold `broadcastFlagStripMs` (default 10000) then collapse/drop even if SDK still set.

Hold-while-active: `yellow`, `red` — hide when flag becomes green/none/other.

Labels:

| flag | label | body text |
|------|-------|-----------|
| white | LAST LAP | FINAL LAP |
| debris | DEBRIS | DEBRIS ON TRACK |
| checkered | CHECKERED | SESSION FINISH |
| yellow | YELLOW | CAUTION |
| red | RED | SESSION STOPPED |

- [ ] **Step 1: Wire elements + timing constants**

Near other `querySelector` bindings:

```javascript
  const elFlagStrip = root.querySelector("[data-bc-flag-strip]");
  const elFlagStripLabel = root.querySelector("[data-bc-flag-strip-label]");
  const elFlagStripText = root.querySelector("[data-bc-flag-strip-text]");
  const flagStripMs = Math.max(
    2000,
    Math.min(30000, Number(cfg.broadcastFlagStripMs) || 10000)
  );
  const FLAG_STRIP_RISE_MS = 420;
  const FLAG_STRIP_EXPAND_MS = 480;
  const FLAG_STRIP_COLLAPSE_MS = 480;
  const FLAG_STRIP_DROP_MS = 420;
  const TIMED_FLAGS = { white: 1, debris: 1, checkered: 1 };
  const HOLD_FLAGS = { yellow: 1, red: 1 };
```

- [ ] **Step 2: Implement strip state machine**

```javascript
  let flagStripPhase = "idle"; // idle|rise|expand|show|collapse|drop
  let flagStripTimer = null;
  let flagStripCurrent = "";
  let flagStripGen = 0;

  function flagStripMeta(flag) {
    var f = String(flag || "").toLowerCase();
    if (f === "white") return { label: "LAST LAP", text: "FINAL LAP" };
    if (f === "debris") return { label: "DEBRIS", text: "DEBRIS ON TRACK" };
    if (f === "checkered") return { label: "CHECKERED", text: "SESSION FINISH" };
    if (f === "yellow") return { label: "YELLOW", text: "CAUTION" };
    if (f === "red") return { label: "RED", text: "SESSION STOPPED" };
    if (f === "blue") return { label: "BLUE", text: "LET LEADER BY" };
    return { label: f.toUpperCase(), text: f.toUpperCase() };
  }

  function clearFlagStripTimer() {
    if (flagStripTimer != null) {
      window.clearTimeout(flagStripTimer);
      flagStripTimer = null;
    }
  }

  function scheduleFlagStrip(ms, fn) {
    clearFlagStripTimer();
    flagStripTimer = window.setTimeout(function () {
      flagStripTimer = null;
      fn();
    }, ms);
  }

  function setFlagStripUp(up) {
    if (!elFlagStrip) return;
    elFlagStrip.classList.toggle("is-up", !!up);
    elFlagStrip.hidden = !up && flagStripPhase === "idle";
    elFlagStrip.setAttribute("aria-hidden", up ? "false" : "true");
  }

  function setFlagStripExpanded(expanded) {
    if (!elFlagStrip) return;
    elFlagStrip.classList.toggle("is-expanded", !!expanded);
  }

  function flagStripGoIdle() {
    flagStripPhase = "idle";
    flagStripCurrent = "";
    setFlagStripExpanded(false);
    setFlagStripUp(false);
    if (elFlagStrip) {
      elFlagStrip.hidden = true;
      elFlagStrip.dataset.flag = "";
    }
  }

  function flagStripDrop() {
    flagStripPhase = "drop";
    setFlagStripUp(false);
    scheduleFlagStrip(FLAG_STRIP_DROP_MS, flagStripGoIdle);
  }

  function flagStripCollapse() {
    if (flagStripPhase === "collapse" || flagStripPhase === "drop" || flagStripPhase === "idle") return;
    flagStripPhase = "collapse";
    clearFlagStripTimer();
    setFlagStripExpanded(false);
    scheduleFlagStrip(FLAG_STRIP_COLLAPSE_MS, flagStripDrop);
  }

  function showFlagStrip(flag) {
    if (!elFlagStrip) return;
    var f = String(flag || "").toLowerCase();
    if (!TIMED_FLAGS[f] && !HOLD_FLAGS[f] && f !== "blue") return;
    flagStripGen += 1;
    var gen = flagStripGen;
    flagStripCurrent = f;
    var meta = flagStripMeta(f);
    elFlagStrip.hidden = false;
    elFlagStrip.dataset.flag = f;
    if (elFlagStripLabel) elFlagStripLabel.textContent = meta.label;
    if (elFlagStripText) elFlagStripText.textContent = meta.text;
    clearFlagStripTimer();
    flagStripPhase = "rise";
    setFlagStripExpanded(false);
    setFlagStripUp(true);
    scheduleFlagStrip(FLAG_STRIP_RISE_MS, function () {
      if (gen !== flagStripGen) return;
      flagStripPhase = "expand";
      setFlagStripExpanded(true);
      scheduleFlagStrip(FLAG_STRIP_EXPAND_MS, function () {
        if (gen !== flagStripGen) return;
        flagStripPhase = "show";
        if (TIMED_FLAGS[f]) {
          scheduleFlagStrip(flagStripMs, function () {
            if (gen !== flagStripGen) return;
            flagStripCollapse();
          });
        }
      });
    });
  }

  function syncFlagStrip(flag) {
    var f = String(flag || "none").toLowerCase();
    if (f === "none" || f === "green") {
      if (HOLD_FLAGS[flagStripCurrent] || flagStripCurrent) {
        // Green clears hold flags; also clear if still showing after SDK drops.
        if (HOLD_FLAGS[flagStripCurrent] || !TIMED_FLAGS[flagStripCurrent]) {
          flagStripCollapse();
        }
      }
      return;
    }
    if (f === flagStripCurrent && flagStripPhase !== "idle" && flagStripPhase !== "drop") return;
    showFlagStrip(f);
  }
```

- [ ] **Step 3: Call from render + events; disable old banner + flag heroes**

Replace `applyFlagBanner` usages in `render` / `enqueueEvent` with `syncFlagStrip(flag)`.

Keep `applyFlagBanner` as no-op or remove calls:

```javascript
  function applyFlagBanner(flag) {
    syncFlagStrip(flag);
  }
```

In `enqueueEvent`, skip director heroes for flag kinds:

```javascript
    if (ev.kind === "flag_change" || ev.kind === "session_end") {
      applyFlagBanner(ev.payload && ev.payload.flag);
      return; // strip owns flag UX — do not enqueue moment chip
    }
```

(Insert the early return **after** strip update, **before** `Director.enqueueEvent`, or filter inside so flag events never become heroes.)

Preferred structure:

```javascript
  function enqueueEvent(ev) {
    if (director !== "auto") return;
    if (!ev || !ev.kind) return;
    if (ev.kind === "flag_change" || ev.kind === "session_end") {
      applyFlagBanner(ev.payload && ev.payload.flag);
      return;
    }
    if (!Director) return;
    ...
  }
```

And in `render`, keep `applyFlagBanner(flag)` / `syncFlagStrip(flag)` so refresh mid-flag still works.

- [ ] **Step 4: Manual check note in TELEMETRY_BROADCAST.md**

Document strip behavior + `broadcastFlagStripMs`.

- [ ] **Step 5: Commit**

```bash
git add overlays/broadcast.js docs/TELEMETRY_BROADCAST.md
git commit -m "feat(broadcast): FIELD-like top flag strip with 10s timed flags"
```

---

### Task 6: Fix cam device IDs + regenerate Marcato pack

**Files:**
- Modify: `tools/generate_pack.py` (`STREAMCAM_ID`, `USBCAM_ID`)
- Create: `tests/test_pack_cameras.py`
- Regenerate: `obs/S_Marcato_42.json`, `obs/S_Marcato_Replay.json`, `obs/S_Marcato_Rec_2K.json` (and PiGreco if same constants)
- Modify: `docs/CAMERAS.md`

**Interfaces:**
- Produces OBS `video_device_id` strings without `#22` escaping:

```text
Logitech StreamCam:\\?\usb#vid_046d&pid_0893&mi_00#8&33ee287c&0&0000#{65e8773d-8f56-11d0-a3b9-00a0c9223196}\global
USB Camera:\\?\usb#vid_0c6a&pid_646a&mi_00#9&1779791d&0&0000#{65e8773d-8f56-11d0-a3b9-00a0c9223196}\global
```

- [ ] **Step 1: Write failing pack camera tests**

```python
"""Cam device ID hygiene for generate_pack."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import generate_pack as gp  # noqa: E402


def test_streamcam_id_has_no_hash22_escape():
    assert "#22" not in gp.STREAMCAM_ID
    assert "vid_046d" in gp.STREAMCAM_ID
    assert "8&33ee287c" in gp.STREAMCAM_ID.lower()


def test_usbcam_id_matches_seat_cam():
    assert "#22" not in gp.USBCAM_ID
    assert "vid_0c6a" in gp.USBCAM_ID
    assert "9&1779791d" in gp.USBCAM_ID.lower()
```

- [ ] **Step 2: Run — expect FAIL on StreamCam**

Run: `python -m pytest tests/test_pack_cameras.py -v`

Expected: FAIL on `#22` in `STREAMCAM_ID`.

- [ ] **Step 3: Fix constants**

```python
STREAMCAM_ID = (
    r"Logitech StreamCam:\\?\usb#vid_046d&pid_0893&mi_00#8&33ee287c&0&0000"
    r"#{65e8773d-8f56-11d0-a3b9-00a0c9223196}\global"
)
USBCAM_ID = (
    r"USB Camera:\\?\usb#vid_0c6a&pid_646a&mi_00#9&1779791d&0&0000"
    r"#{65e8773d-8f56-11d0-a3b9-00a0c9223196}\global"
)
```

Log at pack build time (INFO): both friendly names written.

- [ ] **Step 4: Run pack camera tests — PASS**

Run: `python -m pytest tests/test_pack_cameras.py -v`

- [ ] **Step 5: Regenerate Marcato collections**

**Prerequisite:** OBS closed (or accept `install_marcato_collections_to_obs` restart).

Run:

```powershell
python tools/generate_pack.py --profile marcato
```

Also regenerate PiGreco if it embeds the same cam sources:

```powershell
python tools/generate_pack.py --profile pigreco
```

Verify JSON contains the new StreamCam path (no `#22vid`).

- [ ] **Step 6: Update CAMERAS.md**

Add verify steps: after regen, open nested Cam PIP → Properties → device should be Logitech StreamCam; Cam 2 → USB Camera. If USB port changes, re-pick and update constants.

- [ ] **Step 7: Commit**

```bash
git add tools/generate_pack.py tests/test_pack_cameras.py obs/S_Marcato_42.json obs/S_Marcato_Replay.json obs/S_Marcato_Rec_2K.json obs/PiGreco_Racing.json docs/CAMERAS.md
git commit -m "fix(obs): refresh StreamCam/USB Camera device IDs on PiP nests"
```

(Only include PiGreco JSON if regenerated.)

---

### Task 7: ROADMAP done + acceptance sweep

**Files:**
- Modify: `docs/ROADMAP.md` (P3-12 → `done`)

- [ ] **Step 1: Run full relevant pytest**

```powershell
python -m pytest tests/test_flag_bits.py tests/test_domain_battle.py tests/test_pack_cameras.py tests/test_domain_grid.py tests/test_telemetry_events.py -v
```

Expected: PASS.

- [ ] **Step 2: Manual acceptance checklist**

- [ ] OBS: Cam PIP shows StreamCam; Cam 2 PIP shows USB Camera
- [ ] Mock/bridge: white → LAST LAP strip ~10s then drop
- [ ] debris → red/yellow strip ~10s
- [ ] checkered → ~10s
- [ ] yellow holds until green
- [ ] Battle off in formation / quali; on in practice with others and race lap ≥ 1

- [ ] **Step 3: Mark P3-12 done + commit**

```bash
git add docs/ROADMAP.md
git commit -m "docs(roadmap): mark P3-12 flag strip and battle gate done"
```

---

## Spec coverage (self-review)

| Spec requirement | Task |
|------------------|------|
| Fix StreamCam/USB IDs + regen Marcato PiP | Task 6 |
| Top FIELD-like strip expand L→R | Tasks 4–5 |
| Timed 10s white/debris/checkered | Task 5 |
| Yellow/red hold while active | Task 5 |
| SessionFlags + debris bit | Task 1 |
| Battle race lap1 + practice others + never quali | Tasks 2–3 |
| CONTRACT / docs / config.example | Tasks 1–5 |
| ROADMAP P3-12 | Tasks 1 + 7 |
| Non-goals (no full chrome redesign, keep nested PiP) | respected |

**Placeholder scan:** none intentional.  
**Type consistency:** `battle_panel_eligible` / `battleEligible` / `battleEligibleFromTick` aligned.
