"""Operadores de audio: analizar, poner la cancion en el timeline, loop y curvas."""

import os

import bpy

from ..core.constants import CURVES_PROP
from . import analysis, curves as acurves


def seq_collection(seq, names):
    """Compatibilidad entre versiones del editor de secuencias."""
    for n in names:
        if hasattr(seq, n):
            return getattr(seq, n)
    raise RuntimeError("No pude acceder a las tiras del editor de secuencias.")


class AL_OT_add_audio(bpy.types.Operator):
    bl_idname = "al.add_audio"
    bl_label = "Poner cancion en el timeline"
    bl_description = ("Agrega la cancion al editor de secuencias y ajusta el "
                      "rango de frames a su duracion")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        s = scene.al
        try:
            path = bpy.path.abspath(s.audio_path)
            if not os.path.isfile(path):
                raise RuntimeError("Elige primero el archivo de la cancion.")
            ana = analysis.build_analysis(scene) if s.source == 'AUDIO' else None
            seq = scene.sequence_editor_create()
            allc = seq_collection(seq, ("strips_all", "sequences_all"))
            top = seq_collection(seq, ("strips", "sequences"))
            for st in list(allc):
                if st.name == "AL_Song":
                    top.remove(st)
            top.new_sound(name="AL_Song", filepath=path, channel=1,
                          frame_start=s.audio_start_frame)
            fps = analysis.scene_fps(scene)
            scene.frame_start = s.audio_start_frame
            dur = ana["duration"] if ana else s.audio_duration
            scene.frame_end = s.audio_start_frame + int(dur * fps) - 1
            try:
                scene.sync_mode = 'AUDIO_SYNC'
            except Exception:
                pass
        except Exception as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}
        self.report({'INFO'}, "Cancion agregada. Frames %d - %d"
                    % (scene.frame_start, scene.frame_end))
        return {'FINISHED'}


class AL_OT_analyze(bpy.types.Operator):
    bl_idname = "al.analyze"
    bl_label = "Analizar cancion"
    bl_description = "Detecta BPM, beats, bombos y secciones"

    def execute(self, context):
        try:
            ana = analysis.build_analysis(context.scene)
        except Exception as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}
        self.report({'INFO'}, "BPM %.2f | %d beats | %d kicks | %d secciones" %
                    (ana["bpm"], len(ana["beats"]), len(ana["kicks"]),
                     len(ana["sections"])))
        return {'FINISHED'}


class AL_OT_curves_save(bpy.types.Operator):
    bl_idname = "al.curves_save"
    bl_label = "Guardar curvas en la escena"
    bl_description = ("Convierte el analisis en curvas reactivas y las guarda "
                      "dentro del .blend: los lasers siguen reaccionando aunque "
                      "muevas o pierdas el archivo de audio")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        s = scene.al
        try:
            ana = analysis.get() or analysis.build_analysis(scene)
        except Exception as e:
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}
        fps = analysis.scene_fps(scene)
        T = 60.0 / max(float(ana["bpm"]), 1e-6)
        curv = acurves.build_curves(
            ana, beats_per_bar=s.beats_per_bar, downbeat_shift=s.downbeat_shift,
            decay_s=s.decay_beats * T, attack_s=s.attack_ms / 1000.0,
            release_s=s.release_ms / 1000.0, gate=s.gate, contrast=s.contrast,
            shift_s=s.beat_shift_frames / fps)
        scene[CURVES_PROP] = acurves.to_storable(curv, acurves.meta_from_analysis(ana))
        self.report({'INFO'}, "Curvas guardadas en la escena (%d disparadores)"
                    % len(curv))
        return {'FINISHED'}


class AL_OT_curves_clear(bpy.types.Operator):
    bl_idname = "al.curves_clear"
    bl_label = "Borrar curvas guardadas"
    bl_description = "Quita las curvas reactivas guardadas dentro del .blend"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        if CURVES_PROP in scene:
            del scene[CURVES_PROP]
        return {'FINISHED'}


class AL_OT_set_loop(bpy.types.Operator):
    bl_idname = "al.set_loop"
    bl_label = "Ajustar rango al loop"
    bl_description = ("Ajusta el rango de frames para que el loop dure "
                      "exactamente N compases")
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        s = scene.al
        fps = analysis.scene_fps(scene)
        bpm = s.loop_bpm
        ana = analysis.get()
        if s.loop_use_detected and ana is not None and s.source == 'AUDIO':
            bpm = ana["bpm"]
        beats = s.loop_bars * s.beats_per_bar
        frames = max(1, int(round(beats * 60.0 / bpm * fps)))
        eff = beats * 60.0 * fps / frames
        scene.frame_end = scene.frame_start + frames - 1
        s.loop_bpm = eff
        err = abs(eff - bpm) / bpm * 100.0
        self.report({'INFO'}, "Loop de %d frames (%.2f s). BPM efectivo %.3f "
                              "(error %.3f%%)" % (frames, frames / fps, eff, err))
        return {'FINISHED'}


CLASSES = (
    AL_OT_add_audio,
    AL_OT_analyze,
    AL_OT_curves_save,
    AL_OT_curves_clear,
    AL_OT_set_loop,
)
