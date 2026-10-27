"""Motor de lasers.

Reconstruye en cada frame una unica malla con los tubos de los rayos y los
discos de impacto, resuelve colisiones reales con ``scene.ray_cast`` y, si el
rig tiene el audio activado, modula brillo, apertura, velocidad y color con el
ritmo de la cancion (mismas curvas que usa la sincronizacion de luces).
"""

import math

import bpy
from mathutils import Euler, Matrix, Vector

from ..audio import colors as acolors
from ..core import constants as K
from ..core import utils
from . import audio_color, collision, driver, geometry, looping, materials


# --------------------------------------------------------------------- objetos
def _target_collection(rig, scene):
    return rig.users_collection[0] if rig.users_collection else scene.collection


def _ensure_beams(rig, s, scene):
    """Objeto de malla donde se vuelca toda la geometria del rig."""
    name = "%s%s_Beams" % (K.PREFIX, s.uid)
    obj = bpy.data.objects.get(name)
    if obj is None or obj.type != 'MESH':
        mesh = bpy.data.meshes.get(name) or bpy.data.meshes.new(name)
        obj = bpy.data.objects.new(name, mesh)
        obj.hide_select = True
        try:
            obj.visible_shadow = False
        except Exception:
            pass
    if scene.objects.get(name) is None:
        _target_collection(rig, scene).objects.link(obj)
    if not obj.data.materials:
        obj.data.materials.append(materials.get_material())
    return obj


def _ensure_light(rig, s, scene, k):
    name = "%s%s_L%d" % (K.PREFIX, s.uid, k)
    lo = bpy.data.objects.get(name)
    if lo is None:
        data = bpy.data.lights.get(name) or bpy.data.lights.new(name, 'POINT')
        data.shadow_soft_size = 0.05
        data.energy = 0.0
        lo = bpy.data.objects.new(name, data)
        lo.hide_select = True
        _target_collection(rig, scene).objects.link(lo)
    return lo


def remove_generated(uid):
    """Borra todo lo que genero un rig (mallas, luces y objetos)."""
    pre = "%s%s_" % (K.PREFIX, uid)
    for o in [o for o in bpy.data.objects if o.name.startswith(pre)]:
        bpy.data.objects.remove(o, do_unlink=True)
    for m in [m for m in bpy.data.meshes if m.name.startswith(pre)]:
        bpy.data.meshes.remove(m)
    for l in [l for l in bpy.data.lights if l.name.startswith(pre)]:
        bpy.data.lights.remove(l)


# ----------------------------------------------------------------------- audio
class _AudioState:
    """Niveles de audio del frame actual (ceros si el rig no reacciona).

    Con un loop activo el driver se envuelve en ``looping.LoopDriver``: todo el
    muestreo (nivel, ola por rayo, color) cae dentro del rango y se mezcla en la
    costura, asi el audio tambien cierra.
    """

    def __init__(self, scene, s, frame, plan=None):
        self.drv = None
        self.aset = getattr(scene, "al", None)
        self.t = 0.0
        self.level = 0.0
        self.T = 60.0 / max(s.bpm, 1.0)
        drv = driver.get_driver(scene, s)
        if drv is None:
            return
        if plan is not None:
            drv = looping.LoopDriver(drv, drv.time_at(plan.start), plan.period,
                                     blend=s.loop_audio_blend)
        self.drv = drv
        self.t = drv.time_at(frame)
        self.level = drv.level(self.t)
        self.T = drv.beat_period

    def level_at(self, t):
        return self.drv.level(t) if self.drv is not None else 0.0

    def brightness(self, s, level):
        """Cuanto manda el audio en la intensidad del rayo."""
        if self.drv is None or not s.audio_on_brightness:
            return 1.0
        return (1.0 - s.audio_brightness) + s.audio_brightness * 2.0 * level


def _beam_dir(s, i, N, spread, M, w, w_wave_y, t):
    """Direccion del rayo ``i`` (patron + onda por rayo + giro/barrido ``M``)."""
    # ---- patron de direcciones (eje local +Z) ----
    if s.pattern == 'CONE':
        th = 0.0 if N == 1 else (spread * 0.5) * math.sqrt((i + 0.5) / N)
        ph = i * K.GOLDEN
        d = Vector((math.sin(th) * math.cos(ph), math.sin(th) * math.sin(ph),
                    math.cos(th)))
    elif s.pattern == 'CROSS':
        grp = i & 1
        j = i >> 1
        cnt = (N + 1 - grp) // 2
        a = ((j + 0.5) / cnt - 0.5) * spread
        d = (Vector((math.sin(a), 0.0, math.cos(a))) if grp == 0
             else Vector((0.0, math.sin(a), math.cos(a))))
    else:  # FAN
        a = ((i + 0.5) / N - 0.5) * spread
        d = Vector((math.sin(a), 0.0, math.cos(a)))

    # ---- onda armonica por rayo ----
    if s.wave > 0.0:
        p = (i / N) * K.TAU * s.wave_cycles
        d = Euler((s.wave * math.sin(w * t + p),
                   s.wave * math.cos(w_wave_y * t + 1.7 * p), 0.0)).to_matrix() @ d
    return (M @ d).normalized()


# -------------------------------------------------------------------- rebuild
def update_rig(rig, scene=None, dg=None):
    """Reconstruye el rig completo (geometria, impactos y luces)."""
    s = getattr(rig, "laserfx", None)
    if s is None or not s.is_rig or not s.uid:
        return
    scene = scene or bpy.context.scene
    if dg is None:
        dg = bpy.context.evaluated_depsgraph_get()
    obj = _ensure_beams(rig, s, scene)
    materials.reset_strength()

    try:
        mw = rig.evaluated_get(dg).matrix_world
    except Exception:
        mw = rig.matrix_world
    origin = mw.translation.copy()
    rot = mw.to_3x3().normalized()

    render = scene.render
    fps = render.fps / render.fps_base
    frame = scene.frame_current + scene.frame_subframe
    al = getattr(scene, "al", None)
    plan = None
    if s.loop_anim and s.loop_end > s.loop_start:
        plan = looping.LoopPlan(s.loop_start, s.loop_end, fps, s.loop_close_end)
        # close_end: el frame END es identico al frame START.
        frame = plan.wrap_frame(frame)
        u = plan.local_time(frame)              # segundos dentro del loop
        t = u + s.time_offset
    else:
        t = frame / fps + s.time_offset

    # Frecuencias base. Con loop, cada oscilador (barrido, respiracion, onda,
    # giro, pulso) y el giro de color se ajustan a ciclos ENTEROS por loop.
    base_w = K.TAU * 0.25 * s.speed
    w = base_w
    w_breath = 0.6 * base_w
    w_sweep_y = 0.73 * base_w
    w_wave_y = 1.31 * base_w
    spin_rate = math.radians(s.spin) * s.speed
    color_rate = s.color_speed

    aud = _AudioState(scene, s, frame, plan)
    bpm = aud.drv.bpm if aud.drv is not None else s.bpm
    pulse_rate = bpm / 60.0

    t_osc = t       # tiempo con el que avanzan giro / barrido / onda
    if plan is not None:
        rates = plan.rates(s.speed, s.spin, s.color_speed, bpm,
                           len(acolors.palette_list(al)) if al is not None else 1)
        w, w_breath = rates.w, rates.w_breath
        w_sweep_y, w_wave_y = rates.w_sweep_y, rates.w_wave_y
        spin_rate, color_rate = rates.spin_rate, rates.color_rate
        pulse_rate = rates.pulse_rate
        if aud.drv is not None and s.audio_on_speed:
            # Movimiento con audio: el tiempo se acelera/frena con la musica pero
            # siempre llega a END con los mismos ciclos completos.
            t_osc = (aud.drv.warped_time(u, s.audio_speed, plan.frames)
                     + s.time_offset)
    elif aud.drv is not None and s.audio_on_speed:
        audio_speed_factor = 1.0 + s.audio_speed * (aud.level - 0.4)
        w *= audio_speed_factor
        w_breath *= audio_speed_factor
        w_sweep_y *= audio_speed_factor
        w_wave_y *= audio_speed_factor

    N = s.count
    pal = acolors.palette_list(al) if al is not None else [(1.0, 1.0, 1.0)]
    seed = int(al.seed) if al is not None else 1
    nc = len(pal)
    shift = int(math.floor(t * color_rate))

    spread = min(s.spread * (1.0 + s.breath * math.sin(w_breath * t_osc + 0.5)),
                 math.radians(178.0))
    if aud.drv is not None and s.audio_on_spread:
        spread = utils.clamp(
            spread * (1.0 + s.audio_spread * (2.0 * aud.level - 1.0)),
            0.0, math.radians(178.0))
    sweep = Euler((s.sweep * math.sin(w * t_osc),
                   s.sweep * 0.6 * math.sin(w_sweep_y * t_osc + 1.0), 0.0)).to_matrix()
    spin = Matrix.Rotation(spin_rate * (t_osc if plan is not None else t), 3, 'Z')
    M = rot @ spin @ sweep

    section = geometry.circle_section(s.sides)
    radius0 = s.width * 0.5
    div = s.divergence

    sampler = None
    if aud.drv is not None and al is not None and s.audio_on_color:
        smp = audio_color.Sampler(aud.drv, al, aud.t, N, al.color_spread,
                                  s.audio_color_chase)
        if smp.mode is not None:
            sampler = smp

    verts, faces, cols = [], [], []
    light_hits = []

    for i in range(N):
        level = aud.level
        if aud.drv is not None and s.chase > 0.0:
            level = aud.level_at(aud.t - s.chase * aud.T * (i / N))

        d = _beam_dir(s, i, N, spread, M, w, w_wave_y, t_osc)

        # ---- color (reactivo o de la paleta del rig) ----
        c = sampler.color(i) if sampler is not None else None
        if c is None:
            # Un solo reparto del color para rayos y luces: al.color_spread
            reparto = al.color_spread if al is not None else 'OFFSET'
            if reparto == 'BLOCKS':
                ci = (i * nc // N + shift) % nc
            elif reparto == 'RANDOM':
                ci = (utils.hash_idx(i, seed, nc) + shift) % nc
            elif reparto == 'SAME':
                ci = shift % nc
            else:
                ci = (i + shift) % nc
            c = pal[ci]

        # ---- pulso / estrobo (por BPM o por audio) ----
        pulse = 1.0
        if s.pulse > 0.0:
            if aud.drv is not None and s.audio_strobe:
                f = level
            else:
                f = 0.5 + 0.5 * math.cos(K.TAU * (t * pulse_rate + s.chase * i / N))
            pulse = 1.0 - s.pulse * (1.0 - f ** 3)
        bright = s.intensity * pulse * aud.brightness(s, level)
        if bright <= 1e-4:
            continue

        # ---- trazado con rebotes ----
        pos = origin.copy()
        inten = 1.0
        travelled = 0.0
        remaining = s.max_distance
        for bounce in range(s.max_bounces + 1):
            res = collision.cast(scene, dg, pos, d, remaining)
            if res is None:
                end = pos + d * remaining
                seg_len = remaining
                hit = False
            else:
                loc, nrm, hob, face = res
                end = loc
                seg_len = (loc - pos).length
                hit = True
            k = bright * inten
            c0 = (c[0] * k, c[1] * k, c[2] * k, 1.0)
            c1 = (c0[0], c0[1], c0[2], 1.0 if hit else 1.0 - s.end_fade)
            geometry.add_tube(verts, faces, cols, pos, end,
                              radius0 + travelled * div,
                              radius0 + (travelled + seg_len) * div,
                              c0, c1, section)
            travelled += seg_len
            remaining -= seg_len
            if not hit:
                break
            if nrm.dot(d) > 0.0:
                nrm = -nrm
            mirror = bounce < s.max_bounces and collision.is_mirror(hob, face, s)
            if s.show_hits:
                dk = k * s.dot_intensity * (0.25 if mirror else 1.0)
                geometry.add_disc(verts, faces, cols, loc, nrm, d,
                                  s.dot_size + travelled * div * 2.0,
                                  (c[0] * dk, c[1] * dk, c[2] * dk), travelled)
                if s.max_lights > 0 and not mirror:
                    light_hits.append((loc + nrm * 0.06, c, inten * pulse))
            if not mirror:
                break
            d = d.reflect(nrm).normalized()
            pos = loc + nrm * 1e-4
            inten *= s.reflect
            if remaining <= 0.01 or inten < 0.02:
                break
        if len(verts) > K.MAX_VERTS:
            break

    # ---- escribir malla ----
    mesh = obj.data
    for ca in list(mesh.color_attributes):
        mesh.color_attributes.remove(ca)
    mesh.clear_geometry()
    if verts:
        mesh.from_pydata(verts, [], faces)
        ca = mesh.color_attributes.new("LZ_col", 'FLOAT_COLOR', 'POINT')
        ca.data.foreach_set("color", [x for col in cols for x in col])
    mesh.update()

    # ---- luces reales de impacto (opcional) ----
    K_lights = s.max_lights if s.show_hits else 0
    chosen = []
    if K_lights and light_hits:
        chosen = light_hits[::max(1, len(light_hits) // K_lights)][:K_lights]
    for k in range(K.MAX_LIGHTS):
        if k < len(chosen):
            loc, c, e = chosen[k]
            lo = _ensure_light(rig, s, scene, k)
            lo.location = loc
            lo.data.color = c
            lo.data.energy = s.light_power * e
        else:
            lo = bpy.data.objects.get("%s%s_L%d" % (K.PREFIX, s.uid, k))
            if lo and lo.data.energy != 0.0:
                lo.data.energy = 0.0


def update_all(scene, dg=None):
    """Recalcula todos los rigs de la escena."""
    for ob in scene.objects:
        s = getattr(ob, "laserfx", None)
        if s is not None and s.is_rig:
            update_rig(ob, scene, dg)
