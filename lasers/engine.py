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
from . import audio_color, collision, driver, geometry, materials


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
    """Niveles de audio del frame actual (ceros si el rig no reacciona)."""

    def __init__(self, scene, s, frame):
        self.drv = None
        self.aset = getattr(scene, "al", None)
        self.t = 0.0
        self.level = 0.0
        self.T = 60.0 / max(s.bpm, 1.0)
        drv = driver.get_driver(scene, s)
        if drv is None:
            return
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
    t = frame / fps + s.time_offset
    w = K.TAU * 0.25 * s.speed            # frecuencia base: 0.25 Hz * velocidad

    aud = _AudioState(scene, s, frame)
    # con audio, el BPM del pulso es el de la cancion (no hay que escribirlo)
    bpm = aud.drv.bpm if aud.drv is not None else s.bpm
    if aud.drv is not None and s.audio_on_speed:
        w *= 1.0 + s.audio_speed * (aud.level - 0.4)

    N = s.count
    al = aud.aset
    pal = acolors.palette_list(al) if al is not None else [(1.0, 1.0, 1.0)]
    seed = int(al.seed) if al is not None else 1
    nc = len(pal)
    shift = int(math.floor(t * s.color_speed))

    spread = min(s.spread * (1.0 + s.breath * math.sin(0.6 * w * t + 0.5)),
                 math.radians(178.0))
    if aud.drv is not None and s.audio_on_spread:
        spread = utils.clamp(
            spread * (1.0 + s.audio_spread * (2.0 * aud.level - 1.0)),
            0.0, math.radians(178.0))
    sweep = Euler((s.sweep * math.sin(w * t),
                   s.sweep * 0.6 * math.sin(0.73 * w * t + 1.0), 0.0)).to_matrix()
    spin = Matrix.Rotation(math.radians(s.spin) * s.speed * t, 3, 'Z')
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
                       s.wave * math.cos(1.31 * w * t + 1.7 * p), 0.0)).to_matrix() @ d
        d = (M @ d).normalized()

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
                f = 0.5 + 0.5 * math.cos(K.TAU * (t * bpm / 60.0 + s.chase * i / N))
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
