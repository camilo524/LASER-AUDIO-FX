"""Paneles del rig de lasers: forma, color, movimiento, audio e impactos."""

import bpy

from ..core.constants import CATEGORY, N_SLOTS
from .driver import status as audio_status

_STATUS_ICON = {
    'LIVE': 'CHECKMARK',
    'STORED': 'FILE_TICK',
    'NO_ANALYSIS': 'ERROR',
    'NO_AUDIO': 'ERROR',
    'MISSING': 'ERROR',
    'OFF': 'RADIOBUT_OFF',
}


def active_rig(context):
    """Rig de lasers seleccionado en el objeto activo, o ``None``."""
    ob = context.object
    s = getattr(ob, "laserfx", None)
    return ob if (s is not None and s.is_rig) else None


class LAFX_PT_rig(bpy.types.Panel):
    bl_idname = "LAFX_PT_rig"
    bl_label = "Lasers"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = CATEGORY
    bl_parent_id = "LAFX_PT_main"
    lafx_order = 20

    def draw(self, context):
        lay = self.layout
        row = lay.row(align=True)
        row.operator("laserfx.create", icon='ADD')
        row.operator("laserfx.auto_sync", text="", icon='RNDCURVE')
        row = lay.row(align=True)
        row.operator("laserfx.demo", icon='MESH_CUBE')
        row.operator("laserfx.haze", icon='SHADING_RENDERED')

        rig = active_rig(context)
        if rig is None:
            lay.label(text="Selecciona un Laser Rig (empty).", icon='INFO')
            return
        lay.separator()
        lay.label(text="Rig: %s" % rig.name, icon='OUTLINER_OB_EMPTY')
        lay.use_property_split = True
        lay.use_property_decorate = False
        row = lay.row(align=True)
        row.prop(rig.laserfx, "style_preset", text="")
        row.operator("laserfx.style", text="", icon='PRESET')
        row = lay.row(align=True)
        row.operator("laserfx.update", icon='FILE_REFRESH')
        row.operator("laserfx.remove", icon='TRASH')


class _RigPanel:
    """Base de los subpaneles que dependen del rig activo."""

    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = CATEGORY
    bl_parent_id = "LAFX_PT_rig"

    @classmethod
    def poll(cls, context):
        return active_rig(context) is not None

    def props(self, context, names=None):
        lay = self.layout
        lay.use_property_split = True
        lay.use_property_decorate = False
        s = active_rig(context).laserfx
        for name in (names or ()):
            lay.prop(s, name)
        return s


class LAFX_PT_beams(_RigPanel, bpy.types.Panel):
    bl_idname = "LAFX_PT_beams"
    bl_label = "Forma"

    def draw(self, context):
        self.props(context, ("count", "pattern", "spread", "intensity", "width"))


class LAFX_PT_colors(_RigPanel, bpy.types.Panel):
    bl_idname = "LAFX_PT_colors"
    bl_label = "Color"

    def draw(self, context):
        s = self.props(context, ("color_mode",))
        al = context.scene.al
        lay = self.layout
        # paleta compartida: se puede editar aqui mismo sin abrir otro panel
        row = lay.row(align=True)
        row.use_property_split = False
        for i in range(1, N_SLOTS + 1):
            if getattr(al, "use_c%d" % i):
                row.prop(al, "c%d" % i, text="")
        follows = s.audio_enabled and s.audio_on_color
        if follows:
            if al.color_mode == 'NONE':
                lay.label(text="Cambio de color en 'No animar' (panel Colores).",
                          icon='ERROR')
            else:
                lay.label(text="Cambia con el ritmo (modo del panel Colores).",
                          icon='CHECKMARK')
                lay.prop(s, "audio_color_chase")
        else:
            lay.prop(s, "color_speed")
            if s.audio_enabled:
                lay.label(text="Enciende 'Color' en Audio para animarlo al ritmo.",
                          icon='INFO')


class LAFX_PT_anim(_RigPanel, bpy.types.Panel):
    bl_idname = "LAFX_PT_anim"
    bl_label = "Movimiento y pulso"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        self.props(context, ("speed", "time_offset", "sweep", "spin", "wave",
                             "wave_cycles", "breath"))
        self.layout.label(text="Pulso (estrobo)")
        self.props(context, ("bpm", "pulse", "chase"))


class LAFX_PT_rig_audio(_RigPanel, bpy.types.Panel):
    bl_idname = "LAFX_PT_rig_audio"
    bl_label = "Audio (ritmo)"

    def draw(self, context):
        lay = self.layout
        lay.use_property_split = True
        lay.use_property_decorate = False
        s = active_rig(context).laserfx
        lay.prop(s, "audio_enabled")
        if not s.audio_enabled:
            return
        code, text = audio_status(context.scene, s)
        box = lay.box()
        box.label(text=text, icon=_STATUS_ICON.get(code, 'INFO'))
        lay.prop(s, "audio_trigger")
        lay.label(text="Que sigue el ritmo", icon='MODIFIER')
        grid = lay.grid_flow(row_major=True, columns=2, align=True)
        grid.use_property_split = False
        grid.prop(s, "audio_on_brightness", toggle=True)
        grid.prop(s, "audio_on_spread", toggle=True)
        grid.prop(s, "audio_on_speed", toggle=True)
        grid.prop(s, "audio_on_color", toggle=True)
        if s.audio_on_brightness:
            lay.prop(s, "audio_brightness")
        if s.audio_on_spread:
            lay.prop(s, "audio_spread")
        if s.audio_on_speed:
            lay.prop(s, "audio_speed")
        col = lay.column(align=True)
        col.prop(s, "audio_strobe")
        if s.audio_strobe:
            col.label(text="El pulso (Movimiento y pulso) marca el destello.",
                      icon='INFO')
        if s.audio_strobe or s.audio_on_brightness:
            col.prop(s, "audio_chase")


class LAFX_PT_collision(_RigPanel, bpy.types.Panel):
    bl_idname = "LAFX_PT_collision"
    bl_label = "Impactos y rebotes"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        self.props(context, ("max_bounces", "reflect", "auto_mirror"))
        lay = self.layout
        lay.label(text="Objetos seleccionados:")
        row = lay.row(align=True)
        for mode, text in (('MIRROR', "Espejo"), ('IGNORE', "Ignorar"),
                           ('CLEAR', "Normal")):
            row.operator("laserfx.mark", text=text).mode = mode
        lay.separator()
        self.props(context, ("show_hits", "dot_size", "dot_intensity",
                             "max_lights", "light_power"))


class LAFX_PT_adv(_RigPanel, bpy.types.Panel):
    bl_idname = "LAFX_PT_adv"
    bl_label = "Avanzado"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        self.props(context, ("divergence", "max_distance", "end_fade", "sides",
                             "auto_update"))


CLASSES = (LAFX_PT_rig, LAFX_PT_beams, LAFX_PT_colors, LAFX_PT_anim,
           LAFX_PT_rig_audio, LAFX_PT_collision, LAFX_PT_adv)
