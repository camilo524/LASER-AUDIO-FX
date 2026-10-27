"""Luces en vivo: intensidad y color siguen la cancion al dar play.

Usa las mismas curvas de audio que los lasers (``lasers/driver.py``) y el
mismo muestreador de color (``lasers/audio_color.py``), asi que no hace falta
hornear. Si una luz tiene keyframes horneados, esos mandan sobre el modo en
vivo. El fundido de color solo existe al hornear.
"""

from types import SimpleNamespace

import bpy
from bpy.app.handlers import persistent

from ..audio.targets import Target, has_keyframes
from ..audio.triggers import CURVE_TRIGGERS
from ..core.constants import PREFIX
from ..lasers import driver as ldriver
from ..lasers.audio_color import Sampler



def apply(scene):
    s = getattr(scene, "al", None)
    if s is None or not s.live_lights:
        return
    if not (s.animate_energy or s.animate_color):
        return
    items = []
    for it in s.lights:
        # Los rayos (LZG_*) y el rig ya siguen el audio solos: nunca se tocan aqui
        if it.enabled and it.obj and not it.obj.name.startswith(PREFIX):
            tg = Target(it.obj)
            if tg.ok:
                items.append((it, tg))
    if not items:
        return
    drv = ldriver.get_driver(
        scene, SimpleNamespace(audio_enabled=True, audio_trigger='FULL'))
    if drv is None:
        return
    t = drv.time_at(scene.frame_current + scene.frame_subframe)
    T = drv.beat_period

    if s.animate_energy:
        for it, tg in items:
            if has_keyframes(tg.idb, tg.en_path):
                continue            # ya hornearon esta luz: manda el keyframe
            key = it.trigger if it.trigger in CURVE_TRIGGERS else 'BEAT'
            lvl = drv.raw_level(t - it.delay_beats * T, key)
            e = it.energy_min + (it.energy_max - it.energy_min) * lvl
            tg.put_energy(e * s.master)

    if s.animate_color:
        # "Por bloques" es cosa de los rayos: aqui se comporta como "Desfasado"
        reparto = 'OFFSET' if s.color_spread == 'BLOCKS' else s.color_spread
        sampler = Sampler(drv, s, t, len(items), reparto, 0.0)
        if sampler.mode is not None:
            same = s.color_spread == 'SAME'
            for idx, (it, tg) in enumerate(items):
                if it.color_mode == 'OFF' or has_keyframes(tg.idb, tg.col_path):
                    continue
                if it.color_mode == 'FIXED':
                    rgb = tuple(it.fixed_color)
                else:
                    rgb = sampler.color(0 if same else idx)
                    if rgb is None:
                        continue
                tg.put_color(rgb)


@persistent
def lz_lights_handler(scene, depsgraph=None):
    try:
        apply(scene)
    except Exception as e:
        print("[LaserAudioFX] luces en vivo:", e)


def unregister_handlers():
    h = bpy.app.handlers
    for lst in (h.frame_change_post, h.render_pre):
        for fn in list(lst):
            if getattr(fn, "__name__", "") == "lz_lights_handler":
                lst.remove(fn)


def register_handlers():
    unregister_handlers()
    bpy.app.handlers.frame_change_post.append(lz_lights_handler)
    bpy.app.handlers.render_pre.append(lz_lights_handler)
