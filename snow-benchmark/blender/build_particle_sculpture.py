"""Build a Blender-rendered particle version of the snow-mountain sculpture.

The existing snow_mountain_sculpture.blend is the geometry source.  This script
samples its visible sculpture surfaces into sparse instanced particles, keeps
the human/rock silhouette readable, and adds two restrained vermilion particle
flags.  The original white-film collection is retained but hidden from render
so the output is genuinely particle-based.
"""
import bisect
import json
import math
import random
import sys
from pathlib import Path

import bpy
from mathutils import Vector


ROOT = Path(__file__).resolve().parents[1]
BLEND_SOURCE = ROOT / "blender" / "snow_mountain_sculpture.blend"
OUT_BLEND = ROOT / "blender" / "snow_mountain_particle_sculpture.blend"
OUT_META = ROOT / "assets" / "snow_mountain_particle_info.json"
OUT_OVERVIEW = ROOT / "renders" / "particle_sculpture_overview.png"
OUT_CLOSE = ROOT / "renders" / "particle_sculpture_close.png"
random.seed(1001935)


def safe_input(node, *names):
    for name in names:
        socket = node.inputs.get(name)
        if socket is not None:
            return socket
    return None


def collection(name, parent=None):
    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name)
    if parent is None:
        parent = bpy.context.scene.collection
    if col.name not in {child.name for child in parent.children}:
        parent.children.link(col)
    return col


def remove_collection(name):
    col = bpy.data.collections.get(name)
    if col is None:
        return
    for obj in list(col.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    bpy.data.collections.remove(col)


def is_figure(ob):
    p = ob
    while p is not None:
        if "figure" in p.name.lower():
            return True
        p = p.parent
    return False


def gather_triangles(objects):
    triangles = []
    total = 0.0
    for ob in objects:
        if ob.type != "MESH" or not ob.data or ob.hide_render:
            continue
        verts = ob.data.vertices
        mat = ob.matrix_world
        for poly in ob.data.polygons:
            ids = list(poly.vertices)
            if len(ids) < 3:
                continue
            a = mat @ verts[ids[0]].co
            for j in range(1, len(ids) - 1):
                b = mat @ verts[ids[j]].co
                c = mat @ verts[ids[j + 1]].co
                area = (b - a).cross(c - a).length * 0.5
                if area <= 1e-7:
                    continue
                total += area
                triangles.append((total, a.copy(), b.copy(), c.copy()))
    return triangles, total


def sample_triangles(triangles, total, amount, seed):
    rng = random.Random(seed)
    if not triangles or total <= 0:
        return []
    cumulative = [item[0] for item in triangles]
    points = []
    for _ in range(amount):
        item = triangles[bisect.bisect_left(cumulative, rng.random() * total)]
        _, a, b, c = item
        u = rng.random()
        v = rng.random()
        if u + v > 1:
            u = 1 - u
            v = 1 - v
        point = a * (1 - u - v) + b * u + c * v
        # Small outward lift stops adjacent particles from merging into a flat
        # white skin while retaining the rock/person silhouette.
        normal = (b - a).cross(c - a)
        if normal.length > 1e-8:
            point += normal.normalized() * rng.uniform(0.004, 0.028)
        points.append(point)
    return points


def mesh_points(name, points, col):
    me = bpy.data.meshes.new(name + " | point positions")
    me.from_pydata([tuple(p) for p in points], [], [])
    me.update()
    ob = bpy.data.objects.new(name, me)
    col.objects.link(ob)
    return ob


def particle_material(name, color, roughness, emission=0.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    safe_input(bsdf, "Base Color").default_value = (*color, 1)
    safe_input(bsdf, "Roughness").default_value = roughness
    metallic = safe_input(bsdf, "Metallic")
    if metallic:
        metallic.default_value = 0.04
    spec = safe_input(bsdf, "Specular IOR Level", "Specular")
    if spec:
        spec.default_value = 0.38
    emission_color = safe_input(bsdf, "Emission Color", "Emission")
    emission_strength = safe_input(bsdf, "Emission Strength")
    if emission_color:
        emission_color.default_value = (*color, 1)
    if emission_strength:
        emission_strength.default_value = emission
    mat.node_tree.links.new(bsdf.outputs[0], out.inputs[0])
    return mat


def ico_prototype(col):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=1, location=(0, 0, -100))
    ob = bpy.context.object
    ob.name = "Particle prototype | hidden"
    for old in list(ob.users_collection):
        old.objects.unlink(ob)
    col.objects.link(ob)
    ob.hide_render = True
    ob.hide_viewport = True
    return ob


def add_particle_geometry(points_ob, material, prototype, radius, name):
    ng = bpy.data.node_groups.new(name + " | geometry", "GeometryNodeTree")
    ng.interface.new_socket(name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket(name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    nodes = ng.nodes
    links = ng.links
    inp = nodes.new("NodeGroupInput")
    out = nodes.new("NodeGroupOutput")
    to_points = nodes.new("GeometryNodeMeshToPoints")
    to_points.mode = "VERTICES"
    safe_input(to_points, "Radius").default_value = radius
    info = nodes.new("GeometryNodeObjectInfo")
    info.transform_space = "ORIGINAL"
    safe_input(info, "Object").default_value = prototype
    safe_input(info, "As Instance").default_value = True
    inst = nodes.new("GeometryNodeInstanceOnPoints")
    scale = nodes.new("ShaderNodeCombineXYZ")
    scale.inputs[0].default_value = radius
    scale.inputs[1].default_value = radius
    scale.inputs[2].default_value = radius
    scale_instances = nodes.new("GeometryNodeScaleInstances")
    set_mat = nodes.new("GeometryNodeSetMaterial")
    safe_input(set_mat, "Material").default_value = material
    links.new(inp.outputs[0], to_points.inputs[0])
    links.new(to_points.outputs[0], inst.inputs[0])
    links.new(info.outputs.get("Geometry"), inst.inputs[2])
    links.new(inst.outputs[0], scale_instances.inputs[0])
    links.new(scale.outputs[0], scale_instances.inputs[2])
    links.new(scale_instances.outputs[0], set_mat.inputs[0])
    links.new(set_mat.outputs[0], out.inputs[0])
    mod = points_ob.modifiers.new(name, "NODES")
    mod.node_group = ng
    return mod


def flag_points(anchor, width, height, seed):
    """Generate particles on a waving triangular cloth plus its pole."""
    rng = random.Random(seed)
    ax, ay, az = anchor
    points = []
    pole_count = int(height / 0.055)
    for i in range(pole_count + 1):
        z = az + i * height / pole_count
        points.append(Vector((ax + rng.uniform(-.012, .012), ay, z)))
    cols, rows = 28, 13
    for j in range(rows + 1):
        v = j / rows
        for i in range(cols + 1):
            u = i / cols
            # A tapered pennant with a low-frequency cloth wave.
            taper = 1.0 - 0.28 * v
            x = ax + 0.07 + width * u * taper
            z = az + height * (0.22 + 0.58 * v)
            y = ay - 0.10 * math.sin(u * math.pi * 2.0 + v * 2.6) - 0.025 * u
            if u > 0.82 + v * 0.06:
                continue
            points.append(Vector((x, y, z)))
    return points


def main():
    if not BLEND_SOURCE.exists():
        raise FileNotFoundError(BLEND_SOURCE)
    bpy.ops.wm.open_mainfile(filepath=str(BLEND_SOURCE))
    scene = bpy.context.scene
    # Blender 5.2 exposes the realtime engine under this enum name.
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 1600
    scene.render.resolution_y = 1000
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.fps = 24
    scene.frame_start = 1
    scene.frame_end = 240
    scene.render.film_transparent = False
    scene.view_settings.look = "AgX - Medium High Contrast"
    scene.view_settings.exposure = 0.35

    sculpt = bpy.data.collections.get("01 | SCULPTURE - export this collection")
    if sculpt is None:
        raise RuntimeError("source sculpture collection not found")
    sources = [ob for ob in sculpt.all_objects if ob.type == "MESH"]
    fig_objects = [ob for ob in sources if is_figure(ob)]
    rock_objects = [ob for ob in sources if ob not in fig_objects]

    rock_tri, rock_area = gather_triangles(rock_objects)
    fig_tri, fig_area = gather_triangles(fig_objects)
    # Oversample figures slightly so the marching line remains legible after
    # replacing the solid clay with particles.
    rock_points = sample_triangles(rock_tri, rock_area, 30000, 19350612)
    fig_points = sample_triangles(fig_tri, fig_area, 22000, 271927)
    base_points = rock_points + fig_points
    rng = random.Random(20261011)
    white_points = []
    grey_points = []
    for point in base_points:
        if rng.random() < 0.72:
            white_points.append(point)
        else:
            grey_points.append(point)

    remove_collection("04 | PARTICLE SCULPTURE")
    particle_col = collection("04 | PARTICLE SCULPTURE")
    support_col = collection("05 | PARTICLE SUPPORT")
    white_mat = particle_material("Particle | cool white", (0.79, 0.82, 0.84), 0.62, 0.12)
    grey_mat = particle_material("Particle | smoke grey", (0.32, 0.37, 0.40), 0.68, 0.04)
    red_mat = particle_material("Particle | vermilion flags", (0.36, 0.025, 0.035), 0.58, 0.18)
    proto = ico_prototype(support_col)
    white_ob = mesh_points("Particle field | cool white", white_points, particle_col)
    grey_ob = mesh_points("Particle field | smoke grey", grey_points, particle_col)
    add_particle_geometry(white_ob, white_mat, proto, 0.030, "White particle instances")
    add_particle_geometry(grey_ob, grey_mat, proto, 0.023, "Grey particle instances")

    # Two small pennants are intentionally the only saturated mass in the
    # render.  Their locations follow the long rising axis of the sculpture.
    red_points = []
    red_points.extend(flag_points((-1.55, -2.05, 4.55), 1.35, 1.9, 11))
    red_points.extend(flag_points((3.65, -1.45, 6.55), 1.08, 1.55, 37))
    red_ob = mesh_points("Particle flags | vermilion", red_points, particle_col)
    add_particle_geometry(red_ob, red_mat, proto, 0.026, "Vermilion flag particles")

    # Hide the solid model only for the particle render. The source remains in
    # the same .blend and can be re-enabled from the Outliner for comparison.
    sculpt.hide_render = True
    particle_col["particle_count"] = len(base_points) + len(red_points)
    particle_col["base_particle_count"] = len(base_points)
    particle_col["red_flag_particle_count"] = len(red_points)
    scene["particle_render"] = "full sculpture surface converted to gray-white particles with restrained vermilion flags"
    scene["source_geometry"] = str(BLEND_SOURCE)

    # Slightly brighter cool rim so the grey-white field separates from the
    # charcoal studio while retaining the white-film silhouette.
    light_data = bpy.data.lights.new("Particle rim | cool white", "AREA")
    light_data.energy = 680
    light_data.color = (0.56, 0.72, 0.92)
    light_data.shape = "DISK"
    light_data.size = 8
    light_ob = bpy.data.objects.new("Particle rim | cool white", light_data)
    collection("02 | Studio - not part of export").objects.link(light_ob)
    light_ob.location = (4, 2, 18)
    target = Vector((0, 0, 4.8))
    light_ob.rotation_euler = (target - light_ob.location).to_track_quat("-Z", "Y").to_euler()

    # Render a wide establishing frame and a figure close-up using the existing
    # keyed camera. The source camera remains editable for later animation.
    scene.frame_set(1)
    scene.render.filepath = str(OUT_OVERVIEW)
    bpy.ops.render.render(write_still=True)
    scene.frame_set(75)
    scene.render.filepath = str(OUT_CLOSE)
    bpy.ops.render.render(write_still=True)
    scene.frame_set(1)
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT_BLEND))
    metadata = {
        "sourceBlend": str(BLEND_SOURCE),
        "outputBlend": str(OUT_BLEND),
        "baseParticles": len(base_points),
        "whiteParticles": len(white_points),
        "greyParticles": len(grey_points),
        "redFlagParticles": len(red_points),
        "rockTrianglesSampled": len(rock_tri),
        "figureTrianglesSampled": len(fig_tri),
        "engine": scene.render.engine,
        "materialDirection": "cool gray-white field with restrained vermilion particle flags",
        "originalFilmHiddenFromRender": True,
    }
    OUT_META.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    print("PARTICLE_SCULPTURE_READY", json.dumps(metadata, ensure_ascii=False))


if __name__ == "__main__":
    main()
