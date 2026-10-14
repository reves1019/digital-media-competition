"""Blender snow-mountain group sculpture, reconstructed from supplied video views.

Actual geometry, no image planes. Hidden surfaces are inferred, not a scan.
Commands: blender -b --factory-startup --python build_sculpture.py -- --preview
         blender -b --factory-startup --python build_sculpture.py -- --views
         blender -b --factory-startup --python build_sculpture.py -- --model-only
"""
import bpy, math, random, json, sys
from pathlib import Path
from mathutils import Vector, noise

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
for name in ('assets', 'renders'):
    (ROOT/name).mkdir(exist_ok=True)
random.seed(19350612)
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.samples = 40
scene.cycles.use_denoising = True
scene.cycles.max_bounces = 6
try:
    p = bpy.context.preferences.addons['cycles'].preferences
    p.compute_device_type = 'OPTIX'; p.get_devices()
    for dev in p.devices: dev.use = dev.type == 'OPTIX'
    scene.cycles.device = 'GPU'
except Exception as e: print('GPU_FALLBACK', str(e))
scene.render.resolution_x = 1600
scene.render.resolution_y = 1000
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.render.fps = 24
scene.frame_start = 1; scene.frame_end = 240
scene.view_settings.view_transform = 'AgX'
scene.view_settings.look = 'AgX - Medium High Contrast'
scene.view_settings.exposure = .15
scene.render.film_transparent = False
WHITE_FILM = '--grey' not in sys.argv

def collection(name):
    col = bpy.data.collections.new(name); scene.collection.children.link(col)
    return col
sculpt = collection('01 | SCULPTURE - export this collection')
studio = collection('02 | Studio - not part of export')
rig = collection('03 | Camera path')
root = bpy.data.objects.new('SCULPTURE_ROOT', None); sculpt.objects.link(root)

def material(name, color, rough=.94):
    mat = bpy.data.materials.new(name); mat.use_nodes = True
    mat.diffuse_color = (*color,1)
    n=mat.node_tree.nodes; l=mat.node_tree.links
    bsdf=n.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value=(*color,1)
    bsdf.inputs['Roughness'].default_value=rough
    bsdf.inputs['Specular IOR Level'].default_value=.24
    tex=n.new('ShaderNodeTexNoise'); tex.inputs['Scale'].default_value=17
    tex.inputs['Detail'].default_value=3.6; tex.inputs['Roughness'].default_value=.72
    bump=n.new('ShaderNodeBump'); bump.inputs['Strength'].default_value=.20
    bump.inputs['Distance'].default_value=.036
    l.new(tex.outputs['Fac'],bump.inputs['Height']);l.new(bump.outputs['Normal'],bsdf.inputs['Normal'])
    return mat

if WHITE_FILM:
    clay=material('White film | continuous matte plaster',(.66,.655,.62),.965)
    light_clay=material('White film | rubbed high planes',(.76,.75,.70),.95)
    deep_clay=material('White film | fracture shadow',(.48,.49,.49),.975)
else:
    clay=material('Grey plaster | continuous sculptural surface',(.31,.31,.30))
    light_clay=material('Grey plaster | rubbed high planes',(.38,.375,.36))
    deep_clay=material('Grey plaster | recess',(.24,.25,.26))
floor_mat=material('Stage charcoal',(.022,.026,.033),.99)
palette=[clay,light_clay,deep_clay]

def mesh_obj(name,verts,faces,mats=palette,smooth=True):
    me=bpy.data.meshes.new(name);me.from_pydata(verts,[],faces);me.update()
    ob=bpy.data.objects.new(name,me);sculpt.objects.link(ob);ob.parent=root
    for mat in mats:me.materials.append(mat)
    for f in me.polygons: f.use_smooth=smooth
    return ob

def ns(x,y,z=0,scale=1):
    return noise.noise_vector(Vector((x*scale,y*scale,z*scale)),noise_basis='PERLIN_ORIGINAL').x

def width(x):
    t=max(0,min(1,(x+10)/20))
    # Broad sloping upper face, left knife-edge, right high beak.
    return .12 + 2.65*math.sin(math.pi*t)**.65

def center_y(x): return .22*math.sin(x*.38)

def surface(x,y):
    # Large smooth snow-plane is retained between the broken rock bands.
    return .23+.40*(x+10)+.15*math.sin(x*.6)+.11*y + .085*ns(x,y,2,.6)+.018*ns(x,y,8,4)

def edge_x(t,y):
    # A long tip at the high right, fractured shorter edge toward the front.
    return -10+20*t+.12*math.sin(y*4+t*11)*math.sin(math.pi*t)

# Closed main slab: top, front strata, bottom and back surfaces are one volume.
# Different sample rates keep long waves and fine hand-cut imperfections apart.
nx,ny=190,54
verts=[];faces=[]
for i in range(nx+1):
    t=i/nx; x=-10+20*t; w=width(x); cy=center_y(x)
    for j in range(ny+1):
        q=-1+2*j/ny
        y=cy+w*q
        xx=edge_x(t,y)
        edge=abs(q)**7
        z=surface(xx,y)+edge*(.17*ns(xx,y,1,2)+.05*ns(xx,y,3,9))
        verts.append((xx,y,z))
for i in range(nx):
    for j in range(ny):
        a=i*(ny+1)+j;b=a+ny+1
        faces.extend([(a,b,b+1),(a,b+1,a+1)])

def thickness(t):return .12+2.9*math.sin(math.pi*t)**.82

boundary=[i*(ny+1) for i in range(nx+1)]
boundary += [nx*(ny+1)+j for j in range(1,ny+1)]
boundary += [i*(ny+1)+ny for i in range(nx-1,-1,-1)]
boundary += [j for j in range(ny-1,0,-1)]
n=len(boundary);last_ring=boundary
for row in range(1,19):
    a=row/18;ring=[]
    for vi in boundary:
        x,y,z=verts[vi];t=(x+10)/20
        th=thickness(max(0,min(1,t)))
        ripple=.13*ns(x,y,a*5,2)+.06*ns(x,y,a*5,6)
        # Overhangs and deep linear breaks on the audience-facing surface.
        layer=.14*math.sin(a*29+x*.28)+.08*math.sin(a*61+x*.5)
        yy=y*(1-.28*a)+math.copysign((layer+ripple)*math.sin(math.pi*t),y)
        zz=max(.06,z-th*a+ripple*.25)
        ring.append(len(verts));verts.append((x,yy,zz))
    for k in range(n):
        kk=(k+1)%n;faces.append((last_ring[k],ring[k],ring[kk],last_ring[kk]))
    last_ring=ring
faces.append(tuple(reversed(last_ring)))
body=mesh_obj('Rising slab | closed sloping snow and rock mass',verts,faces)

# Irregular hand-modelled laminated shards. Radial rings give a broad flat face,
# broken edges and a chipped thickness, rather than uniform polygon spikes.
rv=[];rf=[];rm=[]
slope=Vector((1,0,.40)).normalized();side=Vector((0,1,0));normal=slope.cross(side)

def shard(c,L,W,H,seed,angle=0):
    rng=random.Random(seed);c=Vector(c)
    u=(slope*math.cos(angle)+side*math.sin(angle)).normalized()
    v=(-slope*math.sin(angle)+side*math.cos(angle)).normalized()
    nn=u.cross(v)
    N=18
    outline=[1+rng.uniform(-.20,.16) for _ in range(N)]
    offset=len(rv)
    rv.append(tuple(c+nn*H*.3))
    for r,hh in [(.32,.27),(.72,.20),(1,.02),(.90,-.6)]:
        for k in range(N):
            a=2*math.pi*k/N
            jitter=(rng.uniform(-.10,.10) if r>.5 else rng.uniform(-.07,.07))
            p=c+u*(math.cos(a)*L*r*outline[k])+v*(math.sin(a)*W*r*outline[k])+nn*H*(hh+jitter)
            p+=nn*(.026*ns(p.x,p.y,p.z,7))
            rv.append(tuple(p))
    for k in range(N):rf.append((offset,offset+1+k,offset+1+(k+1)%N));rm.append(0)
    for r in range(3):
        for k in range(N):
            a=offset+1+r*N+k;b=offset+1+r*N+(k+1)%N
            cc=offset+1+(r+1)*N+(k+1)%N;d=offset+1+(r+1)*N+k
            rf.extend([(a,d,cc),(a,cc,b)]);rm.extend([2 if r==2 else 0]*2)
    rf.append(tuple(offset+1+3*N+k for k in reversed(range(N))));rm.append(2)

# Front cliff: three long angled strata with irregular lengths and overlaps.
for row in range(4):
    for k in range(28):
        x=-8.9+k*.64+random.uniform(-.24,.24)
        t=(x+10)/20;w=width(x)
        if w<.3:continue
        y=center_y(x)-w*(1-.16*row)
        z=surface(x,y)-thickness(t)*row*.27+random.uniform(-.06,.07)
        shard((x,y,z),random.uniform(.45,1.50),random.uniform(.18,.52),random.uniform(.14,.38),2000+row*100+k,random.uniform(-.18,.15))
# Rear broken crest and lateral boundary.
for k in range(56):
    x=random.uniform(-8.4,9.2);y=center_y(x)+width(x)*random.uniform(.64,1.03)
    shard((x,y,surface(x,y)+.04),random.uniform(.25,.9),random.uniform(.14,.44),random.uniform(.10,.32),4000+k,random.uniform(-.4,.4))
# Top face keeps a quiet diagonal centre; chips cluster near edges.
for k in range(150):
    x=random.uniform(-9.6,9.6);q=random.choice([-1,1])*random.uniform(.6,1)
    if k%5==0:q=random.uniform(-.55,.55)
    y=center_y(x)+width(x)*q
    shard((x,y,surface(x,y)+random.uniform(.015,.075)),random.uniform(.07,.43),random.uniform(.04,.20),random.uniform(.06,.17),6000+k,random.uniform(-.5,.4))
lamina=mesh_obj('Broken strata | 318 broad chipped clay shelves',rv,rf,smooth=True)
for p,mi in zip(lamina.data.polygons,rm):p.material_index=mi

# Narrow recessed seams break up the broad front plane at close range.  They
# are shallow, irregular clay cuts rather than black texture lines: each seam
# follows the local slope, has a small V-like depth, and stops before reaching
# the silhouette.  This gives the white-film render the same hand-cut
# geological rhythm as the reference sculpture without adding a dense noise
# displacement over the whole slab.
cv=[];cf=[]
def fracture_seam(seed,x0,length,side_sign=-1):
    rng=random.Random(seed)
    x1=min(9.25,x0+length)
    y0=center_y(x0)+side_sign*width(x0)*rng.uniform(.72,.92)
    y1=center_y(x1)+side_sign*width(x1)*rng.uniform(.72,.92)
    # A small kink in each seam prevents a repeated procedural stripe.
    xm=(x0+x1)*.5; ym=(y0+y1)*.5 + rng.uniform(-.24,.24)
    points=[]
    for xx,yy in ((x0,y0),(xm,ym),(x1,y1)):
        zz=surface(xx,yy)+.008
        points.append(Vector((xx,yy,zz)))
    width_px=rng.uniform(.025,.075); depth=rng.uniform(.045,.105)
    for a,b in zip(points[:-1],points[1:]):
        tangent=(b-a); tangent.z=0
        if tangent.length<1e-5: continue
        tangent.normalize()
        across=Vector((-tangent.y,tangent.x,0))*width_px
        # Offset toward the surface normal only a little; the dark recess is
        # kept flush enough to avoid hovering over the rock.
        s=len(cv)
        top=[a-across,a+across,b+across,b-across]
        bot=[p+Vector((0,0,-depth)) for p in top]
        cv.extend(tuple(p) for p in top+bot)
        cf.extend([(s,s+1,s+2,s+3),(s+7,s+6,s+5,s+4),
                   (s,s+4,s+5,s+1),(s+1,s+5,s+6,s+2),
                   (s+2,s+6,s+7,s+3),(s+3,s+7,s+4,s)])

for k in range(34):
    x0=random.uniform(-8.6,7.55)
    fracture_seam(7100+k,x0,random.uniform(.55,1.85),-1 if k%3 else 1)
# Short branches make a few junctions read as broken strata rather than
# perfectly parallel seams.  They use the same low polygon budget.
for k in range(12):
    x0=random.uniform(-7.4,7.2)
    fracture_seam(7200+k,x0,random.uniform(.32,.82),-1 if k%2 else 1)
fractures=mesh_obj('Recessed hand-cut fracture seams | 46',cv,cf,[deep_clay],smooth=False)

# Supporting root is a broken buttress under the overhanging high-right end.
def rock_root(name,c,scale,seed):
    rng=random.Random(seed)
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=4,radius=1,location=c)
    ob=bpy.context.object;ob.name=name
    for co in list(ob.users_collection):co.objects.unlink(ob)
    sculpt.objects.link(ob);ob.parent=root;ob.data.materials.append(clay)
    for vertex in ob.data.vertices:
        p=vertex.co
        dis=.12*ns(p.x,p.y,p.z,3)+.055*ns(p.x,p.y,p.z,9)
        vertex.co=(p*(1+dis));vertex.co.x*=scale[0];vertex.co.y*=scale[1];vertex.co.z*=scale[2]
        vertex.co.z=max(-c[2]+.04,vertex.co.z)
    for f in ob.data.polygons:f.use_smooth=True
    return ob
rock_root('Right buttress | cut root', (5.05,.15,2.3),(2.2,1.9,2.8),92)
rock_root('Front broken foot', (4.3,-1.15,.95),(1.5,1.25,1.2),93)
rock_root('Back support', (2.1,1.10,1.25),(1.7,1.6,1.4),94)

# Rock ledges on the visible support, aligned with the same geological gesture.
sv0=len(rv);sf0=len(rf)
for k in range(48):
    x=random.uniform(3.1,6.6);z=random.uniform(.35,4.1)
    y=-1.25-random.uniform(.0,.55)
    shard((x,y,z),random.uniform(.30,1.1),random.uniform(.18,.52),random.uniform(.12,.35),9000+k,random.uniform(-.55,.35))
support=mesh_obj('Broken foot strata',rv[sv0:],[tuple(i-sv0 for i in f) for f in rf[sf0:]],smooth=True)

# Build expressive sculpted figures as part of this one monument, not a separate
# marching parade. The module is kept separate for editable pose iteration.
figure_objects=[]
if '--blockout' not in sys.argv:
    from sculpted_figures import build_figures
    figure_objects=build_figures(root,sculpt,clay,surface)

# World and studio are excluded from the GLB.
world=bpy.data.worlds.new('Charcoal gallery');world.use_nodes=True;scene.world=world
world.node_tree.nodes['Background'].inputs[0].default_value=(.06,.065,.085,1)
world.node_tree.nodes['Background'].inputs[1].default_value=.32
bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,-.045))
floor=bpy.context.object;floor.name='Shadow floor'
for col in list(floor.users_collection):col.objects.unlink(floor)
studio.objects.link(floor);floor.data.materials.append(floor_mat)

def light(name,loc,energy,color,size,aim):
    d=bpy.data.lights.new(name,'AREA');d.energy=energy;d.color=color;d.shape='DISK';d.size=size
    ob=bpy.data.objects.new(name,d);studio.objects.link(ob);ob.location=loc
    ob.rotation_euler=(Vector(aim)-ob.location).to_track_quat('-Z','Y').to_euler()
light('Large grey-white key',(-8,-12,19),1250,(.72,.79,.94),11,(0,0,4))
light('Soft high rim',(9,5,17),950,(.56,.64,.96),8,(3,0,4))
light('Quiet frontal bounce',(-3,-10,6),180,(.80,.84,.90),7,(-2,0,3))

cam_data=bpy.data.cameras.new('Sculpture camera');cam=bpy.data.objects.new('Sculpture camera',cam_data)
rig.objects.link(cam);scene.camera=cam;cam_data.clip_end=350;cam_data.lens=48
cam_data.dof.use_dof=False
poses=[((1,-32,14),(0,0,4.45),48),((-4,-12,8),(-3,.3,3.75),50),((3,-9,9.7),(2,.65,6.0),50),((9,-11,13),(6,.4,7.5),48),((8,-33,17),(1,0,4.5),48)]

def catmull(points,t):
    u=t*(len(points)-1);i=min(len(points)-2,int(u));f=u-i
    p0,p1,p2,p3=[Vector(points[k]) for k in [max(0,i-1),i,i+1,min(len(points)-1,i+2)]]
    return .5*((2*p1)+(-p0+p2)*f+(2*p0-5*p1+4*p2-p3)*f*f+(-p0+3*p1-3*p2+p3)*f**3)
camera_path=[]
for frame in range(1,241):
    t=(frame-1)/239
    pos=catmull([p[0] for p in poses],t);target=catmull([p[1] for p in poses],t)
    cam.location=pos;cam.rotation_mode='QUATERNION';cam.rotation_quaternion=(target-pos).to_track_quat('-Z','Y')
    cam.keyframe_insert('location',frame=frame);cam.keyframe_insert('rotation_quaternion',frame=frame)
    camera_path.append({'frame':frame,'position':list(pos),'target':list(target)})
(ROOT/'assets'/'sculpture-camera-path.json').write_text(json.dumps(camera_path,indent=2),encoding='utf8')
scene.frame_set(1)

# Open Blender into a useful material view, with the whole sculpture selected.
bpy.ops.object.select_all(action='DESELECT')
for ob in sculpt.objects:
    if ob.type=='MESH':ob.select_set(True)
bpy.context.view_layer.objects.active=body
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            sp=area.spaces.active;sp.shading.type='MATERIAL'
            sp.region_3d.view_perspective='CAMERA'
scene['reference']='User supplied still and video 7d1e9dcb...; approximate visible-side reconstruction, not photogrammetry.'
scene['material_mode']='white film / matte plaster first-pass; use --grey for the earlier dark clay preview.'
scene['scope']='One group sculpture, no landscape, flags, parade or ambient snow geometry.'
scene['backside']='Back and unseen cavities are inferred artistic geometry.'
scene['units']='Arbitrary modelling units, not measured real-world dimensions.'
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'blender'/'snow_mountain_sculpture.blend'))

# Export only the model, with its real geometry. Procedural Blender bump shading
# is not portable: the viewer uses the physical geometry plus matte materials.
if '--blockout' not in sys.argv:
    bpy.ops.object.select_all(action='DESELECT')
    for ob in sculpt.objects:ob.select_set(True)
    bpy.ops.export_scene.gltf(filepath=str(ROOT/'assets'/'snow_mountain_sculpture.glb'),export_format='GLB',use_selection=True,export_animations=False,export_cameras=False,export_lights=False,export_apply=True,export_yup=True)

scene.render.filepath=str(ROOT/'renders'/'sculpture_overview.png')
if '--model-only' not in sys.argv:
    bpy.ops.render.render(write_still=True)
if '--views' in sys.argv:
    for name,frame in [('figures',75),('high_ridge',164),('return',240)]:
        scene.frame_set(frame);scene.render.filepath=str(ROOT/'renders'/('sculpture_'+name+'.png'))
        bpy.ops.render.render(write_still=True)
    scene.frame_set(1)

stats={'sculptureMeshes':sum(o.type=='MESH' for o in sculpt.objects),'sourceVertices':sum(len(o.data.vertices) for o in sculpt.objects if o.type=='MESH'),'sourcePolygons':sum(len(o.data.polygons) for o in sculpt.objects if o.type=='MESH'),'figuresModuleObjects':len(figure_objects),'backside':'inferred','referenceViews':'provided still plus video keyframes','glbProceduralBump':'not exported; matte material and real mesh geometry only'}
(ROOT/'assets'/'sculpture-model-info.json').write_text(json.dumps(stats,indent=2),encoding='utf8')
print('SCULPTURE_READY',json.dumps(stats))
