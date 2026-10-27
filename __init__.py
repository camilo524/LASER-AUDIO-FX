"""Laser Audio FX: lasers de discoteca que reaccionan al ritmo de la cancion.

Unifica los dos scripts originales en un solo addon:

* ``Laser FX - Discoteca procedural``  ->  paquete ``lasers/``
* ``Audio Lights Sync``                ->  paquetes ``audio/`` y ``lights/``

El analisis de audio (DSP, BPM, beats, secciones) es comun: los lasers lo
usan para reaccionar en vivo y las luces para hornear keyframes.

Estructura
----------
``core/``    constantes, paletas y utilidades sin bpy.
``audio/``   DSP, analisis, curvas reactivas, triggers, colores y horneado.
``lasers/``  emisor de rayos: propiedades, geometria, colisiones y motor.
``lights/``  lista de luces, bake, marcadores y export a DaVinci Resolve.
"""

bl_info = {
    "name": "Laser Audio FX",
    "author": "Camilo",
    "version": (2, 2, 0),
    "blender": (4, 2, 0),
    "location": "Vista 3D > Barra lateral (N) > Laser Audio FX",
    "description": "Rayos laser procedurales con colisiones, rebotes e impactos "
                   "que reaccionan al ritmo de la cancion, mas sincronizacion de "
                   "luces, bake de keyframes, marcadores y export a DaVinci Resolve",
    "category": "Lighting",
}

import bpy
from bpy.props import PointerProperty

from . import audio, core, lasers, lights  # noqa: F401
from .lasers import handlers as laser_handlers

__all__ = ["audio", "core", "lasers", "lights"]


def _ordered_classes():
    """Orden seguro de registro, sin importar de que modulo viene cada clase.

    1) PropertyGroup  2) operadores / UIList  3) paneles, siempre despues de
    su ``bl_parent_id`` (el panel principal vive en ``audio`` y los hijos en
    ``lights`` y ``lasers``, por eso antes fallaba el registro).
    """
    allc = tuple(audio.CLASSES) + tuple(lasers.CLASSES) + tuple(lights.CLASSES)
    props = [c for c in allc if issubclass(c, bpy.types.PropertyGroup)]
    panels = [c for c in allc if issubclass(c, bpy.types.Panel)]
    others = [c for c in allc if c not in props and c not in panels]
    panels.sort(key=lambda c: getattr(c, "lafx_order", 100))   # orden visual

    ordered, done, pending = [], set(), list(panels)
    while pending:
        moved = False
        for c in list(pending):
            parent = getattr(c, "bl_parent_id", "")
            if not parent or parent in done:
                ordered.append(c)
                done.add(c.bl_idname)
                pending.remove(c)
                moved = True
        if not moved:               # padre inexistente: que Blender avise
            ordered.extend(pending)
            break
    return props + others + ordered


def register():
    unregister()        # permite re-ejecutar el script sin errores
    for cls in _ordered_classes():
        bpy.utils.register_class(cls)
    bpy.types.Scene.al = PointerProperty(type=lights.AL_Settings)
    bpy.types.Object.laserfx = PointerProperty(type=lasers.LZ_Settings)
    laser_handlers.register_handlers()
    lights.live.register_handlers()


def unregister():
    laser_handlers.unregister_handlers()
    if hasattr(bpy.types.Scene, "al"):
        del bpy.types.Scene.al
    if hasattr(bpy.types.Object, "laserfx"):
        del bpy.types.Object.laserfx
    for cls in reversed(_ordered_classes()):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass


if __name__ == "__main__":
    register()
