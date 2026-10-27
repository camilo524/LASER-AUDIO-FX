"""Disparadores (triggers) de reaccion y utilidades de la rejilla de beats.

Trabajan sobre un ``AL_Settings`` (duck typing) y el analisis en memoria.
"""

import numpy as np

# --- catalogo de reacciones disponibles ------------------------------------
TRIGGERS = [
    ('KICK', "Kick (bombo)", "Destello en cada golpe de bajo detectado"),
    ('BASS', "Graves (envolvente)", "Sigue el volumen de los graves"),
    ('MID', "Medios (envolvente)", "Sigue el volumen de los medios (voz, sintes)"),
    ('HIGH', "Agudos (envolvente)", "Sigue el volumen de los agudos (hi-hat)"),
    ('FULL', "Total (envolvente)", "Sigue el volumen general"),
    ('BEAT', "Cada beat", "Destello en cada tiempo de la rejilla de BPM"),
    ('OFFBEAT', "Contratiempo", "Destello entre beats"),
    ('EIGHTHS', "Corcheas", "Dos destellos por beat"),
    ('DOWNBEAT', "Primer tiempo del compas", "Solo en el beat 1 de cada compas"),
    ('EVEN', "Beats pares", "Alterna: beats 1 y 3"),
    ('ODD', "Beats impares", "Alterna: beats 2 y 4"),
]

ENVELOPE_TRIGGERS = frozenset({'BASS', 'MID', 'HIGH', 'FULL'})

# Orden usado por las curvas continuas (el orden importa poco, pero se fija
# para que el guardado en la escena sea estable).
CURVE_TRIGGERS = ('KICK', 'BASS', 'MID', 'HIGH', 'FULL',
                  'BEAT', 'OFFBEAT', 'EIGHTHS', 'DOWNBEAT')

# Subconjunto que se ofrece a los lasers (los pares/impares no aportan ahi)
BEAM_TRIGGERS = [
    ('KICK', "Kick (bombo)", "Destello en cada golpe de bajo"),
    ('BASS', "Graves", "Sigue el volumen de los graves"),
    ('MID', "Medios", "Sigue el volumen de los medios"),
    ('HIGH', "Agudos", "Sigue el volumen de los agudos"),
    ('FULL', "Total", "Sigue el volumen general"),
    ('BEAT', "Cada beat", "Destello en cada tiempo del compas"),
    ('OFFBEAT', "Contratiempo", "Destello entre beats"),
    ('EIGHTHS', "Corcheas", "Dos destellos por beat"),
    ('DOWNBEAT', "Primer tiempo", "Solo en el beat 1 de cada compas"),
]


def trigger_label(key):
    for k, label, _desc in TRIGGERS:
        if k == key:
            return label
    return key


def beat_info(s, ana):
    """Devuelve ``(beats_por_compas, fase_del_compas)``."""
    bpb = max(2, int(s.beats_per_bar))
    phase = (int(ana.get("downbeat_phase", 0)) + int(s.downbeat_shift)) % bpb
    return bpb, phase


def events_for(trigger, ana, s):
    """Instantes (segundos) de cada evento del trigger pedido."""
    beats = np.asarray(ana["beats"], dtype=np.float64)
    T = 60.0 / max(float(ana["bpm"]), 1e-6)
    bpb, phase = beat_info(s, ana)
    rel = (np.arange(len(beats)) - phase) % bpb
    if trigger == 'KICK':
        return np.asarray(ana["kicks"], dtype=np.float64)
    if trigger == 'BEAT':
        return beats
    if trigger == 'OFFBEAT':
        return beats + T / 2.0
    if trigger == 'EIGHTHS':
        if not len(beats):
            return beats
        return np.sort(np.concatenate([beats, beats + T / 2.0]))
    if trigger == 'DOWNBEAT':
        return beats[rel == 0]
    if trigger == 'EVEN':
        return beats[rel % 2 == 0]
    if trigger == 'ODD':
        return beats[rel % 2 == 1]
    return beats


def color_event_times(s, ana):
    """Instantes en los que cambia el color global."""
    if s.color_mode == 'BEAT':
        bpb, phase = beat_info(s, ana)
        idx = np.arange(len(ana["beats"]))
        return np.asarray(ana["beats"])[((idx - phase) % max(1, s.color_every)) == 0]
    if s.color_mode == 'SECTION':
        return np.asarray(ana["sections"])
    return np.array([])


def plan_events(s, ana):
    """Lista ``(segundos, tipo, nombre)`` de compases, beats y cambios de color."""
    bpb, phase = beat_info(s, ana)
    out = []
    bar = 0
    for i, tb in enumerate(ana["beats"]):
        if (i - phase) % bpb == 0:
            bar += 1
            out.append((float(tb), 'BAR', "Compas %d" % bar))
        else:
            out.append((float(tb), 'BEAT', "b"))
    for k, tc in enumerate(color_event_times(s, ana)):
        out.append((float(tc), 'COLOR', "Color %d" % (k + 1)))
    out.sort(key=lambda e: e[0])
    return out


def tc_str(frames, base):
    """Timecode HH:MM:SS:FF para el EDL de DaVinci Resolve."""
    h = frames // (base * 3600)
    m = (frames // (base * 60)) % 60
    sec = (frames // base) % 60
    f = frames % base
    return "%02d:%02d:%02d:%02d" % (h, m, sec, f)
