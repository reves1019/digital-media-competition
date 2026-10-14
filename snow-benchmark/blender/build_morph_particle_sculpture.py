"""Generate a 512x512 fixed-point morph-particle asset from the Blender sculpture.

This is the Blender-side preparation for a morph-particles style WebGL scene:
every point keeps the same index through five target shapes.  The web layer can
upload the binary positions to a 512^2 RGBA32F/FBO simulation without changing
the sculpture's identity during a scroll morph.
"""
import json
import math
import random
import sys
from array import array
from bisect import bisect_left
from pathlib import Path

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_particle_sculpture as particle


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "blender" / "snow_mountain_sculpture.blend"
OUTPUT_BLEND = ROOT / "blender" / "snow_mountain_morph_particles_512.blend"
OUTPUT_BIN = ROOT / "assets" / "snow_mountain_morph_points_512.bin"
OUTPUT_NORMALS = ROOT / "assets" / "snow_mountain_morph_normals_512.bin"
OUTPUT_META = ROOT / "assets" / "snow_mountain_morph_manifest.json"
OUTPUT_RENDER = ROOT / "renders" / "morph_particle_sculpture_512.png"
N = 512 * 512
# The two flag generators below produce 744 fixed samples in total. Keep the
# budget exact so the base field is not padded by duplicated points.
RED_N = 744
BASE_N = N - RED_N
random.seed(20261011)


def is_figure(ob):
    p = ob
    while p is not None:
        if "figure" in p.name.lower():
            return True
        p = p.parent
    return False


def gather_eval_triangles(objects):
    """Gather evaluated, world-space triangles and normals for dense sampling."""
    depsgraph = bpy.context.evaluated_depsgraph_get()
    triangles = []
    total = 0.0
    for ob in objects:
        if ob.type != "MESH" or ob.hide_render:
            continue
        evaluated = ob.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        try:
            mat = evaluated.matrix_world
            for poly in mesh.polygons:
                ids = list(poly.vertices)
                if len(ids) < 3:
                    continue
                a = mat @ mesh.vertices[ids[0]].co
                for j in range(1, len(ids) - 1):
                    b = mat @ mesh.vertices[ids[j]].co
                    c = mat @ mesh.vertices[ids[j + 1]].co
                    normal = (b - a).cross(c - a)
                    area = normal.length * 0.5
                    if area <= 1e-8:
                        continue
                    normal.normalize()
                    total += area
                    triangles.append((total, a.copy(), b.copy(), c.copy(), normal.copy()))
        finally:
            evaluated.to_mesh_clear()
    return triangles, total


def sample_records(triangles, total, amount, seed, role):
    rng = random.Random(seed)
    cumulative = [item[0] for item in triangles]
    records = []
    for _ in range(amount):
        _, a, b, c, normal = triangles[bisect_left(cumulative, rng.random() * total)]
        u = rng.random()
        v = rng.random()
        if u + v > 1:
            u = 1 - u
            v = 1 - v
        point = a * (1 - u - v) + b * u + c * v
        point += normal * rng.uniform(0.002, 0.016)
        records.append({"p": point, "n": normal, "role": role, "seed": rng.random()})
    return records


def add_flag_records(records, anchor, width, height, seed, flag_id):
    for point in particle.flag_points(anchor, width, height, seed):
        records.append({"p": point, "n": Vector((0, 0, 1)), "role": 2, "seed": random.random(), "flag": flag_id})


def build_shapes(records):
    """Make A/B/C/D/E target shapes with a stable point index."""
    rng = random.Random(271927)
    shapes = [[] for _ in range(5)]
    colors = []
    role_masks = []
    phases = []
    for item in records:
        p = item["p"]
        n = item["n"]
        seed = item["seed"]
        role = item["role"]
        phase = rng.random() * math.tau
        phases.append(phase)
        role_masks.append(role)
        if role == 2:
            colors.append((0.52, 0.025, 0.035, 1.0))
        elif rng.random() < 0.72:
            colors.append((0.78, 0.82, 0.85, 1.0))
        else:
            colors.append((0.34, 0.39, 0.42, 1.0))
        wind = Vector((0.45 + 0.22 * math.sin(phase), 0.18 * math.cos(phase), 0.12 * math.sin(phase * 1.7)))
        puff = n * (0.18 + 0.52 * seed) + wind * (0.25 + 0.85 * seed)
        # A: exact white-film surface. B: restrained outward breathing field.
        shapes[0].append(p.copy())
        shapes[1].append(p + puff)
        # C: compress points toward a rising ridge while retaining local spread.
        ridge = Vector((p.x, p.y * 0.42, p.z + 0.22 * math.sin(p.x * 0.32 + phase)))
        shapes[2].append(ridge + n * (0.22 + 0.26 * seed))
        # D: outward dispersal, with flags held as a red focal group.
        if role == 2:
            shapes[3].append(p + Vector((0.12 * math.sin(phase), 0.1 * math.cos(phase), 0.18)))
        else:
            shapes[3].append(p + Vector((1.1 + 2.2 * seed, (seed - .5) * 1.8, .6 + seed * 1.6)) + n * .5)
        # E: return shape, slightly rotated around the long axis for a seamless loop.
        shapes[4].append(p + Vector((0.08 * math.sin(phase), 0.06 * math.cos(phase), 0.04 * math.sin(phase * 2))))
    return shapes, colors, role_masks, phases


def write_binary(shapes, colors, roles, phases):
    # Layout is documented in the manifest: five contiguous float32 position
    # arrays, then RGBA float32 colors, float32 phases, and uint8 role masks.
    floats = array("f")
    for shape in shapes:
        for p in shape:
            floats.extend((p.x, p.y, p.z))
    for color in colors:
        floats.extend(color)
    floats.extend(phases)
    with OUTPUT_BIN.open("wb") as handle:
        floats.tofile(handle)
        handle.write(bytes(roles))


def write_normals(records):
    """Write one world-space Blender Z-up face normal for every point index.

    The normal stream is deliberately a separate little-endian Float32 file so
    the existing morph-point binary layout and offsets remain unchanged.  The
    order is exactly the order of ``records`` (and therefore the order used by
    every target shape, color and role entry).
    """
    normals = array("f")
    for item in records:
        normal = Vector(item["n"])
        if normal.length_squared < 1e-12:
            normal = Vector((0.0, 0.0, 1.0))
        else:
            normal.normalize()
        # Blender's world is Z-up; do not remap axes for the web consumer.
        normals.extend((normal.x, normal.y, normal.z))
    if sys.byteorder != "little":
        normals.byteswap()
    with OUTPUT_NORMALS.open("wb") as handle:
        normals.tofile(handle)
    expected = len(records) * 3 * 4
    actual = OUTPUT_NORMALS.stat().st_size
    if actual != expected:
        raise RuntimeError("normal binary size mismatch: %d != %d" % (actual, expected))
    return actual


def main():
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 1400
    scene.render.resolution_y = 875
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    scene.view_settings.exposure = 0.28
    sculpt = bpy.data.collections.get("01 | SCULPTURE - export this collection")
    sources = [ob for ob in sculpt.all_objects if ob.type == "MESH"]
    figures = [ob for ob in sources if is_figure(ob)]
    rocks = [ob for ob in sources if ob not in figures]
    rock_tri, rock_area = gather_eval_triangles(rocks)
    fig_tri, fig_area = gather_eval_triangles(figures)
    rock_n = int(BASE_N * 0.58)
    fig_n = BASE_N - rock_n
    records = sample_records(rock_tri, rock_area, rock_n, 19350612, 0)
    records.extend(sample_records(fig_tri, fig_area, fig_n, 271927, 1))
    add_flag_records(records, (-1.55, -2.05, 4.55), 1.35, 1.9, 11, 0)
    add_flag_records(records, (3.65, -1.45, 6.55), 1.08, 1.55, 37, 1)
    if len(records) > N:
        records = records[:N]
    while len(records) < N:
        # Fill any rounding gap with a deterministic copy of a base point.
        records.append(records[len(records) % BASE_N].copy())
    shapes, colors, roles, phases = build_shapes(records)
    write_binary(shapes, colors, roles, phases)
    normal_byte_count = write_normals(records)

    particle.remove_collection("04 | PARTICLE MORPH 512")
    particle_col = particle.collection("04 | PARTICLE MORPH 512")
    support_col = particle.collection("05 | PARTICLE SUPPORT 512")
    white_mat = particle.particle_material("Morph particle | cool white", (0.79, 0.82, 0.85), 0.63, 0.12)
    grey_mat = particle.particle_material("Morph particle | smoke grey", (0.34, 0.39, 0.42), 0.68, 0.04)
    red_mat = particle.particle_material("Morph particle | vermilion flags", (0.40, 0.018, 0.028), 0.58, 0.20)
    proto = particle.ico_prototype(support_col)
    white_points = [r["p"] for r, c in zip(records, colors) if c[0] > 0.6 and r["role"] != 2]
    grey_points = [r["p"] for r, c in zip(records, colors) if c[0] <= 0.6 and r["role"] != 2]
    red_points = [r["p"] for r in records if r["role"] == 2]
    white_ob = particle.mesh_points("Morph field | cool white 512", white_points, particle_col)
    grey_ob = particle.mesh_points("Morph field | smoke grey 512", grey_points, particle_col)
    red_ob = particle.mesh_points("Morph flags | vermilion 512", red_points, particle_col)
    particle.add_particle_geometry(white_ob, white_mat, proto, 0.011, "Morph white instances 512")
    particle.add_particle_geometry(grey_ob, grey_mat, proto, 0.008, "Morph grey instances 512")
    particle.add_particle_geometry(red_ob, red_mat, proto, 0.010, "Morph red flag instances 512")
    sculpt.hide_render = True
    particle_col["fixed_point_count"] = N
    particle_col["base_point_count"] = BASE_N
    particle_col["flag_point_count"] = sum(1 for role in roles if role == 2)
    particle_col["shape_targets"] = "A surface / B breathing / C ridge cloud / D disperse / E return"
    scene["morph_particle_ready"] = True
    scene["morph_particle_data"] = str(OUTPUT_BIN)
    scene["morph_particle_normals_data"] = str(OUTPUT_NORMALS)
    scene.frame_set(1)
    scene.render.filepath = str(OUTPUT_RENDER)
    bpy.ops.render.render(write_still=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT_BLEND))
    metadata = {
        "pointCount": N,
        "textureSize": "512x512",
        "basePointCount": BASE_N,
        "flagPointCount": particle_col["flag_point_count"],
        "shapeCount": 5,
        "shapeNames": ["surface", "breathing", "ridgeCloud", "disperse", "return"],
        "binary": str(OUTPUT_BIN),
        "normalsBinary": str(OUTPUT_NORMALS),
        "normalCount": N,
        "normalByteCount": normal_byte_count,
        "blend": str(OUTPUT_BLEND),
        "render": str(OUTPUT_RENDER),
        "sourceTriangles": {"rock": len(rock_tri), "figures": len(fig_tri)},
        "source": str(SOURCE),
        "colorPolicy": "cool gray-white body; vermilion only for flag role",
        "binaryLayout": {
            "endianness": "little",
            "positionShapeCount": 5,
            "positionFloatCount": 5 * N * 3,
            "colorFloatOffset": 5 * N * 3,
            "colorFloatCount": N * 4,
            "phaseFloatOffset": 5 * N * 3 + N * 4,
            "phaseFloatCount": N,
            "roleByteOffset": (5 * N * 3 + N * 4 + N) * 4,
            "roleByteCount": N,
            "roleValues": {"rock": 0, "figure": 1, "flag": 2},
        },
        "normalsBinaryLayout": {
            "endianness": "little",
            "coordinateSystem": "Blender world-space Z-up",
            "componentOrder": ["x", "y", "z"],
            "floatType": "Float32",
            "floatCount": N * 3,
            "byteCount": normal_byte_count,
            "recordStrideBytes": 3 * 4,
            "recordOrder": "same as points, colors, phases, and role masks",
        },
    }
    OUTPUT_META.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    print("MORPH_PARTICLE_READY", json.dumps(metadata, ensure_ascii=False))


if __name__ == "__main__":
    main()
