"""Presets de estilo: configuraciones completas de un rig de lasers.

Cada preset activa el audio y elige el modo de color reactivo mas adecuado,
para pasar de "cero" a "show" en un clic.
"""

import math

import bpy

from ..audio import colors
from ..core import utils

# Orden con el que "Repartir reacciones" asigna disparadores a varios rigs
TRIGGER_ROTATION = ('KICK', 'OFFBEAT', 'HIGH', 'BEAT', 'MID', 'DOWNBEAT')

STYLE_PRESETS = [
    ('DISCO', "Discoteca", "Abanico girando y rotacion de colores con el ritmo"),
    ('TECHNO', "Techno", "Cono rapido, estrobo por kick y colores neon"),
    ('SHOW', "Show grande", "Muchos rayos, cruz, onda y cambios por seccion"),
    ('AMBIENT', "Ambiente", "Pocos rayos, movimiento lento y degradado continuo"),
    ('STROBE', "Estrobo", "Destello duro en cada golpe de bombo, en blanco"),
    ('FIRE', "Fuego", "Paleta calida que respira con los graves"),
]

_DEFS = {
    'DISCO': dict(
        count=24, pattern='FAN', spread=math.radians(70), intensity=6.0,
        width=0.012, divergence=0.001, max_distance=40.0, end_fade=0.6, sides=4,
        max_bounces=2, reflect=0.9, color_mode='CYCLE', preset='TODOS',
        color_speed=0.0, speed=1.0, sweep=math.radians(18), spin=25.0,
        wave=math.radians(6), wave_cycles=2.0, breath=0.3, bpm=120.0,
        pulse=0.0, chase=0.5,
        audio_enabled=True, audio_trigger='KICK', audio_brightness=0.6,
        audio_spread=0.3, audio_speed=0.4, audio_strobe=False, audio_chase=0.0,
        audio_color_mode='PULSE', audio_color_every=4, audio_color_chase=0.6,
        audio_gradient_beats=8.0),
    'TECHNO': dict(
        count=32, pattern='CONE', spread=math.radians(40), intensity=8.0,
        width=0.01, divergence=0.0015, max_distance=45.0, end_fade=0.4, sides=4,
        max_bounces=1, reflect=0.85, color_mode='BLOCKS', preset='NEON',
        color_speed=0.0, speed=1.4, sweep=math.radians(25), spin=60.0,
        wave=math.radians(4), wave_cycles=1.0, breath=0.2, bpm=128.0,
        pulse=0.7, chase=1.0,
        audio_enabled=True, audio_trigger='KICK', audio_brightness=0.8,
        audio_spread=0.5, audio_speed=0.6, audio_strobe=True, audio_chase=0.5,
        audio_color_mode='PULSE', audio_color_every=2, audio_color_chase=0.0,
        audio_gradient_beats=4.0),
    'SHOW': dict(
        count=48, pattern='CROSS', spread=math.radians(100), intensity=7.0,
        width=0.011, divergence=0.0012, max_distance=60.0, end_fade=0.5, sides=5,
        max_bounces=2, reflect=0.9, color_mode='CYCLE', preset='TODOS',
        color_speed=0.0, speed=1.1, sweep=math.radians(14), spin=15.0,
        wave=math.radians(8), wave_cycles=3.0, breath=0.4, bpm=124.0,
        pulse=0.3, chase=0.8,
        audio_enabled=True, audio_trigger='FULL', audio_brightness=0.7,
        audio_spread=0.4, audio_speed=0.5, audio_strobe=False, audio_chase=0.75,
        audio_color_mode='SECTION', audio_color_every=4, audio_color_chase=1.5,
        audio_gradient_beats=8.0),
    'AMBIENT': dict(
        count=12, pattern='FAN', spread=math.radians(45), intensity=3.0,
        width=0.014, divergence=0.002, max_distance=35.0, end_fade=0.85, sides=4,
        max_bounces=3, reflect=0.95, color_mode='CYCLE', preset='NEON',
        color_speed=0.0, speed=0.4, sweep=math.radians(8), spin=5.0,
        wave=math.radians(3), wave_cycles=1.0, breath=0.15, bpm=90.0,
        pulse=0.0, chase=0.2,
        audio_enabled=True, audio_trigger='FULL', audio_brightness=0.5,
        audio_spread=0.15, audio_speed=0.2, audio_strobe=False, audio_chase=0.0,
        audio_color_mode='GRADIENT', audio_color_every=8, audio_color_chase=0.0,
        audio_gradient_beats=12.0),
    'STROBE': dict(
        count=16, pattern='FAN', spread=math.radians(90), intensity=9.0,
        width=0.012, divergence=0.0008, max_distance=50.0, end_fade=0.3, sides=4,
        max_bounces=1, reflect=0.8, color_mode='CYCLE', preset='BLANCO',
        color_speed=0.0, speed=1.0, sweep=0.0, spin=0.0, wave=0.0,
        wave_cycles=1.0, breath=0.0, bpm=140.0, pulse=1.0, chase=0.0,
        audio_enabled=True, audio_trigger='KICK', audio_brightness=1.0,
        audio_spread=0.0, audio_speed=0.0, audio_strobe=True, audio_chase=0.0,
        audio_color_mode='NONE', audio_color_every=4, audio_color_chase=0.0,
        audio_gradient_beats=8.0),
    'FIRE': dict(
        count=20, pattern='FAN', spread=math.radians(60), intensity=7.0,
        width=0.013, divergence=0.0016, max_distance=42.0, end_fade=0.7, sides=4,
        max_bounces=2, reflect=0.9, color_mode='RANDOM', preset='FUEGO',
        color_speed=0.0, speed=1.6, sweep=math.radians(20), spin=35.0,
        wave=math.radians(10), wave_cycles=4.0, breath=0.35, bpm=118.0,
        pulse=0.25, chase=0.7,
        audio_enabled=True, audio_trigger='BASS', audio_brightness=0.7,
        audio_spread=0.35, audio_speed=0.5, audio_strobe=False, audio_chase=0.0,
        audio_color_mode='ENERGY', audio_color_every=4, audio_color_chase=0.0,
        audio_gradient_beats=8.0),
}


# Estos ajustes ya no son del rig: viven en scene.al y los comparten rayos y luces
_SHARED = ('preset', 'audio_color_mode', 'audio_color_every', 'audio_gradient_beats')
_COLOR_MODE_TO_SHARED = {'PULSE': 'BEAT', 'SECTION': 'SECTION', 'GRADIENT': 'GRADIENT',
                         'ENERGY': 'ENERGY', 'SPECTRUM': 'SPECTRUM'}


def apply(settings, key):
    """Aplica un preset de estilo (sin disparar una reconstruccion por propiedad)."""
    values = _DEFS.get(key)
    if not values:
        return False
    with utils.mute_updates():
        for name, value in values.items():
            if name not in _SHARED and hasattr(settings, name):
                setattr(settings, name, value)
        al = getattr(bpy.context.scene, "al", None)
        if al is not None:
            if values.get('preset') and colors.apply_palette_preset(al, values['preset']):
                al.preset = values['preset']
            mode = _COLOR_MODE_TO_SHARED.get(values.get('audio_color_mode'))
            if mode:
                al.color_mode = mode
                al.color_every = values.get('audio_color_every', al.color_every)
                al.gradient_beats = values.get('audio_gradient_beats', al.gradient_beats)
    return True
