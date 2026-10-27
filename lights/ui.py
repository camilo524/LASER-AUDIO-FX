"""Paneles de la sincronizacion de luces (un solo panel + herramientas)."""

import bpy

from ..core.constants import CATEGORY


class AL_UL_items(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data,
                  active_propname, index):
        row = layout.row(align=True)
        row.prop(item, "enabled", text="")
        ic = 'LIGHT' if (item.obj and item.obj.type == 'LIGHT') else 'MESH_DATA'
        row.label(text=item.obj.name if item.obj else "(vacio)", icon=ic)
        row.prop(item, "trigger", text="")


class LAFX_PT_lights(bpy.types.Panel):
    bl_idname = "LAFX_PT_lights"
    bl_label = "Luces"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = CATEGORY
    bl_parent_id = "LAFX_PT_main"
    lafx_order = 30

    def draw(self, context):
        s = context.scene.al
        lay = self.layout
        lay.label(text="Solo luces y mallas con emision.", icon='INFO')
        lay.label(text="Los lasers ya siguen el audio solos.")
        row = lay.row()
        row.template_list("AL_UL_items", "", s, "lights", s, "lights_index", rows=3)
        col = row.column(align=True)
        col.operator("al.add_selected", icon='ADD', text="")
        col.operator("al.remove_item", icon='REMOVE', text="")
        col.operator("al.clear_items", icon='TRASH', text="")
        if 0 <= s.lights_index < len(s.lights):
            item = s.lights[s.lights_index]
            box = lay.box()
            box.use_property_split = True
            box.use_property_decorate = False
            box.prop(item, "obj")
            box.prop(item, "energy_min")
            box.prop(item, "energy_max")
            box.prop(item, "delay_beats")
            box.prop(item, "color_mode")
            if item.color_mode == 'FIXED':
                box.prop(item, "fixed_color")
        row = lay.row(align=True)
        row.operator("al.auto_triggers", icon='RNDCURVE')
        row.operator("al.single_user", icon='DUPLICATE')
        row = lay.row(align=True)
        row.prop(s, "chase_step")
        row.operator("al.chase", icon='FORCE_HARMONIC', text="")

        lay.separator()
        lay.label(text="Que animar", icon='MODIFIER')
        row = lay.row(align=True)
        row.prop(s, "animate_energy", toggle=True)
        row.prop(s, "animate_color", toggle=True)
        if s.animate_color:
            sub = lay.column()
            sub.use_property_split = True
            sub.use_property_decorate = False
            if s.color_mode == 'NONE':
                sub.label(text="El cambio de color esta en 'No animar' (panel Colores).",
                          icon='ERROR')
            sub.prop(s, "color_spread")
            if s.color_mode not in ('GRADIENT', 'NONE'):
                sub.prop(s, "transition")
                if s.transition == 'FADE':
                    sub.prop(s, "fade_frames")
        lay.prop(s, "live_lights")
        if s.live_lights:
            lay.label(text="Siguen la cancion al dar play (sin keyframes).", icon='INFO')
        col = lay.column()
        col.scale_y = 1.3
        col.operator("al.bake", icon='KEYFRAME_HLT')
        lay.operator("al.clear_anim", icon='X')
        lay.label(text="Hornear = keyframes (render / Resolve). Mandan sobre el vivo.")


class LAFX_PT_tools(bpy.types.Panel):
    bl_idname = "LAFX_PT_tools"
    bl_label = "Herramientas"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = CATEGORY
    bl_parent_id = "LAFX_PT_main"
    bl_options = {'DEFAULT_CLOSED'}
    lafx_order = 50

    def draw(self, context):
        col = self.layout.column(align=True)
        col.label(text="Marcadores", icon='MARKER')
        col.operator("al.markers", icon='MARKER_HLT')
        col.operator("al.clear_markers", icon='X')
        col.operator("al.export_resolve", icon='EXPORT')
        col.separator()
        col.label(text="Con los objetos seleccionados", icon='RESTRICT_SELECT_OFF')
        col.operator("al.spin", icon='FILE_REFRESH')
        col.operator("al.sway", icon='FORCE_HARMONIC')


CLASSES = (AL_UL_items, LAFX_PT_lights, LAFX_PT_tools)
