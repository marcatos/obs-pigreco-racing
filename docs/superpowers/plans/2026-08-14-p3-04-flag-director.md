# P3-04 Flag Director Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Optional local process that listens to telemetry WS and switches OBS scenes on yellow/red/checkered, auto-returning home on green, without touching broadcast overlay.

**Architecture:** Pure `domain_flag_director.py` maps flag → target scene + debounce/home stack. `director.py` wires telemetry WS + obs-websocket v5 (or dry-run log). Config from gitignored `config.local.json`.

**Tech Stack:** Python 3, `websockets`, `obsws-python` (obs-websocket v5), pytest, CRLF `Start-FlagDirector.bat`.

## Global Constraints

- ADR-005: overlays never talk to OBS or sim SDK; this adapter is separate from Browser Source.
- No secrets in git; `config.local.json` gitignored; never log passwords.
- Debounce default **1500** ms; v1 switches only yellow/red/checkered; green → home.
- Overlay flag UX unchanged (P3-06).
- Conventional Commits; claim ROADMAP **P3-04**.
- Spec: `docs/superpowers/specs/2026-08-14-p3-04-flag-director-design.md`.

## File map

| Path | Responsibility |
|------|----------------|
| `adapters/obs_flag_director/domain_flag_director.py` | Pure FlagDirector state machine |
| `adapters/obs_flag_director/director.py` | CLI + WS + OBS (or dry-run) |
| `adapters/obs_flag_director/config.example.json` | Template |
| `adapters/obs_flag_director/requirements.txt` | websockets, obsws-python |
| `Start-FlagDirector.bat` | Launcher CRLF |
| `docs/FLAG_DIRECTOR.md` | Setup |
| `tests/test_flag_director.py` | Domain tests |
| `.gitignore` | `config.local.json`, maybe `__pycache__` already |
| `docs/ROADMAP.md` | P3-04 status |

---

### Task 1: Domain FlagDirector (TDD)

**Files:** Create `adapters/obs_flag_director/domain_flag_director.py`, `tests/test_flag_director.py`; claim P3-04 `in_progress` in ROADMAP.

**Interfaces:**
- `FlagDirectorConfig(scenes: dict[str,str], home_scene: str, debounce_ms: int = 1500)`
- `class FlagDirector`: `on_flag(flag: str, *, now_ms: int) -> str | None` returns scene name to switch to, or None
- Remembers home when leaving non-flag scene; green/`none` after flag → home

- [ ] **Step 1:** Write tests for yellow→scene, green→home, debounce suppress, already-on-target None

```python
def test_yellow_then_green_returns_home():
    d = FlagDirector(FlagDirectorConfig(
        scenes={"yellow": "Flag Yellow", "red": "Flag Red", "checkered": "Flag Checkered"},
        home_scene="Rec * Live",
        debounce_ms=1500,
    ))
    assert d.on_flag("yellow", now_ms=1000) == "Flag Yellow"
    assert d.on_flag("yellow", now_ms=1100) is None  # debounce
    assert d.on_flag("green", now_ms=3000) == "Rec * Live"
```

- [ ] **Step 2:** Implement minimal domain; pytest pass
- [ ] **Step 3:** Commit `feat(obs): add flag director domain state machine`

---

### Task 2: Director process + config + bat + docs

**Files:** `director.py`, `config.example.json`, `requirements.txt`, `Start-FlagDirector.bat`, `docs/FLAG_DIRECTOR.md`, `.gitignore`, ROADMAP → done.

- [ ] **Step 1:** Load config; `--dry-run` logs intended switches without OBS
- [ ] **Step 2:** Connect telemetry WS; on `telemetry.event` flag_change and latch from tick.flag
- [ ] **Step 3:** Optional OBS via obsws-python `ReqClient`; if import/connect fails, log ERROR and stay dry-run
- [ ] **Step 4:** Docs: enable OBS websocket, copy config, create three flag scenes, run bat
- [ ] **Step 5:** Commit `feat(obs): add Start-FlagDirector and operator docs`

---

## Acceptance check

- Unit tests green without OBS
- Dry-run against mock telemetry shows yellow/green scene names in logs
- ROADMAP P3-04 done
