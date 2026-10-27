"""Objetivo animable: una luz de Blender o una malla con material emisivo.

Aqui vive todo lo que toca fcurves y keyframes, tanto para el horneado como
para las herramientas (spin, sway).
"""


def _fcurves(idb):
    """fcurves de un ID, soportando el sistema de capas (slots) de Blender 4.4+."""
    ad = getattr(idb, "animation_data", None)
    if not ad or not ad.action:
        return []
    act = ad.action
    out = []
    if hasattr(act, "fcurves"):
        return [(act.fcurves, fc) for fc in act.fcurves]
    slot = getattr(ad, "action_slot", None)
    for layer in act.layers:
        for strip in layer.strips:
            for cb in getattr(strip, "channelbags", []):
                if slot is None or cb.slot_handle == slot.handle:
                    out.extend((cb.fcurves, fc) for fc in cb.fcurves)
    return out


def remove_fcurves(idb, paths):
    try:
        for coll, fc in list(_fcurves(idb)):
            if fc.data_path in paths:
                coll.remove(fc)
    except Exception:
        pass


def set_interp(idb, path, interp):
    try:
        for _coll, fc in _fcurves(idb):
            if fc.data_path == path:
                for kp in fc.keyframe_points:
                    kp.interpolation = interp
    except Exception:
        pass


def emission_sockets(obj):
    """Busca (node_tree, color, strength) de emision en los materiales del objeto."""
    for slot in obj.material_slots:
        mat = slot.material
        if not mat or not mat.node_tree:
            continue
        for n in mat.node_tree.nodes:
            if n.type == 'EMISSION':
                return mat.node_tree, n.inputs["Color"], n.inputs["Strength"]
            if n.type == 'BSDF_PRINCIPLED':
                col = n.inputs.get("Emission Color") or n.inputs.get("Emission")
                st = n.inputs.get("Emission Strength")
                if col is not None and st is not None:
                    return mat.node_tree, col, st
    return None


class Target:
    """Abstrae una luz de Blender o un objeto con material emisivo."""

    def __init__(self, obj):
        self.obj = obj
        self.ok = False
        if obj.type == 'LIGHT':
            self.kind, self.idb = 'LIGHT', obj.data
            self.en_path, self.col_path = "energy", "color"
            self.ok = True
        else:
            found = emission_sockets(obj)
            if found:
                self.kind, self.idb = 'EMIT', found[0]
                self.col, self.st = found[1], found[2]
                self.en_path = self.st.path_from_id() + ".default_value"
                self.col_path = self.col.path_from_id() + ".default_value"
                self.ok = True

    def current_level(self):
        if self.kind == 'LIGHT':
            return float(self.idb.energy)
        return float(self.st.default_value)

    def clear(self, energy=True, color=True):
        paths = set()
        if energy:
            paths.add(self.en_path)
        if color:
            paths.add(self.col_path)
        remove_fcurves(self.idb, paths)

    # --- valores en vivo (sin keyframes) ---
    def put_energy(self, v):
        if self.kind == 'LIGHT':
            self.idb.energy = float(v)
        else:
            self.st.default_value = float(v)

    def put_color(self, rgb):
        if self.kind == 'LIGHT':
            self.idb.color = tuple(rgb)
        else:
            self.col.default_value = (rgb[0], rgb[1], rgb[2], 1.0)

    def set_energy(self, v, frame):
        if self.kind == 'LIGHT':
            self.idb.energy = float(v)
            self.idb.keyframe_insert("energy", frame=frame)
        else:
            self.st.default_value = float(v)
            self.st.keyframe_insert("default_value", frame=frame)

    def set_color(self, rgb, frame):
        if self.kind == 'LIGHT':
            self.idb.color = tuple(rgb)
            self.idb.keyframe_insert("color", frame=frame)
        else:
            self.col.default_value = (rgb[0], rgb[1], rgb[2], 1.0)
            self.col.keyframe_insert("default_value", frame=frame)

    def fix_interp(self, which, interp):
        set_interp(self.idb, self.en_path if which == 'energy' else self.col_path, interp)


class Prefs:
    """Guarda/restaura el tipo de interpolacion por defecto y el frame actual."""

    def __init__(self, context):
        self.scene = context.scene
        self.edit = context.preferences.edit
        self.old_interp = self.edit.keyframe_new_interpolation_type
        self.old_frame = self.scene.frame_current

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.edit.keyframe_new_interpolation_type = self.old_interp
        self.scene.frame_set(self.old_frame)
        return False
