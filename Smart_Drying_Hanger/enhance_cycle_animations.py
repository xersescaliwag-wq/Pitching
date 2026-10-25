"""Upgrade the web GLB with synchronized multi-part cycle animations.

Run after add_web_animations.py. Existing mesh and material payloads are preserved.
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
MARKER = "smart-hanger-cycle-v2"


def flatten(values):
    result = []
    for value in values:
        result.extend(value if isinstance(value, (list, tuple)) else [value])
    return result


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
if any(a.get("extras", {}).get("generated_by") == MARKER for a in doc.get("animations", [])):
    print("Enhanced cycle animations already present")
    raise SystemExit(0)

binary = bytearray(next(data for kind, data in chunks if kind == BIN_CHUNK))
del binary[doc["buffers"][0]["byteLength"]:]
views, accessors, nodes = doc["bufferViews"], doc["accessors"], doc["nodes"]
roots = doc["scenes"][doc.get("scene", 0)]["nodes"]


def accessor(values, kind, minimum=None, maximum=None):
    while len(binary) % 4:
        binary.append(0)
    data = struct.pack(f"<{len(flatten(values))}f", *flatten(values))
    start = len(binary)
    binary.extend(data)
    views.append({"buffer": 0, "byteOffset": start, "byteLength": len(data)})
    item = {"bufferView": len(views) - 1, "componentType": 5126, "count": len(values), "type": kind}
    if minimum is not None:
        item["min"] = minimum
    if maximum is not None:
        item["max"] = maximum
    accessors.append(item)
    return len(accessors) - 1


def mesh_center(node_index):
    mesh = doc["meshes"][nodes[node_index]["mesh"]]
    position = accessors[mesh["primitives"][0]["attributes"]["POSITION"]]
    return [(a + b) / 2 for a, b in zip(position["min"], position["max"])]


def group_world_nodes(name, children, center):
    for index in children:
        if index in roots:
            roots.remove(index)
        original = nodes[index].get("translation", [0.0, 0.0, 0.0])
        nodes[index]["translation"] = [original[i] - center[i] for i in range(3)]
    parent = len(nodes)
    nodes.append({"name": name, "translation": center, "children": children})
    roots.append(parent)
    return parent


def make_animation(name, duration, channels):
    times = sorted({time for channel in channels for time in channel[1]})
    # Each channel may use its own timestamps, so samplers are kept independent.
    samplers, targets = [], []
    for node, channel_times, values, path in channels:
        input_id = accessor(channel_times, "SCALAR", [channel_times[0]], [channel_times[-1]])
        output_id = accessor(values, "VEC4" if path == "rotation" else "VEC3")
        samplers.append({"input": input_id, "output": output_id, "interpolation": "LINEAR"})
        targets.append({"sampler": len(samplers) - 1, "target": {"node": node, "path": path}})
    animation = {
        "name": name,
        "extras": {"generated_by": MARKER, "duration": duration},
        "samplers": samplers,
        "channels": targets,
    }
    doc.setdefault("animations", []).append(animation)


# Sensor face and apertures breathe together while readings are sampled.
sensor_center = [-0.10230937, 0.00827547, 0.00687]
sensor_group = group_world_nodes("Animated environmental sensor", list(range(130, 137)), sensor_center)
sense_times = [0.0, 0.52, 0.78, 1.02, 1.28, 1.53, 1.78, 2.03, 2.30, 6.20]
sense_scales = [[v, v, v] for v in [1, 1, 1.075, 1, 1.06, 1, 1.045, 1, 1, 1]]
make_animation("Sense - sensor sampling", 6.2, [(sensor_group, sense_times, sense_scales, "scale")])

# Each real status lens gets its own pivot so the red/amber/green handoff is physical.
led_groups = []
for index, color in zip((176, 177, 178), ("red", "amber", "green")):
    led_groups.append(group_world_nodes(f"Animated {color} status lens", [index], mesh_center(index)))
control_times = [0.0, 0.48, 0.72, 1.02, 1.28, 1.55, 1.84, 2.12, 2.45, 5.90]
control_values = [
    [1.0, 1.22, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.96, 0.96],
    [1.0, 1.0, 1.0, 1.0, 1.22, 1.0, 1.0, 1.0, 0.96, 0.96],
    [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.24, 1.10, 1.10],
]
make_animation("Control - status sequence", 5.9, [
    (group, control_times, [[v, v, v] for v in values], "scale")
    for group, values in zip(led_groups, control_values)
])

# Air arrows pulse in order along both ducts while the actual rotor turns.
arrow_nodes = [90, 94, 91, 95, 92, 96, 93, 97, 137, 138, 139, 140, 141]
arrow_groups = [group_world_nodes(f"Animated airflow cue {i:02d}", [node], mesh_center(node)) for i, node in enumerate(arrow_nodes)]
dry_times = [0.0, 0.32] + [round(0.57 + i * 0.25, 2) for i in range(34)]
dry_times.append(9.0)
rotations = []
for time in dry_times:
    turns = max(0.0, time - 0.32)
    angle = turns * math.tau
    rotations.append([0.0, 0.0, math.sin(angle / 2), math.cos(angle / 2)])
dry_channels = [(256, dry_times, rotations, "rotation")]
flow_times = [round(i * 0.2, 2) for i in range(46)]
for order, group in enumerate(arrow_groups):
    values = []
    for time in flow_times:
        if time < 0.9:
            scale = 0.88
        else:
            wave = (math.sin((time - 0.9) * math.tau / 1.55 - order * 0.62) + 1) / 2
            scale = 0.76 + 0.42 * wave
        values.append([scale, scale, scale])
    dry_channels.append((group, flow_times, values, "scale"))
make_animation("Dry - full system", 9.0, dry_channels)

# The charging tray rises into position and settles; the green lens confirms completion.
tray_group = group_world_nodes("Animated charging tray assembly", list(range(236, 255)), [0.066, 0.092, -0.014])
finish_times = [0.0, 0.35, 1.15, 1.55, 2.05, 3.30, 6.60]
tray_positions = [[0.066, y, -0.014] for y in [0.082, 0.082, 0.094, 0.091, 0.092, 0.092, 0.092]]
green_scales = [[v, v, v] for v in [1, 1, 1, 1, 1, 1.28, 1.10]]
make_animation("Finish - dock and confirm", 6.6, [
    (tray_group, finish_times, tray_positions, "translation"),
    (led_groups[2], finish_times, green_scales, "scale"),
])

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
info["animations"] = [animation["name"] for animation in doc["animations"]]
INFO.write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
print(f"Added four synchronized system clips; {len(nodes)} nodes, {GLB.stat().st_size} bytes")
