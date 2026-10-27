"""Propiedades del emisor de lasers.

Conserva todas las opciones del script original de discoteca y anade el
bloque de audio que hace que los rayos sigan el ritmo de la cancion.
"""

import math

import bpy
from bpy.props import (BoolProperty, CollectionProperty, EnumProperty,
                       FloatProperty, FloatVectorProperty, IntProperty,
                       StringProperty)

from ..audio.triggers import BEAM_TRIGGERS
from ..core import constants as K
from . import presets, updates

PATTERN_ITEMS = [
    ('FAN', "Abanico", "Plano de rayos como en la referencia 2"),
    ('CONE', "Cono", "Rayos en espiral dentro de un cono"),
    ('CROSS', "Cruz", "Dos abanicos perpendiculares"),
]

class LZ_Settings(bpy.types.PropertyGroup):
    # ------------------------------------------------------------ identidad
    is_rig: BoolProperty(default=False)
    uid: StringProperty(default="")
    auto_update: BoolProperty(
        name="Actualizar en vivo", default=True,
        description="Recalcula al mover objetos (en reproduccion lo hace cada frame)")
    style_preset: EnumProperty(
        name="Estilo", default='DISCO', items=presets.STYLE_PRESETS,
        description="Configuracion completa de un clic (boton Aplicar)")

    # ----------------------------------------------------------------- rayos
    count: IntProperty(name="Cantidad", default=24, min=1, max=K.MAX_BEAMS,
                       soft_max=128, update=updates.on_settings_update)
    pattern: EnumProperty(name="Patron", default='FAN', items=PATTERN_ITEMS,
                          update=updates.on_settings_update)
    spread: FloatProperty(name="Apertura", subtype='ANGLE', default=math.radians(70),
                          min=0.0, max=math.radians(179),
                          update=updates.on_settings_update)
    intensity: FloatProperty(name="Intensidad", default=6.0, min=0.0, soft_max=30.0,
                             update=updates.on_settings_update)
    width: FloatProperty(name="Grosor", subtype='DISTANCE', default=0.012,
                         min=0.0005, soft_max=0.1, precision=4,
                         update=updates.on_settings_update)
    divergence: FloatProperty(
        name="Divergencia", default=0.001, min=0.0, soft_max=0.01, precision=4,
        description="Cuanto se ensancha el rayo por metro recorrido",
        update=updates.on_settings_update)
    max_distance: FloatProperty(name="Alcance", subtype='DISTANCE', default=40.0,
                                min=0.1, soft_max=200.0,
                                update=updates.on_settings_update)
    end_fade: FloatProperty(
        name="Desvanecer sin impacto", default=0.6, min=0.0, max=1.0,
        description="Los rayos que no chocan con nada se apagan hacia el final",
        update=updates.on_settings_update)
    sides: IntProperty(name="Caras del tubo", default=4, min=3, max=8,
                       update=updates.on_settings_update)

    # ------------------------------------------------------------ colisiones
    max_bounces: IntProperty(name="Rebotes max.", default=2, min=0, max=8,
                             update=updates.on_settings_update)
    reflect: FloatProperty(name="Reflectividad", default=0.9, min=0.0, max=1.0,
                           update=updates.on_settings_update)
    auto_mirror: BoolProperty(
        name="Detectar metal liso", default=True,
        description="Material Principled con Metallic>=0.95 y Roughness<=0.12 = espejo",
        update=updates.on_settings_update)

    # ---------------------------------------------------------------- color
    # El reparto del color entre rayos es el mismo para rayos y luces:
    # vive en ``scene.al.color_spread`` (panel "Colores").
    color_speed: FloatProperty(
        name="Giro de color sin audio (/s)", default=0.0,
        description="Gira el color de los rayos por tiempo. Con audio activo el "
                    "color lo marca el ritmo (panel Colores)",
        soft_min=-8.0, soft_max=8.0, update=updates.on_settings_update)

    # ------------------------------------------------------------ animacion
    speed: FloatProperty(name="Velocidad", default=1.0, min=0.0, soft_max=8.0,
                         update=updates.on_settings_update)
    time_offset: FloatProperty(name="Desfase (s)", default=0.0,
                               update=updates.on_settings_update)
    sweep: FloatProperty(name="Barrido", subtype='ANGLE', default=math.radians(18),
                         min=0.0, max=math.radians(90),
                         update=updates.on_settings_update)
    spin: FloatProperty(name="Giro (grados/s)", default=25.0, min=-720.0,
                        max=720.0, update=updates.on_settings_update)
    wave: FloatProperty(name="Onda por rayo", subtype='ANGLE',
                        default=math.radians(6), min=0.0, max=math.radians(45),
                        update=updates.on_settings_update)
    wave_cycles: FloatProperty(name="Ciclos de onda", default=2.0, min=0.0,
                               soft_max=12.0, update=updates.on_settings_update)
    breath: FloatProperty(name="Respiracion", default=0.3, min=0.0, max=0.9,
                          description="Abre y cierra el abanico",
                          update=updates.on_settings_update)
    # ---------------------------------------------------------------- loop
    # La animacion entera (barrido, giro, onda por rayo, respiracion, color,
    # pulso y la reaccion al audio) se repite entre dos frames; por defecto el
    # frame END es igual al frame START (ver ``looping.py``).
    loop_anim: BoolProperty(
        name="Loopear animacion", default=False,
        description="Repite la animacion del rig entre los dos frames de "
                    "abajo, sin saltos al cerrar el ciclo (velocidad y demas "
                    "ajustes siguen en este panel)",
        update=updates.on_settings_update)
    loop_start: IntProperty(
        name="Desde el frame", default=1, min=0,
        update=updates.on_settings_update)
    loop_end: IntProperty(
        name="Hasta el frame", default=250, min=1,
        description="Ultimo frame del bucle (incluido). Despues de este frame "
                    "vuelve a empezar desde el primero",
        update=updates.on_settings_update)
    loop_close_end: BoolProperty(
        name="Ultimo frame = primero", default=True,
        description="El frame final es identico al inicial (el loop dura "
                    "fin - inicio frames). Apagado: el loop dura fin - inicio + 1 "
                    "frames y es el frame fin + 1 el que coincide con el inicio",
        update=updates.on_settings_update)
    loop_audio_blend: BoolProperty(
        name="Suavizar el audio en la costura", default=True,
        description="Con una cancion real, mezcla el ultimo beat del loop con "
                    "lo que suena justo antes del inicio para que brillo, "
                    "apertura, estrobo y colores continuos no den un salto. "
                    "No hace falta con el Loop por BPM",
        update=updates.on_settings_update)

    bpm: FloatProperty(
        name="BPM", default=120.0, min=1.0, soft_max=220.0,
        description="BPM del pulso. Si el rig reacciona al audio se usa el de la "
                    "cancion automaticamente",
        update=updates.on_settings_update)
    pulse: FloatProperty(name="Pulso (estrobo)", default=0.0, min=0.0, max=1.0,
                         update=updates.on_settings_update)
    chase: FloatProperty(
        name="Persecucion (beats)", default=0.5, min=0.0, soft_max=4.0,
        description="Desfase entre rayos: retrasa cada rayo respecto al anterior. "
                    "Sirve para el pulso por BPM y para la ola de la reaccion al audio",
        update=updates.on_settings_update)

    # ------------------------------------------------------------- impactos
    show_hits: BoolProperty(name="Puntos de impacto", default=True,
                            update=updates.on_settings_update)
    dot_size: FloatProperty(name="Tamano punto", subtype='DISTANCE', default=0.04,
                            min=0.001, soft_max=0.5,
                            update=updates.on_settings_update)
    dot_intensity: FloatProperty(name="Brillo punto", default=1.5, min=0.0,
                                 soft_max=10.0, update=updates.on_settings_update)
    max_lights: IntProperty(
        name="Luces reales", default=6, min=0, max=K.MAX_LIGHTS,
        description="Point lights reales en los impactos (iluminan el entorno en EEVEE)",
        update=updates.on_settings_update)
    light_power: FloatProperty(name="Potencia luces (W)", default=30.0, min=0.0,
                               soft_max=500.0, update=updates.on_settings_update)

    # ---------------------------------------------------------------- audio
    audio_enabled: BoolProperty(
        name="Reaccionar al audio", default=False,
        description="Los rayos siguen el ritmo de la fuente configurada arriba "
                    "(cancion analizada o loop por BPM). Se activa solo al encender "
                    "cualquier reaccion (Color, Brillo...)",
        update=updates.on_settings_update)
    audio_trigger: EnumProperty(
        name="Reacciona a", default='KICK', items=BEAM_TRIGGERS,
        update=updates.on_settings_update)
    # Que aspectos del rayo siguen el ritmo (se pueden combinar libremente)
    audio_on_brightness: BoolProperty(
        name="Brillo", default=True, update=updates.on_audio_toggle,
        description="La intensidad de los rayos sigue el ritmo")
    audio_on_spread: BoolProperty(
        name="Apertura", default=True, update=updates.on_audio_toggle,
        description="El abanico se abre y se cierra con el ritmo")
    audio_on_speed: BoolProperty(
        name="Movimiento", default=False, update=updates.on_audio_toggle,
        description="El barrido y el giro aceleran con la musica")
    audio_on_color: BoolProperty(
        name="Color", default=True, update=updates.on_audio_toggle,
        description="Los colores cambian con el ritmo. La paleta y el modo de "
                    "cambio son los del panel 'Colores (rayos y luces)'")
    audio_brightness: FloatProperty(
        name="Audio en el brillo", default=0.6, min=0.0, max=1.0,
        description="Cuanto manda el nivel de audio en la intensidad "
                    "(0 = constante, 1 = solo el audio)",
        update=updates.on_settings_update)
    audio_spread: FloatProperty(
        name="Audio en la apertura", default=0.3, min=0.0, max=1.0,
        description="El abanico se abre en los picos y se cierra en los silencios",
        update=updates.on_settings_update)
    audio_speed: FloatProperty(
        name="Audio en la velocidad", default=0.4, min=0.0, max=1.0,
        description="Acelera el movimiento cuando la musica sube",
        update=updates.on_settings_update)
    audio_strobe: BoolProperty(
        name="Estrobo desde el audio", default=False,
        description="Usa el nivel de audio como disparador del pulso "
                    "en lugar del BPM escrito arriba",
        update=updates.on_settings_update)
    audio_color_chase: FloatProperty(
        name="Ola de color (beats)", default=0.0, min=0.0, max=16.0,
        description="Desfase de color entre rayos: el color recorre el abanico "
                    "(el modo y la paleta se eligen en el panel Colores)",
        update=updates.on_settings_update)
