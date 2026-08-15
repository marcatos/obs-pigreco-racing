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
