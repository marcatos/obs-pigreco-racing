-- PiGreco / S.Marcato — avvia il config server quando OBS parte (una sola volta).
--
-- Niente timer periodico / niente os.execute / niente io.popen (flash cmd su Windows).
-- Avvio silenzioso: LuaJIT FFI → shell32.ShellExecuteW(SW_HIDE).

obs = obslua

local pack_root_cached = ""
local boot_timer_armed = false
local ffi_ok, ffi = pcall(require, "ffi")
local shell32, kernel32

if ffi_ok then
  local ok_cdef = pcall(function()
    ffi.cdef[[
      typedef void* HWND;
      typedef const wchar_t* LPCWSTR;
      void* __stdcall ShellExecuteW(HWND hwnd, LPCWSTR lpOperation, LPCWSTR lpFile,
                          LPCWSTR lpParameters, LPCWSTR lpDirectory, int nShowCmd);
      int __stdcall MultiByteToWideChar(unsigned int CodePage, unsigned long dwFlags,
                              const char* lpMultiByteStr, int cbMultiByte,
                              wchar_t* lpWideCharStr, int cchWideChar);
    ]]
  end)
  if ok_cdef then
    local ok_s, s = pcall(ffi.load, "shell32")
    local ok_k, k = pcall(ffi.load, "kernel32")
    if ok_s and ok_k then
      shell32 = s
      kernel32 = k
    else
      ffi_ok = false
    end
  else
    ffi_ok = false
  end
end

local CP_UTF8 = 65001
local SW_HIDE = 0
local sync_armed = false
local last_sync_key = ""

function script_description()
  return [[Avvia il server del Config Panel (127.0.0.1:8766) all'apertura di OBS
(una sola volta, silenzioso).

Sincronizza anche il layout faccia: se nascondi Cam PIP (o StreamCam),
l'overlay passa a cam=0 e nasconde il riquadro CAM.
Cam 2 PIP e' indipendente: occhio on/off senza toccare la faccia.]]
end

function script_defaults(settings)
  obs.obs_data_set_default_string(settings, "pack_root", "")
end

function script_properties()
  local props = obs.obs_properties_create()
  obs.obs_properties_add_path(
    props,
    "pack_root",
    "Cartella pack (obs-pigreco-racing)",
    obs.OBS_PATH_DIRECTORY,
    nil,
    nil
  )
  obs.obs_properties_add_button(
    props,
    "ensure_now",
    "Avvia / verifica config server ora",
    on_ensure_clicked
  )
  return props
end

function script_load(settings)
  apply_settings(settings)
  if not boot_timer_armed then
    boot_timer_armed = true
    obs.timer_add(on_boot_once, 1500)
  end
  if not sync_armed then
    sync_armed = true
    obs.timer_add(sync_cam_layout, 400)
    obs.script_log(
      obs.LOG_INFO,
      "PiGreco cam layout sync attivo (Cam PIP / StreamCam eye → overlay cam=; Cam 2 indipendente)"
    )
  end
end

function script_unload()
  if boot_timer_armed then
    obs.timer_remove(on_boot_once)
    boot_timer_armed = false
  end
  if sync_armed then
    obs.timer_remove(sync_cam_layout)
    sync_armed = false
  end
  last_sync_key = ""
end

function script_update(settings)
  apply_settings(settings)
end

function apply_settings(settings)
  local raw = obs.obs_data_get_string(settings, "pack_root") or ""
  raw = trim(raw)
  if raw ~= "" then
    pack_root_cached = raw
  else
    pack_root_cached = guess_pack_root() or ""
  end
end

function on_boot_once()
  obs.timer_remove(on_boot_once)
  boot_timer_armed = false
  ensure_server(false)
end

function on_ensure_clicked(props, prop)
  ensure_server(false)
  return true
end

function trim(s)
  return (tostring(s):gsub("^%s+", ""):gsub("%s+$", ""))
end

function path_join(a, b)
  a = tostring(a):gsub("[/\\]+$", "")
  b = tostring(b):gsub("^[/\\]+", "")
  return a .. "\\" .. b
end

function file_exists(path)
  local f = io.open(path, "r")
  if not f then return false end
  f:close()
  return true
end

function guess_pack_root()
  local sp = script_path()
  if sp and sp ~= "" then
    sp = sp:gsub("[/\\]+$", "")
    if sp:lower():match("%.lua$") then
      sp = sp:gsub("[/\\][^/\\]+$", "")
    end
    local scripts_dir = sp
    local obs_dir = scripts_dir:gsub("[/\\][^/\\]+$", "")
    local root = obs_dir:gsub("[/\\][^/\\]+$", "")
    if file_exists(path_join(root, "tools\\ensure_config_server_silent.vbs")) then
      return root
    end
    if file_exists(path_join(root, "tools\\ensure_config_server.py")) then
      return root
    end
  end
  return nil
end

function to_wide(str)
  if not ffi_ok or not kernel32 then return nil end
  str = tostring(str)
  local n = kernel32.MultiByteToWideChar(CP_UTF8, 0, str, #str, nil, 0)
  if n <= 0 then return nil end
  local buf = ffi.new("wchar_t[?]", n + 1)
  kernel32.MultiByteToWideChar(CP_UTF8, 0, str, #str, buf, n)
  buf[n] = 0
  return buf
end

function shell_execute_hidden(file, params)
  if not ffi_ok or not shell32 then
    return false, "ffi/shell32 unavailable"
  end
  local wfile = to_wide(file)
  local wparams = to_wide(params or "")
  local wop = to_wide("open")
  if not wfile or not wop then
    return false, "wide conversion failed"
  end
  local ret = shell32.ShellExecuteW(nil, wop, wfile, wparams, nil, SW_HIDE)
  local code = tonumber(ffi.cast("intptr_t", ret)) or 0
  if code > 32 then
    return true, code
  end
  return false, code
end

function ensure_server(quiet)
  local root = pack_root_cached
  if root == "" then
    root = guess_pack_root() or ""
    pack_root_cached = root
  end
  if root == "" then
    if not quiet then
      obs.script_log(
        obs.LOG_WARNING,
        "PiGreco config autostart: imposta «Cartella pack» nelle proprietà dello script"
      )
    end
    return
  end

  local vbs = path_join(root, "tools\\ensure_config_server_silent.vbs")
  if not file_exists(vbs) then
    if not quiet then
      obs.script_log(obs.LOG_ERROR, "PiGreco: file mancante " .. vbs)
    end
    return
  end

  local ok, info = shell_execute_hidden(
    "wscript.exe",
    '//nologo "' .. vbs .. '"'
  )
  if ok then
    if not quiet then
      obs.script_log(obs.LOG_INFO, "PiGreco config server launch OK (ShellExecute hidden)")
    end
    return
  end

  obs.script_log(
    obs.LOG_WARNING,
    string.format(
      "PiGreco: avvio silenzioso fallito (%s). Usa Start-ConfigPanel.bat.",
      tostring(info)
    )
  )
end

-- ---------------------------------------------------------------------------
-- Face-cam layout sync (no process spawn — safe timer)
-- Prefer "Cam PIP" eye (nested face block). Fallback: direct "StreamCam"
-- (e.g. Rec Triplo Live band slot).
-- Cam 2 PIP is independent — never drives live-chrome cam= query.
-- ---------------------------------------------------------------------------

local OVERLAY_NAMES = {
  ["Overlay Live Chrome"] = true,
  ["Overlay Replay Chrome"] = true,
  ["Overlay Triple Frame Live"] = true,
}

function set_url_cam(url, cam_on)
  local val = cam_on and "1" or "0"
  if url:find("[?&]cam=") then
    return (url:gsub("([?&]cam=)[^&]*", "%1" .. val, 1))
  end
  if url:find("?", 1, true) then
    return url .. "&cam=" .. val
  end
  return url .. "?cam=" .. val
end

function refresh_browser(source)
  local handler = obs.obs_source_get_proc_handler(source)
  if handler == nil then
    return
  end
  local cd = obs.calldata_create()
  local ok = obs.proc_handler_call(handler, "refresh_cache", cd)
  if not ok then
    obs.proc_handler_call(handler, "webpage_refresh_cache", cd)
  end
  obs.calldata_destroy(cd)
end

function apply_cam_to_browser(source, cam_on)
  local settings = obs.obs_source_get_settings(source)
  local url = obs.obs_data_get_string(settings, "url") or ""
  local new_url = set_url_cam(url, cam_on)
  if new_url ~= url then
    obs.obs_data_set_string(settings, "url", new_url)
    obs.obs_source_update(source, settings)
    refresh_browser(source)
  end
  obs.obs_data_release(settings)
end

function sync_cam_layout()
  local scene_source = obs.obs_frontend_get_current_scene()
  if scene_source == nil then
    return
  end

  local scene_name = obs.obs_source_get_name(scene_source) or ""
  local scene = obs.obs_scene_from_source(scene_source)
  if scene == nil then
    obs.obs_source_release(scene_source)
    return
  end

  local items = obs.obs_scene_enum_items(scene)
  local face_found = false
  local face_visible = false
  local stream_found = false
  local stream_visible = false

  if items ~= nil then
    for _, item in ipairs(items) do
      local src = obs.obs_sceneitem_get_source(item)
      local name = obs.obs_source_get_name(src) or ""
      -- Face block only (Cam 2 PIP ignored on purpose)
      if name == "Cam PIP" then
        face_found = true
        face_visible = obs.obs_sceneitem_visible(item)
      elseif name == "StreamCam" then
        stream_found = true
        stream_visible = obs.obs_sceneitem_visible(item)
      end
    end
  end

  -- Prefer Cam PIP; else bare StreamCam (triple band / legacy)
  local cam_found = face_found or stream_found
  local cam_visible = false
  if face_found then
    cam_visible = face_visible
  elseif stream_found then
    cam_visible = stream_visible
  end

  if not cam_found then
    if items ~= nil then
      obs.sceneitem_list_release(items)
    end
    obs.obs_source_release(scene_source)
    return
  end

  local key = scene_name .. "|" .. tostring(cam_visible)
  if key == last_sync_key then
    if items ~= nil then
      obs.sceneitem_list_release(items)
    end
    obs.obs_source_release(scene_source)
    return
  end
  last_sync_key = key

  if items ~= nil then
    for _, item in ipairs(items) do
      local src = obs.obs_sceneitem_get_source(item)
      local name = obs.obs_source_get_name(src) or ""
      if OVERLAY_NAMES[name] then
        apply_cam_to_browser(src, cam_visible)
      end
    end
    obs.sceneitem_list_release(items)
  end

  obs.obs_source_release(scene_source)
end
