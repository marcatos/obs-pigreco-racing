# Marcato Live: Game Capture + Headcam + pedals

**Date:** 2026-08-19  
**Plane:** OBSPI — Marcato Live: Game Capture + Headcam + pedals  
**Scope:** `S.Marcato 42` live collection only (`build_marcato_live_collection`)

## Goal

Two scenic live modes for iRacing with three cams (no work USB Camera):

1. **Live** — Game Capture (iRacing window) + StreamCam face PiP + Creative pedals PiP; Desktop + mic audio.
2. **Headcam** — Logitech Brio fullscreen + Creative pedals PiP ON; no Game Capture / Monitor; same Desktop + mic (game audio).

## Decisions

- Approach A: top-level scenes + nested independent PiP eyes.
- Keep nested name **Cam PIP** for face (Lua `pigreco_config_autostart.lua` sync).
- Pedals nested as **Cam Pedals PIP** (Creative Live! Cam Sync 1080p V2); no NVIDIA VB.
- Brio: no NVIDIA VB; fullscreen on Headcam only.
- USB Camera stays out of Live (still may appear on Replay/Rec until a follow-up).
- Headcam chrome: live-chrome `?cam=0` + same broadcast telecronaca as Live (track map eye-off); no flag FX (face cam).

## Acceptance

- Scene order includes Live and Headcam.
- Live sources include Game Capture, Cam PIP, Cam Pedals PIP; no USB Camera source.
- Headcam: Cam Head + live chrome + broadcast chrome + Cam Pedals PIP + mic; no Game Capture item.
- Automated Marcato live tests pass.
