"""Reference-guided, millimetre-scale smart drying hanger.
Run in Blender 4.x: blender -b --python build_model.py
"""
import sys
sys.path.append('/usr/lib/python3.12/lib-dynload')
sys.path.append('/opt/codex/runtimes/codex-primary-runtime/dependencies/python/lib/python3.12/site-packages')
import bpy, bmesh, math, random, json, os
from pathlib import Path
from mathutils import Vector
from math import sin, cos, pi, sqrt

ROOT=Path(__file__).parent
TEX=ROOT/'textures'
MM=.001
random.seed(1948)
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
for c in list(bpy.data.collections):
    if c.name!='Collection': bpy.data.collections.remove(c)
default=bpy.data.collections.get('Collection')
default.name='01 • White and silver shell'
COL=default
collections={'shell':default}
for key,name in [('inside','02 • Visible cutaway components'),('air','03 • Airflow, UV, vents and controls'),('cloth','04 • Draped terry towel'),('base','05 • Detachable charging cradle'),('studio','06 • Studio lights and cameras')]:
    c=bpy.data.collections.new(name); bpy.context.scene.collection.children.link(c); collections[key]=c

def collection(key):
    global COL
    COL=collections[key]
def link(obj):
    for c in list(obj.users_collection): c.objects.unlink(obj)
    COL.objects.link(obj)
    return obj
def material(name,color,metal=0,rough=.3,coat=0,emission=None,strength=0,trans=0):
    m=bpy.data.materials.new(name);m.use_nodes=True
    p=m.node_tree.nodes.get('Principled BSDF')
    p.inputs['Base Color'].default_value=(*color,1)
    p.inputs['Metallic'].default_value=metal
    p.inputs['Roughness'].default_value=rough
    p.inputs['Coat Weight'].default_value=coat
    p.inputs['Coat Roughness'].default_value=.12
    p.inputs['Transmission Weight'].default_value=trans
    if emission:
        p.inputs['Emission Color'].default_value=(*emission,1)
        p.inputs['Emission Strength'].default_value=strength
    return m

WHITE=material('Gloss white molded polymer',(.89,.915,.925),rough=.18,coat=.42)
SILVER=material('Polished silver metal',(.7,.76,.8),metal=1,rough=.19,coat=.14)
BRUSHED=material('Satin silver channel trim',(.47,.55,.59),metal=.88,rough=.3)
DARK=material('Dark recessed airflow duct',(.075,.105,.12),metal=.25,rough=.32)
BLACK=material('Black blower and electronics',(.018,.024,.028),rough=.31)
RUBBER=material('Black grille and seals',(.012,.018,.02),rough=.48)
TEAL=material('Teal battery sleeve',(.15,.45,.43),metal=.35,rough=.26,coat=.2)
GOLD=material('Gold plated charging contacts',(.82,.53,.15),metal=1,rough=.22)
GLASS=material('Clear cutaway cover',(.91,.98,1),rough=.025,coat=.1,trans=1)
GLASS.node_tree.nodes.get('Principled BSDF').inputs['IOR'].default_value=1.1
BLUE=material('Pale blue airflow markings',(.21,.6,.79),rough=.4,emission=(.11,.38,.6),strength=.12)
UV=material('Violet blue underside LED emitter',(.22,.10,.68),rough=.22,emission=(.20,.075,1),strength=3)
RED=material('Red status LED',(.7,.025,.015),rough=.18,emission=(1,.018,.005),strength=1.8)
AMBER=material('Amber status LED',(.85,.43,.015),rough=.18,emission=(1,.5,.01),strength=1.8)
GREEN=material('Green status LED',(.08,.56,.10),rough=.18,emission=(.12,1,.08),strength=1.6)

def mesh(name,vs,fs,mat,uvs=None,indices=None,smooth=True):
    me=bpy.data.meshes.new(name)
    me.from_pydata([tuple(a*MM for a in v) for v in vs],[],fs);me.update()
    ob=bpy.data.objects.new(name,me);COL.objects.link(ob)
    mats=mat if isinstance(mat,list) else [mat]
    for m in mats:me.materials.append(m)
    if indices:
        for p,i in zip(me.polygons,indices):p.material_index=i
    if uvs:
        layer=me.uv_layers.new(name='UVMap')
        for poly in me.polygons:
            for li in poly.loop_indices:layer.data[li].uv=uvs[me.loops[li].vertex_index]
    for p in me.polygons:p.use_smooth=smooth
    bm=bmesh.new();bm.from_mesh(me);bmesh.ops.recalc_face_normals(bm,faces=bm.faces);bm.to_mesh(me);bm.free()
    return ob
def bevel(ob,width=.3,segments=3):
    if hasattr(ob.data,'use_auto_smooth'):ob.data.use_auto_smooth=True
    b=ob.modifiers.new('Soft manufactured edge radii','BEVEL');b.width=width*MM;b.segments=segments
    b.limit_method='ANGLE'
    w=ob.modifiers.new('Weighted surface normals','WEIGHTED_NORMAL');w.keep_sharp=True
    return ob
def cube(name,loc,dims,mat,r=.4,rot=None):
    bpy.ops.mesh.primitive_cube_add(size=1,location=Vector(loc)*MM)
    ob=link(bpy.context.object);ob.name=name
    ob.dimensions=Vector(dims)*MM
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    if rot:ob.rotation_euler=rot
    ob.data.materials.append(mat)
    if r:bevel(ob,r,5)
    return ob
def cyl(name,loc,radius,depth,mat,axis='Z',verts=64,bev=.15):
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts,radius=radius*MM,depth=depth*MM,location=Vector(loc)*MM)
    ob=link(bpy.context.object);ob.name=name
    if axis=='X':ob.rotation_euler[1]=pi/2
    elif axis=='Y':ob.rotation_euler[0]=pi/2
    ob.data.materials.append(mat)
    for p in ob.data.polygons:p.use_smooth=True
    if bev:bevel(ob,bev,3)
    return ob
def sphere(name,loc,scale,mat):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24,ring_count=12,location=Vector(loc)*MM)
    ob=link(bpy.context.object);ob.name=name;ob.scale=Vector(scale)*MM;ob.data.materials.append(mat)
    for p in ob.data.polygons:p.use_smooth=True
    return ob
def curve(name,points,r,mat,closed=False,res=3):
    cu=bpy.data.curves.new(name,'CURVE');cu.dimensions='3D';cu.resolution_u=16
    cu.bevel_depth=r*MM;cu.bevel_resolution=res
    sp=cu.splines.new('BEZIER');sp.bezier_points.add(len(points)-1)
    for b,p in zip(sp.bezier_points,points):b.co=Vector(p)*MM;b.handle_left_type='AUTO';b.handle_right_type='AUTO'
    sp.use_cyclic_u=closed
    ob=bpy.data.objects.new(name,cu);COL.objects.link(ob);cu.materials.append(mat)
    return ob
def sample(points,count=100,closed=False):
    out=[];n=len(points)
    for k in range(count):
        f=k/count*n if closed else k/(count-1)*(n-1)
        i=int(f);t=f-i
        def v(j):return Vector(points[j%n if closed else max(0,min(n-1,j))])
        a,b,c,d=v(i-1),v(i),v(i+1),v(i+2)
        out.append(.5*((2*b)+(-a+c)*t+(2*a-5*b+4*c-d)*t*t+(-a+3*b-3*c+d)*t*t*t))
    return out
def slab(name,outline,y0,y1,mat,bev=.2):
    n=len(outline);v=[(x,y0,z) for x,z in outline]+[(x,y1,z) for x,z in outline]
    f=[tuple(range(n-1,-1,-1)),tuple(range(n,n*2))]
    f += [(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
    o=mesh(name,v,f,mat,smooth=False)
    if bev:bevel(o,bev,3)
    return o
def ring(name,c,r1,r2,depth,mat,N=96):
    x,y,z=c;v=[]
    for yy in [y-depth/2,y+depth/2]:
        for r in [r1,r2]:
            v += [(x+r*cos(2*pi*i/N),yy,z+r*sin(2*pi*i/N)) for i in range(N)]
    f=[]
    for i in range(N):
        j=(i+1)%N
        f += [(i,j,N+j,N+i),(2*N+i,3*N+i,3*N+j,2*N+j),(i,2*N+i,2*N+j,j),(N+i,N+j,3*N+j,3*N+i)]
    return bevel(mesh(name,v,f,mat),.12,2)

# Cross sections carry two genuine longitudinal recessed ducts.
collection('shell')
ARM_POINTS=[(29,0,67),(37,0,56),(60,0,41),(84,0,25),(101,0,13),(105,0,7)]
PATH=sample(ARM_POINTS,113)
def armwidth(t):return (12.3-2.5*t)*(.70+.30*min(1,t/.18))
def armframe(t,side=1):
    f=t*(len(PATH)-1);i=min(int(f),len(PATH)-2);a=f-i
    p=PATH[i].lerp(PATH[i+1],a)
    d=(PATH[min(i+2,len(PATH)-1)]-PATH[max(i-1,0)]).normalized()
    n=Vector((-d.z,0,d.x))
    p.x*=side;d.x*=side;n.x*=side
    return p,d,n
profile=[(1,0,0),(.98,-.28,0),(.91,-.62,0),(.79,-.85,0),
         (.67,-.94,0),(.62,-.97,2),(.57,-.62,1),(.48,-.48,1),(.22,-.48,1),(.14,-.63,1),(.10,-1,2),
         (.025,-1.045,0),(-.06,-1.035,0),(-.13,-.99,2),(-.19,-.59,1),(-.30,-.45,1),(-.65,-.45,1),(-.73,-.62,1),(-.79,-.92,2),
         (-.86,-.83,0),(-.96,-.55,0),(-1,0,0),(-.96,.53,0),(-.8,.85,0),(-.42,.99,0),(0,1,0),(.42,.99,0),(.8,.85,0),(.96,.53,0)]
for side,label in [(-1,'Left'),(1,'Right')]:
    vs=[];fs=[];inds=[];uv=[]
    for i in range(113):
        t=i/112;p,d,n=armframe(t,side)
        end=max(.035,sqrt(max(0,1-((max(0,t-.90))/.105)**2)))
        width=armwidth(t)*end;dep=(7.7-1.5*t)*end
        fade=min(1,max(0,(t-.10)/.09),max(0,(.94-t)/.07))
        fade=fade*fade*(3-2*fade)
        for j,(q,yy,mi) in enumerate(profile):
            yf=yy
            if mi==1:yf=-.98+(yy+.98)*fade
            pos=p+n*q*width+Vector((0,yf*dep,0))
            vs.append(tuple(pos));uv.append((t,j/len(profile)))
    K=len(profile)
    for i in range(112):
        for j in range(K):
            fs.append((i*K+j,i*K+(j+1)%K,(i+1)*K+(j+1)%K,(i+1)*K+j))
            mi=profile[j][2]
            inds.append(mi if .17<i/112<.925 else 0)
    fs.extend([tuple(range(K-1,-1,-1)),tuple(112*K+j for j in range(K))]);inds.extend([0,0])
    mesh(label+' rounded hollow shoulder with recessed channels',vs,fs,[WHITE,DARK,BRUSHED],uv,inds)
    # Fine seam follows the rounded shoulder side.
    seam=[]
    for t in [i/30 for i in range(3,31)]:
        p,d,n=armframe(t,side);w=armwidth(t)
        seam.append(tuple(p+n*(w*.98)+Vector((0,.8,0))))
    curve(label+' shell molding seam',seam,.13,BRUSHED,res=2)

# White continuous hub rim and recessed cutaway window.
outer=[(0,89),(17,89),(24,85),(29,75),(35,62),(34,51),(23,50),(11,54),(0,56),(-11,54),(-23,50),(-34,51),(-35,62),(-29,75),(-24,85),(-17,89)]
inner=[(0,85),(16,85),(21,82),(23,74),(29,62),(28,56),(20,55),(10,59),(0,61),(-10,59),(-20,55),(-28,56),(-29,62),(-23,74),(-21,82),(-16,85)]
o=sample([(x,0,z) for x,z in outer],128,True);inn=sample([(x,0,z) for x,z in inner],128,True)
vs=[]
for yy,pts in [(-9,o),(-9,inn),(7,o),(7,inn)]:vs += [(p.x,yy,p.z) for p in pts]
fs=[]
for i in range(128):
    j=(i+1)%128;fs += [(i,j,128+j,128+i),(256+i,384+i,384+j,256+j),(i,256+i,256+j,j),(128+i,128+j,384+j,384+i)]
bevel(mesh('Glossy white central cutaway window frame',vs,fs,WHITE),.8,4)
slab('Silver cavity back wall',[(p.x,p.z) for p in inn],6,8,BRUSHED,.3)
curve('Polished edge around clear window',[(p.x,-9.35,p.z) for p in inn],.35,SILVER,True,2)
glass=slab('Transparent front cutaway window',[(p.x,p.z) for p in inn],-10.1,-9.8,GLASS,.1)
glass['purpose']='Thin clear cover; hide to inspect blower, battery and duct.'

curve('Thin polished silver hanging hook',[(0,0,89),(0,0,103),(3,0,110),(8,0,119),(9,0,126),(6,0,132),(-1,0,134),(-8,0,132),(-12,0,126),(-14,0,123)],1.05,SILVER,res=5)
cyl('Hook mounting ferrule',(0,0,89.3),2.2,.9,SILVER)
curve('Thin silver towel crossbar',[(-101,2.5,4),(-70,2.5,4),(0,2.5,4),(70,2.5,4),(101,2.5,4)],1.35,SILVER,res=4)
curve('White curved central loop support',[(-1,3,55),(-3.7,4,43),(-4.8,4,27),(-3.4,4,12),(0,4,9),(2.2,4,12),(1,4,28),(.8,3,43),(1,3,55)],1.35,WHITE,True,4)
cyl('Loop pivot collar',(0,3,54),2.5,4,SILVER,'Y')

collection('inside')
cube('Black control module left of hook',(-13,-1,89.5),(15,10,4.2),BLACK,1)
cube('Control module silver mounting foot',(-13,-1,87.2),(16.2,11.2,.8),BRUSHED,.6)
for i in range(6):cube('Control module pin %02d'%i,(-19+i*2.2,-6.6,87.4),(.6,1.5,.8),SILVER,.12)
cyl('Teal cylindrical battery',(-15,1,74),5.1,23,TEAL,'X',96,.3)
cyl('Battery silver left end cap',(-26.7,1,74),5.05,1.0,SILVER,'X',96,.12)
cyl('Battery terminal inset',(-27.25,1,74),3.4,.2,BRUSHED,'X',64,.08)
cyl('Battery terminal contact',(-27.4,1,74),1.9,.3,SILVER,'X',64,.08)
cyl('Battery end ring',(-3.6,1,74),5.2,.7,SILVER,'X',96,.1)
# Battery mount saddle and black curved wiring are visible behind the clear cover.
cube('Battery support saddle',(-15,4,67.5),(21,5,2),DARK,.6)
curve('Internal battery wiring',[(-4,3,74),(-1,4,81),(6,4,84),(17,3,83)],.45,BLACK)
cyl('Centrifugal blower rear housing',(8,1,73),13.2,7.8,BLACK,'Y',112,.45)
ring('Centrifugal blower front volute',(8,-4,73),13.3,8.6,3.0,BLACK,128)
ring('Blower intake rim',(8,-6.0,73),9,7.9,1.1,DARK,96)
cyl('Blower dark interior rotor',(8,-5.7,73),8,.7,RUBBER,'Y',96,.1)
for k in range(36):
    a=k*2*pi/36
    vs=[]
    for r,aa,yy in [(4.7,a-.08,-6.7),(7.7,a+.09,-6.7),(7.7,a+.14,-6.3),(4.7,a-.01,-6.3)]:vs.append((8+r*cos(aa),yy,73+r*sin(aa)))
    mesh('Blower radial blade %02d'%k,vs,[(0,1,2,3)],DARK,smooth=False)
cyl('Blower round intake hub',(8,-6.8,73),4.8,1.5,BLACK,'Y',96,.3)
cube('Blower tangential outlet',(-1,-.5,62),(12,8,5),BLACK,1,rot=(0,-.32,0))
for x,z in [(-2,83),(19,80),(15,62)]:
    cyl('Blower fixing screw',(x,-6.1,z),.75,.5,SILVER,'Y',24,.07)
    cube('Screw head slot',(x,-6.4,z),(.8,.08,.12),BLACK,.02)

collection('air')
cube('Black upper air intake grille',(13,0,89.2),(17,11,.9),RUBBER,3.3)
for i in range(9):
    # Narrow light metal ribs leave black longitudinal intake slots.
    curve('Intake grille rib %02d'%i,[(5.8+i*1.8,-4.2,89.8),(5.8+i*1.8,4.2,89.8)],.24,BRUSHED,res=2)

def arrow(name,center,d,n,length,width,mat=BLUE):
    # Arrow is a flat graphic on a recess floor.
    sh=[(-.5,-.20),(.12,-.20),(.12,-.5),(.5,0),(.12,.5),(.12,.20),(-.5,.20)]
    pts=[tuple(Vector(center)+d*(a*length)+n*(b*width)) for a,b in sh]
    return mesh(name,pts,[tuple(range(7))],mat,smooth=False)
for label,pts,head,direction in [
    ('Left',[(3,-8.8,62),(-2,-8.8,59),(-10,-8.8,58),(-19,-8.8,55)],(-21,-8.8,54),(-.9,0,-.3)),
    ('Right',[(23,-8.8,79),(22,-8.8,70),(26,-8.8,63),(30,-8.8,58)],(31,-8.8,56),(.48,0,-.88))]:
    curve(label+' curved cutaway airflow path',pts,.42,BLUE,res=2)
    direction=Vector(direction).normalized();up=Vector((-direction.z,0,direction.x))
    arrow(label+' cutaway airflow arrowhead',head,direction,up,4.6,3.2)
for side,label in [(-1,'Left'),(1,'Right')]:
    for ch,q in [('lower',-.46),('upper',.36)]:
        for k,t in enumerate([.25,.43,.62,.79]):
            if side==1 and ch=='upper' and t<.74:continue
            p,d,n=armframe(t,side);w=armwidth(t);dep=7.7-1.5*t
            arrow(label+' '+ch+' duct airflow arrow '+str(k),p+n*(q*w)+Vector((0,-.49*dep-.1,0)),d,n,5.2,2.4)
    pts=[];emit=[]
    for k in range(49):
        t=.17+k/48*.72;p,d,n=armframe(t,side);w=armwidth(t)
        pts.append(tuple(p-n*(w*.9)+Vector((0,1.2,-.4))))
        emit.append(tuple(p-n*(w*.94)+Vector((0,1.1,-.65))))
    curve(label+' underside LED recessed silver track',pts,.85,BRUSHED,res=3)
    curve(label+' long violet-blue UV light strip',emit,.48,UV,res=3)
    for k in range(30):
        t=.19+k/29*.68;p,d,n=armframe(t,side);w=armwidth(t)
        loc=p-n*w+Vector((0,-1.5,-.15))
        o=cube(label+' underside vent slot %02d'%k,loc,(1.0,4,.4),RUBBER,.18)
        o.rotation_euler[1]=math.atan2(-d.z,d.x)
    # A real small round environmental sensor at the left tip only.
    if side==-1:
        p,d,n=armframe(.905,side)
        c=p+n*(-2)+Vector((0,-6.6,0))
        cyl('Round humidity and temperature sensor',c,1.65,.45,BRUSHED,'Y',48,.1)
        cyl('Environmental sensor perforated face',c+Vector((0,-.27,0)),1.2,.15,DARK,'Y',48,.04)
        for j in range(5):
            a=j*2*pi/5
            cyl('Sensor aperture '+str(j),c+Vector((.65*cos(a),-.38,.65*sin(a))),.18,.10,RUBBER,'Y',12,.01)

# Sloped right shoulder status panel with a texture display and three LEDs.
p,d,n=armframe(.40,1)
pc=p+n*3.8+Vector((0,-7.8,0));L=55;W=5.8
def panel_shape(L,W,r=2):
    out=[]
    for cx,cy,start in [(L/2-r,W/2-r,0),(-L/2+r,W/2-r,pi/2),(-L/2+r,-W/2+r,pi),(L/2-r,-W/2+r,3*pi/2)]:
        for k in range(9):
            a=start+k/8*pi/2;out.append((cx+r*cos(a),cy+r*sin(a)))
    return out
outline=panel_shape(L,W,2)
vs=[tuple(pc+d*x+n*z) for x,z in outline]
panelmat=material('Black indicator panel with PBR display texture',(.02,.02,.02),rough=.24,coat=.3)
pn=panelmat.node_tree.nodes.new('ShaderNodeTexImage');pn.image=bpy.data.images.load(str(TEX/'Indicator_BaseColor.png'))
panelmat.node_tree.links.new(pn.outputs['Color'],panelmat.node_tree.nodes.get('Principled BSDF').inputs['Base Color'])
uv=[(x/L+.5,z/W+.5) for x,z in outline]
mesh('Right arm black LED indicator and display strip',vs,[tuple(range(len(vs)))],panelmat,uv,smooth=False)
curve('Indicator panel subtle edge',vs,.14,BRUSHED,True,2)
for k,m in enumerate([RED,AMBER,GREEN]):
    c=pc+d*(-23+k*5.4)+n*.25+Vector((0,-.24,0))
    # Two rounded ends plus central bar form a tiny rectangular indicator lens.
    verts=[tuple(c+d*a+n*b) for a,b in [(-1.25,-.60),(1.25,-.60),(1.25,.60),(-1.25,.60)]]
    mesh(['Red','Amber','Green'][k]+' status indicator lens',verts,[(0,1,2,3)],m,smooth=False)

# Central underside speaker-style oval mesh grille.
sphere('Center underside speaker grille',(0,0,55.1),(12,5.1,.75),RUBBER)
for i in range(-17,18):
    x=i*.63;maxy=4.8*sqrt(max(0,1-(x/11.6)**2))
    if maxy>.1:curve('Speaker grille longitudinal strand '+str(i),[(x,-maxy,54.5),(x,maxy,54.5)],.105,BRUSHED,res=1)
for i in range(-6,7):
    y=i*.7;maxx=11.7*sqrt(max(0,1-(y/4.9)**2))
    curve('Speaker grille transverse strand '+str(i),[(-maxx,y,54.45),(maxx,y,54.45)],.10,BRUSHED,res=1)

# White terry towel: one continuous front-over-bar-back drape with soft folds.
collection('cloth')
cloth=material('White looped terry • textured PBR with UV emission',(.9,.9,.9),rough=.91)
p=cloth.node_tree.nodes.get('Principled BSDF');p.inputs['Sheen Weight'].default_value=.28
p.inputs['Sheen Roughness'].default_value=.7
nodes=cloth.node_tree.nodes;links=cloth.node_tree.links
uvnode=nodes.new('ShaderNodeTexCoord');mapping=nodes.new('ShaderNodeMapping');mapping.inputs['Scale'].default_value=(7,15,1)
links.new(uvnode.outputs['UV'],mapping.inputs['Vector'])
for fname,socket,space in [('Towel_BaseColor.png','Base Color','sRGB'),('Terry_Roughness.png','Roughness','Non-Color')]:
    tex=nodes.new('ShaderNodeTexImage');tex.image=bpy.data.images.load(str(TEX/fname));tex.image.colorspace_settings.name=space
    links.new(uvnode.outputs['UV'] if socket=='Base Color' else mapping.outputs['Vector'],tex.inputs['Vector']);links.new(tex.outputs['Color'],p.inputs[socket])
nt=nodes.new('ShaderNodeTexImage');nt.image=bpy.data.images.load(str(TEX/'Terry_Normal.png'));nt.image.colorspace_settings.name='Non-Color'
links.new(mapping.outputs['Vector'],nt.inputs['Vector']);normal=nodes.new('ShaderNodeNormalMap');normal.inputs['Strength'].default_value=1.15
links.new(nt.outputs['Color'],normal.inputs['Color']);links.new(normal.outputs['Normal'],p.inputs['Normal'])
et=nodes.new('ShaderNodeTexImage');et.image=bpy.data.images.load(str(TEX/'Towel_UV_Emission.png'))
links.new(et.outputs['Color'],p.inputs['Emission Color']);p.inputs['Emission Strength'].default_value=.32

# v=0 front hem, v=.49 top fold, v=1 back hem.
def clothpoint(u,v):
    x=(u-.5)*151
    if v<.465:
        a=v/.465;z=-142+146*a;y=-4.8
        side=-1
    elif v<.535:
        a=(v-.465)/.07*pi;z=4+4.8*sin(a);y=-4.8*cos(a);side=-cos(a)
    else:
        a=(v-.535)/.465;z=4-133*a;y=4.8;side=1
    hang=max(0,abs(v-.5)*2)
    fold=(3.7*sin(u*7*pi+.25)+1.5*sin(u*17*pi+1.2)+.65*sin(u*39*pi+.5))
    fold+=-4.2*math.exp(-((u-.13)/.038)**2)+2.2*math.exp(-((u-.08)/.025)**2)
    fold*=.4+.6*hang
    y += fold
    z += (.7*sin(u*19*pi)+1.0*cos(u*8*pi))*hang**3
    # The thick turned edges curl outward as in the reference towel.
    edge=math.exp(-((u-.025)/.035)**2)+math.exp(-((u-.975)/.035)**2)
    y += side*edge*1.5
    x += .9*sin(v*11*pi+.5)*sin(pi*u)**5*hang
    return Vector((x,y,z))
NU,NV=185,257
vs=[];uv=[];fs=[]
for j in range(NV):
    v=j/(NV-1)
    for i in range(NU):
        u=i/(NU-1);vs.append(tuple(clothpoint(u,v)));uv.append((u,v))
for j in range(NV-1):
    for i in range(NU-1):
        a=j*NU+i;fs.append((a,a+1,a+1+NU,a+NU))
towel=mesh('Thick white towel • continuous folded quad surface',vs,fs,cloth,uv)
solid=towel.modifiers.new('Real terry cloth thickness 2.4 mm','SOLIDIFY');solid.thickness=2.4*MM;solid.offset=0
sub=towel.modifiers.new('Soft textile folds','SUBSURF');sub.levels=1;sub.render_levels=1
towel['construction']='Continuous UV-unwrapped front-over-crossbar-back drape; predominantly quad topology.'
hem=material('White cotton bound hem',(.81,.83,.82),rough=.96)
for u,label in [(0,'Left'),(1,'Right')]:
    curve(label+' thick terry edge binding',[tuple(clothpoint(u,j/100)) for j in range(101)],1.2,hem,res=3)
for v,label in [(.0,'Front'),(1,'Back')]:
    curve(label+' towel hem binding',[tuple(clothpoint(i/100,v)) for i in range(101)],1.1,hem,res=3)
    # Two fine parallel stitched hem seams, following the cloth deformation.
    vv=.022 if v==0 else .978
    pts=[]
    for i in range(101):
        po=clothpoint(i/100,vv);po.y += -.9 if v==0 else .9;pts.append(tuple(po))
    curve(label+' cotton stitched hem seam',pts,.18,hem,res=2)

# Geometric pile gives real fibre silhouette and close-up parallax over normal maps.
pilemat=material('Cotton pile fibres',(.86,.875,.86),rough=.95)
pilemat.node_tree.nodes.get('Principled BSDF').inputs['Sheen Weight'].default_value=.32
pv=[];pf=[]
for k in range(12500):
    u=random.uniform(.002,.998);v=random.uniform(.006,.994)
    if .46<v<.54 and random.random()<.6:continue
    # Keep the emissive diagram legible while retaining a real looped surface.
    side=-1 if v<.5 else 1
    po=clothpoint(u,v);po.y+=side*.76
    radius=random.uniform(.07,.13);height=random.uniform(.20,.44);width=random.uniform(.14,.31)
    theta=random.uniform(-.65,.65)
    along=Vector((cos(theta),0,sin(theta)))
    binorm=Vector((-sin(theta),0,cos(theta)))
    start=len(pv);K=7;R=3
    for j in range(K):
        a=j/(K-1)*pi
        c=po+along*(width*cos(a))+Vector((0,side*height*sin(a),0))
        tangent=along*(-width*sin(a))+Vector((0,side*height*cos(a),0));tangent.normalize()
        radial=tangent.cross(binorm).normalized()
        for s in range(R):
            aa=2*pi*s/R
            pv.append(tuple(c+radial*(radius*.28*cos(aa))+binorm*(radius*.28*sin(aa))))
    for j in range(K-1):
        for s in range(R):
            a=start+j*R+s;b=start+j*R+(s+1)%R
            pf.append((a,b,b+R,a+R))
mesh('Individual raised cotton terry loops',pv,pf,pilemat)

# Detachable rounded tray, with a real recessed cradle and two gold pins.
collection('base')
baseorigin=Vector((66,14,92))
def roundedrect(w,h,r,n=12):
    out=[]
    for cx,cy,start in [(w/2-r,h/2-r,0),(-w/2+r,h/2-r,pi/2),(-w/2+r,-h/2+r,pi),(w/2-r,-h/2+r,3*pi/2)]:
        for k in range(n):
            a=start+k/(n-1)*pi/2;out.append((cx+r*cos(a),cy+r*sin(a)))
    return out
outer=roundedrect(43,31,8);inside=roundedrect(30,20,5)
NN=len(outer);vv=[]
for zz,pts in [(-5.4,outer),(4.5,outer),(4.5,inside),(-1.4,inside)]:
    vv += [tuple(baseorigin+Vector((x,y,zz))) for x,y in pts]
ff=[];ii=[]
for k in range(NN):
    j=(k+1)%NN
    ff += [(k,j,NN+j,NN+k),(NN+k,NN+j,2*NN+j,2*NN+k),(2*NN+k,2*NN+j,3*NN+j,3*NN+k)]
    ii += [0,0,1]
ff += [tuple(range(NN-1,-1,-1)),tuple(3*NN+k for k in range(NN))];ii += [0,1]
bevel(mesh('Detachable white charging tray with recessed cradle',vv,ff,[WHITE,material('Charging cradle pale grey inset',(.69,.74,.76),rough=.35)],indices=ii),.75,4)
curve('Charging tray silver lower seam',[tuple(baseorigin+Vector((x,y,-3.8))) for x,y in outer],.13,BRUSHED,True,2)
for x in [-4.0,4.0]:
    cyl('Gold charging pogo contact',baseorigin+Vector((x,0,.4)),.72,4.0,GOLD,'Z',32,.12)
    cyl('Charging contact foot',baseorigin+Vector((x,0,-1.1)),1.1,.5,BRUSHED,'Z',32,.1)
# USB-C opening is placed on the visible front side, with a metal shell and tongue.
port=baseorigin+Vector((-7,-15.5,-.7))
cube('USB-C silver receptacle surround',port,(7.8,.7,3.2),SILVER,1.3)
cube('USB-C black recessed opening',port+Vector((0,-.42,0)),(6.8,.3,2.3),RUBBER,1.0)
cube('USB-C inner tongue',port+Vector((0,-.65,0)),(4.7,.2,.42),DARK,.15)
for k in range(10):cube('USB-C contact %02d'%k,port+Vector((-2.1+k*.46,-.78,0)),(.2,.10,.22),GOLD,.03)

# UV fill light on the real cloth, separate from the illustrated emissive map.
collection('studio')
def light(name,loc,target,power,size,color=(1,1,1),shape='DISK',size_y=None):
    data=bpy.data.lights.new(name,'AREA');data.energy=power;data.shape=shape;data.size=size*MM;data.color=color
    if size_y and shape=='RECTANGLE':data.size_y=size_y*MM
    ob=bpy.data.objects.new(name,data);COL.objects.link(ob);ob.location=Vector(loc)*MM
    ob.rotation_euler=(Vector(target)*MM-ob.location).to_track_quat('-Z','Y').to_euler()
    return ob
light('Large soft studio key',(-200,-210,300),(0,0,20),2.0,230,(1,.97,.93))
light('Cool broad studio fill',(240,-100,150),(0,0,25),1.2,200,(.84,.93,1))
light('Upper rim softbox',(-20,110,230),(0,0,40),2.4,190,(1,1,1),'RECTANGLE',90)
light('Silver reflection strip',(-180,10,80),(0,0,60),.7,65,(.88,.94,1),'RECTANGLE',200)
light('UV blue violet towel wash',(0,-28,21),(0,-6,-65),.0025,130,(.26,.30,1),'RECTANGLE',7)
floor=material('Neutral studio floor',(.77,.79,.80),rough=.8)
cube('Studio ground',(0,0,-146),(2000,2000,2),floor,0)
scene=bpy.context.scene
scene.world.color=(.22,.22,.22)
world=scene.world;world.use_nodes=True
world.node_tree.nodes.get('Background').inputs['Color'].default_value=(.65,.70,.74,1)
world.node_tree.nodes.get('Background').inputs['Strength'].default_value=.25
def camera(name,loc,target,ortho):
    data=bpy.data.cameras.new(name);data.type='ORTHO';data.ortho_scale=ortho*MM;data.lens=65;data.clip_start=.001;data.clip_end=20
    ob=bpy.data.objects.new(name,data);COL.objects.link(ob);ob.location=Vector(loc)*MM
    ob.rotation_euler=(Vector(target)*MM-ob.location).to_track_quat('-Z','Y').to_euler()
    return ob
hero=camera('Camera • full reference perspective',(210,-580,270),(4,0,-8),325)
detail=camera('Camera • cutaway and arms',(105,-500,190),(0,0,65),185)
rear=camera('Camera • rear and underside',(-200,580,170),(0,0,20),300)
under=camera('Camera • underside details',(50,-450,-170),(0,0,54),270)
scene.camera=hero
scene.render.engine='CYCLES';scene.cycles.samples=96;scene.cycles.use_denoising=False
scene.cycles.max_bounces=8;scene.cycles.transmission_bounces=8
scene.render.resolution_x=1500;scene.render.resolution_y=1500;scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG';scene.render.film_transparent=False
scene.view_settings.view_transform='AgX'
scene.render.threads_mode='FIXED';scene.render.threads=12
scene.unit_settings.system='METRIC';scene.unit_settings.length_unit='MILLIMETERS'
# A small, restrained glare catches the two violet-blue LED strips.
scene.use_nodes=True
nt=scene.node_tree;nt.nodes.clear()
rl=nt.nodes.new('CompositorNodeRLayers');gl=nt.nodes.new('CompositorNodeGlare');gl.glare_type='FOG_GLOW';gl.quality='HIGH';gl.threshold=2;gl.size=6
out=nt.nodes.new('CompositorNodeComposite');nt.links.new(rl.outputs['Image'],gl.inputs['Image']);nt.links.new(gl.outputs['Image'],out.inputs['Image'])

# Store explicit reference and scale information, without embedding a false CAD claim.
scene['reference_image']='image(20261025-145918).png'
scene['model_notes']='Visual reconstruction of the supplied multi-view concept drawing. Visible shapes follow the reference; hidden surfaces are inferred. No manufacturing validation.'
scene['nominal_width_mm']=220
scene['PBR']='Base color, metallic, roughness, tangent normal, clear transmission and UV emission. Maps packed in .blend and embedded in .glb.'

# Product-only export; neutral studio remains in the editable Blender scene.
for ob in bpy.context.selected_objects:ob.select_set(False)
for key,c in collections.items():
    if key=='studio':continue
    for ob in c.objects:ob.select_set(True)
if bpy.context.selected_objects:bpy.context.view_layer.objects.active=bpy.context.selected_objects[0]
for im in bpy.data.images:
    if im.source=='FILE':im.pack()
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'Smart_Drying_Hanger.blend'))
bpy.ops.export_scene.gltf(filepath=str(ROOT/'Smart_Drying_Hanger.glb'),export_format='GLB',use_selection=True,export_apply=True,export_yup=True,export_cameras=False,export_lights=False,export_texcoords=True,export_normals=True,export_materials='EXPORT',export_extras=True)

stats={'objects':sum(len(c.objects) for k,c in collections.items() if k!='studio'),'mesh_vertices':sum(len(o.data.vertices) for o in bpy.data.objects if o.type=='MESH' and o.name!='Studio ground'),'nominal_width_mm':220,'materials':len(bpy.data.materials),'maps':[x.name for x in TEX.glob('*.png')]}
(ROOT/'model_statistics.json').write_text(json.dumps(stats,indent=2))
print('MODEL_COMPLETE',json.dumps(stats),flush=True)
mode=os.environ.get('HANGER_RENDER','draft')
if mode!='none':
    if mode=='draft':scene.render.resolution_percentage=55;scene.cycles.samples=16
    scene.camera=hero;scene.render.filepath=str(ROOT/'renders'/('Preview_Draft.png' if mode=='draft' else 'Smart_Drying_Hanger_Preview.png'))
    bpy.ops.render.render(write_still=True)
    if mode=='final':
        scene.camera=detail;scene.render.resolution_x=1800;scene.render.resolution_y=1200;scene.cycles.samples=56
        scene.render.filepath=str(ROOT/'renders'/'Cutaway_Detail.png');bpy.ops.render.render(write_still=True)
print('DONE',flush=True)
