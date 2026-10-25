import bpy
from pathlib import Path
ROOT=Path(__file__).parent
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'Smart_Drying_Hanger.blend'))
s=bpy.context.scene
s.camera=bpy.data.objects['Camera • full reference perspective']
s.render.filepath='//renders/Smart_Drying_Hanger_Preview.png'
s.render.resolution_x=1800;s.render.resolution_y=1800;s.render.resolution_percentage=100
s.cycles.samples=96;s.cycles.use_denoising=False
s.view_layers[0].cycles.denoising_store_passes=False
for node in list(s.node_tree.nodes):
    if node.type=='OUTPUT_FILE':s.node_tree.nodes.remove(node)
for ob in bpy.data.objects:
    ob.select_set(False)
    ob.hide_render=False
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            sp=area.spaces.active
            sp.shading.type='MATERIAL';sp.overlay.show_overlays=False
            sp.region_3d.view_perspective='CAMERA';sp.clip_start=.001
for im in bpy.data.images:
    if im.source=='FILE' and not im.packed_file:im.pack()
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'Smart_Drying_Hanger.blend'))
print('EDITABLE_PROJECT_FINALIZED',flush=True)
