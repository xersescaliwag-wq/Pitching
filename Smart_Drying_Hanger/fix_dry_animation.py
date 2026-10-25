"""Refine Dry with blower acceleration, subtle duct flow, and soft towel flutter."""
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
MARKER = "accelerated-dry-system-v1"
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
dry = next(animation for animation in doc["animations"] if animation["name"] == "Dry - full system")
if dry.get("extras", {}).get("motion") == MARKER:
    print("Refined Dry animation already present")
    raise SystemExit(0)

binary = bytearray(next(data for kind, data in chunks if kind == BIN_CHUNK))
del binary[doc["buffers"][0]["byteLength"]:]
views, accessors = doc["bufferViews"], doc["accessors"]


def add_accessor(values, kind, minimum=None, maximum=None):
    width = 1 if kind == "SCALAR" else 3 if kind == "VEC3" else 4
    flat = []
    for value in values:
        flat.extend(value if isinstance(value, (list, tuple)) else [value])
    while len(binary) % 4:
        binary.append(0)
    start = len(binary)
    payload = struct.pack(f"<{len(flat)}f", *flat)
    binary.extend(payload)
    views.append({"buffer": 0, "byteOffset": start, "byteLength": len(payload)})
    item = {"bufferView": len(views) - 1, "componentType": 5126, "count": len(flat) // width, "type": kind}
    if minimum is not None:
        item["min"] = minimum
    if maximum is not None:
        item["max"] = maximum
    accessors.append(item)
    return len(accessors) - 1


times = [round(i * 0.1, 2) for i in range(91)]
time_id = add_accessor(times, "SCALAR", [0.0], [9.0])

# Ease from rest to three revolutions per second instead of snapping to speed.
rotations = []
for time in times:
    u = max(0.0, time - 0.32)
    turns = 0.0 if not u else 3.0 * (u - (1.0 - math.exp(-3.0 * u)) / 3.0)
    angle = turns * math.tau
    rotations.append([0.0, 0.0, math.sin(angle / 2), math.cos(angle / 2)])
dry["samplers"][0]["input"] = time_id
dry["samplers"][0]["output"] = add_accessor(rotations, "VEC4")

# Existing airflow cues stay physically sized; only a small sequential pulse remains.
for order, channel in enumerate(dry["channels"][1:14]):
    values = []
    for time in times:
        if time < 0.9 or time == 9.0:
            scale = 1.0
        else:
            ramp = min(1.0, (time - 0.9) / 0.65)
            scale = 1.0 + ramp * 0.045 * math.sin((time - 0.9) * math.tau / 1.55 - order * 0.62)
        values.append([scale, scale, scale])
    sampler = dry["samplers"][channel["sampler"]]
    sampler["input"] = time_id
    sampler["output"] = add_accessor(values, "VEC3")

# Drive the soft-cloth morph after the vents open. The fold remains pinned by
# the morph itself; only the free fabric receives sub-millimetre flutter.
weights = []
for time in times:
    u = max(0.0, time - 0.9)
    ramp = min(1.0, u / 1.25)
    fade = min(1.0, max(0.0, (9.0 - time) / 0.55))
    wave = 0.72 * math.sin(math.tau * 0.72 * u) + 0.28 * math.sin(math.tau * 1.34 * u + 0.8)
    weights.append(0.15 * ramp * fade * wave)
weight_id = add_accessor(weights, "SCALAR")
dry["samplers"].append({"input": time_id, "output": weight_id, "interpolation": "LINEAR"})
weight_sampler = len(dry["samplers"]) - 1
for node_index in TOWEL_NODES:
    mesh = doc["meshes"][doc["nodes"][node_index]["mesh"]]
    if not mesh["primitives"][0].get("targets"):
        raise ValueError("Run soften_towel_animation.py before fixing Dry")
    dry["channels"].append({"sampler": weight_sampler, "target": {"node": node_index, "path": "weights"}})

dry["extras"] = {
    "generated_by": "smart-hanger-cycle-v2",
    "motion": MARKER,
    "duration": 9.0,
    "blower_speed_rps": 3.0,
    "towel_flutter_weight": 0.15,
}

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
info["dry_animation"] = {
    "blower": "accelerated to 3 revolutions per second",
    "airflow": "sequential low-amplitude duct pulses",
    "towel": "pinned soft-cloth flutter after vent opening",
}
INFO.write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
print("Dry animation refined: accelerated blower, duct flow, and soft towel flutter")
