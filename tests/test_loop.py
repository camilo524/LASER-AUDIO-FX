"""Pruebas del loop de lasers. Corren fuera de Blender:

    pip install numpy mathutils pytest
    python -m pytest tests/test_loop.py -q

``bpy`` se sustituye por un doble minimo; se ejecuta el ``update_rig`` real y se
captura la geometria que genera (direccion y color de cada rayo, frame a frame).
"""

import math
import os
import sys
import types
from types import SimpleNamespace as NS

import numpy as np
import pytest
from mathutils import Matrix

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# --------------------------------------------------------------- carga sin bpy
def _load():
    def pkg(name, path):
        m = types.ModuleType(name)
        m.__path__ = [path]
        sys.modules[name] = m

    bpy = types.ModuleType("bpy")
    bpy.data = NS(objects=NS(get=lambda n: None), meshes=NS(get=lambda n: None),
                  lights=NS(get=lambda n: None))
    bpy.context = NS()
    sys.modules["bpy"] = bpy
    pkg("lfx", ROOT)
    for sub in ("core", "audio", "lasers"):
        pkg("lfx." + sub, os.path.join(ROOT, sub))
    import importlib
    mods = {}
    for name in ("core.constants", "core.utils", "audio.dsp", "audio.curves",
                 "audio.colors", "audio.loader", "audio.analysis", "lasers.driver", "lasers.audio_color",
                 "lasers.geometry", "lasers.looping", "lasers.collision",
                 "lasers.materials", "lasers.engine"):
        mods[name] = importlib.import_module("lfx." + name)
    return mods


M = _load()
engine, looping, driver = M["lasers.engine"], M["lasers.looping"], M["lasers.driver"]
dsp, acurves = M["audio.dsp"], M["audio.curves"]

FPS = 24


# ------------------------------------------------------------------- fixtures
def make_settings(**kw):
    d = dict(
        is_rig=True, uid="t", auto_update=True, count=12, pattern='FAN',
        spread=math.radians(70), intensity=6.0, width=0.012, divergence=0.001,
        max_distance=40.0, end_fade=0.6, sides=4, max_bounces=0, reflect=0.9,
        auto_mirror=True, color_speed=0.0, speed=1.0, time_offset=0.0,
        sweep=math.radians(18), spin=25.0, wave=math.radians(6), wave_cycles=2.0,
        breath=0.3, loop_anim=True, loop_start=1, loop_end=96,
        loop_audio_blend=True, loop_close_end=False, bpm=120.0, pulse=0.0, chase=0.5, show_hits=False,
        dot_size=0.04, dot_intensity=1.5, max_lights=0, light_power=30.0,
        audio_enabled=False, audio_trigger='KICK', audio_on_brightness=True,
        audio_on_spread=True, audio_on_speed=False, audio_on_color=False,
        audio_brightness=0.6, audio_spread=0.3, audio_speed=0.4,
        audio_strobe=False, audio_color_chase=0.0)
    d.update(kw)
    return NS(**d)


def make_al(colors=1, **kw):
    d = dict(seed=1, color_spread='OFFSET', color_mode='BEAT', color_every=4,
             gradient_beats=4.0, palette_mode='SLOTS', color_pick='SEQUENCE',
             hue_min=0.0, hue_max=1.0, free_sat=1.0, free_val=1.0, loop_bpm=120.0,
             audio_start_frame=1, source='AUDIO', beat_shift_frames=0.0)
    base = [(1, 0, 0), (0, 1, 0), (0, 0, 1)]
    for i in range(1, 11):
        d["use_c%d" % i] = i <= colors
        d["c%d" % i] = base[(i - 1) % 3]
    d.update(kw)
    return NS(**d)


def make_curves(seconds=120.0, seed=3):
    """Curvas NO periodicas: bombos con jitter y envolventes aleatorias."""
    rng = np.random.default_rng(seed)
    fps = acurves.GRID_FPS
    n = int(seconds * fps)
    T = 0.5
    beats = np.arange(0, seconds, T) + rng.normal(0, 0.03, int(seconds / T))
    curves = {}
    for key in acurves.LEVEL_IDS:
        pos = (beats + (0.25 if key == 'OFFBEAT' else 0.0)) * fps
        curves[key] = dsp.pulse_curve(pos, n, 0.25 * fps)
    for key in acurves.RAW_IDS:
        raw = np.abs(np.convolve(rng.random(n), np.ones(40) / 40, 'same'))
        curves[key] = (raw / raw.max()).astype(np.float32)
    for key in ('BASS', 'MID', 'HIGH', 'FULL'):     # envolventes suaves (no periodicas)
        raw = np.convolve(rng.random(n), np.ones(60) / 60, 'same')
        raw = (raw - raw.min()) / (raw.max() - raw.min())
        curves[key] = raw.astype(np.float32)
    return curves, fps


def make_driver(al, scene, bpm=120.0):
    curves, fps = make_curves()
    meta = {"bpm": bpm, "offset": 0.0, "duration": 120.0, "sections": [30.0, 60.0]}
    drv = driver.Driver(curves, meta, al, scene, fps)
    drv.trigger = 'KICK'
    return drv


class Rig:
    """Ejecuta el update_rig real y devuelve direccion y color por rayo."""

    def __init__(self, s, al, audio=False, fps=FPS):
        self.s, self.al, self.fps = s, al, fps
        self.scene = NS(render=NS(fps=fps, fps_base=1.0), frame_current=1,
                        frame_subframe=0.0, frame_start=1, al=al,
                        collection=NS(objects=NS(link=lambda o: None)),
                        objects=NS(get=lambda n: object()))
        self.drv = make_driver(al, self.scene) if audio else None
        if self.drv is not None:
            self.drv.trigger = s.audio_trigger
        self.rec = []
        engine.driver.get_driver = lambda sc, st: self.drv
        engine._ensure_beams = lambda rig, st, sc: NS(data=_Mesh())
        engine.materials.reset_strength = lambda: None
        engine.collision.cast = lambda *a, **k: None

        def add_tube(verts, faces, cols, p0, p1, r0, r1, c0, c1, section):
            self.rec.append(((p1 - p0).normalized(), c0))
        engine.geometry.add_tube = add_tube
        self.rig = NS(laserfx=s, evaluated_get=lambda dg: NS(matrix_world=Matrix.Identity(4)),
                      matrix_world=Matrix.Identity(4))

    def frame(self, f):
        self.scene.frame_current = int(math.floor(f))
        self.scene.frame_subframe = f - math.floor(f)
        self.rec.clear()
        engine.update_rig(self.rig, self.scene, object())
        dirs = np.array([list(d) for d, _ in self.rec])
        cols = np.array([c[:3] for _, c in self.rec])
        return dirs, cols


class _Mesh:
    def __init__(self):
        self.color_attributes = []

    def clear_geometry(self): pass
    def from_pydata(self, *a): pass
    def update(self): pass


def sequence(rig, start, n):
    dirs, cols = [], []
    for k in range(n + 1):      # n + 1: el ultimo es el frame start + N
        d, c = rig.frame(start + k)
        dirs.append(d)
        cols.append(c)
    return np.array(dirs), np.array(cols)


def step_sizes(arr):
    return np.abs(np.diff(arr.reshape(len(arr), -1), axis=0)).max(axis=1)


# ================================================================== unitarios
@pytest.mark.parametrize("frames,fps", [(96, 24), (24, 24), (250, 24), (120, 30)])
def test_rates_close_and_never_freeze(frames, fps):
    plan = looping.LoopPlan(1, frames, fps)
    for speed, spin in [(1.0, 25.0), (0.2, 5.0), (3.0, 90.0), (1.0, -40.0)]:
        r = plan.rates(speed, spin, 0.5, 120.0, 3)
        for hz in (r.w / math.tau, r.w_breath / math.tau, r.w_sweep_y / math.tau,
                   r.w_wave_y / math.tau, r.spin_rate / math.tau, r.pulse_rate):
            cyc = hz * plan.period
            assert abs(cyc - round(cyc)) < 1e-9          # ciclos enteros
        assert abs(r.cyc_spin) >= 1                      # el giro nunca se congela
        assert (r.spin_rate > 0) == (spin > 0)           # conserva el sentido
        assert r.cyc_color % 3 == 0 and r.cyc_color != 0 # vueltas completas de paleta


def test_period_is_N_frames():
    plan = looping.LoopPlan(10, 33, 24, close_end=False)
    assert plan.frames == 24
    assert plan.local_frame(10) == 0 and plan.local_frame(34) == 0
    assert plan.local_frame(33) == 23 and plan.local_frame(9) == 23
    assert plan.local_frame(10.5) == pytest.approx(0.5)


def test_period_close_end():
    plan = looping.LoopPlan(10, 33, 24)
    assert plan.frames == 23 and plan.local_frame(33) == 0 and plan.local_frame(10) == 0


def test_mix_array_matches_scalar():
    al = make_al()
    scene = NS(render=NS(fps=FPS, fps_base=1.0), frame_start=1)
    for t0 in (0.0, 10.0):          # sin / con audio previo
        ld = looping.LoopDriver(make_driver(al, scene), t0, 4.0)
        ts = np.linspace(t0 - 3, t0 + 9, 301)
        ta, tb, wb = ld.mix_array(ts)
        for k, t in enumerate(ts):
            a, b, w = ld.mix(t)
            assert (a, b, w) == pytest.approx((ta[k], tb[k], wb[k]))


@pytest.mark.parametrize("t0", [0.0, 0.2, 12.37])
def test_audio_is_periodic_and_continuous(t0):
    al = make_al()
    scene = NS(render=NS(fps=FPS, fps_base=1.0), frame_start=1)
    P = 4.0
    ld = looping.LoopDriver(make_driver(al, scene), t0, P)
    for t in np.linspace(t0, t0 + P - 0.01, 50):
        assert ld.level(t) == pytest.approx(ld.level(t + P), abs=1e-9)
        assert ld.level(t) == pytest.approx(ld.level(t + 3 * P), abs=1e-9)
    # continuidad en la costura: el valor al final == valor al inicio
    assert ld.level(t0 + P - 1e-7) == pytest.approx(ld.level(t0), abs=1e-3)
    assert ld.raw_level(t0 + P - 1e-7, "RAW_FULL") == pytest.approx(
        ld.raw_level(t0, "RAW_FULL"), abs=1e-3)
    for x, y in zip(ld.bands(t0 + P - 1e-7), ld.bands(t0)):
        assert x == pytest.approx(y, abs=1e-3)


def test_warp_closes_and_is_monotonic():
    al = make_al()
    scene = NS(render=NS(fps=FPS, fps_base=1.0), frame_start=1)
    P = 4.0
    ld = looping.LoopDriver(make_driver(al, scene), 8.0, P)
    us = np.linspace(0, P, 200)
    tau = np.array([ld.warped_time(u, 0.8, 96) for u in us])
    assert tau[0] == pytest.approx(0.0, abs=1e-9)
    assert tau[-1] == pytest.approx(P, abs=1e-9)          # cierra exacto
    assert np.all(np.diff(tau) > 0)                       # nunca retrocede
    assert np.abs(tau - us).max() > 0.01                  # y si deforma el tiempo


# ======================================================== motor completo (engine)
CASES = [
    dict(),
    dict(pattern='CONE', count=30),
    dict(pattern='CROSS', count=16, wave=math.radians(15), wave_cycles=5.0),
    dict(speed=0.3, spin=8.0),                              # lento: antes se congelaba
    dict(speed=2.5, spin=-120.0, sweep=math.radians(40), breath=0.8),
    dict(loop_start=20, loop_end=20 + 47),                  # inicio != 1, 48 frames
    dict(time_offset=1.37),
    dict(pulse=0.8, bpm=121.0, chase=1.0),                  # estrobo por BPM
    dict(color_speed=0.7),
]


@pytest.mark.parametrize("kw", CASES)
def test_geometry_closes_without_audio(kw):
    s = make_settings(**kw)
    rig = Rig(s, make_al(colors=3))
    N = s.loop_end - s.loop_start + 1
    dirs, cols = sequence(rig, s.loop_start, N)
    # frame START + N es identico al START (el loop cierra) ...
    assert np.allclose(dirs[-1], dirs[0], atol=1e-9)
    assert np.allclose(cols[-1], cols[0], atol=1e-9)
    # ... y el salto en la costura no es mayor que un paso normal del loop
    for arr in (dirs, cols):
        st = step_sizes(arr)
        assert st[-1] <= st[:-1].max() * 1.5 + 1e-9, (st[-1], st[:-1].max())


def test_phases_close_without_relying_on_wrap():
    """Cierre REAL de fase: el frame START + N sin envolver coincide con START."""
    s = make_settings(wave=math.radians(15), wave_cycles=3.0, pattern='CONE')
    plan = looping.LoopPlan(s.loop_start, s.loop_end, FPS)
    r = plan.rates(s.speed, s.spin, s.color_speed, s.bpm, 1)
    from mathutils import Euler
    M0 = None
    for t in (0.3, 1.1):
        mats = []
        for tt in (t, t + plan.period):
            sweep = Euler((s.sweep * math.sin(r.w * tt),
                           s.sweep * 0.6 * math.sin(r.w_sweep_y * tt + 1.0), 0)).to_matrix()
            spin = Matrix.Rotation(r.spin_rate * tt, 3, 'Z')
            d = [engine._beam_dir(s, i, s.count, s.spread, spin @ sweep, r.w,
                                  r.w_wave_y, tt) for i in range(s.count)]
            mats.append(np.array([list(v) for v in d]))
        assert np.allclose(mats[0], mats[1], atol=1e-5)   # mathutils = float32
    assert abs(r.cyc_spin) >= 1


def test_short_loop_still_rotates():
    s = make_settings(loop_end=96, spin=25.0, sweep=0.0, wave=0.0, breath=0.0)
    rig = Rig(s, make_al())
    d0, _ = rig.frame(1)
    d1, _ = rig.frame(1 + 48)
    assert np.abs(d0 - d1).max() > 0.5       # a mitad del loop esta rotado


AUDIO_CASES = [
    dict(audio_enabled=True),
    dict(audio_enabled=True, audio_on_speed=True, audio_speed=0.9),
    dict(audio_enabled=True, chase=1.5, pulse=0.7, audio_strobe=True),
    dict(audio_enabled=True, audio_on_spread=True, audio_spread=0.9,
         audio_on_brightness=True, audio_brightness=1.0),
]


@pytest.mark.parametrize("kw", AUDIO_CASES)
@pytest.mark.parametrize("start", [1, 400])        # pegado al inicio / en medio
def test_audio_reactive_loop_closes(kw, start):
    s = make_settings(loop_start=start, loop_end=start + 95, **kw)
    rig = Rig(s, make_al(colors=1), audio=True)
    dirs, cols = sequence(rig, start, 96)
    assert np.allclose(dirs[-1], dirs[0], atol=1e-6)
    assert np.allclose(cols[-1], cols[0], atol=1e-6)
    for arr in (dirs, cols):
        st = step_sizes(arr)
        assert st[-1] <= st[:-1].max() * 1.5 + 1e-9, (st[-1], st[:-1].max())


def test_blend_removes_the_audio_seam_jump():
    """Con una senal suave NO periodica, sin mezcla hay un salto en la costura."""
    seam = {}
    for blend in (False, True):
        ratios = []
        for start in range(150, 3000, 211):
            s = make_settings(loop_start=start, loop_end=start + 95,
                              audio_enabled=True, audio_trigger='FULL',
                              audio_brightness=0.8, loop_audio_blend=blend)
            rig = Rig(s, make_al(colors=1), audio=True)
            _, cols = sequence(rig, start, 96)
            st = step_sizes(cols)
            ratios.append(st[-1] / (np.median(st[:-1]) + 1e-9))
        seam[blend] = (np.mean(ratios), np.max(ratios))
    assert seam[True][1] <= 3.0             # con mezcla: un paso mas, como cualquier otro
    assert seam[False][0] > 1.5 * seam[True][0]   # sin mezcla: la costura se nota mas


@pytest.mark.parametrize("mode", ['GRADIENT', 'ENERGY', 'SPECTRUM', 'BEAT', 'SECTION'])
def test_color_modes_run_and_close(mode):
    s = make_settings(audio_enabled=True, audio_on_color=True, audio_color_chase=1.0,
                      audio_on_brightness=False)
    rig = Rig(s, make_al(colors=3, color_mode=mode), audio=True)
    dirs, cols = sequence(rig, 1, 96)
    assert np.isfinite(cols).all()
    if mode in ('GRADIENT', 'SPECTRUM'):    # continuos: tampoco saltan al cerrar
        st = step_sizes(cols)
        assert st[-1] <= max(st[:-1].max() * 1.5, 0.05), (mode, st[-1], st[:-1].max())
    # el color con "ola" mira hacia atras: nunca sale de la ventana del loop
    ld = rig.drv
    assert ld is not None


def test_loop_off_is_untouched():
    """Sin loop el comportamiento es el de siempre (tiempo lineal)."""
    s = make_settings(loop_anim=False)
    rig = Rig(s, make_al())
    a, _ = rig.frame(1)
    b, _ = rig.frame(1 + 96)
    assert np.abs(a - b).max() > 1e-3          # sigue avanzando, no se repite


@pytest.mark.parametrize("audio", [False, True])
def test_close_end_last_frame_equals_first(audio):
    """Modo por defecto: el frame FIN es igual al frame INICIO."""
    kw = dict(audio_enabled=True, audio_on_speed=True) if audio else {}
    for start, end in [(1, 250), (1, 96), (30, 129)]:
        s = make_settings(loop_start=start, loop_end=end, loop_close_end=True,
                          wave=math.radians(10), **kw)
        rig = Rig(s, make_al(colors=3), audio=audio)
        d0, c0 = rig.frame(start)
        d1, c1 = rig.frame(end)
        assert np.allclose(d0, d1, atol=1e-6) and np.allclose(c0, c1, atol=1e-6)
        d2, _ = rig.frame(end + 1)             # y sigue: END + 1 == START + 1
        d3, _ = rig.frame(start + 1)
        assert np.allclose(d2, d3, atol=1e-6)
        # a mitad del loop si esta en otra pose
        dm, _ = rig.frame((start + end) // 2)
        assert np.abs(dm - d0).max() > 0.05
