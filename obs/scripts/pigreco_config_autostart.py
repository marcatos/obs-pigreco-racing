# PiGreco / S.Marcato — DEPRECATED for OBS Scripts.
#
# This Python script causes a black console flash on Windows when the timer
# runs (subprocess / cmd). Use the Lua script instead:
#   obs/scripts/pigreco_config_autostart.lua
#
# Left in the repo only as reference. script_load is a no-op.

from __future__ import annotations

import obspython as obs


def script_description():
    return (
        "DEPRECATED — usa pigreco_config_autostart.lua. "
        "Questo script Python è disattivato (evita flash della console)."
    )


def script_defaults(settings):
    pass


def script_properties():
    return obs.obs_properties_create()


def script_load(settings):
    obs.script_log(
        obs.LOG_WARNING,
        "PiGreco: pigreco_config_autostart.py è disattivato — rimuovilo da Scripts "
        "e tieni solo pigreco_config_autostart.lua",
    )


def script_unload():
    pass


def script_update(settings):
    pass
