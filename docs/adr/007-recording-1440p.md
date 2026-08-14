# ADR-007: Recording canvas 2560×1440 (2K)

## Status

Accepted — 2026-08-12

## Context

Gameplay monitors are Odyssey G5 **2560×1440**. ADR-002 keeps the **stream** canvas at 1920×1080 so Twitch/Restream overlays stay simple. Recording that same 1080 canvas throws away native detail.

## Decision

- **Stream** (Live* collections + default profile): stay **1920×1080** (ADR-002).
- **Recording**: dedicated OBS profile **`Rec_2K`** + scene collection **`S.Marcato Rec 2K`** with base/output **2560×1440**.
- Brand overlays (live chrome / triple frame) are the same 1920×1080 HTML artboards, **scaled ×4/3** onto the 2K canvas.
- Clean Rec scenes (no overlay) remain available alongside **Rec * Live** (with graphics + cam).
- **Encoder (recording):** NVIDIA NVENC **HEVC** (`obs_nvenc_hevc_tex`), **VBR 25 Mbps / max 40 Mbps**. H.264 CQP 18 at 1440p60 iRacing produced ~230 Mbps (~29 GB / 17 min) because CQP has no bitrate cap. HEVC VBR stays above YouTube’s 1440p60 recommendation (24 Mbps) with a hard size ceiling (~3–5 GB / 17 min). Split files every 15 minutes.

## Consequences

- Switch profile + collection when you want native 1440p VODs.
- Do not mix 1080 overlay Browser Sources on the 2K canvas without an explicit upscale layout.
- `tools/generate_pack.py --profile marcato` also emits `S_Marcato_Rec_2K.json`.
- Profile template under `obs/profiles/Rec_2K/` (no auth tokens).
