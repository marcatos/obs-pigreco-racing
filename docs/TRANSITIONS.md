# Transizioni scena OBS

Ogni cambio scena usa di default lo **Stinger** brandizzato (~0.85 s) con whoosh.

## S.Marcato 42

| Transizione | Tipo | Note |
|-------------|------|------|
| **S.Marcato Stinger** (default) | Stinger WebM | Dual-blade carbon + ice, mark **42** rosso, whoosh |
| Swipe Racing | Swipe | Alternativa veloce |
| Slide Racing | Slide | |
| Flash Carbon | Fade to color | Flash sul carbon |
| Dissolvenza / Taglio | Built-in | |

Asset: `overlays-marcato/stinger/marcato-stinger.webm`  
Rigenera: `python tools/generate_stinger.py --profile marcato --with-whoosh`

## PiGreco Racing

| Transizione | Tipo |
|-------------|------|
| **PiGreco Stinger** (default) | Wipe verde/blu + π + whoosh |
| Swipe / Slide / Flash / Fade | Come sopra |

Asset: `overlays/stinger/pigreco-stinger.webm`  
Rigenera: `python tools/generate_stinger.py --profile pigreco --with-whoosh`

## Dopo regenerate pack

```powershell
python tools/generate_pack.py --profile marcato
# chiudi OBS, copia obs\S_Marcato_42.json in %APPDATA%\obs-studio\basic\scenes\
```

In OBS: dock **Transizioni scene** → deve risultare selezionato lo Stinger. Prova Starting Soon → Live Race.

### Regolare il punto di taglio

Stinger → proprietà → **Transition Point** (~420 ms = metà copertura). Se taglia troppo presto/tardi, sposta di ±50 ms.
