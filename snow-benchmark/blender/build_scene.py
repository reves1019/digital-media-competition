"""Original low-poly Long March snow-mountain study, Blender 5.2.
Run: blender -b --factory-startup --python build_scene.py -- --preview
All geometry is procedural. The supplied painting is a composition reference only.
"""
import bpy
import math
import random
import json
import sys
from pathlib import Path
from mathutils import Vector, noise

ROOT = Path(__file__).resolve().parents[1]
ROOT.mkdir(exist_ok=True)
(ROOT / 'assets' / 'frames').mkdir(parents=True, exist_ok=True)
(ROOT / 'renders').mkdir(exist_ok=True)
random.seed(1935)
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.samples = 20
scene.cycles.use_denoising = True
scene.cycles.max_bounces = 5
scene.cycles.diffuse_bounces = 2
scene.cycles.glossy_bounces = 2
scene.cycles.volume_bounces = 0
try:
    preferences = bpy.context.preferences.addons['cycles'].preferences
    preferences.compute_device_type = 'OPTIX'
    preferences.get_devices()
    for device in preferences.devices:
        device.use = device.type == 'OPTIX'
    scene.cycles.device = 'GPU'
except Exception as exc:
    print('GPU fallback:', exc)
scene.render.resolution_x = 1152
scene.render.resolution_y = 648
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.render.fps = 24
scene.frame_start = 1
scene.frame_end = 120
scene.render.film_transparent = False
scene.view_settings.view_transform = 'AgX'
scene.view_settings.look = 'AgX - Medium High Contrast'
scene.view_settings.exposure = .65

# The website benchmark uses a lightweight Eevee render sequence. The master
# .blend remains Cycles + OptiX capable for final stills and a competition film.
WEB_PREVIEW = '--web-preview' in sys.argv
if WEB_PREVIEW:
    scene.render.engine = 'BLENDER_EEVEE'
    scene.render.image_settings.file_format = 'WEBP'
    scene.render.image_settings.color_mode = 'RGB'
    scene.render.image_settings.compression = 55
    scene.render.filepath = str(ROOT / 'assets' / 'frames' / 'frame_')

collections = {}
for name in ['Snow ridge', 'Distant ranges', 'Marching column', 'Flags', 'Atmosphere', 'Camera choreography']:
    col = bpy.data.collections.new(name)
    scene.collection.children.link(col)
    collections[name] = col

def place_in(obj, collection):
    for col in list(obj.users_collection):
        col.objects.unlink(obj)
    collections[collection].objects.link(obj)
    return obj

def material(name, color, roughness=.85, noise_scale=None, bump=.1):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value = (*color, 1)
    bsdf.inputs['Roughness'].default_value = roughness
    if noise_scale:
        texture = mat.node_tree.nodes.new('ShaderNodeTexNoise')
        texture.inputs['Scale'].default_value = noise_scale
        texture.inputs['Detail'].default_value = 3
        ramp = mat.node_tree.nodes.new('ShaderNodeValToRGB')
        ramp.color_ramp.elements[0].position = .15
        ramp.color_ramp.elements[0].color = (*(v*.60 for v in color), 1)
        ramp.color_ramp.elements[1].position = .82
        ramp.color_ramp.elements[1].color = (*color, 1)
        mat.node_tree.links.new(texture.outputs['Fac'], ramp.inputs[0])
        mat.node_tree.links.new(ramp.outputs[0], bsdf.inputs['Base Color'])
        normal = mat.node_tree.nodes.new('ShaderNodeBump')
        normal.inputs['Strength'].default_value = bump
        normal.inputs['Distance'].default_value = .13
        mat.node_tree.links.new(texture.outputs['Fac'], normal.inputs['Height'])
        mat.node_tree.links.new(normal.outputs[0], bsdf.inputs['Normal'])
    return mat

snow_mat = material('Snow | blue-white matte', (.72,.79,.82), .9, 5.6, .19)
ice_mat = material('Compressed snow | path', (.43,.51,.54), .97, 8, .07)
rock_mat = material('Exposed slate', (.105,.14,.17), .96, 3.8, .25)
snow_shade = material('Wind-scoured snow', (.37,.47,.53), .96, 4.2, .18)
uniforms = [material('Coat | grey %s'%i, c, .95, 18,.12) for i,c in enumerate([
    (.125,.16,.155), (.17,.19,.175), (.12,.155,.17), (.185,.195,.18), (.14,.165,.155)])]
boots = material('Worn boots', (.039,.046,.043), .95)
packs = material('Canvas packs', (.18,.16,.12), .99, 21, .13)
roll_mat = material('Blanket rolls', (.21,.215,.19), .96, 25, .12)
skin = material('Face | subdued clay', (.27,.165,.115), .94)
wood = material('Walking staff | wood', (.12,.075,.035), .89)
belt_mat = material('Canvas straps', (.095,.085,.061), .99)
red = material('Faded red cloth', (.42,.014,.012), .96, 7,.1)
flake_mat = material('Snow crystals', (.84,.9,.95), .68)

def mesh_obj(name, vertices, faces, mat, group, smooth=False):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.materials.append(mat)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    collections[group].objects.link(obj)
    if smooth:
        for polygon in mesh.polygons:
            polygon.use_smooth = True
    return obj

def ridge_x(y):
    return 6.5 * math.sin(y*.056) + 2.4 * math.sin(y*.123)

def center_z(y):
    return 5.0 + .058*y + 1.6*math.sin(y*.037)

def ground_z(x,y):
    distance = abs(x-ridge_x(y))
    base = center_z(y) - .105 * distance**1.65
    ripple = noise.fractal(Vector((x*.15,y*.11,2.4)), 1.0, 2.0, 4)
    fine = .14 * math.sin(y*1.5+x*2.1)
    return base + ripple * min(1.0, distance / 5) * 1.3 + fine*min(1,distance/3)

vertices, faces = [], []
nx, ny = 140, 190
for j in range(ny+1):
    y = -45 + 190*j/ny
    for i in range(nx+1):
        x = -65 + 130*i/nx
        vertices.append((x,y,ground_z(x,y)))
for j in range(ny):
    for i in range(nx):
        a=j*(nx+1)+i
        faces.extend([(a,a+1,a+nx+2),(a,a+nx+2,a+nx+1)])
ridge = mesh_obj('Main winding snow ridge', vertices, faces, snow_mat, 'Snow ridge', True)
ridge.data.materials.append(rock_mat)
ridge.data.materials.append(snow_shade)
for face in ridge.data.polygons:
    if face.normal.z < .65:
        face.material_index = 1 if face.normal.x > .2 else 2

# A narrow, broken ribbon of compressed snow follows the marching route.
verts, quads = [], []
for j in range(290):
    y=-21+j*.46
    width=.48 + .12*math.sin(j*.32)
    for side in [-1,1]:
        x=ridge_x(y)+width*side
        verts.append((x,y,ground_z(x,y)+.018))
    if j: quads.append((2*j-2,2*j-1,2*j+1,2*j))
mesh_obj('Narrow traversed path',verts,quads,ice_mat,'Snow ridge',True)

def mountain(name,cx,cy,rx,ry,height,seed):
    n=80
    verts=[]; faces=[]
    for j in range(n+1):
        v=(j/n*2-1)
        for i in range(n+1):
            u=(i/n*2-1)
            x=cx+u*rx; y=cy+v*ry
            r=math.sqrt((u+.12*math.sin(v*5))**2+v*v)
            core=max(0,1-r)**1.18
            strata=noise.ridged_multi_fractal(Vector((x*.12,y*.14,seed)),1.0,2.15,4,1.0,2.0)
            ridge_wave=(math.sin(math.atan2(v,u)*9+seed)*.08+.92)
            z=-13+height*core*ridge_wave + strata*core*4
            z+=math.sin(u*13+v*6)*math.sin(v*12)*core*2.8
            verts.append((x,y,z))
    for j in range(n):
        for i in range(n):
            a=j*(n+1)+i
            faces.extend([(a,a+1,a+n+2),(a,a+n+2,a+n+1)])
    obj=mesh_obj(name,verts,faces,snow_mat,'Distant ranges',True)
    obj.data.materials.append(rock_mat); obj.data.materials.append(snow_shade)
    for face in obj.data.polygons:
        if face.normal.z<.54 and face.normal.x<.25:
            face.material_index=1 if face.normal.z<.37 else 2
    return obj

for spec in [
    ('West buttress',-65,35,43,65,62,1),
    ('West summit',-54,104,56,54,87,2),
    ('Central broken massif',6,150,69,49,94,3),
    ('East wall',59,102,46,66,100,4),
    ('Near east face',66,10,40,50,57,5),
    ('Distant pass',-108,173,80,70,102,6),
    ('Far east peak',106,173,70,70,106,7),
]: mountain(*spec)

def uv(name,loc,scale,mat,parent=None,segments=12,rings=8):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segments,ring_count=rings,location=loc)
    obj=bpy.context.object; obj.name=name; obj.scale=scale
    obj.data.materials.append(mat)
    if parent: obj.parent=parent
    place_in(obj,'Marching column')
    for p in obj.data.polygons: p.use_smooth=True
    return obj

def box(name,loc,scale,mat,parent=None,bevel=.03):
    bpy.ops.mesh.primitive_cube_add(size=1,location=loc)
    obj=bpy.context.object; obj.name=name; obj.scale=scale
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    obj.data.materials.append(mat)
    if parent: obj.parent=parent
    place_in(obj,'Marching column')
    if bevel:
        mod=obj.modifiers.new('Soft worn edges','BEVEL'); mod.width=bevel; mod.segments=2
        obj.modifiers.new('Weighted normals','WEIGHTED_NORMAL')
    return obj

def limb(name,a,b,r1,r2,mat,parent=None,vertices=10):
    a=Vector(a); b=Vector(b); diff=b-a
    bpy.ops.mesh.primitive_cone_add(vertices=vertices,radius1=r1,radius2=r2,depth=diff.length,location=(a+b)/2)
    obj=bpy.context.object; obj.name=name
    obj.rotation_quaternion=diff.to_track_quat('Z','Y'); obj.rotation_mode='QUATERNION'
    obj.data.materials.append(mat)
    if parent: obj.parent=parent
    place_in(obj,'Marching column')
    for p in obj.data.polygons:p.use_smooth=True
    return obj

def coat(parent,mat,lean):
    verts=[]
    # Tailored cross sections, broad shoulders and a flared overcoat hem.
    for z,w,d,offset in [(.60,.28,.19,.04),(.86,.21,.145,-.02),(1.05,.205,.15,-.07),(1.4,.29,.17,-lean),(1.49,.18,.13,-lean-.02)]:
        for k in range(12):
            a=k*math.tau/12
            verts.append((math.cos(a)*w,offset+math.sin(a)*d,z))
    faces=[]
    for j in range(4):
        for k in range(12):
            faces.append((j*12+k,j*12+(k+1)%12,(j+1)*12+(k+1)%12,(j+1)*12+k))
    faces.append(tuple(range(48,60)))
    obj=mesh_obj('Weathered overcoat',verts,faces,mat,'Marching column',True)
    obj.parent=parent

def flag(parent,scale=1):
    pole=limb('Flag pole',(.43,-.32,.05),(.24,-.38,3.12),.028,.024,wood,parent,8)
    place_in(pole,'Flags')
    verts=[]; faces=[]
    nu,nv=30,16
    for j in range(nv+1):
        v=j/nv
        for i in range(nu+1):
            u=i/nu
            verts.append((.24+u*1.7*scale,-.38 + u*(.13*math.sin(u*8+v*3)+.11),3.1-v*.92*scale-u*.18))
    for j in range(nv):
        for i in range(nu):
            a=j*(nu+1)+i; faces.append((a,a+1,a+nu+2,a+nu+1))
    obj=mesh_obj('Red flag | artistic plain cloth',verts,faces,red,'Flags',True); obj.parent=parent
    obj.shape_key_add(name='Basis')
    wave=obj.shape_key_add(name='Wind')
    for index,vertex in enumerate(wave.data):
        u=(index%(nu+1))/nu; v=(index//(nu+1))/nv
        vertex.co.y += u*.23*math.sin(u*7+v*5+1.8)
        vertex.co.z += u*.11*math.cos(u*6+v*2)
    for f,value in [(1,0),(24,1),(49,0),(75,1),(99,0),(120,.85)]:
        wave.value=value; wave.keyframe_insert('value',frame=f)
    solid=obj.modifiers.new('Cloth thickness','SOLIDIFY'); solid.thickness=.004

def soldier(y,index,flag_bearer=False):
    mat=uniforms[index%len(uniforms)]
    root=bpy.data.objects.new('Marcher %02d'%index,None)
    collections['Marching column'].objects.link(root)
    x=ridge_x(y) + random.uniform(-.38,.38)
    root.location=(x,y,ground_z(x,y)+.045)
    direction=math.atan2(ridge_x(y+.4)-ridge_x(y-.4),.8)
    root.rotation_euler.z=-direction+random.uniform(-.12,.12)
    scale=random.uniform(.94,1.06); root.scale=(scale,scale,scale)
    lean=random.uniform(.15,.24)
    coat(root,mat,lean)
    stride=.20 if index%2==0 else -.20
    for side in [-1,1]:
        hip=(side*.12,-.02,.78)
        knee=(side*.14,-.08+side*stride*.75,.46)
        ankle=(side*.16,side*stride,.12)
        limb('Trouser thigh',hip,knee,.112,.092,mat,root)
        limb('Bound leg',knee,ankle,.084,.059,mat,root)
        box('Boot',(side*.16,side*stride-.07,.085),(.16,.30,.15),boots,root,.035)
        for z in [.20,.26,.32]:
            box('Leg wrap',(side*.15,side*stride*.75,z),(.135,.14,.025),belt_mat,root,.005)
    head_y=-lean-.06
    uv('Head',(0,head_y,1.64),(.118,.117,.162),skin,root)
    # Small face planes; no portrait claims or named individuals.
    uv('Nose',(0,head_y-.117,1.65),(.029,.045,.044),skin,root,8,6)
    uv('Cap crown',(0,head_y+.014,1.78),(.14,.145,.063),mat,root)
    box('Cap brim',(0,head_y-.12,1.76),(.25,.16,.018),mat,root,.012)
    for side in [-1,1]:
        box('Red collar tab',(side*.082,-lean-.153,1.44),(.052,.018,.070),red,root,.004)
    box('Waist belt',(0,-.025,1.0),(.44,.34,.055),belt_mat,root,.018)
    box('Backpack',(0,.185,1.26),(.39,.225,.48),packs,root,.055)
    limb('Rolled blanket',(-.27,.24,1.55),(.27,.24,1.55),.095,.095,roll_mat,root,12)
    for side in [-1,1]:
        limb('Shoulder strap',(side*.145,-lean-.13,1.4),(side*.14,-.14,1.04),.020,.020,belt_mat,root,6)
    # Hiking pole and two distinct tired walking poses.
    shoulder=(.28,-lean,1.35); elbow=(.39,-.38,1.10); hand=(.46,-.51,1.21)
    limb('Upper sleeve R',shoulder,elbow,.094,.080,mat,root)
    limb('Sleeve R',elbow,hand,.079,.057,mat,root)
    uv('Hand R',hand,(.06,.058,.07),skin,root)
    if not flag_bearer:
        limb('Walking staff',(.5,-.62,.03),(.46,-.51,1.63),.018,.016,wood,root,7)
    shoulder=(-.28,-lean,1.35)
    elbow=(-.4,-.11,1.02)
    hand=(-.32,-.36,.89) if index%3 else (-.30,-.36,1.59)
    limb('Upper sleeve L',shoulder,elbow,.094,.074,mat,root)
    limb('Sleeve L',elbow,hand,.074,.054,mat,root)
    uv('Hand L',hand,(.06,.052,.07),skin,root)
    if flag_bearer: flag(root,1 if index<15 else .83)
    return root

ys=[-9,-5.5,-2,1.7,5.5,9.5,13.5,17.5,21.7,26,30.5,35,39.5,44,49,54,59,64,69,74,79,84,89,94,99,104]
for index,y in enumerate(ys): soldier(y,index,index in [4,12,21])

# A field of actual 3D snow particles, moving with wind in the Blender timeline.
verts=[]; faces=[]
for i in range(3800):
    x=random.uniform(-44,45); y=random.uniform(-40,120); z=random.uniform(2,48)
    size=random.uniform(.012,.055)
    a=len(verts)
    verts.extend([(x-size,y,z),(x+size,y,z),(x,y-size,z),(x,y+size,z),(x,y,z-size*1.7),(x,y,z+size*1.7)])
    faces.extend([(a,a+2,a+5),(a+2,a+1,a+5),(a+1,a+3,a+5),(a+3,a,a+5),(a+2,a,a+4),(a+1,a+2,a+4),(a+3,a+1,a+4),(a,a+3,a+4)])
snow=mesh_obj('Snowfall | 3800 volumetric crystals',verts,faces,flake_mat,'Atmosphere')
snow.location=(0,0,0); snow.keyframe_insert('location',frame=1)
snow.location=(6,0,-4); snow.keyframe_insert('location',frame=120)

# Atmospheric perspective is rendered in 3D, not painted over the image.
fog=bpy.data.materials.new('Thin alpine haze'); fog.use_nodes=True
fog.node_tree.nodes.clear()
output=fog.node_tree.nodes.new('ShaderNodeOutputMaterial')
volume=fog.node_tree.nodes.new('ShaderNodeVolumePrincipled')
volume.inputs['Density'].default_value=.004
volume.inputs['Color'].default_value=(.37,.46,.55,1)
volume.inputs['Anisotropy'].default_value=.15
fog.node_tree.links.new(volume.outputs['Volume'],output.inputs['Volume'])
bpy.ops.mesh.primitive_cube_add(size=1,location=(0,65,31))
fog_box=bpy.context.object; fog_box.name='Alpine atmosphere volume'; fog_box.scale=(350,370,160)
fog_box.data.materials.append(fog); place_in(fog_box,'Atmosphere')

world=bpy.data.worlds.new('Cold overcast sky'); world.use_nodes=True; scene.world=world
world.node_tree.nodes['Background'].inputs[0].default_value=(.105,.15,.22,1)
world.node_tree.nodes['Background'].inputs[1].default_value=.38

def light(name,kind,loc,energy,color,size,aim):
    data=bpy.data.lights.new(name,kind); data.energy=energy; data.color=color
    if kind=='AREA':data.shape='DISK';data.size=size
    if kind=='SUN':data.angle=size
    obj=bpy.data.objects.new(name,data); collections['Atmosphere'].objects.link(obj)
    obj.location=loc; obj.rotation_euler=(Vector(aim)-obj.location).to_track_quat('-Z','Y').to_euler()
    return obj
light('Pale sun through cloud','SUN',(-30,-25,55),2.2,(.72,.81,1),.20,(0,20,0))
light('Soft foreground bounce','AREA',(7,-16,22),1900,(.73,.82,1),18,(0,5,6))
light('Distant rim through mist','AREA',(-16,60,35),3200,(.80,.86,1),25,(0,20,5))

cam_data=bpy.data.cameras.new('Cinematic camera'); cam=bpy.data.objects.new('Cinematic camera',cam_data)
collections['Camera choreography'].objects.link(cam); scene.camera=cam
cam_data.clip_end=700; cam_data.clip_start=.1
cam_data.lens=43
cam_data.dof.use_dof=False

positions=[(25,-38,18),(11,-22,10.5),(-11,-11,10.5),(-23,8,19),(-34,34,30)]
targets=[(1,23,10),(1,11,7.5),(2,16,8.6),(3,35,11),(4,52,14)]
lenses=[43,43,42,39,36]

def curve_debug(name,points,color):
    curve=bpy.data.curves.new(name,'CURVE');curve.dimensions='3D'
    spline=curve.splines.new('BEZIER');spline.bezier_points.add(len(points)-1)
    for p,co in zip(spline.bezier_points,points):
        p.co=co;p.handle_left_type='AUTO';p.handle_right_type='AUTO'
    obj=bpy.data.objects.new(name,curve);collections['Camera choreography'].objects.link(obj)
    obj.hide_render=True;obj.color=(*color,1)
    return obj
curve_debug('CAMERA PATH | wide > approach > side > rise',positions,(.8,.15,.2))
curve_debug('LOOK AT PATH',targets,(.1,.5,.8))

def catmull(points,t):
    u=t*(len(points)-1);i=min(len(points)-2,int(u));f=u-i
    p0=Vector(points[max(0,i-1)]);p1=Vector(points[i]);p2=Vector(points[i+1]);p3=Vector(points[min(len(points)-1,i+2)])
    return .5*((2*p1)+(-p0+p2)*f+(2*p0-5*p1+4*p2-p3)*f*f+(-p0+3*p1-3*p2+p3)*f*f*f)

camera_export=[]
for frame in range(1,121):
    t=(frame-1)/119
    cam.location=catmull(positions,t)
    target=catmull(targets,t)
    cam.rotation_mode='QUATERNION';cam.rotation_quaternion=(target-cam.location).to_track_quat('-Z','Y')
    cam.keyframe_insert('location',frame=frame);cam.keyframe_insert('rotation_quaternion',frame=frame)
    u=t*4;i=min(3,int(u));f=u-i
    cam_data.lens=lenses[i]*(1-f)+lenses[i+1]*f;cam_data.keyframe_insert('lens',frame=frame)
    camera_export.append({'frame':frame,'position':list(cam.location),'quaternion':list(cam.rotation_quaternion),'lookAt':list(target),'lens':cam_data.lens})
(ROOT/'assets'/'camera-path.json').write_text(json.dumps(camera_export,indent=2),encoding='utf-8')

scene['scene_note']='Original low-poly artistic study. Not a faithful reconstruction of a specific photograph or named unit.'
scene['reference_note']='User supplied painting used only for compositional ideas; no image texture copied into scene.'
scene['camera_chapters']='1-30 wide, 31-60 approach, 61-90 side-track, 91-120 crane-and-reveal'
scene.frame_set(38)
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'blender'/'snow_march.blend'))
if '--preview' in sys.argv:
    scene.render.filepath=str(ROOT/'renders'/'preview_0038.png')
    bpy.ops.render.render(write_still=True)
elif WEB_PREVIEW:
    scene.render.filepath=str(ROOT/'assets'/'frames'/'frame_')
    bpy.ops.render.render(animation=True)
    frames=sorted((ROOT/'assets'/'frames').glob('frame_*.webp'))
    (ROOT/'assets'/'manifest.json').write_text(json.dumps({
        'title':'翻雪山 · 长征时期的雪脊行军',
        'fps':24,'frameCount':len(frames),'width':1152,'height':648,
        'frames':[f'frames/{p.name}' for p in frames],
        'poster':f'frames/{frames[len(frames)//3].name}' if frames else '',
        'duration':len(frames)/24,
        'segments':[
            {'start':0.00,'end':0.25,'title':'远望雪脊','subtitle':'一条路，穿过风雪。','body':'镜头先停在高处。队伍沿着雪脊进入画面，红旗成为远景里唯一稳定的暖色。'},
            {'start':0.25,'end':0.50,'title':'靠近队伍','subtitle':'脚下是雪，前方仍有路。','body':'1935年6月12日，中央红军先头部队从四川宝兴大硗碛出发，向夹金山进发。人物为原创低模艺术表达，不对应特定个人。'},
            {'start':0.50,'end':0.75,'title':'同行侧拍','subtitle':'让每一步都留下回声。','body':'镜头沿山脊侧向移动，风雪从前景掠过，队伍的节奏与山体的起伏保持同一条线。'},
            {'start':0.75,'end':1.00,'title':'回望雪山','subtitle':'翻过雪山，记忆没有被风吹散。','body':'先头部队翻越后，中央红军主力于6月17日翻过这座长征途中第一座大雪山。这里的风雪、稀薄空气与骤变天气，成为队伍共同面对的险阻。'}
        ],
        'historySources':[
            {'label':'中央网信办转载：中国历史网《翻越夹金山》','url':'https://www.cac.gov.cn/2016-08/22/c_1119431608.htm'},
            {'label':'国家林业和草原局：长征相关资料','url':'https://www.forestry.gov.cn/c/www/fzcj/100747.jhtml'}
        ],
        'production':{'renderer':'Blender 5.2 Eevee preview; master scene uses Cycles + OptiX','camera':'baked camera path; web scroll scrubs frame sequence','particleLayer':'web overlay + Blender snowfall in each frame','verification':'historical copy and source links require final human review'}
    },ensure_ascii=False,indent=2),encoding='utf-8')
else:
    scene.render.filepath=str(ROOT/'renders'/'frame_')
    bpy.ops.render.render(animation=True)
print('SNOW_BENCHMARK_COMPLETE',len(scene.objects),len(bpy.data.meshes))
