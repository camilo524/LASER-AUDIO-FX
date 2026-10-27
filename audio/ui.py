"""Paneles de audio y color: cancion, ajustes avanzados y paleta unica.

``LAFX_PT_main`` es el panel principal de la pestana; el resto (lasers, luces,
colores...) cuelga de el con ``bl_parent_id``.
"""

import bpy

from ..core.constants import CATEGORY, CURVES_PROP, N_SLOTS


class LAFX_PT_main(bpy.types.Panel):
    bl_idname = "LAFX_PT_main"
    bl_label = "Laser Audio FX"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = CATEGORY
    lafx_order = 0

    def draw(self, context):
        s = context.scene.al
        col = self.layout.column()
        col.prop(s, "source", expand=True)
        if s.source == 'AUDIO':
            col.prop(s, "audio_path")
            col.prop(s, "audio_start_frame")
            row = col.row(align=True)
            row.operator("al.add_audio", icon='SEQUENCE')
            row.operator("al.analyze", icon='PLAY_SOUND')
        else:
            col.prop(s, "loop_bpm")
            col.prop(s, "loop_bars")
            col.prop(s, "loop_use_detected")
            col.operator("al.set_loop", icon='FILE_REFRESH')
        if s.bpm_detected > 0:
            box = col.box()
            box.label(text="BPM: %.2f   Beats: %d   Fase compas: %d" %
                      (s.bpm_detected, s.beats_found, s.downbeat_detected),
                      icon='INFO')


class LAFX_PT_palette(bpy.types.Panel):
    bl_idname = "LAFX_PT_palette"
    bl_label = "Colores (rayos y luces)"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = CATEGORY
    bl_parent_id = "LAFX_PT_main"
    lafx_order = 10

    def draw(self, context):
        s = context.scene.al
        lay = self.layout
        lay.use_property_split = True
        lay.use_property_decorate = False
        lay.label(text="Una sola paleta para todo.", icon='INFO')
        lay.prop(s, "preset")
        lay.prop(s, "palette_mode", expand=True)
        if s.palette_mode == 'PALETTE':
            grid = lay.grid_flow(row_major=True, columns=2, align=True)
            grid.use_property_split = False
            for i in range(1, N_SLOTS + 1):
                cell = grid.row(align=True)
                cell.prop(s, "use_c%d" % i, text="")
                sub = cell.row()
                sub.enabled = getattr(s, "use_c%d" % i)
                sub.prop(s, "c%d" % i, text="")
        else:
            lay.prop(s, "hue_min")
            lay.prop(s, "hue_max")
            lay.prop(s, "free_sat")
            lay.prop(s, "free_val")
        lay.separator()
        lay.label(text="Cambio de color con el ritmo", icon='COLOR')
        lay.prop(s, "color_mode", text="Modo")
        if s.color_mode == 'BEAT':
            lay.prop(s, "color_every")
        if s.color_mode == 'GRADIENT':
            lay.prop(s, "gradient_beats")
        if s.color_mode in ('BEAT', 'SECTION'):
            lay.prop(s, "color_pick")
        if s.color_mode == 'SPECTRUM':
            lay.label(text="Graves = rojo, medios = verde, agudos = azul.")
        if s.color_mode != 'NONE':
            lay.prop(s, "color_spread")
            lay.prop(s, "seed")
            lay.label(text="Este modo y esta paleta los usan rayos y luces.",
                      icon='INFO')


class LAFX_PT_react(bpy.types.Panel):
    bl_idname = "LAFX_PT_react"
    bl_label = "Ajustes avanzados de audio"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = CATEGORY
    bl_parent_id = "LAFX_PT_main"
    bl_options = {'DEFAULT_CLOSED'}
    lafx_order = 40

    def draw(self, context):
        s = context.scene.al
        lay = self.layout
        lay.use_property_split = True
        lay.use_property_decorate = False
        if s.source == 'AUDIO':
            lay.prop(s, "bpm_mode", expand=True)
            if s.bpm_mode == 'MANUAL':
                lay.prop(s, "bpm_manual")
            else:
                lay.prop(s, "bpm_mult", expand=True)
            lay.prop(s, "sensitivity")
        lay.prop(s, "beats_per_bar")
        lay.prop(s, "downbeat_shift")
        lay.prop(s, "beat_shift_frames")
        lay.separator()
        lay.label(text="Forma de la reaccion (rayos y luces)")
        for p in ("decay_beats", "attack_ms", "release_ms", "gate",
                  "contrast", "master", "key_step"):
            lay.prop(s, p)
        box = lay.box()
        box.label(text="Curvas reactivas", icon='FCURVE')
        if CURVES_PROP in context.scene:
            box.label(text="Guardadas en el .blend", icon='CHECKMARK')
        else:
            box.label(text="Solo en memoria", icon='INFO')
        row = box.row(align=True)
        row.operator("al.curves_save", icon='FILE_TICK')
        row.operator("al.curves_clear", icon='X')


CLASSES = (LAFX_PT_main, LAFX_PT_palette, LAFX_PT_react)
