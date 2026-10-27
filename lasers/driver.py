"""Puente entre el analisis de audio y el motor de lasers.

Convierte el analisis en curvas continuas (``audio/curves.py``) y las cachea,
de modo que cada frame los rayos solo tienen que muestrear un array. Se usan
las mismas curvas guardadas en la escena cuando no hay analisis en memoria.
"""

from ..audio import analysis
from ..audio import curves as acurves
from ..core.constants import CURVES_PROP

_MAX_CACHE = 6
_CACHE = {}


class Driver:
    """Niveles de audio listos para el motor, en el tiempo de la cancion."""

    def __init__(self, curves, meta, al, scene, grid_fps):
        self.curves = curves
        self.meta = meta
        self.al = al
        self.scene = scene
        self.grid_fps = float(grid_fps or acurves.GRID_FPS)
        self.bpm = float(meta.get("bpm") or al.loop_bpm or 100.0)
        self.offset = float(meta.get("offset") or 0.0)
        self.duration = float(meta.get("duration") or 0.0)
        self.sections = list(meta.get("sections") or ())
        self.beat_period = 60.0 / max(self.bpm, 1e-6)
        if self.duration <= 0.0:        # sin duracion en los datos: sale de la curva
            for c in curves.values():
                if c is not None and len(c):
                    self.duration = len(c) / self.grid_fps
                    break
        self.trigger = 'KICK'

    # ------------------------------------------------------------- tiempo
    def time_at(self, frame):
        """Segundos de audio correspondientes a un frame de la escena."""
        render = self.scene.render
        fps = render.fps / render.fps_base
        start = (self.al.audio_start_frame if self.al.source == 'AUDIO'
                 else self.scene.frame_start)
        return (float(frame) - start) / fps - self.al.beat_shift_frames / fps

    # Ganchos del loop: aqui no hacen nada; ``looping.LoopDriver`` los
    # sobreescribe para que el audio sea periodico dentro del rango.
    loop = False

    def wrap(self, t):
        return t

    def mix(self, t):
        """``(ta, tb, wb)``: senal = (1 - wb) * f(ta) + wb * f(tb)."""
        return t, t, 0.0

    # ---------------------------------------------------------- muestreo
    def level(self, t):
        """Nivel del trigger elegido por el rig, 0..1."""
        return acurves.sample(self.curves.get(self.trigger), t, self.grid_fps)

    def raw_level(self, t, key):
        return acurves.sample(self.curves.get(key), t, self.grid_fps)

    def bands(self, t):
        """(graves, medios, agudos, total) sin procesar, 0..1."""
        return (self.raw_level(t, "RAW_BASS"), self.raw_level(t, "RAW_MID"),
                self.raw_level(t, "RAW_HIGH"), self.raw_level(t, "RAW_FULL"))

    def section_state(self, t):
        return acurves.section_state(self.meta, t)

    def beat_state(self, t, beats_per_step):
        return acurves.beat_state(self.meta, t, beats_per_step)


# ---------------------------------------------------------------- cache
def _signature(al, ana, scene):
    render = scene.render
    return (id(ana), int(al.beats_per_bar), int(al.downbeat_shift),
            round(float(al.gate), 4), round(float(al.contrast), 3),
            round(float(al.decay_beats), 4), round(float(al.attack_ms), 3),
            round(float(al.release_ms), 3), round(float(al.beat_shift_frames), 4),
            round(float(render.fps), 4), round(float(render.fps_base), 6))


def _cache_put(key, value):
    _CACHE[key] = value
    while len(_CACHE) > _MAX_CACHE:
        _CACHE.pop(next(iter(_CACHE)))


def clear_cache():
    _CACHE.clear()


def get_driver(scene, settings):
    """Devuelve un ``Driver`` listo para muestrear, o ``None`` si no hay audio."""
    if not settings.audio_enabled:
        return None
    al = getattr(scene, "al", None)
    if al is None:
        return None

    ana = analysis.ensure(scene)
    if ana is not None:
        key = _signature(al, ana, scene)
        entry = _CACHE.get(key)
        if entry is None:
            fps = analysis.scene_fps(scene)
            T = 60.0 / max(float(ana["bpm"]), 1e-6)
            built = acurves.build_curves(
                ana, beats_per_bar=al.beats_per_bar,
                downbeat_shift=al.downbeat_shift, decay_s=al.decay_beats * T,
                attack_s=al.attack_ms / 1000.0, release_s=al.release_ms / 1000.0,
                gate=al.gate, contrast=al.contrast,
                shift_s=al.beat_shift_frames / fps)
            entry = (built, acurves.meta_from_analysis(ana), acurves.GRID_FPS)
            _cache_put(key, entry)
        curves, meta, grid = entry
    else:
        stored = scene.get(CURVES_PROP)
        if not stored:
            return None
        curves, meta, grid = acurves.from_storable(stored)

    drv = Driver(curves, meta, al, scene, grid)
    drv.trigger = settings.audio_trigger
    return drv


def status(scene, settings):
    """Estado del audio para mostrar en la interfaz: ``(codigo, texto)``."""
    if not settings.audio_enabled:
        return 'OFF', "Audio desactivado"
    al = getattr(scene, "al", None)
    if al is None:
        return 'MISSING', "Faltan los ajustes de audio"
    ana = analysis.ensure(scene)
    if ana is not None:
        return 'LIVE', "Sigue el audio (%.1f BPM)" % ana["bpm"]
    if scene.get(CURVES_PROP):
        return 'STORED', "Usando las curvas guardadas"
    if al.source == 'AUDIO' and al.audio_path:
        return 'NO_ANALYSIS', "Pulsa 'Analizar cancion' arriba"
    return 'NO_AUDIO', "Elige una cancion o el Loop por BPM"
