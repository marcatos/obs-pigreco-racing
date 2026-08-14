"""Broadcast director overlay: config, mounts, and queue policy (P3-06 Task 7)."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_director_config_defaults_in_both_packs():
    for rel in ("overlays/config.values.json", "overlays-marcato/config.values.json"):
        data = json.loads((ROOT / rel).read_text(encoding="utf-8"))
        assert data["broadcastDirector"] == "auto", rel
        assert data["broadcastDirectorSensitivity"] == "normal", rel


def test_director_keys_in_config_example():
    text = (ROOT / "overlays" / "config.example.js").read_text(encoding="utf-8")
    assert "broadcastDirector:" in text
    assert "broadcastDirectorSensitivity:" in text


def test_moment_mount_in_both_chrome_html():
    needle = 'class="bc-moment" data-bc-moment hidden aria-live="polite"'
    for rel in (
        "overlays/broadcast-chrome.html",
        "overlays-marcato/broadcast-chrome.html",
    ):
        html = (ROOT / rel).read_text(encoding="utf-8")
        assert needle in html, rel
        flag_i = html.index("data-bc-flag-banner")
        moment_i = html.index("data-bc-moment")
        status_i = html.index("data-bc-status")
        assert flag_i < moment_i < status_i, rel


def test_config_panel_has_director_selects():
    html = (ROOT / "overlays" / "config-panel.html").read_text(encoding="utf-8")
    assert 'name="broadcastDirector"' in html
    assert 'name="broadcastDirectorSensitivity"' in html
    assert 'value="auto"' in html
    assert 'value="manual"' in html
    assert 'value="off"' in html
    assert 'value="calm"' in html
    assert 'value="hype"' in html
    assert "SELECTS" in html


def test_moment_css_is_peripheral_not_center_fov():
    css = (ROOT / "overlays" / "assets" / "broadcast.css").read_text(encoding="utf-8")
    assert ".bc-moment {" in css
    assert "top: 120px" in css
    assert "left: 50%" in css
    css_l = css.lower()
    assert "border: 2px solid var(--accent, #00c400)" in css_l
    assert 'data-kind="overtake"] .bc-moment-chip { border-color: var(--accent, #00c400); }' in css_l
    assert "bcMomentIn" in css
    assert "bcMomentOut" in css
    assert "top: 50%" not in css.split(".bc-moment {")[1].split("}")[0]


def test_broadcast_js_handles_telemetry_event():
    js = (ROOT / "overlays" / "broadcast.js").read_text(encoding="utf-8")
    assert 'msg.type === "telemetry.event"' in js
    assert "enqueueEvent" in js
    assert 'broadcastDirector || "auto"' in js


def test_director_queue_and_labels_via_node():
    director = ROOT / "overlays" / "broadcast-director.js"
    assert director.is_file(), "broadcast-director.js domain module missing"
    script = r"""
const fs = require("fs");
const vm = require("vm");
const path = process.env.DIRECTOR_JS;
const sandbox = { console };
sandbox.globalThis = sandbox;
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(path, "utf8"), sandbox);
const D = sandbox.PigrecoBroadcastDirector;
if (!D) throw new Error("PigrecoBroadcastDirector not exported");

function assertEq(a, b, msg) {
  if (a !== b) throw new Error((msg || "assertEq") + ": " + JSON.stringify(a) + " !== " + JSON.stringify(b));
}
function assert(cond, msg) {
  if (!cond) throw new Error(msg || "assert failed");
}

assertEq(D.formatMomentLabel({ kind: "flag_change", payload: { flag: "yellow" } }), "YELLOW");
assertEq(D.formatMomentLabel({ kind: "overtake", payload: { toPos: 4 } }), "OVERTAKE P4");
assertEq(D.formatMomentLabel({ kind: "fast_lap", payload: {} }), "FASTEST");
assertEq(D.formatMomentLabel({ kind: "battle", payload: {} }), "BATTLE");
assertEq(D.formatMomentLabel({ kind: "pit", payload: { state: "enter" } }), "PIT ENTER");
assertEq(D.formatMomentLabel({ kind: "session_end", payload: {} }), "FINISH");

let st = { hero: null, queue: [] };
st = D.enqueueEvent(st, { kind: "battle", priority: 60, ttlMs: 4000, payload: {} }, "manual");
assert(st.hero === null, "manual ignores events");

st = D.enqueueEvent(st, { kind: "battle", priority: 60, ttlMs: 4000, payload: {} }, "off");
assert(st.hero === null, "off ignores events");

st = D.enqueueEvent(st, { kind: "battle", priority: 60, ttlMs: 4000, payload: {} }, "auto");
assertEq(st.hero.kind, "battle");
assertEq(st.queue.length, 0);

st = D.enqueueEvent(st, { kind: "fast_lap", priority: 50, ttlMs: 3000, payload: {} }, "auto");
assertEq(st.hero.kind, "battle");
assertEq(st.queue.length, 1);
assertEq(st.queue[0].kind, "fast_lap");

st = D.enqueueEvent(st, { kind: "flag_change", priority: 100, ttlMs: 4000, payload: { flag: "yellow" } }, "auto");
assertEq(st.hero.kind, "flag_change");
assertEq(st.queue[0].kind, "battle");
assertEq(st.queue.length, 2);

st = D.enqueueEvent(st, { kind: "pit", priority: 40, ttlMs: 4000, payload: { state: "enter" } }, "auto");
assertEq(st.hero.kind, "flag_change");
assertEq(st.queue.length, 2, "queue max 2");
assert(st.queue.every(function (x) { return x.kind !== "pit"; }), "low prio dropped when queue full");

console.log("ok");
"""
    env = os.environ.copy()
    env["DIRECTOR_JS"] = str(director)
    proc = subprocess.run(
        ["node", "-e", script],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert "ok" in proc.stdout


def test_director_module_does_not_add_no_widget_classes():
    text = (ROOT / "overlays" / "broadcast-director.js").read_text(encoding="utf-8")
    for cls in ("no-leaderboard", "no-relative", "no-focus", "no-session"):
        assert cls not in text, "director module must not hide widgets via " + cls
    assert "classList" not in text


def test_overlay_runtime_director_policies_via_node():
    script = ROOT / "tests" / "broadcast_overlay_runtime.js"
    assert script.is_file(), "overlay runtime harness missing"
    proc = subprocess.run(
        ["node", str(script)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert "ok" in proc.stdout
