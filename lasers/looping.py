"""Loop de la animacion de los lasers (logica pura, sin ``bpy``).

Para que el rango ``loop_start..loop_end`` se repita sin saltos hay que cerrar
TODO lo que cambia con el tiempo:

* Por defecto el frame ``end`` es IDENTICO al frame ``start`` (periodo
  ``end - start``). Con ``close_end=False`` el periodo es ``end - start + 1`` y
  el identico a ``start`` es ``end + 1``.
* Cada oscilador (giro, barrido, respiracion, onda por rayo, pulso) se ajusta a
  un numero ENTERO de ciclos por loop, con minimo 1 (antes un giro lento se
  redondeaba a 0 vueltas y se quedaba quieto).
* El giro de color recorre la paleta un numero entero de veces.
* El audio real no es periodico: todo muestreo se hace DENTRO de la ventana del
  loop (tambien la "ola" por rayo, que mira un poco hacia atras) y en la
  costura se mezclan los ultimos instantes con los que preceden al inicio, asi
  brillo, apertura, estrobo y colores continuos no pegan un salto.
* ``Movimiento`` (el audio acelera barrido y giro) se aplica como una
  deformacion del tiempo que conserva el numero de ciclos: acelera y frena
  dentro del loop pero siempre vuelve a la misma fase al cerrarlo.
"""

import math

import numpy as np


# ------------------------------------------------------------------ utilidades
def _round_half_up(x):
    return int(math.floor(x + 0.5))


def _smooth(b):
    """Smoothstep 0..1 (sin esquina en los extremos de la mezcla)."""
    b = min(max(b, 0.0), 1.0)
    return b * b * (3.0 - 2.0 * b)


class LoopRates:
    """Frecuencias ya ajustadas para cerrar el loop (rad/s, Hz o pasos/s)."""

    __slots__ = ("w", "w_breath", "w_sweep_y", "w_wave_y", "spin_rate",
                 "color_rate", "pulse_rate", "cyc_sweep", "cyc_breath",
                 "cyc_wave", "cyc_spin", "cyc_pulse", "cyc_color")


class LoopPlan:
    """Rango del loop y reglas de cierre de fase."""

    def __init__(self, start, end, fps, close_end=True):
        self.start = int(start)
        # close_end: el frame END es igual al frame START (periodo END - START).
        # Si no, END es el ultimo frame distinto y END + 1 vuelve a START.
        span = int(end) - int(start) + (0 if close_end else 1)
        self.close_end = bool(close_end)
        self.frames = max(1, span)
        self.fps = float(fps)
        self.period = self.frames / self.fps          # segundos del loop

    # ------------------------------------------------------------- tiempo
    def local_frame(self, frame):
        """Posicion dentro del loop en frames: 0 <= u < N (admite subframes)."""
        return (float(frame) - self.start) % self.frames

    def wrap_frame(self, frame):
        """Frame equivalente dentro de ``start .. start + N``."""
        return self.start + self.local_frame(frame)

    def local_time(self, frame):
        return self.local_frame(frame) / self.fps

    # ------------------------------------------------------- ajuste de ciclos
    def cycles(self, freq_hz):
        """Ciclos enteros por loop mas cercanos (minimo 1, conserva el signo)."""
        if abs(freq_hz) < 1e-9:
            return 0
        n = max(1, _round_half_up(abs(freq_hz) * self.period))
        return n if freq_hz > 0 else -n

    def snap(self, freq_hz):
        """Frecuencia (Hz) con un numero entero de ciclos por loop."""
        return self.cycles(freq_hz) / self.period

    def color_steps(self, rate, palette_size):
        """Pasos de color por loop: multiplo de la paleta (minimo 1 vuelta)."""
        if abs(rate) < 1e-9:
            return 0
        size = max(1, int(palette_size))
        laps = max(1, _round_half_up(abs(rate) * self.period / size))
        steps = laps * size
        return steps if rate > 0 else -steps

    def rates(self, speed, spin_deg, color_speed, bpm, palette_size):
        """Todas las frecuencias del rig ajustadas al loop."""
        base = 0.25 * speed                      # Hz del barrido (como engine)
        r = LoopRates()
        r.cyc_sweep = self.cycles(base)
        r.cyc_breath = self.cycles(0.6 * base)
        r.cyc_wave = self.cycles(1.31 * base)
        r.w = math.tau * self.snap(base)
        r.w_breath = math.tau * self.snap(0.6 * base)
        r.w_sweep_y = math.tau * self.snap(0.73 * base)
        r.w_wave_y = math.tau * self.snap(1.31 * base)
        spin_hz = math.radians(spin_deg) * speed / math.tau
        r.cyc_spin = self.cycles(spin_hz)
        r.spin_rate = math.tau * r.cyc_spin / self.period
        r.cyc_color = self.color_steps(color_speed, palette_size)
        r.color_rate = r.cyc_color / self.period
        r.cyc_pulse = self.cycles(bpm / 60.0)
        r.pulse_rate = r.cyc_pulse / self.period
        return r


# ---------------------------------------------------------------------- audio
class LoopDriver:
    """Envuelve un ``Driver`` para que el audio sea periodico en el loop.

    Mantiene la misma interfaz (``level``, ``raw_level``, ``bands``,
    ``beat_state``, ``section_state`` ...). Todo lo demas se delega.

    Costura: en el ultimo ``fade`` segundos (un beat como mucho) la senal se
    mezcla con la que precede al inicio del loop, de modo que el valor al cerrar
    es el del frame inicial. Si el loop empieza pegado al inicio de la cancion
    (no hay audio previo) se mezcla el principio con lo que sigue al final.
    """

    loop = True

    def __init__(self, drv, t0, period, blend=True):
        self._drv = drv
        self.t0 = float(t0)
        self.period = max(float(period), 1e-6)
        # Con el audio sintetico (Loop por BPM) ya es periodico: sin mezcla.
        synthetic = getattr(getattr(drv, "al", None), "source", 'AUDIO') != 'AUDIO'
        self.blend = bool(blend) and not synthetic
        self.fade = max(1e-6, min(0.5 * self.period, float(drv.beat_period)))
        self._tail = (self.t0 - self.fade) >= -1e-9   # hay audio previo

    def __getattr__(self, name):          # bpm, beat_period, duration, time_at...
        return getattr(self._drv, name)

    # ---------------------------------------------------------- tiempo
    def wrap(self, t):
        """Instante de audio equivalente dentro de la ventana del loop."""
        return self.t0 + (float(t) - self.t0) % self.period

    def mix(self, t):
        """``(ta, tb, wb)``: senal = (1 - wb) * f(ta) + wb * f(tb)."""
        u = (float(t) - self.t0) % self.period
        ta = self.t0 + u
        if not self.blend:
            return ta, ta, 0.0
        if self._tail:
            lim = self.period - self.fade
            if u >= lim:
                return ta, ta - self.period, _smooth((u - lim) / self.fade)
        elif u < self.fade:
            return ta, ta + self.period, 1.0 - _smooth(u / self.fade)
        return ta, ta, 0.0

    def mix_array(self, ts):
        """Version vectorizada de ``mix`` (mismos resultados)."""
        ts = np.asarray(ts, dtype=np.float64)
        u = np.mod(ts - self.t0, self.period)
        ta = self.t0 + u
        tb = ta.copy()
        wb = np.zeros_like(ta)
        if self.blend:
            if self._tail:
                lim = self.period - self.fade
                m = u >= lim
                b = np.clip((u - lim) / self.fade, 0.0, 1.0)
                tb = np.where(m, ta - self.period, ta)
                wb = np.where(m, b * b * (3.0 - 2.0 * b), 0.0)
            else:
                m = u < self.fade
                b = np.clip(u / self.fade, 0.0, 1.0)
                tb = np.where(m, ta + self.period, ta)
                wb = np.where(m, 1.0 - b * b * (3.0 - 2.0 * b), 0.0)
        return ta, tb, wb

    def _mixed(self, fn, t):
        ta, tb, wb = self.mix(t)
        a = fn(ta)
        if wb <= 0.0:
            return a
        return a + (fn(tb) - a) * wb

    # ---------------------------------------------------------- muestreo
    def level(self, t):
        return self._mixed(self._drv.level, t)

    def raw_level(self, t, key):
        return self._mixed(lambda x: self._drv.raw_level(x, key), t)

    def bands(self, t):
        ta, tb, wb = self.mix(t)
        a = self._drv.bands(ta)
        if wb <= 0.0:
            return a
        b = self._drv.bands(tb)
        return tuple(x + (y - x) * wb for x, y in zip(a, b))

    def section_state(self, t):
        return self._drv.section_state(self.wrap(t))

    def beat_state(self, t, beats_per_step):
        return self._drv.beat_state(self.wrap(t), beats_per_step)

    def level_array(self, ts):
        """Nivel del trigger en muchos instantes a la vez (numpy)."""
        curve = self._drv.curves.get(self._drv.trigger)
        if curve is None or len(curve) == 0:
            return np.zeros(len(np.atleast_1d(ts)))
        fps = self._drv.grid_fps
        x = np.arange(len(curve), dtype=np.float64)
        ta, tb, wb = self.mix_array(ts)
        a = np.interp(ta * fps, x, curve)
        return a + (np.interp(tb * fps, x, curve) - a) * wb

    # -------------------------------------------------- Movimiento con audio
    def warped_time(self, u_seconds, amount, frames, base=0.4, sub=4):
        """Tiempo deformado por el audio que cierra en ``period``.

        La velocidad instantanea es ``1 + amount * (nivel - base)`` y se
        normaliza para que al final del loop el tiempo deformado valga exactamente
        ``period``. Asi el barrido y el giro aceleran con la musica pero cada
        oscilador termina con su numero entero de ciclos.
        """
        m = max(1, int(frames)) * sub
        grid = np.linspace(0.0, self.period, m + 1)
        g = np.clip(1.0 + amount * (self.level_array(self.t0 + grid) - base),
                    0.05, None)
        tau = np.concatenate(([0.0], np.cumsum(0.5 * (g[1:] + g[:-1]))))
        tau *= self.period / tau[-1]
        return float(np.interp(u_seconds, grid, tau))
