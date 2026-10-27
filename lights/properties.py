"""Propiedades de la sincronizacion de luces (reaccion, paleta y horneado)."""

import bpy
from bpy.props import (BoolProperty, CollectionProperty, EnumProperty,
                       FloatProperty, FloatVectorProperty, IntProperty,
                       PointerProperty, StringProperty)

from ..audio import colors as acolors
from ..audio.triggers import TRIGGERS
from ..core import utils
from ..core.constants import AUDIO_PALETTE_SLOTS

PALETTE_PRESET_ITEMS = [
    ('RGB', "Rojo / Verde / Azul", ""),
    ('NEON', "Neon (Cian / Magenta / Violeta)", ""),
    ('NEON2', "Neon arcade (Rosa / Cian / Verde / Amarillo)", ""),
    ('FUEGO', "Fuego (Rojo / Naranja / Amarillo)", ""),
    ('BAR', "Bar (Naranja / Rosa / Violeta / Azul)", ""),
    ('WARM', "Calido", ""),
    ('COLD', "Frio", ""),
    ('VERDE', "Solo verde", ""),
    ('ROJO', "Solo rojo", ""),
    ('AZUL', "Solo azul", ""),
    ('BLANCO', "Solo blanco", ""),
    ('TODOS', "Todos los colores", ""),
    ('CUSTOM', "Personalizada", "Elige tu mismas las ranuras"),
]


def _refresh_rigs(self, context):
    """Cambio de paleta / color: los rayos se recalculan al instante."""
    if utils.is_muted():
        return
    try:
        from ..lasers import engine
        scene = self.id_data if isinstance(self.id_data, bpy.types.Scene) else context.scene
        engine.update_all(scene)
    except Exception as e:      # no romper la UI por un error
        print("[LaserAudioFX] error al refrescar rayos:", e)


def _preset_update(self, context):
    if utils.is_muted():
        return
    acolors.apply_palette_preset(self, self.preset)
    _refresh_rigs(self, context)


def _pal(i, col, use):
    """Anotaciones de una ranura de la paleta (c1..c6 / use_c1..c6)."""
    return {
        "c%d" % i: FloatVectorProperty(name="Color %d" % i, subtype='COLOR',
                                       size=3, min=0.0, max=1.0, default=col,
                                       update=_refresh_rigs),
        "use_c%d" % i: BoolProperty(name="Usar", default=use, update=_refresh_rigs),
    }


class AL_Item(bpy.types.PropertyGroup):
    """Una luz (o malla emisiva) de la lista a animar."""

    enabled: BoolProperty(name="Activa", default=True)
    obj: PointerProperty(name="Objeto", type=bpy.types.Object)
    trigger: EnumProperty(name="Reacciona a", items=TRIGGERS, default='KICK')
    energy_min: FloatProperty(
        name="Energia minima", default=10.0, min=0.0,
        description="Valor entre golpes (apagada/tenue)")
    energy_max: FloatProperty(
        name="Energia maxima", default=1000.0, min=0.0,
        description="Valor en el pico del destello")
    delay_beats: FloatProperty(
        name="Retraso (beats)", default=0.0,
        description="Desfasa esta luz respecto al beat (efecto ola/chase)")
    color_mode: EnumProperty(name="Color", items=[
        ('FOLLOW', "Seguir paleta global", ""),
        ('FIXED', "Color fijo", "Esta luz siempre tiene el mismo color"),
        ('OFF', "No tocar", "No anima el color de esta luz")], default='FOLLOW')
    fixed_color: FloatVectorProperty(name="Color fijo", subtype='COLOR', size=3,
                                     min=0.0, max=1.0, default=(1.0, 0.8, 0.5))


class AL_Settings(bpy.types.PropertyGroup):
    """Fuente de audio, rejilla de BPM, color y ajustes del horneado."""

    # ----------------------------------------------------------- fuente
    source: EnumProperty(name="Fuente", items=[
        ('AUDIO', "Cancion", "Analiza el archivo de audio y sigue su ritmo"),
        ('LOOP', "Loop por BPM",
         "Patron sintetico por BPM, sin audio: ideal para renderizar un loop corto")],
        default='AUDIO')
    audio_path: StringProperty(name="Cancion", subtype='FILE_PATH')
    audio_start_frame: IntProperty(name="Frame donde empieza la cancion", default=1)
    audio_duration: FloatProperty(name="Duracion", default=0.0)
    sensitivity: FloatProperty(
        name="Sensibilidad", default=1.0, min=0.2, max=3.0,
        description="Mas alto = detecta mas golpes (kick)")
    bpm_mode: EnumProperty(name="BPM", items=[('AUTO', "Automatico", ""),
                                              ('MANUAL', "Manual", "")],
                           default='AUTO')
    bpm_manual: FloatProperty(name="BPM manual", default=96.0, min=40.0, max=240.0)
    bpm_mult: EnumProperty(name="Corregir", items=[
        ('1', "x1", "Tal cual"), ('0.5', "Mitad", "Si detecto el doble"),
        ('2', "Doble", "Si detecto la mitad")], default='1')
    beats_per_bar: IntProperty(name="Beats por compas", default=4, min=2, max=8)
    downbeat_shift: IntProperty(
        name="Mover el 'uno' (beats)", default=0,
        description="Si el 'uno' del compas quedo mal detectado, muevelo")
    beat_shift_frames: FloatProperty(
        name="Ajuste de sync (frames)", default=0.0,
        description="Positivo = las luces llegan despues. Afinalo viendo el video "
                    "con el audio")
    bpm_detected: FloatProperty(name="BPM detectado", default=0.0)
    beats_found: IntProperty(name="Beats", default=0)
    downbeat_detected: IntProperty(name="Fase del compas", default=0)

    # ------------------------------------------------------------- loop
    loop_bars: IntProperty(name="Compases del loop", default=4, min=1, max=64)
    loop_bpm: FloatProperty(name="BPM del loop", default=96.0, min=40.0, max=240.0)
    loop_use_detected: BoolProperty(name="Usar BPM detectado", default=True)

    # -------------------------------------------------- forma de la onda
    attack_ms: FloatProperty(name="Ataque (ms)", default=15.0, min=1.0, max=1000.0)
    release_ms: FloatProperty(name="Caida (ms)", default=180.0, min=1.0, max=3000.0)
    decay_beats: FloatProperty(name="Duracion del destello (beats)", default=0.5,
                               min=0.05, max=4.0)
    gate: FloatProperty(name="Compuerta de ruido", default=0.05, min=0.0, max=0.9,
                        description="Ignora niveles por debajo de este valor")
    contrast: FloatProperty(name="Contraste", default=1.4, min=0.3, max=4.0,
                            description=">1 hace los picos mas marcados")
    master: FloatProperty(name="Intensidad general", default=1.0, min=0.0, max=5.0)
    key_step: IntProperty(name="Keyframe cada N frames", default=1, min=1, max=10)
    animate_energy: BoolProperty(
        name="Intensidad", default=True,
        description="Animar la intensidad (energia) de las luces con el ritmo")
    animate_color: BoolProperty(
        name="Color", default=True,
        description="Animar el color de las luces (segun 'Cambio de color')")
    live_lights: BoolProperty(
        name="Animar al dar play (en vivo)", default=True,
        description="Las luces siguen la cancion al reproducir, sin hornear. "
                    "Si hay keyframes horneados, estos mandan")

    # ------------------------------------------------------------- color
    color_mode: EnumProperty(name="Cambio de color", items=[
        ('NONE', "No animar", "Deja los colores como estan"),
        ('BEAT', "Cada N beats", "Cambia de color al ritmo"),
        ('SECTION', "Por seccion",
         "Cambia cuando la cancion cambia de energia (coro, drop)"),
        ('GRADIENT', "Degradado continuo", "Recorre los colores suavemente"),
        ('ENERGY', "Segun energia", "Mas fuerte = colores mas 'altos' de la paleta"),
        ('SPECTRUM', "Espectro RGB (solo rayos)",
         "Graves al rojo, medios al verde, agudos al azul")],
        default='BEAT', update=_refresh_rigs)
    color_every: IntProperty(name="Cada cuantos beats", default=4, min=1, max=64,
                             update=_refresh_rigs)
    color_pick: EnumProperty(name="Orden", items=[
        ('SEQUENCE', "En secuencia", ""), ('PINGPONG', "Ida y vuelta", ""),
        ('RANDOM', "Aleatorio", "")], default='SEQUENCE',
        update=_refresh_rigs)
    # Un solo reparto del color, compartido por rayos y luces
    color_spread: EnumProperty(
        name="Reparto del color", items=[
            ('OFFSET', "Desfasado",
             "El color avanza de un objeto al siguiente: en los rayos alterna "
             "rayo a rayo (el clasico abanico) y en las luces va en cadena"),
            ('SAME', "Todos igual", "Todos del mismo color a la vez"),
            ('BLOCKS', "Por bloques",
             "Un bloque de rayos por color (en las luces: como Desfasado)"),
            ('RANDOM', "Independiente",
             "Cada rayo o luz con su propia secuencia (usa la semilla)")],
        default='OFFSET', update=_refresh_rigs)
    transition: EnumProperty(name="Transicion", items=[
        ('CUT', "Corte seco", ""), ('FADE', "Fundido", "")], default='CUT')
    fade_frames: IntProperty(name="Frames de fundido", default=6, min=1, max=120)
    gradient_beats: FloatProperty(name="Beats por color", default=8.0, min=0.5,
                                  max=64.0, update=_refresh_rigs)
    palette_mode: EnumProperty(name="Colores", items=[
        ('PALETTE', "Paleta limitada", "Solo usa los colores de abajo"),
        ('FREE', "Libre (rango de tono)",
         "Colores aleatorios dentro de un rango de tono")], default='PALETTE',
        update=_refresh_rigs)
    preset: EnumProperty(name="Paleta", items=PALETTE_PRESET_ITEMS, default='RGB',
                         update=_preset_update)
    hue_min: FloatProperty(name="Tono min", default=0.0, min=0.0, max=1.0,
                         update=_refresh_rigs)
    hue_max: FloatProperty(name="Tono max", default=1.0, min=0.0, max=1.0,
                         update=_refresh_rigs)
    free_sat: FloatProperty(name="Saturacion", default=0.9, min=0.0, max=1.0,
                          update=_refresh_rigs)
    free_val: FloatProperty(name="Brillo", default=1.0, min=0.0, max=1.0,
                          update=_refresh_rigs)
    seed: IntProperty(name="Semilla", default=1, update=_refresh_rigs)

    # ------------------------------------------------- lista y chase
    lights: CollectionProperty(type=AL_Item)
    lights_index: IntProperty()
    chase_step: FloatProperty(name="Paso del chase (beats)", default=0.25, min=0.0,
                              max=4.0)


for _i, (_r, _g, _b, _use) in enumerate(AUDIO_PALETTE_SLOTS, start=1):
    AL_Settings.__annotations__.update(_pal(_i, (_r, _g, _b), _use))
