"""Construccion de la malla de los rayos y de los puntos de impacto."""

import math

from mathutils import Vector

from ..core.constants import TAU


def add_tube(verts, faces, cols, p0, p1, r0, r1, c0, c1, section):
    """Anade el tubo de un tramo de rayo a las listas de geometria."""
    d = p1 - p0
    length = d.length
    if length < 1e-6:
        return
    d /= length
    ref = Vector((0.0, 0.0, 1.0)) if abs(d.z) < 0.99 else Vector((1.0, 0.0, 0.0))
    u = d.cross(ref).normalized()
    v = d.cross(u)
    n = len(section)
    base = len(verts)
    for cs, sn in section:
        verts.append(p0 + (u * cs + v * sn) * r0)
        cols.append(c0)
    for cs, sn in section:
        verts.append(p1 + (u * cs + v * sn) * r1)
        cols.append(c1)
    for k in range(n):
        k2 = (k + 1) % n
        faces.append((base + k, base + k2, base + n + k2, base + n + k))


def add_disc(verts, faces, cols, pos, nrm, dvec, radius, color, dist):
    """Mancha de luz: se estira en angulos rasantes y se difumina en el borde."""
    cosang = max(abs(nrm.dot(dvec)), 0.2)
    t1 = dvec - nrm * dvec.dot(nrm)
    if t1.length < 1e-5:
        t1 = nrm.orthogonal()
    t1.normalize()
    t2 = nrm.cross(t1)
    center = pos + nrm * max(0.003, dist * 0.0004)
    seg = 12
    base = len(verts)
    verts.append(center)
    cols.append((color[0], color[1], color[2], 1.0))
    for rf, alpha in ((0.5, 0.7), (1.0, 0.0)):
        for k in range(seg):
            a = TAU * k / seg
            verts.append(center + t1 * (math.cos(a) * radius * rf / cosang)
                         + t2 * (math.sin(a) * radius * rf))
            cols.append((color[0], color[1], color[2], alpha))
    r1 = base + 1
    r2 = base + 1 + seg
    for k in range(seg):
        k2 = (k + 1) % seg
        faces.append((base, r1 + k, r1 + k2))
        faces.append((r1 + k, r1 + k2, r2 + k2, r2 + k))


def circle_section(sides):
    """Puntos unitarios del poligono de la seccion del tubo."""
    return [(math.cos(TAU * k / sides + math.pi / sides),
             math.sin(TAU * k / sides + math.pi / sides)) for k in range(sides)]
