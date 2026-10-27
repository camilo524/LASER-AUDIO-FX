"""Horneado: convierte el analisis de audio en keyframes de luces.

Es la herramienta del script original de sincronizacion. Los lasers no la
necesitan (reaccionan en vivo, ver ``lasers/driver.py``), pero sigue siendo
la via util para animar luces reales y mallas emisivas.
"""

import colorsys
import math
import random

import numpy as np

from . import analysis, colors, dsp, triggers
from .targets import Prefs, Target
from .triggers import ENVELOPE_TRIGGERS
from ..core.constants import PREFIX


def run_bake(context):
    """Anima intensidad y color de las luces de la lista. Devuelve (n, ana)."""
    scene = context.scene
    s = scene.al
    targets = []
    for item in s.lights:
        if item.enabled and item.obj and not item.obj.name.startswith(PREFIX):
            tg = Target(item.obj)
            if tg.ok:
                targets.append((item, tg))
    if not targets:
        raise RuntimeError("No hay luces en la lista (agrega luces con 'Agregar seleccion').")

    ana = analysis.build_analysis(scene)
    fps = analysis.scene_fps(scene)
    # Las luces tratan "Por bloques" como "Desfasado": el reparto por bloques es
    # cosa de los rayos, pero el control es el mismo (scene.al.color_spread).
    spread_mode = 'OFFSET' if s.color_spread == 'BLOCKS' else s.color_spread
    f0, f1 = scene.frame_start, scene.frame_end
    start_frame = s.audio_start_frame if s.source == 'AUDIO' else f0
    nF = f1 - f0 + 1
    frames = np.arange(f0, f1 + 1)
    t = (frames - start_frame) / fps
    T = 60.0 / ana["bpm"]
    shift_s = s.beat_shift_frames / fps
    ta = np.arange(len(ana["bands"]["FULL"])) / dsp.ANALYSIS_FPS
    step = max(1, int(s.key_step))
    key_idx = [j for j in range(nF) if j % step == 0]
    if key_idx[-1] != nF - 1:
        key_idx.append(nF - 1)

    with Prefs(context) as prefs:
        for _item, tg in targets:
            tg.clear(energy=s.animate_energy, color=s.animate_color)

        # ---- pasada 1: intensidad ----
        prefs.edit.keyframe_new_interpolation_type = 'LINEAR'
        for item, tg in (targets if s.animate_energy else ()):
            delay_s = item.delay_beats * T
            if item.trigger in ENVELOPE_TRIGGERS:
                raw = np.interp(t - shift_s - delay_s, ta, ana["bands"][item.trigger],
                                left=0.0, right=0.0)
                raw = dsp.smooth_env(raw, fps, s.attack_ms / 1000.0,
                                     s.release_ms / 1000.0)
            else:
                ev = triggers.events_for(item.trigger, ana, s)
                pos = (ev + shift_s + delay_s) * fps + start_frame - f0
                raw = dsp.pulse_curve(pos, nF, s.decay_beats * T * fps)
            lvl = np.clip((raw - s.gate) / max(1e-6, 1.0 - s.gate), 0.0, 1.0) ** s.contrast
            energy = (item.energy_min + (item.energy_max - item.energy_min) * lvl) * s.master
            for j in key_idx:
                tg.set_energy(energy[j], int(frames[j]))
            tg.fix_interp('energy', 'LINEAR')

        # ---- pasada 2: color ----
        cmode = s.color_mode
        if cmode == 'SPECTRUM':          # el espectro RGB solo existe en vivo
            cmode = 'NONE'
        free = s.palette_mode == 'FREE'
        pal = colors.palette_list(s)
        npal = len(pal)
        smooth_color = (cmode == 'GRADIENT') or s.transition == 'FADE'
        prefs.edit.keyframe_new_interpolation_type = 'LINEAR' if smooth_color else 'CONSTANT'
        color_interp = 'LINEAR' if smooth_color else 'CONSTANT'

        state, n_states = None, 0
        if cmode in ('BEAT', 'SECTION'):
            ev_pos = np.round(triggers.color_event_times(s, ana) * fps + start_frame - f0)
            state = np.searchsorted(ev_pos, np.arange(nF), side='right')
            n_states = len(ev_pos) + 1
        elif cmode == 'ENERGY':
            nb = 6 if free else npal
            e = np.interp(t - shift_s, ta, ana["bands"]["FULL"], left=0.0, right=0.0)
            e = dsp.smooth_env(e, fps, 0.4, 1.2)
            state = np.minimum((e * nb).astype(int), nb - 1)
            n_states = nb

        base_seq = None
        if cmode in ('BEAT', 'SECTION'):
            if free:
                base_seq = colors.make_free(n_states, s, random.Random(s.seed))
            else:
                base_seq = colors.make_sequence(n_states, npal, s.color_pick,
                                                random.Random(s.seed))

        def lookup(i):
            if cmode == 'ENERGY':
                if free:
                    return [colors.free_color_at(s, b / max(1, n_states - 1))
                            for b in range(n_states)]
                off = i if spread_mode == 'OFFSET' else 0
                return [pal[(b + off) % npal] for b in range(n_states)]
            if free:
                if spread_mode == 'SAME':
                    return base_seq
                if spread_mode == 'OFFSET':
                    return [base_seq[(k + i) % n_states] for k in range(n_states)]
                return colors.make_free(n_states, s, random.Random(s.seed * 1000 + i))
            if spread_mode == 'SAME':
                idxs = base_seq
            elif spread_mode == 'OFFSET':
                idxs = [(b + i) % npal for b in base_seq]
            else:
                idxs = colors.make_sequence(n_states, npal, 'RANDOM',
                                            random.Random(s.seed * 1000 + i))
            return [pal[k] for k in idxs]

        rng_off = random.Random(s.seed + 7)
        for i, (item, tg) in enumerate(targets):
            if not s.animate_color:
                break
            if item.color_mode == 'OFF':
                continue
            if item.color_mode == 'FIXED':
                tg.set_color(tuple(item.fixed_color), f0)
                continue
            if cmode == 'NONE':
                continue
            if cmode == 'GRADIENT':
                offset = {'SAME': 0.0, 'OFFSET': i * 0.7,
                          'RANDOM': rng_off.random() * npal}[spread_mode]
                for j in key_idx:
                    pos = t[j] / (s.gradient_beats * T) + offset
                    if free:
                        h = s.hue_min + (s.hue_max - s.hue_min) * (
                            0.5 - 0.5 * math.cos(math.pi * pos))
                        rgb = colorsys.hsv_to_rgb(h % 1.0, s.free_sat, s.free_val)
                    else:
                        k0 = int(math.floor(pos))
                        fr = pos - k0
                        a, b = pal[k0 % npal], pal[(k0 + 1) % npal]
                        rgb = tuple(a[c] + (b[c] - a[c]) * fr for c in range(3))
                    tg.set_color(rgb, int(frames[j]))
            else:
                lk = lookup(i)
                change = [0] + (np.flatnonzero(np.diff(state) != 0) + 1).tolist()
                if cmode == 'ENERGY':
                    hold, kept = int(0.25 * fps), []
                    for j in change:
                        if not kept or j - kept[-1] >= hold:
                            kept.append(j)
                    change = kept
                last_key = None
                prev_rgb = None
                for j in change:
                    fr = int(frames[j])
                    rgb = lk[int(state[j])]
                    if s.transition == 'FADE' and prev_rgb is not None:
                        kf = max(fr - s.fade_frames, last_key + 1)
                        if kf < fr:
                            tg.set_color(prev_rgb, kf)
                    tg.set_color(rgb, fr)
                    last_key, prev_rgb = fr, rgb
            tg.fix_interp('color', color_interp)
    return len(targets), ana
