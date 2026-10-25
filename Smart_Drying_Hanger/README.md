# Smart Drying Hanger — PBR 3D Reconstruction

Reference: the supplied multi-view product illustration, `image(20261025-145918).png`.

## Open the model

- **Smart_Drying_Hanger.glb** — portable 3D model with embedded PBR textures. Import into Blender, a glTF viewer, Three.js, or other glTF 2.0 software. The charger and towel remain separate named objects.
- **Smart_Drying_Hanger.blend** — editable Blender 4.x project. Contains organized parts, packed texture images, soft studio lights, and four cameras. The main camera is selected when the file opens.
- **renders/** — full product, central cutaway, and underside detail images.
- **textures/** — editable PNG source maps. Normal and roughness maps use linear/non-color data. Terry normal maps use the OpenGL tangent-space convention.

## Modeled details

Gloss white wide shoulders with two recessed dark channels on each arm; silver trim and hook; pale-blue airflow markings; a thin clear cutaway cover; round black centrifugal blower; teal cylindrical battery with silver end cap; a black control module and slotted intake grille; right-arm indicator panel, red/amber/green LEDs and display; central underside grille; two violet-blue LED strips, vent slots and the round left-tip sensor; silver crossbar and curved white center support.

The thick white towel is one continuous, predominantly quad surface folded over the crossbar. It includes layered folds, thickness, stitched hems, modeled terry loops, repeating fabric normal and roughness maps, and separate UV-mapped color and emission artwork with dotted strips, down arrows and circled UV markers. The recessed charging tray has two gold pins and a detailed side USB-C port.

## Materials and units

The GLB uses glTF 2.0 metallic/roughness PBR, plus clearcoat, transmission, index of refraction, sheen, texture transforms and emissive-strength extensions. A viewer supporting these extensions best reproduces the transparent cover and UV lighting. Studio lights are retained in the Blender project; GLB lighting comes from the importing application.

Geometry is stored in meters. The approximate display scale follows the reference's nominal 220 mm hanger-width callout. This is a visual reconstruction: the illustration does not specify every depth or concealed surface, and those parts are inferred. Exact equivalence to an unavailable original CAD model cannot be verified.

## Source maps

| Map | Use |
| --- | --- |
| Terry_BaseColor.png | Seamless white cotton source tile |
| Terry_Normal.png | Repeating raised terry-loop tangent normal |
| Terry_Roughness.png | Repeating fabric roughness |
| Terry_AO.png | Optional source-tile ambient occlusion |
| Terry_Height.png | Optional 16-bit source-tile displacement |
| Towel_BaseColor.png | Complete drape artwork and blue-violet light tint |
| Towel_UV_Emission.png | Emissive UV diagram artwork |
| Indicator_BaseColor.png | Black control panel labels and display |

AO and height are included as editable source maps; the portable model uses modeled pile, normal mapping and PBR roughness.

## Rebuild

`build_model.py` regenerates the editable geometry, packs maps, and exports GLB from Blender 4.x. Set `HANGER_RENDER=none` to export without rendering. `make_textures.py` regenerates PNG source maps using Python, NumPy, Pillow and SciPy. `render_model.py` renders the camera views. The optional `denoise_renders.py` uses Intel Open Image Denoise with albedo/normal guide passes.

After rebuilding the GLB, run `python add_web_animations.py`, `python enhance_cycle_animations.py`, `python polish_hang_animation.py`, `python soften_towel_animation.py`, `python fix_sense_animation.py`, and `python fix_dry_animation.py`. These add the synchronized cycle clips, pinned soft-cloth deformation, localized sensor-face motion, and the accelerated blower/duct/towel drying response, then refresh the manifest checksum.

The exported GLB was checked with the Khronos glTF Validator; it reported zero errors and zero warnings.
