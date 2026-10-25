import sys
sys.path.extend(['/usr/lib/python3.12/lib-dynload','/opt/codex/runtimes/codex-primary-runtime/dependencies/python/lib/python3.12/site-packages'])
import bpy
from pathlib import Path
ROOT=Path(__file__).parent
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'Smart_Drying_Hanger.blend'))
replacements={}
for mat in bpy.data.materials:
    if not mat.use_nodes:continue
    for node in mat.node_tree.nodes:
        if node.type=='TEX_IMAGE' and node.image:
            name=Path(node.image.filepath).name
            if (ROOT/'textures'/name).exists():
                if name not in replacements:
                    im=bpy.data.images.load(str(ROOT/'textures'/name),check_existing=False)
                    if 'Normal' in name or 'Roughness' in name:im.colorspace_settings.name='Non-Color'
                    im.pack();replacements[name]=im
                node.image=replacements[name]
        if node.type=='NORMAL_MAP' and 'terry' in mat.name.lower():node.inputs['Strength'].default_value=1.15
for im in list(bpy.data.images):
    if im.users==0:bpy.data.images.remove(im)
for ob in bpy.data.objects:
    if ob.name.startswith('Blower radial blade'):
        ob.data.materials.clear();ob.data.materials.append(bpy.data.materials['Dark recessed airflow duct'])
s=bpy.context.scene
for node in list(s.node_tree.nodes):
    if node.type=='OUTPUT_FILE':s.node_tree.nodes.remove(node)
s.camera=bpy.data.objects['Camera • full reference perspective']
s.render.filepath='//renders/Smart_Drying_Hanger_Preview.png'
for ob in bpy.context.selected_objects:ob.select_set(False)
for c in bpy.data.collections:
    if c.name.startswith('06'):continue
    for ob in c.objects:ob.select_set(True)
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'Smart_Drying_Hanger.blend'))
bpy.ops.export_scene.gltf(filepath=str(ROOT/'Smart_Drying_Hanger.glb'),export_format='GLB',use_selection=True,export_apply=True,export_yup=True,export_cameras=False,export_lights=False,export_texcoords=True,export_normals=True,export_materials='EXPORT',export_extras=True)
print('REFRESH_COMPLETE',flush=True)
