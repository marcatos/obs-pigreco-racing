# Transizioni scena OBS

Il cambio scena di default usa **Move Transition** (plugin Exeldro): le source presenti in entrambe le scene (es. `StreamCam`) si morfano in posizione/scala; quelle che spariscono escono animate; quelle nuove entrano animate (~650 ms).

## Prerequisito: plugin Move

Deve essere installato **Move** di Exeldro:

- Download: https://obsproject.com/forum/resources/move.913/
- DLL attesa: `C:\Program Files\obs-studio\obs-plugins\64bit\move-transition.dll`

Senza il plugin, OBS non caricherà la transizione Move nella collection.

## S.Marcato 42

| Transizione | Tipo | Note |
|-------------|------|------|
| **S.Marcato Move** (default) | Move | Matched morph; appear da sinistra; disappear a destra |
| S.Marcato Stinger | Stinger WebM | Alternativa brand (dual-blade + whoosh) |
| Swipe Racing | Swipe | |
| Slide Racing | Slide | |
| Flash Carbon | Fade to color | Flash sul carbon |
| Dissolvenza / Taglio | Built-in | |

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

In OBS: dock **Transizioni scene** → deve risultare selezionato **S.Marcato Move** (o PiGreco Move). Prova Starting Soon → Live Race: la cam deve spostarsi tra le due layout; overlay e game entrano/escono.

### Alternativa stinger

Se preferisci il wipe brandizzato: dock Transizioni → **S.Marcato Stinger** / **PiGreco Stinger**.  
Stinger → proprietà → **Transition Point** (~420 ms). Se taglia troppo presto/tardi, sposta di ±50 ms.
