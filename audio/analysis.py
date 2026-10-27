"""Analisis de la fuente de audio activa (cache en memoria).

``build_analysis`` hace el trabajo pesado; ``ensure`` solo analiza si hace
falta. Los lasers llaman a ``ensure`` en cada frame, por eso para una cancion
real se exige pulsar "Analizar cancion" antes (o usar curvas guardadas).
"""

import numpy as np

from . import dsp
from .loader import load_audio_mono

_STATE = {"ana": None}


def scene_fps(scene):
    return scene.render.fps / scene.render.fps_base


def get():
    """Devuelve el analisis en cache o ``None``."""
    return _STATE["ana"]


def clear():
    _STATE["ana"] = None


def build_analysis(scene):
    """Analiza la fuente configurada en ``scene.al`` y guarda el resultado."""
    s = scene.al
    fps = scene_fps(scene)
    if s.source == 'LOOP':
        dur = (scene.frame_end - scene.frame_start + 1) / fps + 2.0
        ana = dsp.synthetic_analysis(s.loop_bpm, dur, s.beats_per_bar)
    else:
        x, sr = load_audio_mono(s.audio_path)
        manual = s.bpm_manual if s.bpm_mode == 'MANUAL' else 0.0
        ana = dsp.analyze_signal(x, sr, s.sensitivity, manual,
                                 float(s.bpm_mult), s.beats_per_bar)
        s.audio_duration = ana["duration"]
    s.bpm_detected = ana["bpm"]
    s.beats_found = len(ana["beats"])
    s.downbeat_detected = ana["downbeat_phase"]
    _STATE["ana"] = ana
    return ana


def ensure(scene):
    """Analisis disponible: lo construye solo si es barato (fuente LOOP)."""
    ana = _STATE["ana"]
    if ana is not None:
        return ana
    al = getattr(scene, "al", None)
    if al is None or al.source != 'LOOP':
        return None
    return build_analysis(scene)


def current_bpm(s):
    """BPM efectivo segun la configuracion de la fuente."""
    if s.source == 'LOOP':
        return s.loop_bpm
    if s.bpm_mode == 'MANUAL':
        return s.bpm_manual
    ana = _STATE["ana"]
    if ana is not None:
        return ana["bpm"]
    raise RuntimeError("Primero analiza la cancion (o usa BPM manual).")


def analysis_seconds(scene):
    """Rejilla temporal del analisis en segundos (para interpolar)."""
    ana = _STATE["ana"]
    if ana is None:
        return np.array([])
    n = len(ana["bands"]["FULL"])
    return np.arange(n, dtype=np.float64) / dsp.ANALYSIS_FPS
