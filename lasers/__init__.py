"""Lasers procedurales con colisiones, rebotes y reaccion al audio."""

from . import (audio_color, collision, driver, engine, geometry,  # noqa: F401
               handlers, materials, operators, presets, properties, ui, updates)
from .properties import LZ_Settings  # noqa: F401

__all__ = ["audio_color", "collision", "driver", "engine", "geometry",
           "handlers", "materials", "operators", "presets", "properties",
           "ui", "updates", "LZ_Settings"]

# El orden importa: primero los PropertyGroup, luego operadores y paneles
CLASSES = (properties.LZ_Settings,) + tuple(operators.CLASSES) + tuple(ui.CLASSES)
