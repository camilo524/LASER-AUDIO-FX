"""Sincronizacion de luces: lista de objetivos, bake de keyframes y utilidades.

Es la parte del addon que viene de ``audio_lights_sync.py``. Los lasers usan
las mismas curvas de audio a traves de ``lasers/driver.py``.
"""

from . import live, operators, properties, ui  # noqa: F401
from .properties import AL_Item, AL_Settings  # noqa: F401

__all__ = ["live", "operators", "properties", "ui", "AL_Item", "AL_Settings"]

# Primero los PropertyGroup, luego los operadores y por ultimo paneles/UIList
CLASSES = (properties.AL_Item, properties.AL_Settings) + \
    tuple(operators.CLASSES) + tuple(ui.CLASSES)
