"""Raycast real contra la geometria de la escena.

Ignora los objetos que genera el propio addon y los marcados con
``laser_ignore``; reconoce espejos marcados con ``laser_mirror`` o detectados
por material metalico y liso.
"""

from ..core.constants import PREFIX


def cast(scene, dg, origin, direction, dist):
    """Primer impacto util del rayo.

    Devuelve ``(posicion, normal, objeto, indice_de_cara)`` o ``None``.
    """
    pos = origin
    for _ in range(256):
        ok, loc, n, idx, ob, _m = scene.ray_cast(dg, pos, direction, distance=dist)
        if not ok:
            return None
        if ob.name.startswith(PREFIX) or ob.get("laser_ignore"):
            dist -= (loc - pos).length + 1e-4
            if dist <= 0.0:
                return None
            pos = loc + direction * 1e-4
            continue
        return loc, n.normalized(), ob, idx
    return None


def is_mirror(ob, face, settings):
    """Decide si la cara golpeada actua como espejo."""
    value = ob.get("laser_mirror")
    if value is not None:
        return bool(value)
    if not settings.auto_mirror:
        return False
    try:
        mi = ob.data.polygons[face].material_index if face >= 0 else 0
        mat = ob.material_slots[mi].material if mi < len(ob.material_slots) else None
        if mat and mat.node_tree:
            for n in mat.node_tree.nodes:
                if n.type == 'BSDF_PRINCIPLED':
                    return (n.inputs['Metallic'].default_value >= 0.95 and
                            n.inputs['Roughness'].default_value <= 0.12)
    except Exception:
        pass
    return False
