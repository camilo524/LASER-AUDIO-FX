"""Materiales del addon: rayos emisivos, materiales simples y humo (haze)."""

import bpy

from ..core.constants import PREFIX


def get_material():
    """Material de los rayos: emision con atributo de color y mezcla transparente.

    Funciona igual en EEVEE y Cycles porque el color viaja en el atributo de
    malla ``LZ_col``, no en el material.
    """
    mat = bpy.data.materials.get(PREFIX + "Laser_Mat")
    if mat:
        return mat
    mat = bpy.data.materials.new(PREFIX + "Laser_Mat")
    try:
        mat.use_nodes = True
    except Exception:
        pass
    nt = mat.node_tree
    nt.nodes.clear()
    attr = nt.nodes.new("ShaderNodeAttribute")
    attr.attribute_type = 'GEOMETRY'
    attr.attribute_name = "LZ_col"
    attr.location = (-400, 0)
    em = nt.nodes.new("ShaderNodeEmission")
    em.location = (-150, 80)
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    tr.location = (-150, -60)
    mix = nt.nodes.new("ShaderNodeMixShader")
    mix.location = (80, 0)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    out.location = (300, 0)
    link = nt.links.new
    link(attr.outputs["Color"], em.inputs["Color"])
    link(attr.outputs["Alpha"], mix.inputs["Fac"])
    link(tr.outputs[0], mix.inputs[1])
    link(em.outputs[0], mix.inputs[2])
    link(mix.outputs[0], out.inputs["Surface"])
    try:
        mat.surface_render_method = 'BLENDED'
        mat.show_transparent_back = False
    except Exception:
        pass
    return mat


def reset_strength():
    """Mantiene la emision del material de los rayos en 1 (el brillo va en el color)."""
    mat = bpy.data.materials.get(PREFIX + "Laser_Mat")
    if mat is None or mat.node_tree is None:
        return
    for node in mat.node_tree.nodes:
        if node.type == 'EMISSION':
            sock = node.inputs["Strength"]
            if abs(sock.default_value - 1.0) > 1e-6:
                sock.default_value = 1.0


def simple_material(name, color, metal=0.0, rough=0.5):
    """Material Principled plano (para la escena de prueba)."""
    mat = bpy.data.materials.new(name)
    try:
        mat.use_nodes = True
    except Exception:
        pass
    base = mat.node_tree.nodes.get("Principled BSDF")
    if base:
        base.inputs["Base Color"].default_value = (*color, 1.0)
        base.inputs["Metallic"].default_value = metal
        base.inputs["Roughness"].default_value = rough
    return mat


def haze_material():
    """Volumen de niebla que hace visibles los haces (mejor en Cycles)."""
    mat = bpy.data.materials.new(PREFIX + "Haze_Mat")
    try:
        mat.use_nodes = True
    except Exception:
        pass
    nt = mat.node_tree
    nt.nodes.clear()
    vol = nt.nodes.new("ShaderNodeVolumePrincipled")
    vol.inputs["Density"].default_value = 0.015
    vol.inputs["Anisotropy"].default_value = 0.5
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(vol.outputs[0], out.inputs["Volume"])
    return mat
