"""Logica de color compartida: paletas, secuencias y modo libre por tono.

La usan tanto el horneado de luces como el modo de color reactivo de los
lasers, asi los dos reaccionan igual si comparten los ajustes de ``scene.al``.
"""

import colorsys

from ..core import utils
from ..core.constants import AUDIO_PALETTE_SLOTS, N_SLOTS, PALETTE_PRESETS


def palette_list(s):
    """Colores activos de la paleta unica (rayos y luces)."""
    out = []
    for i in range(1, N_SLOTS + 1):
        if getattr(s, "use_c%d" % i):
            out.append(tuple(getattr(s, "c%d" % i)))
    return out or [(1.0, 1.0, 1.0)]


def apply_palette_preset(s, key):
    """Vuelca un preset en las ranuras; las que sobran vuelven a su color base."""
    cols = PALETTE_PRESETS.get(key)
    if cols is None:
        return False
    with utils.mute_updates():
        for i in range(1, N_SLOTS + 1):
            if i <= len(cols):
                setattr(s, "c%d" % i, cols[i - 1])
                setattr(s, "use_c%d" % i, True)
            else:
                setattr(s, "c%d" % i, AUDIO_PALETTE_SLOTS[i - 1][:3])
                setattr(s, "use_c%d" % i, False)
    return True


def make_sequence(n, ncol, pick, rng, offset=0):
    """Secuencia de indices de color de longitud ``n``."""
    out, last = [], -1
    for k in range(n):
        if pick == 'SEQUENCE':
            v = (k + offset) % ncol
        elif pick == 'PINGPONG':
            p = 2 * ncol - 2 if ncol > 1 else 1
            m = (k + offset) % p
            v = m if m < ncol else p - m
        else:
            v = rng.randrange(ncol)
            if ncol > 1:
                while v == last:
                    v = rng.randrange(ncol)
        out.append(v)
        last = v
    return out


def make_free(n, s, rng):
    """Secuencia de colores aleatorios dentro del rango de tono configurado."""
    out, prev = [], None
    for _ in range(n):
        h = s.hue_min
        for _t in range(12):
            h = s.hue_min + (s.hue_max - s.hue_min) * rng.random()
            if prev is None or min(abs(h - prev), 1 - abs(h - prev)) > 0.08:
                break
        prev = h
        out.append(colorsys.hsv_to_rgb(h % 1.0, s.free_sat, s.free_val))
    return out


def free_color_at(s, frac):
    """Color del modo libre para una posicion 0..1 del rango de tono."""
    h = s.hue_min + (s.hue_max - s.hue_min) * frac
    return colorsys.hsv_to_rgb(h % 1.0, s.free_sat, s.free_val)
