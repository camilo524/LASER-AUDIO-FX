"""Utilidades comunes: flags globales, hashing determinista y color.

Sin dependencias de Blender ni de numpy.
"""

import contextlib
import math

# --- banderas globales ------------------------------------------------------
BUSY = False    # evita reentradas de los handlers
MUTE = False    # evita reconstruir el rig mientras se cambian propiedades


def is_busy():
    return BUSY


def is_muted():
    return MUTE


@contextlib.contextmanager
def mute_updates():
    """Silencia los callbacks de propiedades mientras se toca un preset."""
    global MUTE
    prev = MUTE
    MUTE = True
    try:
        yield
    finally:
        MUTE = prev


@contextlib.contextmanager
def handler_lock():
    """No ejecuta el cuerpo si ya hay un handler en curso.

    Produce ``True`` cuando el cuerpo debe ejecutarse y ``False`` cuando se
    trata de una reentrada (frame handler -> depsgraph update -> etc).
    """
    global BUSY
    if BUSY:
        yield False
        return
    BUSY = True
    try:
        yield True
    finally:
        BUSY = False


# --- hashing determinista (mismo resultado en cada frame) ------------------
def hash_idx(i, seed, n):
    h = ((i + 1) * 2654435761 + seed * 97) & 0xFFFFFFFF
    h ^= h >> 15
    h = (h * 2246822519) & 0xFFFFFFFF
    h ^= h >> 13
    return h % max(1, int(n))


def hash_float(i, seed):
    """Valor pseudoaleatorio estable en [0, 1)."""
    return hash_idx(i, seed, 1 << 20) / float(1 << 20)


# --- matematicas y color ----------------------------------------------------
def clamp(v, lo, hi):
    return lo if v < lo else (hi if v > hi else v)


def lerp(a, b, f):
    return a + (b - a) * f


def rgb_lerp(c0, c1, f):
    return tuple(c0[i] + (c1[i] - c0[i]) * f for i in range(3))


def degrees(v):
    return math.radians(v)
