"""Curvas reactivas: del analisis de audio a senales continuas por frame.

Es el puente que permite que los lasers reaccionen al ritmo sin depender de
keyframes: cada trigger se convierte en un array que se muestrea en cualquier
instante. Modulo puro (solo numpy) para poder probarlo fuera de Blender.
"""

import numpy as np

from . import dsp

GRID_FPS = dsp.ANALYSIS_FPS      # resolucion con la que se construyen
STORE_FPS = 50.0                 # resolucion al guardarlas en la escena

LEVEL_IDS = ('KICK', 'BASS', 'MID', 'HIGH', 'FULL',
             'BEAT', 'OFFBEAT', 'EIGHTHS', 'DOWNBEAT')
RAW_IDS = ('RAW_BASS', 'RAW_MID', 'RAW_HIGH', 'RAW_FULL')
ALL_IDS = LEVEL_IDS + RAW_IDS


def _shape(raw, gate, contrast):
    out = np.clip((raw - gate) / max(1e-6, 1.0 - gate), 0.0, 1.0)
    return np.power(out, max(float(contrast), 1e-3)).astype(np.float32)


def meta_from_analysis(ana):
    """Datos ligeros de la cancion que acompanan a las curvas."""
    return {
        "bpm": float(ana["bpm"]),
        "offset": float(ana["offset"]),
        "duration": float(ana["duration"]),
        "sections": [float(x) for x in np.asarray(ana["sections"]).reshape(-1)],
    }


def build_curves(ana, beats_per_bar=4, downbeat_shift=0, decay_s=0.25,
                 attack_s=0.015, release_s=0.18, gate=0.05, contrast=1.4,
                 shift_s=0.0, fps=GRID_FPS):
    """Construye el diccionario ``trigger -> curva``.

    - Los triggers de envolvente (BASS/MID/HIGH/FULL) siguen el volumen.
    - Los de evento (KICK/BEAT/...) son picos con caida exponencial.
    - ``shift_s`` positivo retrasa la reaccion respecto al audio.
    """
    bands = ana["bands"]
    n = len(bands["FULL"])
    t = np.arange(n, dtype=np.float64) / fps
    t_src = t - float(shift_s)
    out = {}

    for key in ('BASS', 'MID', 'HIGH', 'FULL'):
        env = dsp.smooth_env(np.asarray(bands[key], dtype=np.float32),
                             fps, attack_s, release_s)
        out['RAW_' + key] = env.astype(np.float32)
        moved = np.interp(t_src, t, env, left=0.0, right=0.0)
        out[key] = _shape(moved, gate, contrast)

    beats = np.asarray(ana["beats"], dtype=np.float64)
    bpm = max(float(ana["bpm"]), 1e-6)
    T = 60.0 / bpm
    bpb = max(2, int(beats_per_bar))
    phase = (int(ana.get("downbeat_phase", 0)) + int(downbeat_shift)) % bpb
    rel = (np.arange(len(beats)) - phase) % bpb

    events = {
        'KICK': np.asarray(ana["kicks"], dtype=np.float64),
        'BEAT': beats,
        'OFFBEAT': beats + T / 2.0,
        'DOWNBEAT': beats[rel == 0],
    }
    if len(beats):
        events['EIGHTHS'] = np.sort(np.concatenate([beats, beats + T / 2.0]))
    else:
        events['EIGHTHS'] = beats

    decay = max(float(decay_s), 1e-3) * fps
    for key in LEVEL_IDS:
        ev = events.get(key)
        if ev is None or not len(ev):
            out[key] = np.zeros(n, dtype=np.float32)
            continue
        pos = (np.asarray(ev, dtype=np.float64) + float(shift_s)) * fps
        out[key] = dsp.pulse_curve(pos, n, decay).astype(np.float32)
    return out


def sample(curve, t, fps=GRID_FPS):
    """Valor de la curva en el instante ``t`` (segundos de audio)."""
    if curve is None:
        return 0.0
    n = len(curve)
    if n == 0:
        return 0.0
    x = float(t) * fps
    if x <= 0.0:
        return float(curve[0])
    if x >= n - 1:
        return float(curve[n - 1])
    i = int(x)
    f = x - i
    a = float(curve[i])
    return a + (float(curve[i + 1]) - a) * f


def beat_state(meta, t, beats_per_step):
    """Numero de paso de color (cada ``beats_per_step`` beats) en el instante ``t``."""
    bpm = max(float(meta.get("bpm") or 100.0), 1e-6)
    step = max(1e-6, float(beats_per_step) * 60.0 / bpm)
    off = float(meta.get("offset") or 0.0)
    return int(max(0.0, (float(t) - off) / step))


def section_state(meta, t):
    """Indice de seccion (coro, drop...) activo en el instante ``t``."""
    i = 0
    for s in (meta.get("sections") or ()):
        if float(t) >= float(s):
            i += 1
        else:
            break
    return i


def to_storable(curves, meta, fps=STORE_FPS):
    """Version compacta (redondeada y submuestreada) para guardar en la escena."""
    step = max(1, int(round(GRID_FPS / max(float(fps), 1.0))))
    data = {}
    for key in ALL_IDS:
        curve = curves.get(key)
        if curve is None:
            continue
        arr = np.asarray(curve, dtype=np.float32)[::step]
        data[key] = [round(float(v), 3) for v in arr]
    return {"fps": GRID_FPS / step, "meta": dict(meta), "curves": data}


def from_storable(data):
    """Reconstruye ``(curves, meta, fps)`` desde lo guardado en la escena."""
    fps = float(data.get("fps") or STORE_FPS)
    curves = {k: np.asarray(v, dtype=np.float32)
              for k, v in (data.get("curves") or {}).items()}
    meta = dict(data.get("meta") or {})
    return curves, meta, fps
