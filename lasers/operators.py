"""Operadores del rig de lasers: crear, reconstruir, marcar, presets y extras."""

import math
import uuid

import bpy
from bpy.props import BoolProperty, EnumProperty
from mathutils import Vector

from ..core import constants as K
from ..core import utils
from ..core.constants import PREFIX
from . import engine, materials, presets
from .ui import active_rig as _active_rig


class LASERFX_OT_create(bpy.types.Operator):
    bl_idname = "laserfx.create"
    bl_label = "Crear Laser Rig"
    bl_description = ("Crea un emisor de lasers en el cursor 3D con la "
                      "reaccion al audio lista para usar")
    bl_options = {'REGISTER', 'UNDO'}

    sync_audio: BoolProperty(
        name="Reaccionar al audio", default=True,
        description="Los rayos siguen el ritmo de la fuente configurada en el panel")

    def execute(self, context):
        scene = context.scene
        rig = bpy.data.objects.new("LZ_Rig", None)
        rig.empty_display_type = 'SINGLE_ARROW'
        rig.empty_display_size = 0.6
        rig.location = scene.cursor.location + Vector((0.0, 0.0, 3.0))
        rig.rotation_euler = (math.pi, 0.0, 0.0)     # apunta hacia abajo
        context.collection.objects.link(rig)
        with utils.mute_updates():
            s = rig.laserfx
            s.uid = uuid.uuid4().hex[:6]
            s.is_rig = True
            s.audio_enabled = bool(self.sync_audio)
        for o in context.selected_objects:
            o.select_set(False)
        rig.select_set(True)
        context.view_layer.objects.active = rig
        context.view_layer.update()
        engine.update_rig(rig, scene)
        return {'FINISHED'}


class LASERFX_OT_update(bpy.types.Operator):
    bl_idname = "laserfx.update"
    bl_label = "Recalcular"
    bl_description = "Fuerza la actualizacion de todos los rigs"

    def execute(self, context):
        engine.update_all(context.scene)
        return {'FINISHED'}


class LASERFX_OT_remove(bpy.types.Operator):
    bl_idname = "laserfx.remove"
    bl_label = "Eliminar Rig"
    bl_description = "Borra el rig activo y todo lo que genero"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return _active_rig(context) is not None

    def execute(self, context):
        rig = _active_rig(context)
        engine.remove_generated(rig.laserfx.uid)
        bpy.data.objects.remove(rig, do_unlink=True)
        return {'FINISHED'}


class LASERFX_OT_mark(bpy.types.Operator):
    bl_idname = "laserfx.mark"
    bl_label = "Marcar seleccion"
    bl_description = "Marca los objetos seleccionados como espejo, ignorados o normales"
    bl_options = {'REGISTER', 'UNDO'}
    mode: EnumProperty(items=[('MIRROR', "Espejo", ""), ('IGNORE', "Ignorar", ""),
                              ('CLEAR', "Normal", "")])

    def execute(self, context):
        for ob in context.selected_objects:
            if ob.name.startswith(PREFIX):
                continue
            for k in ("laser_mirror", "laser_ignore"):
                if k in ob:
                    del ob[k]
            if self.mode == 'MIRROR':
                ob["laser_mirror"] = 1
            elif self.mode == 'IGNORE':
                ob["laser_ignore"] = 1
        engine.update_all(context.scene)
        return {'FINISHED'}


class LASERFX_OT_style(bpy.types.Operator):
    bl_idname = "laserfx.style"
    bl_label = "Aplicar estilo"
    bl_description = "Configura todo el rig con el preset de estilo elegido"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return _active_rig(context) is not None

    def execute(self, context):
        rig = _active_rig(context)
        style = rig.laserfx.style_preset
        if not presets.apply(rig.laserfx, style):
            return {'CANCELLED'}
        engine.update_rig(rig, context.scene)
        self.report({'INFO'}, "Estilo aplicado: %s" % style)
        return {'FINISHED'}


class LASERFX_OT_auto_sync(bpy.types.Operator):
    bl_idname = "laserfx.auto_sync"
    bl_label = "Repartir reacciones"
    bl_description = ("Activa el audio en todos los rigs y reparte disparadores "
                      "para que no reaccionen todos igual")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        rigs = [ob for ob in context.scene.objects
                if hasattr(ob, "laserfx") and ob.laserfx.is_rig]
        if not rigs:
            self.report({'ERROR'}, "No hay rigs de lasers en la escena.")
            return {'CANCELLED'}
        with utils.mute_updates():
            for i, ob in enumerate(rigs):
                ob.laserfx.audio_enabled = True
                ob.laserfx.audio_trigger = presets.TRIGGER_ROTATION[
                    i % len(presets.TRIGGER_ROTATION)]
                ob.laserfx.audio_color_chase = 0.5 * i
        engine.update_all(context.scene)
        self.report({'INFO'}, "%d rigs configurados." % len(rigs))
        return {'FINISHED'}


class LASERFX_OT_demo(bpy.types.Operator):
    bl_idname = "laserfx.demo"
    bl_label = "Escena de prueba"
    bl_description = "Piso, pared, cubos y espejos para probar colisiones y rebotes"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        ops = bpy.ops.mesh

        def put(ob, mat, name):
            ob.name = name
            ob.data.materials.append(mat)
            return ob

        gray = materials.simple_material("Demo_Gris", (0.25, 0.25, 0.28), 0.0, 0.5)
        ops.primitive_plane_add(size=40, location=(0, 0, 0))
        put(context.active_object, gray, "Demo_Piso")
        ops.primitive_plane_add(size=40, location=(0, 12, 8),
                                rotation=(math.pi / 2, 0, 0))
        put(context.active_object, gray, "Demo_Pared")
        for i, (x, y) in enumerate(((-4, 2), (3, -1), (0, 5), (6, 4))):
            ops.primitive_cube_add(size=1.2 + 0.4 * i, location=(x, y, 0.6 + 0.2 * i))
            put(context.active_object, gray, "Demo_Cubo%d" % i)
        mirror = materials.simple_material("Demo_Espejo", (0.9, 0.9, 0.95), 1.0, 0.02)
        ops.primitive_uv_sphere_add(radius=1.0, location=(-2, -3, 1.0))
        ob = put(context.active_object, mirror, "Demo_EsferaEspejo")
        ob["laser_mirror"] = 1
        ops.primitive_plane_add(size=4, location=(5, -5, 2),
                                rotation=(math.pi / 2, 0, math.radians(35)))
        ob = put(context.active_object, mirror, "Demo_PlanoEspejo")
        ob["laser_mirror"] = 1
        try:
            if scene.world is None:
                scene.world = bpy.data.worlds.new("World")
            scene.world.use_nodes = True
            bg = scene.world.node_tree.nodes.get("Background")
            if bg:
                bg.inputs[0].default_value = (0.0, 0.0, 0.0, 1.0)
                bg.inputs[1].default_value = 0.02
        except Exception:
            pass
        context.view_layer.update()
        engine.update_all(scene)
        return {'FINISHED'}


class LASERFX_OT_haze(bpy.types.Operator):
    bl_idname = "laserfx.haze"
    bl_label = "Anadir humo (haze)"
    bl_description = "Cubo con volumen de niebla; se ve mejor en Cycles"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        bpy.ops.mesh.primitive_cube_add(
            size=1, location=context.scene.cursor.location + Vector((0, 0, 5)))
        ob = context.active_object
        ob.name = PREFIX + "Haze"
        ob.scale = (22, 22, 10)
        ob.display_type = 'WIRE'
        ob.data.materials.append(materials.haze_material())
        return {'FINISHED'}


CLASSES = (
    LASERFX_OT_create,
    LASERFX_OT_update,
    LASERFX_OT_remove,
    LASERFX_OT_mark,
    LASERFX_OT_style,
    LASERFX_OT_auto_sync,
    LASERFX_OT_demo,
    LASERFX_OT_haze,
)
