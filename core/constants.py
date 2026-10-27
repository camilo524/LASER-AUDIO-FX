"""Constantes, limites y paletas compartidas por todo el addon.

Este modulo no importa ``bpy`` a proposito: es la base comun entre el motor
de lasers, el analisis de audio y la sincronizacion de luces.
"""

import math

# --- prefijos de nombres generados -----------------------------------------
PREFIX = "LZG_"                     # todo lo que genera el addon empieza asi
MARKER_PREFIX = "AL_"               # marcadores del timeline
CURVES_PROP = "lzf_audio_curves"    # curvas reactivas guardadas en la escena

# --- limites de seguridad ---------------------------------------------------
MAX_BEAMS = 512
MAX_LIGHTS = 32
MAX_VERTS = 600_000
TAU = math.tau
GOLDEN = 2.399963229728653          # angulo aureo para el patron en cono

# --- paleta clasica de los lasers (indices usados por LASER_PRESETS) -------
LASER_PALETTE = [
    ("Rojo", (1.0, 0.02, 0.02)),
    ("Verde", (0.02, 1.0, 0.05)),
    ("Azul", (0.05, 0.12, 1.0)),
    ("Cian", (0.0, 0.9, 1.0)),
    ("Magenta", (1.0, 0.0, 0.75)),
    ("Amarillo", (1.0, 0.8, 0.0)),
    ("Violeta", (0.5, 0.1, 1.0)),
    ("Naranja", (1.0, 0.3, 0.0)),
    ("Rosa", (1.0, 0.25, 0.5)),
    ("Blanco", (1.0, 1.0, 1.0)),
]

# Nombre de preset -> indices de LASER_PALETTE que se activan
LASER_PRESETS = {
    'RGB': {0, 1, 2},
    'NEON': {3, 4, 6},
    'FUEGO': {0, 7, 5},
    'VERDE': {1},
    'ROJO': {0},
    'AZUL': {2},
    'BLANCO': {9},
    'TODOS': set(range(10)),
}

# --- paletas de la sincronizacion de luces ---------------------------------
AUDIO_PALETTES = {
    'BAR': [(1.0, 0.45, 0.05), (1.0, 0.04, 0.35), (0.5, 0.1, 1.0),
            (0.05, 0.25, 1.0)],
    'NEON': [(1.0, 0.0, 0.5), (0.0, 0.9, 1.0), (0.1, 1.0, 0.2),
             (1.0, 0.9, 0.0)],
    'WARM': [(1.0, 0.05, 0.02), (1.0, 0.3, 0.02), (1.0, 0.6, 0.1),
             (1.0, 0.85, 0.5)],
    'COLD': [(0.02, 0.15, 1.0), (0.0, 0.7, 1.0), (0.4, 0.1, 1.0),
             (0.7, 0.9, 1.0)],
    'RGB': [(1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.1, 1.0)],
}

# Paleta unica compartida por rayos y luces: 10 ranuras (las 3 primeras activas)
AUDIO_PALETTE_SLOTS = [(c[0], c[1], c[2], i < 3)
                       for i, (_n, c) in enumerate(LASER_PALETTE)]
N_SLOTS = len(AUDIO_PALETTE_SLOTS)


def _lp(*idx):
    return [LASER_PALETTE[i][1] for i in idx]


# Preset -> colores que ocupan las primeras ranuras (el resto se apaga)
PALETTE_PRESETS = {
    'RGB': _lp(0, 1, 2),
    'NEON': _lp(3, 4, 6),
    'NEON2': AUDIO_PALETTES['NEON'],
    'FUEGO': _lp(0, 7, 5),
    'BAR': AUDIO_PALETTES['BAR'],
    'WARM': AUDIO_PALETTES['WARM'],
    'COLD': AUDIO_PALETTES['COLD'],
    'VERDE': _lp(1),
    'ROJO': _lp(0),
    'AZUL': _lp(2),
    'BLANCO': _lp(9),
    'TODOS': _lp(*range(10)),
}

# --- categoria unica del panel lateral -------------------------------------
CATEGORY = "Laser Audio FX"
