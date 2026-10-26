"""
Stage D: Binary glTF 2.0 (.glb) Exporter
Exports separate wearable 3D garments with embedded PBR textures, clean normals, and UVs.
100% specification-compliant with glTF 2.0 specification.
"""

import json
import struct
import numpy as np
from typing import Dict, Any
from .garment_mesh_builder import GarmentMesh


class GLBExporter:
    """Encodes 3D garment mesh and textures into a single self-contained binary .glb file."""

    def export(
        self,
        mesh: GarmentMesh,
        diffuse_png_bytes: bytes,
        normal_png_bytes: bytes,
        name: str = "yorvyn_garment"
    ) -> bytes:
        # Prepare binary arrays
        pos_bytes = mesh.positions.astype("<f4").tobytes()
        norm_bytes = mesh.normals.astype("<f4").tobytes()
        
        # glTF standard expects V coordinates with origin at top-left
        uvs_flipped = mesh.uvs.copy()
        uvs_flipped[:, 1] = 1.0 - uvs_flipped[:, 1]
        uv_bytes = uvs_flipped.astype("<f4").tobytes()
        
        idx_bytes = mesh.indices.flatten().astype("<u4").tobytes()
        
        # Calculate bounding box
        pos_min = mesh.positions.min(axis=0).tolist()
        pos_max = mesh.positions.max(axis=0).tolist()
        
        # Binary chunk buffers
        bin_chunks = []
        buffer_views = []
        accessors = []
        
        def add_buffer_view(data: bytes, target: int = None) -> int:
            offset = sum(len(c) for c in bin_chunks)
            pad = (4 - (offset % 4)) % 4
            if pad:
                bin_chunks.append(b"\x00" * pad)
                offset += pad
            
            bv_idx = len(buffer_views)
            bv_entry = {
                "buffer": 0,
                "byteOffset": offset,
                "byteLength": len(data)
            }
            if target:
                bv_entry["target"] = target
            buffer_views.append(bv_entry)
            bin_chunks.append(data)
            return bv_idx

        # Target 34963 = ELEMENT_ARRAY_BUFFER (indices)
        idx_bv = add_buffer_view(idx_bytes, 34963)
        accessors.append({
            "bufferView": idx_bv,
            "byteOffset": 0,
            "componentType": 5125, # UNSIGNED_INT
            "count": len(mesh.indices) * 3,
            "type": "SCALAR"
        })
        idx_accessor = 0
        
        # Target 34962 = ARRAY_BUFFER (vertex attributes)
        pos_bv = add_buffer_view(pos_bytes, 34962)
        accessors.append({
            "bufferView": pos_bv,
            "byteOffset": 0,
            "componentType": 5126, # FLOAT
            "count": len(mesh.positions),
            "type": "VEC3",
            "min": pos_min,
            "max": pos_max
        })
        pos_accessor = 1
        
        norm_bv = add_buffer_view(norm_bytes, 34962)
        accessors.append({
            "bufferView": norm_bv,
            "byteOffset": 0,
            "componentType": 5126, # FLOAT
            "count": len(mesh.normals),
            "type": "VEC3"
        })
        norm_accessor = 2
        
        uv_bv = add_buffer_view(uv_bytes, 34962)
        accessors.append({
            "bufferView": uv_bv,
            "byteOffset": 0,
            "componentType": 5126, # FLOAT
            "count": len(mesh.uvs),
            "type": "VEC2"
        })
        uv_accessor = 3
        
        # Add embedded texture image buffers
        diffuse_img_bv = add_buffer_view(diffuse_png_bytes)
        normal_img_bv = add_buffer_view(normal_png_bytes)
        
        images = [
            {"bufferView": diffuse_img_bv, "mimeType": "image/png", "name": "diffuse"},
            {"bufferView": normal_img_bv, "mimeType": "image/png", "name": "normal"}
        ]
        
        samplers = [{
            "magFilter": 9729, # LINEAR
            "minFilter": 9987, # LINEAR_MIPMAP_LINEAR
            "wrapS": 10497,    # REPEAT
            "wrapT": 10497     # REPEAT
        }]
        
        textures = [
            {"sampler": 0, "source": 0, "name": "baseColorTexture"},
            {"sampler": 0, "source": 1, "name": "normalTexture"}
        ]
        
        materials = [{
            "name": f"{name}_mat",
            "pbrMetallicRoughness": {
                "baseColorTexture": {"index": 0},
                "metallicFactor": 0.04,
                "roughnessFactor": 0.72
            },
            "normalTexture": {"index": 1, "scale": 1.0},
            "doubleSided": True
        }]
        
        meshes = [{
            "name": name,
            "primitives": [{
                "attributes": {
                    "POSITION": pos_accessor,
                    "NORMAL": norm_accessor,
                    "TEXCOORD_0": uv_accessor
                },
                "indices": idx_accessor,
                "material": 0,
                "mode": 4 # TRIANGLES
            }]
        }]
        
        nodes = [{
            "name": name,
            "mesh": 0
        }]
        
        scenes = [{
            "name": "DefaultScene",
            "nodes": [0]
        }]
        
        # Construct JSON descriptor
        total_bin_length = sum(len(c) for c in bin_chunks)
        buffers = [{
            "byteLength": total_bin_length
        }]
        
        gltf_dict: Dict[str, Any] = {
            "asset": {
                "version": "2.0",
                "generator": "Yorvyn AI 3D Garment Engine v2.0"
            },
            "scene": 0,
            "scenes": scenes,
            "nodes": nodes,
            "meshes": meshes,
            "materials": materials,
            "textures": textures,
            "images": images,
            "samplers": samplers,
            "accessors": accessors,
            "bufferViews": buffer_views,
            "buffers": buffers
        }
        
        json_bytes = json.dumps(gltf_dict, separators=(",", ":")).encode("utf-8")
        
        # glTF requires JSON chunk to be padded with space (0x20) to 4-byte alignment
        json_pad = (4 - (len(json_bytes) % 4)) % 4
        if json_pad:
            json_bytes += b" " * json_pad
            
        # glTF requires BIN chunk to be padded with 0x00 to 4-byte alignment
        bin_data = b"".join(bin_chunks)
        bin_pad = (4 - (len(bin_data) % 4)) % 4
        if bin_pad:
            bin_data += b"\x00" * bin_pad
            
        # Construct GLB Container
        # Header: magic (4), version (4), totalLength (4)
        # Chunk 0: length (4), type "JSON" (4), data
        # Chunk 1: length (4), type "BIN\0" (4), data
        total_length = 12 + 8 + len(json_bytes) + 8 + len(bin_data)
        
        header = struct.pack("<4sII", b"glTF", 2, total_length)
        chunk0_header = struct.pack("<I4s", len(json_bytes), b"JSON")
        chunk1_header = struct.pack("<I4s", len(bin_data), b"BIN\x00")
        
        return header + chunk0_header + json_bytes + chunk1_header + bin_data


# Singleton GLB exporter
glb_exporter = GLBExporter()
