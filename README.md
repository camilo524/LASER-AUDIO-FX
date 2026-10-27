# Laser Audio FX (Blender 4.2+ / 5.x)

Addon que unifica los dos scripts originales en **un solo plugin estructurado**:

| Script original | Ahora vive en | Que aporta |
|---|---|---|
| `laser_fx_discoteca.py` | `laser_audio_fx/lasers/` | Rayos laser procedurales con colision real, rebotes en espejos, impactos con luces y todas sus opciones de personalizacion |
| `audio_lights_sync.py` | `laser_audio_fx/audio/` + `lights/` | Analisis de la cancion (BPM, beats, bombos, secciones), bake de keyframes, paletas, marcadores y export a DaVinci Resolve |

La union no es solo juntar archivos: **el motor de lasers ahora usa las mismas
herramientas de audio**, asi que los rayos cambian de color, brillo, apertura y
velocidad al ritmo de la cancion, sin depender de keyframes.

---

## Instalacion

1. `Edit > Preferences > Add-ons > Install...` y elige `laser_audio_fx.zip`.
2. Activa **Laser Audio FX**.
3. En la Vista 3D pulsa `N` y abre la pestana **Laser Audio FX**.

Tambien puedes copiar la carpeta `laser_audio_fx` dentro de
`scripts/addons/` (o `extensions/`) del directorio de usuario de Blender.

`build_zip.sh` regenera el ZIP instalable desde el codigo fuente.

---

## Flujo de trabajo rapido

1. **Configura la fuente** (panel principal): elige una cancion y pulsa
   *Analizar cancion*, o usa **Loop por BPM** para trabajar sin audio.
2. **Crea el rig**: panel *Lasers* > *Crear Laser Rig* (aparece en el cursor 3D,
   ya reaccionando al audio).
3. **Ajusta el estilo**: el desplegable de estilo + boton `PRESET`
   (Discoteca, Techno, Show grande, Ambiente, Estrobo, Fuego).
4. **Color y ritmo**: la paleta y el cambio de color estan una sola vez en el
   panel **Colores** (los usan rayos y luces). El boton **Color** del panel
   *Ritmo y color* basta para animar los rayos: no hay que activar nada mas.
5. Pulsa *Reproducir*: el rig se reconstruye en cada frame siguiendo la musica.

Para luces reales (spots, mallas emisivas) usa el panel **Luces**: cualquier
objeto con material se puede agregar (si no tiene emision, se le crea) y ahi
estan *Que animar*, el modo en vivo y *Hornear keyframes*, mas las herramientas
(marcadores, `.edl` para Resolve, spin, sway) en **Herramientas**. Los rayos
laser no se agregan a esa lista: ya siguen el audio por su cuenta.

---

## Estructura del codigo

```
laser_audio_fx/
├── __init__.py            bl_info + registro ordenado de todo el addon
├── core/
│   ├── constants.py       prefijos, limites y paletas (sin bpy)
│   └── utils.py           flags globales, hashing determinista y color
├── audio/                 analisis de audio reutilizable
│   ├── dsp.py             FFT, bandas, BPM, onsets y secciones (solo numpy)
│   ├── loader.py          lectura de mp3/ogg/flac/wav a mono
│   ├── analysis.py        cache del analisis activo
│   ├── curves.py          analisis -> curvas continuas por frame (numpy puro)
│   ├── triggers.py        kick/beat/offbeat/corcheas/compas y plan de eventos
│   ├── colors.py          paletas, secuencias y modo libre por tono
│   ├── targets.py         luz o malla emisiva + fcurves (bake de keyframes)
│   ├── bake.py            horneado de intensidad y color
│   ├── operators.py       analizar, poner la cancion, loop y guardar curvas
│   └── ui.py              panel principal y forma de la onda
├── lasers/                el emisor de rayos
│   ├── properties.py      todas las opciones del rig + bloque de audio
│   ├── updates.py         callbacks que reconstruyen el rig
│   ├── materials.py       material emisivo de los rayos, humo (haze)
│   ├── collision.py       raycast con espejos e ignorados
│   ├── geometry.py        tubos y discos de impacto
│   ├── driver.py          puente audio -> motor (curvas + cache)
│   ├── audio_color.py     color reactivo de cada rayo
│   ├── engine.py          reconstruccion del rig (nucleo)
│   ├── handlers.py        frame handler y modo en vivo
│   ├── presets.py         presets de estilo completos
│   ├── operators.py       crear, presets, marcar, demo, humo...
│   └── ui.py              paneles del rig
└── lights/                sincronizacion de luces (script original de luces)
    ├── properties.py      fuente, rejilla, color, horneado y lista de luces
    ├── operators.py       lista, chase, bake, marcadores, EDL, spin, sway
    └── ui.py              paneles de luces
```

Regla de oro: **nada depende de Blender en `core/` y en el DSP**. `dsp.py` y
`curves.py` solo usan numpy, por eso se pueden probar sin abrir Blender.

---

## Como reaccionan los lasers al audio

`lasers/driver.py` convierte el analisis en **curvas continuas** (una por
trigger) y las cachea. En cada frame el motor solo tiene que muestrear un array,
asi que la reaccion es instantanea y no crea ni un keyframe:

* `audio_trigger` -> que dispara el rig (KICK, BASS, MID, HIGH, FULL, BEAT,
  OFFBEAT, EIGHTHS, DOWNBEAT).
* `audio_brightness` -> cuanto manda el nivel en la intensidad del rayo.
* `audio_spread` -> el abanico se abre en los picos y se cierra en los silencios.
* `audio_speed` -> el movimiento (barrido, giro, onda) acelera con la musica.
* `audio_strobe` -> el pulso de `Movimiento y pulso` se dispara con el audio en
  vez de con el BPM escrito.
* `chase` (**Persecucion**) -> retraso por rayo, que crea olas de luz que
  recorren el abanico. Es el mismo ajuste para el pulso por BPM y para el audio.

**Modos de cambio de color** (`scene.al.color_mode`, panel *Colores*):

| Modo | Que hace |
|---|---|
| No animar | Deja los colores como estan |
| Cambio cada N beats | Salta de color de la paleta siguiendo el ritmo |
| Por seccion | Cambia cuando la cancion cambia de energia (coro, drop) |
| Segun energia | Mas volumen = colores mas altos de la paleta |
| Degradado continuo | Recorre los colores suavemente |
| Espectro (RGB) | Graves al rojo, medios al verde, agudos al azul (solo rayos) |

**Una sola paleta y un solo reparto.** La paleta (10 ranuras o modo Libre) y el
**Reparto del color** (`scene.al.color_spread`: *Desfasado*, *Todos igual*,
*Por bloques*, *Independiente*) viven en el panel *Colores* y los usan por igual
rayos y luces: no hay que configurarlos dos veces. *Ola de color (beats)* hace
que el color viaje por el abanico.

---

## Novedades respecto a los dos scripts

* **Reaccion al audio en vivo** en los lasers (el objetivo central de la union).
* **6 presets de estilo** que configuran todo el rig de un clic, ya con audio.
* **Curvas guardadas en el .blend**: `Guardar curvas en la escena` mete el
  analisis dentro del archivo, asi los lasers siguen reaccionando aunque muevas
  o pierdas el mp3 (sin volver a analizar).
* **Repartir reacciones**: reparte disparadores entre varios rigs para que no
  reaccionen todos igual.
* **Editor de humo** (`Anadir humo (haze)`) para que los haces se vean, ahora
  junto al resto de herramientas en un solo panel.
* Una sola pestana (`Laser Audio FX`) con subpaneles plegables, en lugar de dos
  paneles separados: fuente -> colores -> luces -> lasers (forma, movimiento,
  *Ritmo y color*, impactos) y al final los plegados (audio avanzado,
  herramientas).
* El registro es idempotente: puedes recargar el addon sin errores.

### Corregido en 2.3

* El humo usaba un nodo de volumen inexistente: `Anadir humo (haze)` fallaba en
  Blender 5.2.
* **Cualquier objeto con material se puede agregar** a la lista de luces: si no
  tenia emision se le crea, en vez de ignorarlo en silencio.
* **Los keyframes horneados mandan** sobre el modo en vivo (antes el vivo los
  pisaba al reproducir).
* Encender **Color** (o cualquier reaccion) ya activa *Reaccionar al audio*: los
  rayos se animan con el boton de color, sin agregarlos a la lista de luces.
* Un solo panel de *Ritmo y color* por rig (antes habia dos con el mismo
  interruptor de color).

---

## Notas utiles

* Los rayos se generan en una unica malla con atributo de color, asi que se
  renderizan igual en EEVEE y Cycles.
* Para muchos rayos sube `MAX_BEAMS` en `core/constants.py` (por defecto 512).
* Las luces reales de impacto son caras: sube `Luces reales` solo si lo necesitas.
* El horneado de luces (`Hornear keyframes`) si crea keyframes; los lasers no
  los necesitan porque se recalculan frame a frame.
* Si `Pulso` es 0, no hay estrobo; para que `Estrobo desde el audio` haga algo,
  sube primero `Animacion > Pulso`.
