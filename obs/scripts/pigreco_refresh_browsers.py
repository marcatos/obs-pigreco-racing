# PiGreco Racing — refresh Browser Source overlays after Config Panel save.
# OBS → Strumenti/Tools → Scripts → + → select this file.
# Click the button after "Salva e applica" nel dock.

import obspython as obs


def script_description():
    return (
        "PiGreco Config: ricarica la cache delle Browser Source del pack "
        "(dopo Salva su http://127.0.0.1:8766/)."
    )


def _refresh_browser(source) -> bool:
    handler = obs.obs_source_get_proc_handler(source)
    if handler is None:
        return False
    cd = obs.calldata_create()
    # OBS browser source proc (CEF)
    ok = obs.proc_handler_call(handler, "refresh_cache", cd)
    if not ok:
        ok = obs.proc_handler_call(handler, "webpage_refresh_cache", cd)
    obs.calldata_destroy(cd)
    return bool(ok)


def refresh_browsers(props, prop):
    sources = obs.obs_enum_sources()
    refreshed = 0
    skipped = 0
    if sources is not None:
        for src in sources:
            if obs.obs_source_get_unversioned_id(src) != "browser_source":
                continue
            settings = obs.obs_source_get_settings(src)
            url = (obs.obs_data_get_string(settings, "url") or "").replace("\\", "/")
            obs.obs_data_release(settings)
            if "obs-pigreco-racing" not in url and "/overlays/" not in url:
                skipped += 1
                continue
            name = obs.obs_source_get_name(src)
            if _refresh_browser(src):
                refreshed += 1
                obs.script_log(obs.LOG_INFO, f"PiGreco refreshed: {name}")
            else:
                obs.script_log(obs.LOG_WARNING, f"PiGreco refresh failed: {name}")
        obs.source_list_release(sources)

    obs.script_log(
        obs.LOG_INFO,
        f"PiGreco done — refreshed={refreshed} skipped_other_browsers={skipped}",
    )
    return True


def script_properties():
    props = obs.obs_properties_create()
    obs.obs_properties_add_button(
        props,
        "refresh",
        "Refresh overlay Browser Sources",
        refresh_browsers,
    )
    return props
