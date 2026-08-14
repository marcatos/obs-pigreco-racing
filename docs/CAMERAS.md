# Dual cam + sfondo virtuale (P1-04)

## Cosa fa il pack

| Source | Ruolo | Occhio OBS |
|--------|--------|------------|
| **Cam PIP** | Faccia (basso sinistra) = StreamCam + carbon + NVIDIA | on / off **da sola** |
| **Cam 2 PIP** | USB Camera sedile (basso destra) + carbon + NVIDIA | on / off **da sola** |

Combinazioni supportate:

| Cam PIP | Cam 2 PIP | Risultato |
|---------|-----------|-----------|
| ON | ON | entrambe |
| ON | OFF | solo faccia |
| OFF | ON | solo sedile |
| OFF | OFF | nessuna cam |

Non toccare StreamCam / Cam 2 dentro le nested scene: usa solo gli occhi di **Cam PIP** e **Cam 2 PIP**.

## Sfondo virtuale

Filtro **NVIDIA Background Removal** in mode **Quality + Chair** (tiene sedile e microfono, toglie la stanza).
Dietro: lastra carbon brand (`Cam Backdrop *`).

Serve OBS con `nv-filters` e **NVIDIA Video Effects / Broadcast** installati.

## Uso in OBS

1. Chiudi OBS → reimporta `S.Marcato Replay` / `S.Marcato Rec 2K`.
2. Nella scena, occhio indipendente su **Cam PIP** e **Cam 2 PIP**.
3. Nascondi **Cam PIP** → il lower-third torna a sinistra (script Lua).
4. Nascondi **Cam 2 PIP** → sparisce solo la cam destra (nessun effetto sul lower-third).
5. Se una cam è nera: apri la nested scene → Properties sul device corretto.

## Non usare

- NVIDIA Broadcast come unica Virtual Camera per entrambe (ne gestisce una sola).
- Mode senza “chair” se vuoi vedere il sedile.
- Accoppiare i due occhi: devono restare indipendenti.

## Note

- StreamCam staccata: Status Unknown in Windows — ricollegala o ripesca il device in OBS.
- Guida breve anche in `obs/profiles/Rec_2K/LEGGIMI.txt` e `replays/LEGGIMI.txt`.
