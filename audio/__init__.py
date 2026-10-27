"""Analisis de audio, curvas reactivas, horneado y operadores de sincronizacion."""

from . import (analysis, bake, colors, curves, dsp, loader, operators,  # noqa: F401
               targets, triggers, ui)

__all__ = ["analysis", "bake", "colors", "curves", "dsp", "loader",
           "operators", "targets", "triggers", "ui"]

CLASSES = tuple(operators.CLASSES) + tuple(ui.CLASSES)
