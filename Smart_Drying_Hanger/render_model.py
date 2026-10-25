import bpy, os
from pathlib import Path
ROOT=Path(__file__).parent
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'Smart_Drying_Hanger.blend'))
s=bpy.context.scene
s.cycles.use_denoising=False
s.render.threads_mode='FIXED';s.render.threads=12
bpy.data.objects['Camera • underside details'].data.ortho_scale=.270
s.view_layers[0].cycles.denoising_store_passes=True
rl=next(n for n in s.node_tree.nodes if n.type=='R_LAYERS')
aux=s.node_tree.nodes.new('CompositorNodeOutputFile')
aux.base_path=str(ROOT/'renders'/'auxiliary')
aux.format.file_format='OPEN_EXR';aux.format.color_mode='RGB';aux.format.color_depth='32';aux.format.exr_codec='ZIP'
aux.file_slots.clear()
for label,socket in [('Albedo','Denoising Albedo'),('Normal','Denoising Normal')]:
    aux.file_slots.new(label)
    s.node_tree.links.new(rl.outputs[socket],aux.inputs[label])
def auxname(stem):
    for slot,label in zip(aux.file_slots,['Albedo','Normal']):slot.path=stem+'_'+label+'_'
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            area.spaces.active.region_3d.view_perspective='CAMERA'
            area.spaces.active.clip_start=.001
            area.spaces.active.overlay.show_overlays=False
mode=os.environ.get('HANGER_RENDER','draft')
if mode=='draft':
    s.render.resolution_percentage=55;s.cycles.samples=24
    auxname('Preview_Draft')
    s.render.filepath=str(ROOT/'renders'/'Preview_Draft.png')
    bpy.ops.render.render(write_still=True)
else:
    s.render.resolution_percentage=100;s.cycles.samples=48
    s.render.resolution_x=1800;s.render.resolution_y=1800
    s.render.filepath=str(ROOT/'renders'/'Smart_Drying_Hanger_Preview_Raw.png')
    auxname('Smart_Drying_Hanger_Preview')
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'Smart_Drying_Hanger.blend'))
    bpy.ops.render.render(write_still=True)
    s.camera=bpy.data.objects['Camera • cutaway and arms']
    s.render.resolution_x=1800;s.render.resolution_y=1200;s.cycles.samples=48
    s.render.filepath=str(ROOT/'renders'/'Cutaway_Detail_Raw.png')
    auxname('Cutaway_Detail')
    bpy.ops.render.render(write_still=True)
    for key in ['04 • Draped terry towel','05 • Detachable charging cradle']:
        for ob in bpy.data.collections[key].objects:ob.hide_render=True
    bpy.data.objects['Studio ground'].hide_render=True
    s.camera=bpy.data.objects['Camera • underside details'];s.cycles.samples=48
    s.render.filepath=str(ROOT/'renders'/'Underside_Detail_Raw.png')
    auxname('Underside_Detail')
    bpy.ops.render.render(write_still=True)
print('RENDERS_COMPLETE',flush=True)
