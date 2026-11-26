"""Apply bounded edits to the embedded buffers produced by YORVYN's GLB exporter."""
import json
import struct

import numpy as np

EDIT_OPERATIONS = {"widen", "shorten", "widen_sleeves", "denim"}


def edit_candidate(source: bytes, operation: str) -> bytes:
    if operation not in EDIT_OPERATIONS:
        raise ValueError("Unsupported garment edit.")
    magic, version, size, json_length, kind = struct.unpack_from("<4sIII4s", source)
    if (magic, version, size, kind) != (b"glTF", 2, len(source), b"JSON"):
        raise ValueError("Expected an embedded GLB candidate.")
    model = json.loads(source[20:20 + json_length])
    length, kind = struct.unpack_from("<I4s", source, 20 + json_length)
    binary = bytearray(source[28 + json_length:])
    if kind != b"BIN\0" or length != len(binary):
        raise ValueError("Candidate buffer is incomplete.")

    def array(index, gl_type, shape, dtype):
        accessor = model["accessors"][index]
        view = model["bufferViews"][accessor["bufferView"]]
        if (accessor["componentType"] != gl_type or accessor["type"] != shape
                or view["buffer"] != 0 or "byteStride" in view or "sparse" in accessor):
            raise ValueError("This candidate uses an unsupported mesh layout.")
        width = 3 if shape == "VEC3" else 1
        values = np.frombuffer(binary, dtype=dtype, count=accessor["count"] * width,
                               offset=view.get("byteOffset", 0) + accessor.get("byteOffset", 0))
        return values.reshape(-1, width) if width > 1 else values

    if operation == "denim":
        for material in model["materials"]:
            pbr = material["pbrMetallicRoughness"]
            pbr.update(baseColorFactor=[0.23, 0.35, 0.58, 1], roughnessFactor=0.92, metallicFactor=0)
    else:
        # Components share attribute accessors but have distinct index ranges.
        groups = {}
        for node in model["nodes"]:
            if "mesh" not in node:
                continue
            semantic = str(node.get("extras", {}).get("semantic_type", "")) + " " + node.get("name", "")
            target = operation != "widen_sleeves" or "sleeve" in semantic.lower()
            for primitive in model["meshes"][node["mesh"]]["primitives"]:
                attrs = primitive["attributes"]
                key = (attrs["POSITION"], attrs["NORMAL"])
                selected, protected = groups.setdefault(key, ([], []))
                indices = array(primitive["indices"], 5125, "SCALAR", "<u4")
                (selected if target else protected).append(indices)
        edited = False
        for (pos_id, normal_id), (selected, protected) in groups.items():
            if not selected:
                continue
            indices = np.unique(np.concatenate(selected))
            if protected:
                indices = np.setdiff1d(indices, np.concatenate(protected))
            if not len(indices):
                continue
            pos = array(pos_id, 5126, "VEC3", "<f4")
            normals = array(normal_id, 5126, "VEC3", "<f4")
            if operation == "widen_sleeves":
                # Each sleeve has its own longitudinal axis. Scale its cross-section
                # about that axis and leave vertices shared with other components fixed.
                for section in selected:
                    section_ids = np.intersect1d(indices, section)
                    if len(section_ids) < 3:
                        continue
                    coords = pos[section_ids]
                    center = coords.mean(axis=0)
                    _, _, axes = np.linalg.svd(coords - center, full_matrices=False)
                    radial = np.eye(3) - np.outer(axes[0], axes[0])
                    pos[section_ids] = coords + .1 * (coords - center) @ radial
                    normals[section_ids] -= (1 - 1 / 1.1) * normals[section_ids] @ radial
            else:
                axis, scale = (1, 0.9) if operation == "shorten" else (0, 1.1)
                original = pos[indices, axis]
                anchor = original.max() if operation == "shorten" else (original.max() + original.min()) / 2
                pos[indices, axis] = anchor + (original - anchor) * scale
                normals[indices, axis] /= scale
            normals[indices] /= np.maximum(np.linalg.norm(normals[indices], axis=1, keepdims=True), 1e-12)
            model["accessors"][pos_id].update(min=pos.min(axis=0).tolist(), max=pos.max(axis=0).tolist())
            edited = True
        if not edited:
            raise ValueError("This candidate has no isolated geometry for that component.")

    encoded = json.dumps(model, separators=(",", ":"), allow_nan=False).encode()
    encoded += b" " * (-len(encoded) % 4)
    return (struct.pack("<4sIII4s", b"glTF", 2, 28 + len(encoded) + length, len(encoded), b"JSON")
            + encoded + struct.pack("<I4s", length, kind) + binary)


def remove_invalid_triangles(source: bytes) -> bytes:
    """Append corrected index views while preserving attributes, rig and embedded textures."""
    _, _, _, json_length, _ = struct.unpack_from("<4sIII4s", source)
    model = json.loads(source[20:20 + json_length])
    binary = bytearray(source[28 + json_length:])
    changed = False
    for mesh in model["meshes"]:
        for primitive in mesh["primitives"]:
            if primitive.get("mode", 4) != 4:
                continue
            indexes = model["accessors"][primitive["indices"]]
            positions = model["accessors"][primitive["attributes"]["POSITION"]]
            if indexes["componentType"] != 5125 or positions["componentType"] != 5126:
                continue
            iv = model["bufferViews"][indexes["bufferView"]]
            pv = model["bufferViews"][positions["bufferView"]]
            if "byteStride" in iv or "byteStride" in pv:
                continue
            tris = np.frombuffer(binary, dtype="<u4", count=indexes["count"],
                                 offset=iv.get("byteOffset", 0) + indexes.get("byteOffset", 0)).reshape(-1, 3).copy()
            points = np.frombuffer(binary, dtype="<f4", count=positions["count"] * 3,
                                   offset=pv.get("byteOffset", 0) + positions.get("byteOffset", 0)).reshape(-1, 3)[tris]
            areas = np.linalg.norm(np.cross(points[:, 1]-points[:, 0], points[:, 2]-points[:, 0]), axis=1) / 2
            _, unique = np.unique(np.sort(tris, axis=1), axis=0, return_index=True)
            cleaned = tris[np.sort(unique)]
            cleaned = cleaned[areas[np.sort(unique)] > 1e-9]
            if not len(cleaned) or len(cleaned) == len(tris):
                continue
            changed = True
            view_id = len(model["bufferViews"])
            model["bufferViews"].append({"buffer":0, "byteOffset":len(binary),"byteLength":cleaned.nbytes,"target":34963})
            binary.extend(cleaned.tobytes())
            primitive["indices"] = len(model["accessors"])
            model["accessors"].append({"bufferView":view_id,"componentType":5125,"type":"SCALAR","count":cleaned.size,
                                       "min":[int(cleaned.min())],"max":[int(cleaned.max())]})
    if not changed:
        return source
    model["buffers"][0]["byteLength"] = len(binary)
    encoded = json.dumps(model, separators=(",", ":"), allow_nan=False).encode()
    encoded += b" " * (-len(encoded) % 4)
    return (struct.pack("<4sIII4s", b"glTF", 2, 28 + len(encoded) + len(binary), len(encoded), b"JSON")
            + encoded + struct.pack("<I4s", len(binary), b"BIN\0") + binary)


def apply_parametric_design_edit(
    source: bytes,
    *,
    torso_length_scale: float = 1.0,
    torso_width_scale: float = 1.0,
    shoulder_width_scale: float = 1.0,
    sleeve_length_scale: float = 1.0,
    sleeve_width_scale: float = 1.0,
    collar_width_scale: float = 1.0,
    cuff_width_scale: float = 1.0,
    hem_width_scale: float = 1.0,
    waistband_width_scale: float = 1.0,
    leg_width_scale: float = 1.0,
    leg_length_scale: float = 1.0,
    pocket_offset_y_m: float = 0.0,
    base_color_rgba: list = None,
    roughness: float = None,
    metalness: float = None,
) -> bytes:
    """Apply bounded semantic real-time geometry & material edits to a GLB preserving UVs, normals, and skeleton."""
    bounds = {
        "torso_length_scale": (0.65, 1.40, torso_length_scale),
        "torso_width_scale": (0.70, 1.45, torso_width_scale),
        "shoulder_width_scale": (0.80, 1.30, shoulder_width_scale),
        "sleeve_length_scale": (0.50, 1.35, sleeve_length_scale),
        "sleeve_width_scale": (0.70, 1.45, sleeve_width_scale),
        "collar_width_scale": (0.70, 1.35, collar_width_scale),
        "cuff_width_scale": (0.75, 1.35, cuff_width_scale),
        "hem_width_scale": (0.75, 1.40, hem_width_scale),
        "waistband_width_scale": (0.75, 1.40, waistband_width_scale),
        "leg_width_scale": (0.75, 1.45, leg_width_scale),
        "leg_length_scale": (0.60, 1.35, leg_length_scale),
        "pocket_offset_y_m": (-0.06, 0.06, pocket_offset_y_m),
    }
    for name, (lo, hi, val) in bounds.items():
        if not (lo <= float(val) <= hi):
            raise ValueError(f"Parameter '{name}'={val} outside valid bounds [{lo}, {hi}].")

    magic, version, size, json_length, kind = struct.unpack_from("<4sIII4s", source)
    if (magic, version, size, kind) != (b"glTF", 2, len(source), b"JSON"):
        raise ValueError("Expected an embedded GLB candidate.")
    model = json.loads(source[20:20 + json_length])
    length, kind = struct.unpack_from("<I4s", source, 20 + json_length)
    binary = bytearray(source[28 + json_length:])
    if kind != b"BIN\0" or length != len(binary):
        raise ValueError("Candidate buffer is incomplete.")

    if base_color_rgba is not None or roughness is not None or metalness is not None:
        for material in model.get("materials", []):
            pbr = material.setdefault("pbrMetallicRoughness", {})
            if base_color_rgba is not None and len(base_color_rgba) == 4:
                pbr["baseColorFactor"] = [float(c) for c in base_color_rgba]
            if roughness is not None:
                pbr["roughnessFactor"] = max(0.04, min(1.0, float(roughness)))
            if metalness is not None:
                pbr["metallicFactor"] = max(0.0, min(1.0, float(metalness)))

    def _acc(index, gl_type, shape, dtype):
        accessor = model["accessors"][index]
        view = model["bufferViews"][accessor["bufferView"]]
        if accessor["componentType"] != gl_type or accessor["type"] != shape or view["buffer"] != 0 or "byteStride" in view:
            raise ValueError("Unsupported GLB buffer layout for parametric edit.")
        width = 3 if shape == "VEC3" else 1
        vals = np.frombuffer(binary, dtype=dtype, count=accessor["count"] * width,
                             offset=view.get("byteOffset", 0) + accessor.get("byteOffset", 0))
        return vals.reshape(-1, width) if width > 1 else vals

    # Track already-adjusted vertex indices per POSITION accessor to avoid double-scaling shared vertices
    touched_by_acc = {}
    for node in model.get("nodes", []):
        if "mesh" not in node:
            continue
        semantic = (str(node.get("extras", {}).get("semantic_type", "")) + " " + node.get("name", "")).lower()
        is_sleeve = "sleeve" in semantic
        is_cuff = "cuff" in semantic
        is_collar = "collar" in semantic or "lapel" in semantic or "hood" in semantic or "neck" in semantic
        is_waistband = "waistband" in semantic or "pelvis" in semantic
        is_leg = "leg" in semantic
        is_pocket = "pocket" in semantic
        is_hem = "hem" in semantic

        for primitive in model["meshes"][node["mesh"]].get("primitives", []):
            attrs = primitive.get("attributes", {})
            if "POSITION" not in attrs or "NORMAL" not in attrs:
                continue
            pos_id, norm_id = attrs["POSITION"], attrs["NORMAL"]
            pos = _acc(pos_id, 5126, "VEC3", "<f4")
            norms = _acc(norm_id, 5126, "VEC3", "<f4")
            if "indices" in primitive:
                idx = np.unique(_acc(primitive["indices"], 5125, "SCALAR", "<u4"))
            else:
                idx = np.arange(len(pos), dtype=np.int64)
            seen = touched_by_acc.setdefault(pos_id, set())
            idx = np.array([i for i in idx if int(i) not in seen], dtype=np.int64)
            if not len(idx):
                continue
            seen.update(int(i) for i in idx)

            coords = pos[idx].copy()
            center = coords.mean(axis=0)
            y_min, y_max = float(coords[:, 1].min()), float(coords[:, 1].max())
            span_y = max(1e-4, y_max - y_min)
            sx, sy, sz = torso_width_scale, torso_length_scale, torso_width_scale
            dy = 0.0
            dx_shift = 0.0
            if is_cuff:
                sx, sy, sz = cuff_width_scale, 1.0, cuff_width_scale
            elif is_sleeve:
                sx, sy, sz = sleeve_width_scale, sleeve_length_scale, sleeve_width_scale
                if shoulder_width_scale != 1.0:
                    dx_shift = np.sign(center[0]) * abs(center[0]) * (shoulder_width_scale - 1.0) * 0.5
            elif is_collar:
                sx, sy, sz = collar_width_scale, 1.0, collar_width_scale
            elif is_pocket:
                sx, sy, sz = 1.0, 1.0, 1.0
                dy = pocket_offset_y_m
            elif is_waistband:
                sx, sy, sz = waistband_width_scale, 1.0, waistband_width_scale
            elif is_leg:
                sx, sy, sz = leg_width_scale, leg_length_scale, leg_width_scale
            elif is_hem:
                sx, sy, sz = hem_width_scale, 1.0, hem_width_scale

            if shoulder_width_scale != 1.0 and not (is_sleeve or is_cuff or is_collar or is_leg or is_pocket):
                y_norm = np.clip((coords[:, 1] - y_min) / span_y, 0.0, 1.0)
                upper_blend = np.maximum(0.0, (y_norm - 0.65) / 0.35)
                sx_arr = sx + upper_blend * (shoulder_width_scale - 1.0)
                coords[:, 0] = center[0] + (coords[:, 0] - center[0]) * sx_arr + dx_shift
            else:
                coords[:, 0] = center[0] + (coords[:, 0] - center[0]) * sx + dx_shift
            if hem_width_scale != 1.0 and not (is_sleeve or is_cuff or is_collar or is_leg or is_pocket):
                y_norm = np.clip((coords[:, 1] - y_min) / span_y, 0.0, 1.0)
                lower_blend = np.maximum(0.0, (0.25 - y_norm) / 0.25)
                hx_arr = 1.0 + lower_blend * (hem_width_scale - 1.0)
                coords[:, 0] = center[0] + (coords[:, 0] - center[0]) * hx_arr
            coords[:, 1] = y_max + (coords[:, 1] - y_max) * sy + dy
            coords[:, 2] = center[2] + (coords[:, 2] - center[2]) * sz
            pos[idx] = coords

            norms[idx, 0] /= max(1e-4, sx)
            norms[idx, 1] /= max(1e-4, sy)
            norms[idx, 2] /= max(1e-4, sz)
            norms[idx] /= np.maximum(np.linalg.norm(norms[idx], axis=1, keepdims=True), 1e-12)
            model["accessors"][pos_id].update(min=pos.min(axis=0).tolist(), max=pos.max(axis=0).tolist())

    encoded = json.dumps(model, separators=(",", ":"), allow_nan=False).encode()
    encoded += b" " * (-len(encoded) % 4)
    return (struct.pack("<4sIII4s", b"glTF", 2, 28 + len(encoded) + length, len(encoded), b"JSON")
            + encoded + struct.pack("<I4s", length, kind) + binary)
