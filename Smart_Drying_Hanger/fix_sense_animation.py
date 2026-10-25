"""Refine Sense: keep the sensor body fixed and animate only its sensing face."""
from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path

ROOT = Path(__file__).parent
GLB = ROOT / "Smart_Drying_Hanger.glb"
INFO = ROOT / "Model_Info.json"
MAGIC, JSON_CHUNK, BIN_CHUNK = 0x46546C67, 0x4E4F534A, 0x004E4942
MARKER = "localized-sensor-face-v1"

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
sense = next(animation for animation in doc["animations"] if animation["name"] == "Sense - sensor sampling")
if sense.get("extras", {}).get("motion") == MARKER:
    print("Localized Sense animation already present")
    raise SystemExit(0)

binary = bytearray(next(data for kind, data in chunks if kind == BIN_CHUNK))
del binary[doc["buffers"][0]["byteLength"]:]
nodes, accessors, views = doc["nodes"], doc["accessors"], doc["bufferViews"]
sensor_group = sense["channels"][0]["target"]["node"]
face_parts = list(range(131, 137))
for part in face_parts:
    nodes[sensor_group]["children"].remove(part)
face_group = len(nodes)
nodes.append({
    "name": "Animated sensing face only",
    "children": face_parts,
    "extras": {"localized_motion": True},
})
nodes[sensor_group]["children"].append(face_group)

# A very small focus response; the housing remains at exactly 1.0 scale.
values = [1.0, 1.0, 1.006, 1.0, 1.004, 1.0, 1.0025, 1.0, 1.0, 1.0]
scales = [component for value in values for component in (value, value, value)]
while len(binary) % 4:
    binary.append(0)
start = len(binary)
payload = struct.pack(f"<{len(scales)}f", *scales)
binary.extend(payload)
views.append({"buffer": 0, "byteOffset": start, "byteLength": len(payload)})
accessors.append({"bufferView": len(views) - 1, "componentType": 5126, "count": len(values), "type": "VEC3"})
sense["samplers"][0]["output"] = len(accessors) - 1
sense["channels"][0]["target"]["node"] = face_group
sense["extras"] = {"generated_by": "smart-hanger-cycle-v2", "motion": MARKER, "duration": 6.2}

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
info["sense_animation"] = {
    "housing_motion": "fixed",
    "animated_parts": "sensor face and apertures only",
    "maximum_scale": 1.006,
}
INFO.write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
print("Sense animation localized to the sensing face; housing remains fixed")
