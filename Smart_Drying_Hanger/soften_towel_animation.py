"""Add a pinned, vertex-level soft-cloth morph to the Hang animation.

Run after polish_hang_animation.py. The top fold stays fixed while motion grows
toward the free hem, including all towel bindings, seams, and terry loops.
"""
from __future__ import annotations

from array import array
import hashlib
import json
import math
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).parent
GLB = ROOT / "Smart_Drying_Hanger.glb"
INFO = ROOT / "Model_Info.json"
MAGIC, JSON_CHUNK, BIN_CHUNK = 0x46546C67, 0x4E4F534A, 0x004E4942
MARKER = "pinned-soft-cloth-v1"
TOWEL_NODES = list(range(228, 236))

raw = GLB.read_bytes()
magic, version, _ = struct.unpack_from("<III", raw, 0)
if (magic, version) != (MAGIC, 2):
    raise ValueError("Expected a glTF 2.0 binary file")

chunks, offset = [], 12
while offset < len(raw):
    length, kind = struct.unpack_from("<II", raw, offset)
    offset += 8
    chunks.append((kind, raw[offset:offset + length]))
    offset += length

doc = json.loads(next(data for kind, data in chunks if kind == JSON_CHUNK).rstrip(b" \0"))
hang = next(animation for animation in doc["animations"] if animation["name"] == "Hang - towel settle")
if hang.get("extras", {}).get("soft_cloth") == MARKER:
    print("Soft towel morph already present")
    raise SystemExit(0)

binary = bytearray(next(data for kind, data in chunks if kind == BIN_CHUNK))
del binary[doc["buffers"][0]["byteLength"]:]
views, accessors = doc["bufferViews"], doc["accessors"]


def position_reader(accessor_id):
    item = accessors[accessor_id]
    if item["componentType"] != 5126 or item["type"] != "VEC3" or item.get("sparse"):
        raise ValueError("Towel positions must be non-sparse float VEC3 accessors")
    view = views[item["bufferView"]]
    start = view.get("byteOffset", 0) + item.get("byteOffset", 0)
    stride = view.get("byteStride", 12)
    for index in range(item["count"]):
        yield struct.unpack_from("<3f", binary, start + index * stride)


def append_delta_accessor(position_accessor):
    top, bottom = 0.0110, -0.1450
    height = top - bottom
    values = array("f")
    for x, y, z in position_reader(position_accessor):
        u = max(0.0, min(1.0, (top - y) / height))
        # Smooth attachment mask: effectively zero across the folded top band.
        free = u * u * (3.0 - 2.0 * u)
        free *= max(0.0, min(1.0, (u - 0.055) / 0.19))
        broad = math.sin(math.tau * (u * 1.18 + x / 0.125))
        secondary = math.sin(math.tau * (u * 2.75 - x / 0.072 + z / 0.026))
        cross = math.sin(math.tau * (x / 0.095 - u * 0.62))
        dx = free * (0.00255 * broad + 0.00072 * secondary)
        dy = free * (0.00072 * cross - 0.00028 * broad)
        dz = free * (0.00285 * broad + 0.00088 * secondary)
        values.extend((dx, dy, dz))
    if sys.byteorder != "little":
        values.byteswap()
    while len(binary) % 4:
        binary.append(0)
    start = len(binary)
    payload = values.tobytes()
    binary.extend(payload)
    views.append({"buffer": 0, "byteOffset": start, "byteLength": len(payload)})
    source = accessors[position_accessor]
    accessors.append({
        "bufferView": len(views) - 1,
        "componentType": 5126,
        "count": source["count"],
        "type": "VEC3",
        "min": [-0.0034, -0.0011, -0.0038],
        "max": [0.0034, 0.0011, 0.0038],
    })
    return len(accessors) - 1


vertex_total = 0
for node_index in TOWEL_NODES:
    node = doc["nodes"][node_index]
    mesh = doc["meshes"][node["mesh"]]
    for primitive in mesh["primitives"]:
        position_id = primitive["attributes"]["POSITION"]
        vertex_total += accessors[position_id]["count"]
        primitive.setdefault("targets", []).append({"POSITION": append_delta_accessor(position_id)})
    mesh["weights"] = [0.0]
    node["weights"] = [0.0]

# Reuse the Hang translation sampler's timestamps so deformation, stretch, and
# sway always land on the exact same frames.
time_accessor = hang["samplers"][0]["input"]
weights = [0.0, 0.04, 0.16, 0.44, 0.82, 1.0, -0.48, 0.27, -0.14, 0.065, -0.018, 0.0]
while len(binary) % 4:
    binary.append(0)
start = len(binary)
payload = struct.pack(f"<{len(weights)}f", *weights)
binary.extend(payload)
views.append({"buffer": 0, "byteOffset": start, "byteLength": len(payload)})
accessors.append({"bufferView": len(views) - 1, "componentType": 5126, "count": len(weights), "type": "SCALAR"})
weight_accessor = len(accessors) - 1
hang["samplers"].append({"input": time_accessor, "output": weight_accessor, "interpolation": "LINEAR"})
weight_sampler = len(hang["samplers"]) - 1
for node_index in TOWEL_NODES:
    hang["channels"].append({"sampler": weight_sampler, "target": {"node": node_index, "path": "weights"}})
hang.setdefault("extras", {})["soft_cloth"] = MARKER
hang["extras"]["deformed_vertices"] = vertex_total
hang["extras"]["pinned_top"] = True

doc["buffers"][0]["byteLength"] = len(binary)
json_data = json.dumps(doc, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
json_data += b" " * (-len(json_data) % 4)
binary += b"\0" * (-len(binary) % 4)
body = struct.pack("<II", len(json_data), JSON_CHUNK) + json_data
body += struct.pack("<II", len(binary), BIN_CHUNK) + binary
GLB.write_bytes(struct.pack("<III", MAGIC, 2, 12 + len(body)) + body)

info = json.loads(INFO.read_text(encoding="utf-8"))
info["file_bytes"] = GLB.stat().st_size
info["sha256"] = hashlib.sha256(GLB.read_bytes()).hexdigest()
info["towel_deformation"] = {
    "type": "pinned vertex morph",
    "vertices": vertex_total,
    "pinned_fold": True,
    "falloff": "progressive toward free hem",
}
INFO.write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
print(f"Added pinned soft-cloth deformation to {vertex_total:,} towel vertices")
