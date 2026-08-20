from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "adapters" / "telemetry"))

import iracing_bridge as bridge
from domain_session_reset import SessionResetTracker


class FakeIR:
    def __init__(self, values: dict[str, Any]) -> None:
        self.values = values

    def __getitem__(self, key: str) -> Any:
        return self.values[key]


class FakeWebSocket:
    def __init__(self, incoming: list[str] | None = None) -> None:
        self.incoming = incoming or []
        self.messages: list[str] = []
        self.remote_address = ("127.0.0.1", 12345)

    def __aiter__(self) -> Any:
        return self

    async def __anext__(self) -> str:
        if not self.incoming:
            raise StopAsyncIteration
        return self.incoming.pop(0)

    async def send(self, payload: str) -> None:
        self.messages.append(payload)


def _ir(*, unique_id: str, session_num: int = 0, session_type: str = "Race") -> FakeIR:
    return FakeIR(
        {
            "SessionUniqueID": unique_id,
            "SessionNum": session_num,
            "WeekendInfo": {"TrackID": 449},
            "SessionInfo": {"Sessions": [{"SessionType": session_type}]},
        }
    )


def _reset_bridge_state() -> None:
    bridge.reset_continuity()
    bridge._session_tracker = SessionResetTracker()


def test_session_identity_latches_then_resets_continuity_on_change() -> None:
    _reset_bridge_state()
    try:
        assert bridge.note_session_identity(_ir(unique_id="race-a"), now_ms=1_000) is None
        bridge.detector.feed(
            {
                "type": "telemetry.tick",
                "schemaVersion": 1,
                "ts": 1,
                "flag": "green",
                "position": 2,
            }
        )
        bridge._prev_pos_by_car = {42: 2}

        event = bridge.note_session_identity(_ir(unique_id="race-b"), now_ms=3_000)

        assert event == {
            "type": "telemetry.session_reset",
            "schemaVersion": 1,
            "ts": 3_000,
            "reason": "session_changed",
            "sessionKey": "race-b",
            "previousKey": "race-a",
        }
        assert bridge.detector._prev is None
        assert bridge._prev_pos_by_car == {}
    finally:
        _reset_bridge_state()


def test_manual_command_uses_same_reset_path() -> None:
    _reset_bridge_state()
    try:
        bridge._session_tracker.note("race-a", now_ms=1_000)
        bridge._prev_pos_by_car = {42: 2}

        event = bridge.handle_telemetry_command(
            {
                "type": "telemetry.command",
                "command": "session_reset",
                "reason": "manual",
                "ts": 2_000,
            }
        )

        assert event == {
            "type": "telemetry.session_reset",
            "schemaVersion": 1,
            "ts": 2_000,
            "reason": "manual",
            "sessionKey": "race-a",
            "previousKey": "race-a",
        }
        assert bridge._prev_pos_by_car == {}
    finally:
        _reset_bridge_state()


def test_command_debounce_uses_server_clock_not_client_ts() -> None:
    _reset_bridge_state()
    try:
        bridge._session_tracker.note("race-a", now_ms=1_000)

        event = bridge.handle_telemetry_command(
            {
                "type": "telemetry.command",
                "command": "session_reset",
                "reason": "manual",
                "ts": 1,  # skewed client clock
            },
            now_ms=10_000,
        )

        assert event is not None
        assert event["ts"] == 1  # envelope keeps the client stamp
        assert bridge._session_tracker._last_emit_ms == 10_000
        # A sim session change inside the server debounce window stays suppressed.
        assert bridge.note_session_identity(_ir(unique_id="race-b"), now_ms=10_500) is None
        assert bridge.note_session_identity(_ir(unique_id="race-b"), now_ms=12_000) is not None
    finally:
        _reset_bridge_state()


def test_command_with_invalid_ts_falls_back_to_server_now(caplog: Any) -> None:
    _reset_bridge_state()
    try:
        with caplog.at_level(logging.WARNING):
            event = bridge.handle_telemetry_command(
                {
                    "type": "telemetry.command",
                    "command": "session_reset",
                    "ts": "not-a-number",
                },
                now_ms=7_000,
            )

        assert event is not None
        assert event["ts"] == 7_000
        assert "invalid ts" in caplog.text
    finally:
        _reset_bridge_state()


def test_main_loop_notes_session_before_building_tick() -> None:
    """The tick that triggers a reset must not be built from stale continuity."""
    src = (ROOT / "adapters" / "telemetry" / "iracing_bridge.py").read_text(encoding="utf-8")
    loop = src[src.index("async with serve(handler") :]
    assert loop.index("note_session_identity") < loop.index("build_tick_from_ir")


def test_unknown_command_warns_without_reset(caplog: Any) -> None:
    _reset_bridge_state()
    with caplog.at_level(logging.WARNING):
        event = bridge.handle_telemetry_command(
            {"type": "telemetry.command", "command": "unsupported"},
            now_ms=2_000,
        )
    assert event is None
    assert "unsupported telemetry command" in caplog.text


def test_disconnect_clears_session_key_and_returns_reset() -> None:
    _reset_bridge_state()
    bridge._session_tracker.note("race-a", now_ms=1_000)

    event = bridge.disconnect_session_reset(now_ms=2_000)

    assert event["reason"] == "sim_disconnected"
    assert event["sessionKey"] is None
    assert event["previousKey"] == "race-a"
    assert bridge._session_tracker.current_key is None


def test_broadcast_message_sends_to_all_clients() -> None:
    first = FakeWebSocket()
    second = FakeWebSocket()
    clients = {first, second}
    message = {"type": "telemetry.session_reset", "schemaVersion": 1, "ts": 2_000}

    asyncio.run(bridge.broadcast_message(clients, message))

    assert first.messages == second.messages
    assert '"type":"telemetry.session_reset"' in first.messages[0]


def test_websocket_handler_routes_session_reset_command_to_all_clients() -> None:
    _reset_bridge_state()
    try:
        bridge._session_tracker.note("race-a", now_ms=1_000)
        bridge.detector.feed(
            {
                "type": "telemetry.tick",
                "schemaVersion": 1,
                "ts": 1,
                "flag": "green",
                "position": 2,
            }
        )
        bridge._prev_pos_by_car = {42: 2}
        sender = FakeWebSocket(
            [
                json.dumps(
                    {
                        "type": "telemetry.command",
                        "command": "session_reset",
                        "reason": "manual",
                        "ts": 2_000,
                    }
                )
            ]
        )
        observer = FakeWebSocket()
        clients = {observer}

        asyncio.run(
            bridge.handle_websocket_client(
                sender,
                clients,
                tick_hz=10.0,
                also_file=False,
            )
        )

        sender_frames = [json.loads(payload) for payload in sender.messages]
        observer_frames = [json.loads(payload) for payload in observer.messages]
        assert [frame["type"] for frame in sender_frames] == [
            "telemetry.hello",
            "telemetry.session_reset",
        ]
        assert observer_frames == [sender_frames[1]]
        assert observer_frames[0]["reason"] == "manual"
        assert bridge.detector._prev is None
        assert bridge._prev_pos_by_car == {}
    finally:
        _reset_bridge_state()


def test_contract_documents_session_reset_and_command() -> None:
    text = (ROOT / "adapters" / "telemetry" / "CONTRACT.md").read_text(encoding="utf-8")
    assert "telemetry.session_reset" in text
    assert "telemetry.command" in text
