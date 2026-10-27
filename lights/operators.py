"""Operadores de la sincronizacion de luces (lista, horneado, marcadores, EDL)."""

import math
import os

import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, StringProperty
from bpy_extras.io_utils import ExportHelper

from ..audio import analysis, bake, colors, triggers
from ..audio.targets import Prefs, Target, set_interp
from ..core.constants import MARKER_PREFIX, PREFIX


class AL_OT_add_selected(bpy.types.Operator):
    bl_idname = "al.add_selected"
    bl_label = "Agregar seleccion"
    bl_description = "Agrega las luces (y mallas con emision) seleccionadas a la lista"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        s = context.scene.al
        have = {it.obj for it in s.lights if it.obj}
        added = 0
        lasers = 0
        for obj in context.selected_objects:
            if obj in have:
                continue
            if (obj.name.startswith(PREFIX)
                    or getattr(getattr(obj, "laserfx", None), "is_rig", False)):
                lasers += 1
                continue
            tg = Target(obj)
            if not tg.ok:
                continue
            it = s.lights.add()
            it.obj = obj
            cur = tg.current_level()
            it.energy_max = max(cur, 0.001)
            it.energy_min = it.energy_max * 0.05
            added += 1
        s.lights_index = max(0, len(s.lights) - 1)
        msg = "%d objetos agregados" % added
        if lasers:
            msg += " (los rayos no hace falta agregarlos: ya siguen el audio solos)"
        self.report({'INFO'}, msg)
        return {'FINISHED'}


class AL_OT_remove_item(bpy.types.Operator):
    bl_idname = "al.remove_item"
    bl_label = "Quitar"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        s = context.scene.al
        if 0 <= s.lights_index < len(s.lights):
            s.lights.remove(s.lights_index)
            s.lights_index = max(0, s.lights_index - 1)
        return {'FINISHED'}


class AL_OT_clear_items(bpy.types.Operator):
    bl_idname = "al.clear_items"
    bl_label = "Vaciar lista"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        context.scene.al.lights.clear()
        return {'FINISHED'}


class AL_OT_auto_triggers(bpy.types.Operator):
    bl_idname = "al.auto_triggers"
    bl_label = "Repartir reacciones"
    bl_description = "Asigna reacciones variadas a las luces para que no todas hagan lo mismo"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        pattern = ['KICK', 'OFFBEAT', 'HIGH', 'BEAT', 'MID', 'DOWNBEAT']
        for i, it in enumerate(context.scene.al.lights):
            it.trigger = pattern[i % len(pattern)]
        return {'FINISHED'}


class AL_OT_chase(bpy.types.Operator):
    bl_idname = "al.chase"
    bl_label = "Aplicar chase (ola)"
    bl_description = "Desfasa cada luz un poco mas que la anterior para crear efecto ola"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        s = context.scene.al
        for i, it in enumerate(s.lights):
            it.delay_beats = i * s.chase_step
        return {'FINISHED'}


class AL_OT_single_user(bpy.types.Operator):
    bl_idname = "al.single_user"
    bl_label = "Hacer luces unicas"
    bl_description = ("Si varias luces comparten datos, se animarian igual. "
                      "Esto las separa")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        n = 0
        for it in context.scene.al.lights:
            if it.obj and it.obj.type == 'LIGHT' and it.obj.data.users > 1:
                it.obj.data = it.obj.data.copy()
                n += 1
        self.report({'INFO'}, "%d luces separadas" % n)
        return {'FINISHED'}


class AL_OT_palette_preset(bpy.types.Operator):
    bl_idname = "al.palette_preset"
    bl_label = "Preset de paleta"
    bl_options = {'REGISTER', 'UNDO'}
    preset: StringProperty()

    def execute(self, context):
        colors.apply_palette_preset(context.scene.al, self.preset)
        return {'FINISHED'}


class AL_OT_bake(bpy.types.Operator):
    bl_idname = "al.bake"
    bl_label = "Hornear luces al ritmo"
    bl_description = ("Analiza la fuente y crea los keyframes de intensidad y "
                      "color en el rango de frames de la escena")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        try:
            n, ana = bake.run_bake(context)
        except Exception as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}
        self.report({'INFO'}, "Listo: %d luces animadas a %.1f BPM" % (n, ana["bpm"]))
        return {'FINISHED'}


class AL_OT_clear_anim(bpy.types.Operator):
    bl_idname = "al.clear_anim"
    bl_label = "Borrar animacion de luces"
    bl_description = "Quita los keyframes de energia y color de las luces de la lista"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        for it in context.scene.al.lights:
            if it.obj:
                tg = Target(it.obj)
                if tg.ok:
                    tg.clear()
        context.scene.frame_set(context.scene.frame_current)
        return {'FINISHED'}


class AL_OT_markers(bpy.types.Operator):
    bl_idname = "al.markers"
    bl_label = "Marcadores en el timeline"
    bl_description = ("Crea marcadores en cada compas (y cambio de color) para "
                      "guiarte visualmente")
    bl_options = {'REGISTER', 'UNDO'}
    include_beats: BoolProperty(name="Incluir cada beat", default=False)

    def execute(self, context):
        scene = context.scene
        s = scene.al
        try:
            ana = analysis.get() or analysis.build_analysis(scene)
        except Exception as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}
        for m in list(scene.timeline_markers):
            if m.name.startswith(MARKER_PREFIX):
                scene.timeline_markers.remove(m)
        fps = analysis.scene_fps(scene)
        start = s.audio_start_frame if s.source == 'AUDIO' else scene.frame_start
        shift = s.beat_shift_frames
        n = 0
        for tsec, kind, name in triggers.plan_events(s, ana):
            if kind == 'BEAT' and not self.include_beats:
                continue
            fr = int(round(start + tsec * fps + shift))
            if scene.frame_start <= fr <= scene.frame_end:
                scene.timeline_markers.new(MARKER_PREFIX + name, frame=fr)
                n += 1
        self.report({'INFO'}, "%d marcadores creados" % n)
        return {'FINISHED'}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)


class AL_OT_clear_markers(bpy.types.Operator):
    bl_idname = "al.clear_markers"
    bl_label = "Borrar marcadores"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        for m in list(scene.timeline_markers):
            if m.name.startswith(MARKER_PREFIX):
                scene.timeline_markers.remove(m)
        return {'FINISHED'}


class AL_OT_export_resolve(bpy.types.Operator, ExportHelper):
    bl_idname = "al.export_resolve"
    bl_label = "Exportar marcadores para DaVinci Resolve"
    bl_description = ("Crea un .edl con marcadores de compases/beats y cambios de "
                      "color. En Resolve: Timeline > Import > Timeline Markers from EDL")
    filename_ext = ".edl"
    filter_glob: StringProperty(default="*.edl", options={'HIDDEN'})
    include_beats: BoolProperty(name="Incluir cada beat", default=False)
    tc_hour: IntProperty(name="Hora inicial del timeline", default=1, min=0, max=23,
                         description="Resolve empieza en 01:00:00:00 por defecto")
    max_seconds: FloatProperty(name="Hasta (segundos, 0 = todo)", default=0.0, min=0.0)

    def execute(self, context):
        scene = context.scene
        s = scene.al
        try:
            ana = analysis.get() or analysis.build_analysis(scene)
        except Exception as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}
        fps = analysis.scene_fps(scene)
        base = int(round(fps))
        palette = {'BAR': "ResolveColorRed", 'BEAT': "ResolveColorBlue",
                   'COLOR': "ResolveColorYellow"}
        shift = s.beat_shift_frames
        lines = ["TITLE: AudioLights", "FCM: NON-DROP FRAME", ""]
        n = 0
        for tsec, kind, name in triggers.plan_events(s, ana):
            if kind == 'BEAT' and not self.include_beats:
                continue
            if self.max_seconds and tsec > self.max_seconds:
                continue
            fr = int(round(tsec * fps + shift)) + self.tc_hour * base * 3600
            if fr < self.tc_hour * base * 3600:
                continue
            n += 1
            a, b = triggers.tc_str(fr, base), triggers.tc_str(fr + 1, base)
            lines.append("%03d  001      V     C        %s %s %s %s  " % (n, a, b, a, b))
            lines.append(" |C:%s |M:%s |D:1" % (palette[kind], name))
            lines.append("")
        with open(self.filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        self.report({'INFO'}, "%d marcadores exportados a %s"
                    % (n, os.path.basename(self.filepath)))
        return {'FINISHED'}


class AL_OT_spin(bpy.types.Operator):
    bl_idname = "al.spin"
    bl_label = "Girar objetos (loop perfecto)"
    bl_description = ("Gira los objetos seleccionados (bola disco) un numero "
                      "entero de vueltas en el rango de frames, sin saltos al repetir")
    bl_options = {'REGISTER', 'UNDO'}
    revolutions: IntProperty(name="Vueltas", default=1, min=-20, max=20)
    axis: EnumProperty(name="Eje", items=[('0', "X", ""), ('1', "Y", ""),
                                          ('2', "Z", "")], default='2')

    def execute(self, context):
        scene = context.scene
        ax = int(self.axis)
        f0, f1 = scene.frame_start, scene.frame_end
        with Prefs(context) as prefs:
            prefs.edit.keyframe_new_interpolation_type = 'LINEAR'
            for obj in context.selected_objects:
                base = obj.rotation_euler[ax]
                obj.rotation_euler[ax] = base
                obj.keyframe_insert("rotation_euler", index=ax, frame=f0)
                obj.rotation_euler[ax] = base + 2 * math.pi * self.revolutions
                obj.keyframe_insert("rotation_euler", index=ax, frame=f1 + 1)
                obj.rotation_euler[ax] = base
                set_interp(obj, "rotation_euler", 'LINEAR')
        return {'FINISHED'}


class AL_OT_sway(bpy.types.Operator):
    bl_idname = "al.sway"
    bl_label = "Balancear spots al ritmo"
    bl_description = ("Oscila los objetos seleccionados (spots/moving heads) "
                      "sincronizado con el BPM")
    bl_options = {'REGISTER', 'UNDO'}
    amplitude: FloatProperty(name="Amplitud (grados)", default=25.0, min=0.0, max=180.0)
    period_beats: FloatProperty(name="Periodo (beats)", default=8.0, min=0.5, max=64.0)
    axis: EnumProperty(name="Eje", items=[('0', "X", ""), ('1', "Y", ""),
                                          ('2', "Z", "")], default='0')
    phase_step: FloatProperty(name="Desfase entre objetos", default=0.6,
                              description="Radianes de desfase por objeto")

    def execute(self, context):
        scene = context.scene
        s = scene.al
        try:
            bpm = analysis.current_bpm(s)
        except Exception as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}
        fps = analysis.scene_fps(scene)
        T = 60.0 / bpm
        ax = int(self.axis)
        f0, f1 = scene.frame_start, scene.frame_end
        start = s.audio_start_frame if s.source == 'AUDIO' else f0
        step = max(1, int(s.key_step))
        with Prefs(context) as prefs:
            prefs.edit.keyframe_new_interpolation_type = 'LINEAR'
            for i, obj in enumerate(context.selected_objects):
                base = obj.rotation_euler[ax]
                for f in range(f0, f1 + 1, step):
                    tb = (f - start) / fps / (T * self.period_beats)
                    ang = (math.radians(self.amplitude) *
                           math.sin(2 * math.pi * tb + i * self.phase_step))
                    obj.rotation_euler[ax] = base + ang
                    obj.keyframe_insert("rotation_euler", index=ax, frame=f)
                obj.rotation_euler[ax] = base
                set_interp(obj, "rotation_euler", 'LINEAR')
        return {'FINISHED'}


CLASSES = (
    AL_OT_add_selected,
    AL_OT_remove_item,
    AL_OT_clear_items,
    AL_OT_auto_triggers,
    AL_OT_chase,
    AL_OT_single_user,
    AL_OT_palette_preset,
    AL_OT_bake,
    AL_OT_clear_anim,
    AL_OT_markers,
    AL_OT_clear_markers,
    AL_OT_export_resolve,
    AL_OT_spin,
    AL_OT_sway,
)
