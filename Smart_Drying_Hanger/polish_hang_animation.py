"""Replace the basic Hang clip with a smooth, weighted towel-settle motion.

Run after add_web_animations.py and enhance_cycle_animations.py.
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
MAGIC, JSON_CHUNK, BIN_CHUNK = 0x46546C67, 0x4E4F534A, 0x004E4942
MARKER = "weighted-towel-settle-v2"


def flatten(values):
    result = []
    for value in values:
        result.extend(value)
    return result


def smooth_triplets(times, values):
    """Create glTF cubic-spline tangents using time-aware finite differences."""
    tangents = []
    for i, value in enumerate(values):
        if i == 0:
            left, right = 0, 1
        elif i == len(values) - 1:
            left, right = i - 1, i
        else:
            left, right = i - 1, i + 1
        dt = times[right] - times[left]
        tangents.append([(values[right][axis] - values[left][axis]) / dt for axis in range(3)])
    output = []
    for tangent, value in zip(tangents, values):
        output.extend((tangent, value, tangent))
    return output


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
if hang.get("extras", {}).get("motion") == MARKER:
    print("Polished Hang animation already present")
    raise SystemExit(0)

binary = bytearray(next(data for kind, data in chunks if kind == BIN_CHUNK))
del binary[doc["buffers"][0]["byteLength"]:]
views, accessors = doc["bufferViews"], doc["accessors"]
towel_node = hang["channels"][0]["target"]["node"]

# Keep the fold line attached to the crossbar. Earlier versions transformed the
# assembly around the scene origin, which could make the towel look detached.
towel_pivot = [0.0, 0.0095, 0.0]
towel_parent = doc["nodes"][towel_node]
if towel_parent.get("extras", {}).get("anchored_pivot") != towel_pivot:
    old_parent = towel_parent.get("translation", [0.0, 0.0, 0.0])
    for child_index in towel_parent.get("children", []):
        child = doc["nodes"][child_index]
        old_child = child.get("translation", [0.0, 0.0, 0.0])
        child["translation"] = [old_child[i] + old_parent[i] - towel_pivot[i] for i in range(3)]
    towel_parent["translation"] = towel_pivot
    towel_parent.setdefault("extras", {})["anchored_pivot"] = towel_pivot


def accessor(values, kind, *, count=None, minimum=None, maximum=None):
    while len(binary) % 4:
        binary.append(0)
    payload = struct.pack(f"<{len(flatten(values))}f", *flatten(values))
    start = len(binary)
    binary.extend(payload)
    views.append({"buffer": 0, "byteOffset": start, "byteLength": len(payload)})
    item = {"bufferView": len(views) - 1, "componentType": 5126, "count": count or len(values), "type": kind}
    if minimum is not None:
        item["min"] = minimum
    if maximum is not None:
        item["max"] = maximum
    accessors.append(item)
    return len(accessors) - 1


# The irregular spacing gives the initial fall energy and the final motion room to decay.
times = [0.0, 0.18, 0.42, 0.70, 0.98, 1.26, 1.56, 1.90, 2.26, 2.66, 3.08, 3.45]
positions = [
    [0.0000, 0.0118, 0.0000],
    [-0.0001, 0.0114, 0.0001],
    [0.0002, 0.0107, -0.0001],
    [-0.0002, 0.0098, 0.0001],
    [0.0002, 0.0091, -0.0001],
    [-0.0001, 0.0097, 0.0000],
    [0.0001, 0.00935, 0.0000],
    [-0.0001, 0.00958, 0.0000],
    [0.0000, 0.00946, 0.0000],
    [0.0000, 0.00952, 0.0000],
    [0.0000, 0.00949, 0.0000],
    [0.0000, 0.00950, 0.0000],
]
scales = [
    [0.996, 0.976, 1.000],
    [0.997, 0.980, 1.000],
    [0.998, 0.988, 1.000],
    [1.000, 0.998, 1.000],
    [1.002, 1.012, 0.999],
    [1.003, 1.018, 0.999],
    [0.999, 0.993, 1.001],
    [1.002, 1.007, 0.999],
    [0.999, 0.997, 1.000],
    [1.001, 1.002, 1.000],
    [1.000, 0.999, 1.000],
    [1.000, 1.000, 1.000],
]
angles = [0.75, 0.68, 0.48, 0.12, -0.62, -0.82, 0.50, -0.32, 0.18, -0.08, 0.03, 0.0]
rotations = [[0.0, 0.0, math.sin(math.radians(angle) / 2), math.cos(math.radians(angle) / 2)] for angle in angles]

time_id = accessor([[time] for time in times], "SCALAR", minimum=[times[0]], maximum=[times[-1]])
translation_id = accessor(smooth_triplets(times, positions), "VEC3", count=len(times) * 3)
scale_id = accessor(smooth_triplets(times, scales), "VEC3", count=len(times) * 3)
rotation_id = accessor(rotations, "VEC4")
hang["samplers"] = [
    {"input": time_id, "output": translation_id, "interpolation": "CUBICSPLINE"},
    {"input": time_id, "output": scale_id, "interpolation": "CUBICSPLINE"},
    {"input": time_id, "output": rotation_id, "interpolation": "LINEAR"},
]
hang["channels"] = [
    {"sampler": 0, "target": {"node": towel_node, "path": "translation"}},
    {"sampler": 1, "target": {"node": towel_node, "path": "scale"}},
    {"sampler": 2, "target": {"node": towel_node, "path": "rotation"}},
]
hang["extras"] = {"generated_by": "smart-hanger-cycle-v1", "motion": MARKER, "duration": times[-1]}

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
info["hang_animation"] = {
    "duration_seconds": times[-1],
    "tracks": ["translation", "scale", "rotation"],
    "motion": "weighted drop, stretch, sway and damped settle",
}
INFO.write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
print(f"Polished Hang animation: {len(times)} keys across three synchronized tracks")
