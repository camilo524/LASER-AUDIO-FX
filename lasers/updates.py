"""Callbacks de las propiedades del rig.

El import del motor se hace dentro de la funcion para que no haya ciclos de
importacion entre propiedades y motor.
"""

from ..core import constants as K
from ..core import utils


def on_audio_toggle(self, context):
    """Encender 'Color' (o cualquier reaccion) ya pone el rig a reaccionar.

    Asi el boton de color alcanza: no hace falta activar aparte
    "Reaccionar al audio".
    """
    if utils.is_muted():
        return
    if not self.audio_enabled:
        with utils.mute_updates():
            self.audio_enabled = True
    on_settings_update(self, context)


def on_settings_update(self, context):
    """Cualquier cambio de propiedad reconstruye el rig."""
    if utils.is_muted():
        return
    try:
        from . import engine
        engine.update_rig(self.id_data)
    except Exception as e:      # no romper la UI por un error
        print("[LaserFX] error al actualizar:", e)
