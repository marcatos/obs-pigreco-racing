# OBS VirtualDeck (iPhone) — WebSocket setup

Control **S.Marcato 42** (and other collections) from the **OBS VirtualDeck** app on iPhone over the local network. No extra OBS plugin is required on **OBS Studio 28+** — WebSocket is built in.

Related: Session Director ([`SESSION_DIRECTOR.md`](SESSION_DIRECTOR.md)), button map ([`adapters/streamdeck/marcato-live-deck.json`](../adapters/streamdeck/marcato-live-deck.json)).

## 1. Enable WebSocket on this PC

1. Open **OBS Studio**.
2. **Tools → WebSocket Server Settings**.
3. Check **Enable WebSocket server**.
4. Port: **4455** (default — keep unless you change Session Director config too).
5. Keep **Enable authentication** on; set a password (or use the generated one).
6. Click **Show Connect Info** — note **Server IP**, port, password.

Optional checklist script (prints LAN IPv4 hints, no secrets):

```powershell
python tools\check_obs_websocket.py
```

## 2. Firewall

Allow **inbound TCP 4455** from your LAN (Windows Defender Firewall) so the phone can reach the PC. Same Wi‑Fi / subnet required (unless you use a VPN/proxy the app supports).

## 3. Connect OBS VirtualDeck

1. Install **OBS VirtualDeck** on the iPhone.
2. Enter:
   - Host = PC LAN IP from Connect Info (not `127.0.0.1` — that is loopback on the phone)
   - Port = `4455`
   - Password = OBS WebSocket password
3. Connect. The app should list scenes from the active collection.

## 4. Recommended buttons (S.Marcato 42 slim)

| Button | Action |
|--------|--------|
| Starting Soon | Switch scene |
| Live | Switch scene |
| Lobby | Switch scene |
| BRB | Switch scene |
| Ending | Switch scene |
| Reset Session | Clear session state |
| Start / Stop Stream | OBS stream |
| Start / Stop Record | OBS record |

Flags are **overlay FX on Live** (telemetry) — no Flag * buttons on the slim deck.

Full checklist: `adapters/streamdeck/marcato-live-deck.json`.

**Note:** `Reset Session` clears telemetry, overlay, replay, and director continuity, then returns automatically to the previous `Live` or `Headcam` scene. Session Director full-auto will re-assert `Live` or `Lobby` from telemetry when you are on those “race” scenes. It will **not** yank you out of Starting Soon / BRB / Ending — use VirtualDeck for show flow.

## 5. Session Director password

Put the same OBS password in gitignored:

`adapters/obs_flag_director/config.local.json` → `obsPassword`

Never commit that file. Example keys: `adapters/obs_flag_director/config.example.json`.

## Troubleshooting

| Symptom | Check |
|---------|--------|
| App cannot connect | Same Wi‑Fi; firewall; WebSocket enabled; correct LAN IP |
| Scenes missing | Active collection is **S.Marcato 42** (reimport after `generate_pack.py --profile marcato`) |
| Auto fights manual cuts | On Starting Soon/BRB/Ending auto is idle; on Live/Lobby it resumes after debounce |
| Flag Director dry-run | Set `dryRun: false` in `config.local.json` |
