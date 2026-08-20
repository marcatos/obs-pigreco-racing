# Dual / triple cam + sfondo virtuale

## Pack Live `S.Marcato 42`

| Source | Ruolo | Occhio OBS |
|--------|--------|------------|
| **Cam PIP** | Faccia (basso sinistra) = StreamCam + carbon + NVIDIA | on / off **da sola** |
| **Cam Pedals PIP** | Creative Live pedali (basso destra) + carbon, **senza** NVIDIA; crop zoom piedi/pedali | on / off **da sola** |
| **Cam Head** | Logitech Brio 4K fullscreen | solo scena **Headcam** |

| Scena | Video | Cam di default |
|-------|--------|----------------|
| **Live** | Game Capture iRacing | Face ON + Pedals ON |
| **Headcam** | Brio fullscreen (niente Game Capture / Monitor) | Pedals ON; telecronaca come Live; audio Desktop + mic |

USB Camera (Windows Hello / lavoro) **non** è nel pack Live.

Combinazioni tipiche su Live:

| Cam PIP | Cam Pedals PIP | Risultato |
|---------|----------------|-----------|
| ON | ON | faccia + pedali |
| ON | OFF | solo faccia |
| OFF | ON | solo pedali |
| OFF | OFF | nessuna cam PiP |

Non toccare StreamCam / Cam Pedals dentro le nested scene: usa solo gli occhi di **Cam PIP** e **Cam Pedals PIP**.

## Sfondo virtuale (solo faccia)

Filtro **NVIDIA Background Removal** (mode **Quality + Chair**) su **StreamCam**, solo se è installato il redistributable **NVIDIA Video Effects**.

Dietro: lastra carbon brand (`Cam Backdrop Face`).

**Obbligatorio per il VB (RTX 4070 = Ada / 40 Series):**

1. Scarica **Video Effects** per **RTX 40 Series** da  
   https://www.nvidia.com/en-us/geforce/broadcasting/broadcast-sdk/resources/
2. Installa, riavvia OBS.
3. Rigenera il pack: `python tools/generate_pack.py --profile marcato`

Senza SDK il generatore **non** attacca il filtro (altrimenti è no-op e può rendere la PiP scattosa).

StreamCam capture: **1280×720 @ 30 fps MJPEG** (scala sul PiP 360×202; NV Background Removal a interval 1).

**Cam Pedals** e **Cam Head** sono senza NVIDIA (rig / headcam reali).

Serve OBS con `nv-filters` (incluso in OBS recenti) + Video Effects installato.

## Replay / Rec (legacy dual cam)

Su `S.Marcato Replay` / Rec 2K restano **Cam PIP** + **Cam 2 PIP** (USB Camera sedile) finché non allineati al kit Live.

## Uso in OBS

1. Chiudi OBS → reimporta / seleziona **S.Marcato 42**.
2. **Live** ↔ **Headcam** = cambio scena (director cut).
3. Nascondi **Cam PIP** → sparisce il riquadro CAM faccia (script Lua `?cam=0`).
4. Nascondi **Cam Pedals PIP** → sparisce solo i pedali.
5. Se una cam è nera: Properties sul device corretto (StreamCam / Creative / Brio).

## Verifica dopo regen

Dopo `python tools/generate_pack.py --profile marcato`:

1. Nested **Cam PIP** → device **Logitech StreamCam**.
2. Nested **Cam Pedals PIP** → **Creative Live! Cam Sync 1080p V2**.
3. **Cam Head** → **Logitech BRIO**.
4. Se USB cambia porta: ripesca in OBS, aggiorna `STREAMCAM_ID` / `BRIO_ID` / `CREATIVE_ID` in `tools/generate_pack.py` e rigenera.

## Exposure presets (UVC)

Driver-level exposure/gain/WB for the three Live cams live in **Fix MiniBeast**:

`C:\Users\simot\Documents\Projects\fixminibeast\tools\webcam-presets\`

| Role | Device | Preset |
|------|--------|--------|
| headcam | Logitech BRIO | `presets/headcam-brio.json` |
| face | Logitech StreamCam | `presets/face-streamcam.json` |
| pedals | Creative Live! Cam Sync 1080p V2 | `presets/pedals-creative.json` |

Boot order before going live:

1. In Logitech G HUB, disable webcam auto/effects control (once) — G HUB can overwrite UVC.
2. Run `Apply-WebcamPresets.cmd` or `dotnet run --project …WebcamPresets.Cli -c Release -- apply --role all`.
3. Open OBS (`S.Marcato 42`) and check **Headcam** + Live PiPs.

Headcam preset: manual exposure (typically −9), gain 0, backlight compensation **off** — counters screen + LED washout.

## Non usare

- USB Camera (lavoro / Hello) nel pack Live.
- NVIDIA Broadcast come unica Virtual Camera per più device.
- Accoppiare gli occhi Cam PIP / Cam Pedals PIP.
