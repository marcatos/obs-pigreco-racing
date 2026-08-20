# Transizioni scena OBS

Il default dipende dal profilo collection:

- **S.Marcato 42:** **S.Marcato Move** (plugin Exeldro, ~650 ms) — morph posizione/scala sulle source matched; appearing/disappearing animate.
- **PiGreco Racing:** **PiGreco Move** (stesso preset racing, ~650 ms).

Dissolvenza e Stinger restano disponibili come alternative manuali; nessuno override per-scena.

## Prerequisito: plugin Move

Deve essere installato **Move** di Exeldro:

- Download: https://obsproject.com/forum/resources/move.913/
- DLL attesa: `C:\Program Files\obs-studio\obs-plugins\64bit\move-transition.dll`

Senza il plugin, OBS non caricherà la transizione Move nella collection.

## S.Marcato 42

Default collection transition: **S.Marcato Move** (~650 ms).

| Transizione | Tipo | Note |
|-------------|------|------|
| **S.Marcato Move** (default) | Move | Matched morph racing preset |
| Dissolvenza | Fade | Alternativa audio-aware (~900 ms) |
| **S.Marcato Stinger** | Stinger WebM | Alternativa brandizzata (dual-blade + Opus whoosh) |
| Swipe Racing | Swipe | |
| Slide Racing | Slide | |
| Flash Carbon | Fade to color | Flash sul carbon |
| Taglio | Cut | Emergency / quick hard-cut |

**Quick transitions** (dock Transizioni): Move · Dissolvenza · Taglio.

`S_Marcato_Replay` condivide lo stesso default (profilo `marcato`) e aggiunge Stinger fra le quick transitions.

Asset stinger: `overlays-marcato/stinger/marcato-stinger.webm`  
Rigenera stinger: `python tools/generate_stinger.py --profile marcato --with-whoosh`

## PiGreco Racing

| Transizione | Tipo |
|-------------|------|
| **PiGreco Move** (default) | Move (stesso preset racing) |
| PiGreco Stinger | Stinger WebM (alternativo) |
| Swipe / Slide / Flash / Fade | Come sopra |

Asset stinger: `overlays/stinger/pigreco-stinger.webm`  
Rigenera: `python tools/generate_stinger.py --profile pigreco --with-whoosh`

## Preset Move (racing)

- Durata: **650 ms**
- Matched: ease-in-out cubic (morph pos/scale)
- Appearing: ease-in cubic, da sinistra, fade, curve −0.5
- Disappearing: ease-out cubic, verso destra, fade, curve −0.5
- Matching: `name_part_match` + `name_number_match`

## Dopo regenerate pack

```powershell
python tools/generate_pack.py --profile marcato
# chiudi OBS, copia obs\S_Marcato_42.json in %APPDATA%\obs-studio\basic\scenes\
```

In OBS: dock **Transizioni scene** → **S.Marcato Move** (Marcato) o **PiGreco Move** (PiGreco). Prova Starting Soon → Lobby → Live.

### Alternativa stinger

Se preferisci il wipe brandizzato: dock Transizioni → **S.Marcato Stinger** / **PiGreco Stinger**.  
Stinger → proprietà → **Transition Point** (~420 ms). Se taglia troppo presto/tardi, sposta di ±50 ms.
