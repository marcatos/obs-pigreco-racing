# Transizioni scena OBS

Il cambio scena di default usa **Move Transition** (plugin Exeldro): le source presenti in entrambe le scene (es. `StreamCam`) si morfano in posizione/scala; quelle che spariscono escono animate; quelle nuove entrano animate (~650 ms).

## Prerequisito: plugin Move

Deve essere installato **Move** di Exeldro:

- Download: https://obsproject.com/forum/resources/move.913/
- DLL attesa: `C:\Program Files\obs-studio\obs-plugins\64bit\move-transition.dll`

Senza il plugin, OBS non caricherà la transizione Move nella collection.

## S.Marcato 42

Default collection transition: **Dissolvenza 900 ms** — full mix crossfade (beds, Desktop, mic dissolve together; no hard audio cut mid-fade).

| Transizione | Tipo | Note |
|-------------|------|------|
| **Dissolvenza** (default) | Fade | 900 ms; audio-aware crossfade |
| **S.Marcato Stinger** | Stinger WebM | Override **→ Live** and **→ Ending** (dual-blade + Opus whoosh) |
| S.Marcato Move | Move | Opzionale (matched morph racing preset) |
| Swipe Racing | Swipe | |
| Slide Racing | Slide | |
| Flash Carbon | Fade to color | Flash sul carbon |
| Taglio | Cut | Emergency / quick hard-cut |

**Quick transitions** (dock Transizioni): Dissolvenza · Stinger · Taglio.

Scene **transition overrides** (set by `generate_pack.py --profile marcato`): switching **to Live** or **to Ending** uses **S.Marcato Stinger** instead of Dissolvenza.

> **Monitoring:** judge crossfades from **stream or recording**, not headphones alone — OBS “Monitor only” may not mirror the full mix fade.

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

In OBS: dock **Transizioni scene** → **Dissolvenza** (900 ms) per Marcato; **PiGreco Move** per PiGreco. Prova Starting Soon → Lobby → Live: beds crossfade on Dissolvenza; Live/Ending use Stinger + whoosh.

### Alternativa stinger

Se preferisci il wipe brandizzato: dock Transizioni → **S.Marcato Stinger** / **PiGreco Stinger**.  
Stinger → proprietà → **Transition Point** (~420 ms). Se taglia troppo presto/tardi, sposta di ±50 ms.
