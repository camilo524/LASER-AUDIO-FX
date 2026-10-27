"""Paneles del rig de lasers: forma, color, movimiento, audio e impactos."""

import bpy

from ..core.constants import CATEGORY
from .driver import get_driver, status as audio_status

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
    lafx_order = 21

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


class LAFX_PT_anim(_RigPanel, bpy.types.Panel):
    bl_idname = "LAFX_PT_anim"
    bl_label = "Movimiento y pulso"
    bl_options = {'DEFAULT_CLOSED'}
    lafx_order = 22

    def draw(self, context):
        s = self.props(context, ("speed", "time_offset", "sweep", "spin", "wave",
                                 "wave_cycles", "breath"))
        lay = self.layout
        lay.separator()
        lay.label(text="Loopear animacion", icon='LOOP_BACK')
        row = lay.row(align=True)
        row.prop(s, "loop_anim", toggle=True)
        if s.loop_anim:
            box = lay.box()
            row = box.row(align=True)
            row.prop(s, "loop_start", text="Desde el frame")
            row.prop(s, "loop_end", text="Hasta el frame")
            if s.loop_end <= s.loop_start:
                box.label(text="El frame final debe ser mayor que el "
                               "inicial.", icon='ERROR')
            else:
                n = s.loop_end - s.loop_start + 1
                fps = (context.scene.render.fps
                       / context.scene.render.fps_base)
                box.label(text="Se repite cada %d frames (%.1f s). La "
                               "velocidad y los demas ajustes se ponen "
                               "arriba." % (n, n / fps), icon='INFO')
        lay.separator()
        lay.label(text="Pulso (estrobo)")
        drv = get_driver(context.scene, s) if s.audio_enabled else None
        if drv is not None:
            self.props(context, ("pulse", "chase", "audio_strobe"))
            lay.label(text="Pulso a %.1f BPM (el de la cancion)." % drv.bpm,
                      icon='CHECKMARK')
        else:
            self.props(context, ("bpm", "pulse", "chase", "audio_strobe"))


class LAFX_PT_rig_audio(_RigPanel, bpy.types.Panel):
    """Un solo panel para el ritmo y el color de los rayos.

    Antes habia dos paneles ("Color" y "Audio") con el mismo interruptor de
    color y dos sitios donde mirar el estado del audio.
    """

    bl_idname = "LAFX_PT_rig_audio"
    bl_label = "Ritmo y color"
    lafx_order = 23

    def draw(self, context):
        lay = self.layout
        lay.use_property_split = True
        lay.use_property_decorate = False
        s = active_rig(context).laserfx
        al = context.scene.al
        lay.prop(s, "audio_enabled")
        if not s.audio_enabled:
            return
        code, text = audio_status(context.scene, s)
        box = lay.box()
        box.label(text=text, icon=_STATUS_ICON.get(code, 'INFO'))
        if code in ('NO_ANALYSIS', 'NO_AUDIO', 'MISSING'):
            box.operator("al.analyze", icon='PLAY_SOUND')
        lay.prop(s, "audio_trigger")
        lay.separator()
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
        if s.audio_strobe:
            lay.label(text="El pulso y el estrobo se ajustan en "
                           "'Movimiento y pulso'.", icon='INFO')
        if s.audio_on_color:
            lay.separator()
            if al.color_mode == 'NONE':
                lay.label(text="El cambio de color esta en 'No animar' "
                               "(panel 'Colores').", icon='ERROR')
            lay.prop(s, "audio_color_chase")
            lay.label(text="Paleta y cambio de color: panel 'Colores'.", icon='INFO')
        else:
            lay.prop(s, "color_speed")


class LAFX_PT_collision(_RigPanel, bpy.types.Panel):
    bl_idname = "LAFX_PT_collision"
    bl_label = "Impactos y rebotes"
    bl_options = {'DEFAULT_CLOSED'}
    lafx_order = 24

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
    lafx_order = 25

    def draw(self, context):
        self.props(context, ("divergence", "max_distance", "end_fade", "sides",
                             "auto_update"))


CLASSES = (LAFX_PT_rig, LAFX_PT_beams, LAFX_PT_anim,
           LAFX_PT_rig_audio, LAFX_PT_collision, LAFX_PT_adv)
