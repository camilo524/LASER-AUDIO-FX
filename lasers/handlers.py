"""Handlers de Blender: animacion frame a frame y modo en vivo."""

import bpy
from bpy.app.handlers import persistent

from ..core import constants as K
from ..core import utils
from . import engine


@persistent
def lz_frame_handler(scene, depsgraph=None):
    """Durante la reproduccion / render: recalcula cada rig en cada frame."""
    with utils.handler_lock() as run:
        if not run:
            return
        try:
            for ob in scene.objects:
                if getattr(ob, "laserfx", None) and ob.laserfx.is_rig:
                    engine.update_rig(ob, scene, depsgraph)
        except Exception as e:
            print("[LaserFX] error en frame handler:", e)


@persistent
def lz_depsgraph_handler(scene, depsgraph):
    """Modo en vivo: si mueves un objeto (o el rig) fuera de la reproduccion."""
    try:
        screen = bpy.context.screen
        if screen and screen.is_animation_playing:
            return
    except Exception:
        pass
    changed = False
    for u in depsgraph.updates:
        idb = u.id
        if (isinstance(idb, (bpy.types.Object, bpy.types.Mesh))
                and not idb.name.startswith(K.PREFIX)):
            changed = True
            break
    if not changed:
        return
    with utils.handler_lock() as run:
        if not run:
            return
        try:
            for ob in scene.objects:
                s = getattr(ob, "laserfx", None)
                if s is not None and s.is_rig and s.auto_update:
                    engine.update_rig(ob, scene, depsgraph)
        except Exception as e:
            print("[LaserFX] error en depsgraph handler:", e)


def register_handlers():
    unregister_handlers()
    bpy.app.handlers.frame_change_post.append(lz_frame_handler)
    bpy.app.handlers.render_pre.append(lz_frame_handler)
    bpy.app.handlers.depsgraph_update_post.append(lz_depsgraph_handler)


def unregister_handlers():
    handlers = bpy.app.handlers
    for lst in (handlers.frame_change_post, handlers.render_pre,
                handlers.depsgraph_update_post):
        for fn in list(lst):
            if getattr(fn, "__name__", "").startswith("lz_"):
                lst.remove(fn)
