"""P1 battle panel must ignore gapAheadMs=0 (leader sentinel)."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIRECTOR = ROOT / "overlays" / "broadcast-director.js"


def test_leader_zero_gap_ahead_does_not_hold_or_arm_battle():
    director = DIRECTOR.as_posix().replace("\\", "/")
    script = f"""
const fs = require('fs');
const vm = require('vm');
const src = fs.readFileSync({director!r}, 'utf8');
const root = {{}};
vm.runInNewContext(src, {{ globalThis: root, console }});
const D = root.PigrecoBroadcastDirector;
if (D.isActiveGapMs(0)) throw new Error('0 must not be active');
if (!D.isActiveGapMs(1)) throw new Error('1 must be active');
const p1Far = {{ ga: 0, gb: 500, closeAhead: 0, closeBehind: 0 }};
if (D.fightGapsHold(p1Far, 400)) throw new Error('P1 far behind must not hold');
if (D.fightGapsArm(p1Far, {{ doorstopMs: 110, engageMs: 850, closeRate: 280 }})) {{
  throw new Error('P1 far behind must not arm');
}}
const p1Close = {{ ga: 0, gb: 250, closeAhead: 0, closeBehind: 300 }};
if (!D.fightGapsHold(p1Close, 400)) throw new Error('P1 close behind must hold');
if (!D.fightGapsArm(p1Close, {{ doorstopMs: 110, engageMs: 850, closeRate: 280 }})) {{
  throw new Error('P1 closing behind must arm');
}}
console.log('ok');
"""
    proc = subprocess.run(
        ["node", "-e", script],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    assert "ok" in proc.stdout


def test_broadcast_js_uses_active_gap_helpers():
    js = (ROOT / "overlays" / "broadcast.js").read_text(encoding="utf-8")
    assert "fightGapsArm" in js
    assert "fightGapsHold" in js
    assert "sample.ga > 0" in js
    assert "sample.gb > 0" in js
