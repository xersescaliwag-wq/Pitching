"""Add lightweight product animations directly to the exported GLB.

Run after build_model.py. The operation is idempotent and does not touch mesh data.
"""
from __future__ import annotations

import hashlib
import json
import math
import struct
from pathlib import Path

ROOT = Path(__file__).parent
GLB = ROOT / "Smart_Drying_Hanger.glb"
INFO = ROOT / "Model_Info.json"
MAGIC = 0x46546C67
JSON_CHUNK = 0x4E4F534A
BIN_CHUNK = 0x004E4942
MARKER = "smart-hanger-cycle-v1"


def packed_floats(values):
    flat = []
    for value in values:
        flat.extend(value if isinstance(value, (list, tuple)) else [value])
    return struct.pack(f"<{len(flat)}f", *flat)


raw = GLB.read_bytes()
magic, version, _ = struct.unpack_from("<III", raw, 0)
if magic != MAGIC or version != 2:
    raise ValueError("Expected a glTF 2.0 binary file")

offset = 12
chunks = []
while offset < len(raw):
    length, kind = struct.unpack_from("<II", raw, offset)
    offset += 8
    chunks.append((kind, raw[offset:offset + length]))
    offset += length

document = json.loads(next(data for kind, data in chunks if kind == JSON_CHUNK).rstrip(b" \0"))
if any(a.get("extras", {}).get("generated_by") == MARKER for a in document.get("animations", [])):
    print("Web animation clips already present")
    raise SystemExit(0)

binary = bytearray(next((data for kind, data in chunks if kind == BIN_CHUNK), b""))
logical_length = document["buffers"][0]["byteLength"]
del binary[logical_length:]
buffer_views = document.setdefault("bufferViews", [])
accessors = document.setdefault("accessors", [])


def add_accessor(values, gltf_type, *, minimum=None, maximum=None):
    while len(binary) % 4:
        binary.append(0)
    start = len(binary)
    payload = packed_floats(values)
    binary.extend(payload)
    buffer_views.append({"buffer": 0, "byteOffset": start, "byteLength": len(payload)})
    size = {"SCALAR": 1, "VEC3": 3, "VEC4": 4}[gltf_type]
    accessor = {
        "bufferView": len(buffer_views) - 1,
        "componentType": 5126,
        "count": len(values),
        "type": gltf_type,
    }
    if minimum is not None:
        accessor["min"] = minimum
    if maximum is not None:
        accessor["max"] = maximum
    accessors.append(accessor)
    return len(accessors) - 1


nodes = document["nodes"]
roots = document["scenes"][document.get("scene", 0)]["nodes"]

# Parent the complete towel so its geometry and stitched details settle together.
towel_parts = list(range(228, 236))
for index in towel_parts:
    roots.remove(index)
towel_node = len(nodes)
nodes.append({"name": "Animated towel assembly", "children": towel_parts})
roots.append(towel_node)

# Parent the moving blower components around their physical rotor center.
blower_parts = [31, *range(32, 68), 68]
blower_center = [0.008, 0.073, 0.0065]
for index in blower_parts:
    roots.remove(index)
    original = nodes[index].get("translation", [0.0, 0.0, 0.0])
    nodes[index]["translation"] = [original[i] - blower_center[i] for i in range(3)]
blower_node = len(nodes)
nodes.append({"name": "Animated blower rotor", "translation": blower_center, "children": blower_parts})
roots.append(blower_node)

animations = document.setdefault("animations", [])

# A damp towel drops, overshoots under its weight, then settles on the bar.
hang_times = [0.0, 0.18, 0.72, 1.08, 1.55, 2.15]
hang_positions = [
    [0.0, 0.018, 0.0],
    [0.0, 0.016, 0.0],
    [0.0, -0.0028, 0.0],
    [0.0, 0.0015, 0.0],
    [0.0, -0.0005, 0.0],
    [0.0, 0.0, 0.0],
]
hang_input = add_accessor(hang_times, "SCALAR", minimum=[0.0], maximum=[hang_times[-1]])
hang_output = add_accessor(hang_positions, "VEC3")
animations.append({
    "name": "Hang - towel settle",
    "extras": {"generated_by": MARKER},
    "samplers": [{"input": hang_input, "output": hang_output, "interpolation": "CUBICSPLINE"}],
    "channels": [{"sampler": 0, "target": {"node": towel_node, "path": "translation"}}],
})

# CUBICSPLINE outputs require in-tangent/value/out-tangent triplets.
# Replace the simple values above with soft zero-tangent triplets.
hang_triplets = []
for value in hang_positions:
    hang_triplets.extend(([0.0, 0.0, 0.0], value, [0.0, 0.0, 0.0]))
payload = packed_floats(hang_triplets)
view = buffer_views[accessors[hang_output]["bufferView"]]
start = view["byteOffset"]
old_length = view["byteLength"]
if len(payload) != old_length:
    # This is the final payload currently in the buffer, so it can be expanded in place.
    del binary[start:start + old_length]
    binary[start:start] = payload
    view["byteLength"] = len(payload)
    accessors[hang_output]["count"] = len(hang_triplets)

# A continuous, constant-speed rotor animation used only during the Dry step.
dry_times = [0.0, 0.25, 0.5, 0.75, 1.0]
dry_rotations = []
for turn in (0.0, 0.25, 0.5, 0.75, 1.0):
    angle = turn * math.tau
    dry_rotations.append([0.0, 0.0, math.sin(angle / 2), math.cos(angle / 2)])
dry_input = add_accessor(dry_times, "SCALAR", minimum=[0.0], maximum=[1.0])
dry_output = add_accessor(dry_rotations, "VEC4")
animations.append({
    "name": "Dry - blower rotation",
    "extras": {"generated_by": MARKER},
    "samplers": [{"input": dry_input, "output": dry_output, "interpolation": "LINEAR"}],
    "channels": [{"sampler": 0, "target": {"node": blower_node, "path": "rotation"}}],
})

document["buffers"][0]["byteLength"] = len(binary)
json_bytes = json.dumps(document, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
json_bytes += b" " * (-len(json_bytes) % 4)
binary += b"\0" * (-len(binary) % 4)
body = struct.pack("<II", len(json_bytes), JSON_CHUNK) + json_bytes
body += struct.pack("<II", len(binary), BIN_CHUNK) + binary
GLB.write_bytes(struct.pack("<III", MAGIC, 2, 12 + len(body)) + body)

info = json.loads(INFO.read_text(encoding="utf-8"))
info["file_bytes"] = GLB.stat().st_size
info["sha256"] = hashlib.sha256(GLB.read_bytes()).hexdigest()
info["animations"] = ["Hang - towel settle", "Dry - blower rotation"]
INFO.write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
print(f"Added {len(animations)} web animation clips; {GLB.stat().st_size} bytes")
