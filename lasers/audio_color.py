"""Color reactivo de los rayos: convierte el audio en el color de cada haz."""

import colorsys
import math
import random

from ..audio import colors as acolors
from ..core import utils


# Modo de color compartido (scene.al.color_mode) -> modo interno del muestreador
MODE_MAP = {'BEAT': 'PULSE', 'SECTION': 'SECTION', 'GRADIENT': 'GRADIENT',
            'ENERGY': 'ENERGY', 'SPECTRUM': 'SPECTRUM'}


class Sampler:
    """Resuelve el color del rayo (o luz) ``i`` segun el cambio de color compartido.

    Todo sale de ``scene.al`` (paleta, modo, cada cuantos beats, semilla), asi
    rayos y luces se ven iguales. ``mode`` queda en ``None`` si no hay que animar.
    """

    def __init__(self, drv, aset, t, n_beams, reparto='OFFSET', chase_beats=0.0):
        self.drv = drv
        self.a = aset
        self.t = float(t)
        self.n = max(1, int(n_beams))
        self.mode = MODE_MAP.get(aset.color_mode)
        self.reparto = reparto
        self.every = max(1, int(aset.color_every))
        self.grad_beats = max(0.5, float(aset.gradient_beats))
        self.seed = int(aset.seed)
        self.free = aset.palette_mode == 'FREE'
        self.pal = acolors.palette_list(aset)
        self.nc = len(self.pal)
        self.T = drv.beat_period
        self.chase_s = float(chase_beats) * self.T
        self._seq = None
        self._free_colors = None
        self._states = 1
        if self.mode in ('PULSE', 'SECTION'):
            self._build_states()

    # ------------------------------------------------------------- estados
    def _build_states(self):
        rng = random.Random(self.a.seed)
        if self.mode == 'PULSE':
            every = self.every * self.T
            self._states = max(1, int(max(0.0, self.drv.duration) / every) + 2)
        else:
            self._states = max(1, len(self.drv.sections) + 1)
        if self.free:
            self._free_colors = acolors.make_free(self._states, self.a, rng)
        else:
            self._seq = acolors.make_sequence(self._states, self.nc,
                                              self.a.color_pick, rng)

    def _state(self, t):
        if self.mode == 'SECTION':
            return self.drv.section_state(t)
        return self.drv.beat_state(t, self.every)

    # ------------------------------------------------------ reparto de color
    def _index(self, shift, i):
        """Reparte el color base (rayos o luces) segun ``al.color_spread``."""
        nc = self.nc
        mode = self.reparto
        if mode == 'SAME':
            return shift % nc
        if mode == 'BLOCKS':
            return (i * nc // self.n + shift) % nc
        if mode == 'RANDOM':
            return (utils.hash_idx(i, self.seed, nc) + shift) % nc
        return (i + shift) % nc

    def _palette(self, shift, i):
        return self.pal[self._index(shift, i)]

    def _free_beam(self, rgb, i):
        """En modo libre cada rayo puede llevar un tono algo distinto."""
        if self.reparto != 'RANDOM':
            return tuple(rgb)
        hue = colorsys.rgb_to_hsv(*rgb)[0] + utils.hash_float(i, self.seed) * 0.2
        return colorsys.hsv_to_rgb(hue % 1.0, self.a.free_sat, self.a.free_val)

    def _sequential(self, state, i):
        st = min(max(int(state), 0), self._states - 1)
        if self.free:
            return self._free_beam(self._free_colors[st], i)
        return self._palette(self._seq[st], i)

    # ----------------------------------------------------------------- api
    def color(self, i):
        """Color del rayo ``i`` (0..1 por canal) o ``None`` si no aplica."""
        t = self.t - (i / self.n) * self.chase_s
        if self.mode == 'GRADIENT':
            # Continuo en el tiempo: en un loop se mezcla en la costura.
            ta, tb, wb = self.drv.mix(t)
            c = self._gradient(ta)
            if wb > 0.0:
                c = utils.rgb_lerp(c, self._gradient(tb), wb)
            return c
        # La "ola" mira hacia atras: en un loop ese instante tiene que seguir
        # dentro del rango (sin loop, ``wrap`` no cambia nada).
        t = self.drv.wrap(t)
        if self.mode == 'SPECTRUM':
            return self._spectrum(t)
        if self.mode == 'ENERGY':
            return self._energy(t, i)
        return self._sequential(self._state(t), i)

    def _spectrum(self, t):
        bass, mid, high, _full = self.drv.bands(t)
        top = max(bass, mid, high)
        if top < 1e-4:
            return (0.0, 0.0, 0.0)
        return (bass / top, mid / top, high / top)

    def _gradient(self, t):
        beats = self.grad_beats
        pos = t / (beats * self.T)
        if self.free:
            frac = 0.5 - 0.5 * math.cos(math.pi * pos)
            hue = self.a.hue_min + (self.a.hue_max - self.a.hue_min) * frac
            return colorsys.hsv_to_rgb(hue % 1.0, self.a.free_sat, self.a.free_val)
        k0 = int(math.floor(pos))
        frac = pos - k0
        c0 = self.pal[k0 % self.nc]
        c1 = self.pal[(k0 + 1) % self.nc]
        return utils.rgb_lerp(c0, c1, frac)

    def _energy(self, t, i):
        level = self.drv.raw_level(t, "RAW_FULL")
        if self.free:
            hue = self.a.hue_min + (self.a.hue_max - self.a.hue_min) * level
            return colorsys.hsv_to_rgb(hue % 1.0, self.a.free_sat, self.a.free_val)
        shift = int(level * self.nc) % self.nc
        return self._palette(shift, i)
