"""Original monochrome climbing figures for the mountain sculpture benchmark.

The supplied exhibition video guides the visual vocabulary (compressed poses,
heavy garments, connected human gestures).  These are original meshes, not a
scan or a claim of exact reconstruction of the exhibited sculpture.

Public API: build_figures(parent, collection, material, surface_fn) -> objects.
Coordinates: uphill is +X; the audience is at -Y; Z is vertical.  ``surface_fn``
returns the actual sculpture surface elevation for world-space (x, y).
"""
import math
import random
import bpy
from mathutils import Vector


def build_figures(parent, collection, material, surface_fn):
    """Make 14 sculpted human studies attached to the supplied sculpture.

    Return the generated mesh/curve objects.  Each has an empty parent named
    ``Sculpted figure NN | pose`` parented to ``parent``.  The collection may be
    a bpy collection or a collection name.  No other scene object is modified.
    """
    if isinstance(collection, str):
        collection = bpy.data.collections.get(collection)
        if collection is None:
            raise ValueError("Sculpture figure collection does not exist")
    rng = random.Random(271927)
    generated = []

    def mesh(name, verts, faces, group):
        data = bpy.data.meshes.new(name)
        data.from_pydata(verts, [], faces)
        data.materials.append(material)
        data.update()
        ob = bpy.data.objects.new(name, data)
        collection.objects.link(ob)
        ob.parent = group
        generated.append(ob)
        return ob

    def curve(name, coords, thickness, group, cyclic=False):
        data = bpy.data.curves.new(name, "CURVE")
        data.dimensions = "3D"
        data.resolution_u = 2
        data.bevel_resolution = 1
        data.bevel_depth = thickness
        spline = data.splines.new("POLY")
        spline.points.add(len(coords) - 1)
        for p, co in zip(spline.points, coords):
            p.co = (*co, 1)
        spline.use_cyclic_u = cyclic
        data.materials.append(material)
        ob = bpy.data.objects.new(name, data)
        collection.objects.link(ob)
        ob.parent = group
        generated.append(ob)
        return ob

    def append_loft(verts, faces, centers, radii, radial=12, axis_hint=(0, 1, 0), phase=0):
        """A continuous, tapered cloth/anatomical volume, with closed ends."""
        begin = len(verts)
        centers = [Vector(p) for p in centers]
        hint = Vector(axis_hint)
        for j, c in enumerate(centers):
            tangent = centers[min(j + 1, len(centers) - 1)] - centers[max(0, j - 1)]
            if tangent.length < 1e-6:
                tangent = Vector((0, 0, 1))
            tangent.normalize()
            side = hint - tangent * hint.dot(tangent)
            if side.length < 0.1:
                side = Vector((1, 0, 0)) - tangent * tangent.x
            side.normalize()
            front = tangent.cross(side).normalized()
            r_side, r_front = radii[j]
            for k in range(radial):
                theta = 2 * math.pi * k / radial
                # Irregular garment cross sections survive remeshing as broad
                # sculptor's planes rather than cylindrical stick limbs.
                wrinkle = 1 + .055 * math.sin(theta * 3 + j * 1.4 + phase)
                co = c + side * (math.cos(theta) * r_side * wrinkle)
                co += front * (math.sin(theta) * r_front * wrinkle)
                verts.append(tuple(co))
        for j in range(len(centers) - 1):
            for k in range(radial):
                a = begin + j * radial + k
                b = begin + j * radial + (k + 1) % radial
                c = begin + (j + 1) * radial + (k + 1) % radial
                d = begin + (j + 1) * radial + k
                faces.append((a, b, c, d))
        faces.append(tuple(begin + k for k in range(radial - 1, -1, -1)))
        last = begin + (len(centers) - 1) * radial
        faces.append(tuple(last + k for k in range(radial)))

    def ellipsoid(verts, faces, center, scale, rings=9, segments=12, rough=0.04):
        """Softly faceted anatomically scaled volume; only used inside union."""
        base = len(verts)
        for j in range(rings + 1):
            lat = -math.pi / 2 + math.pi * j / rings
            for k in range(segments):
                ang = 2 * math.pi * k / segments
                n = 1 + rough * math.sin(k * 2.1 + j * 3.3)
                verts.append((center[0] + scale[0] * math.cos(lat) * math.cos(ang) * n,
                              center[1] + scale[1] * math.cos(lat) * math.sin(ang) * n,
                              center[2] + scale[2] * math.sin(lat)))
        for j in range(rings):
            for k in range(segments):
                a = base + j * segments + k
                b = base + j * segments + (k + 1) % segments
                faces.append((a, b, b + segments, a + segments))

    def union_body(name, verts, faces, group):
        ob = mesh(name, verts, faces, group)
        bpy.ops.object.select_all(action="DESELECT")
        ob.select_set(True)
        bpy.context.view_layer.objects.active = ob
        # Voxel union removes primitive intersections, crucial for sculptural
        # rather than assembled toy silhouettes.  Keep fine details separate.
        remesh = ob.modifiers.new("Continuous hand-modelled clay", "REMESH")
        remesh.mode = "VOXEL"
        remesh.voxel_size = .025
        remesh.use_smooth_shade = True
        try:
            bpy.ops.object.modifier_apply(modifier=remesh.name)
        except Exception:
            ob.modifiers.remove(remesh)
        smooth = ob.modifiers.new("Broad sculpting strokes", "SMOOTH")
        smooth.factor = .48
        smooth.iterations = 2
        bpy.ops.object.modifier_apply(modifier=smooth.name)
        dec = ob.modifiers.new("Carved low-mid-poly planes", "DECIMATE")
        dec.ratio = .62
        bpy.ops.object.modifier_apply(modifier=dec.name)
        # Subtle low-frequency vertex variation evokes clay/tool-work without
        # making the heads or hands into noisy pebbles.
        for v in ob.data.vertices:
            co = v.co
            d = .006 * math.sin(co.x * 24.3 + co.z * 17.1) * math.sin(co.y * 23.7 - co.z * 13.3)
            v.co += v.normal * d
        for p in ob.data.polygons:
            p.use_smooth = True
        return ob

    def blob(name, center, scale, group, rough=.035):
        v, f = [], []
        ellipsoid(v, f, center, scale, rings=7, segments=12, rough=rough)
        return mesh(name, v, f, group)

    def ribbon(name, points, width, group):
        verts, faces = [], []
        for co in points:
            verts.extend([(co[0], co[1] - width / 2, co[2]),
                          (co[0], co[1] + width / 2, co[2])])
        for j in range(len(points) - 1):
            faces.append((j*2, j*2+1, j*2+3, j*2+2))
        ob = mesh(name, verts, faces, group)
        thick = ob.modifiers.new("Cast strap thickness", "SOLIDIFY")
        thick.thickness = .014
        return ob

    def pose_points(kind):
        """Figure coordinates are uphill X, transverse Y, above ground Z."""
        if kind in ("climb", "reach", "helper"):
            hip = Vector((-.02, 0, .74))
            chest = Vector((.24, 0, 1.10))
            head = Vector((.41, -.018, 1.39))
            legs = [((-.38,-.125,-.09),(-.25,-.14,.34)),
                    ((.31,.12,.17),(.40,.13,.51))]
            arms = [((.26,-.245,1.09),(.57,-.30,.92),(.84,-.28,1.10)),
                    ((.25,.24,1.09),(.59,.29,1.20),(.78,.26,1.39))]
            if kind == "helper":
                arms[0] = ((.24,-.245,1.09),(-.11,-.37,1.00),(-.56,-.44,.92))
            if kind == "reach":
                arms[1] = ((.25,.24,1.09),(.50,.30,1.40),(.72,.25,1.59))
        elif kind in ("kneel", "support"):
            hip = Vector((-.15,0,.45)); chest = Vector((.03,0,.86)); head = Vector((.17,-.02,1.16))
            legs = [((-.54,-.15,-.16),(-.10,-.17,.10)),
                    ((.43,.14,.20),(.35,.16,.50))]
            arms = [((.02,-.245,.85),(.23,-.35,.61),(.58,-.34,.41)),
                    ((.02,.24,.85),(.30,.33,.98),(.58,.26,1.12))]
            if kind == "support":
                arms[0]=((.02,-.245,.85),(.35,-.42,.91),(.74,-.50,1.12))
        elif kind == "crawl":
            hip = Vector((-.38,0,.37)); chest = Vector((.07,0,.58)); head = Vector((.40,-.03,.79))
            legs = [((-.89,-.17,-.29),(-.52,-.20,.04)),
                    ((-.63,.16,-.20),(-.15,.19,.10))]
            arms = [((.06,-.245,.56),(.38,-.37,.41),(.73,-.32,.35)),
                    ((.06,.24,.56),(.41,.32,.70),(.71,.22,.83))]
        elif kind == "recline":
            hip=Vector((-.05,0,.26)); chest=Vector((.38,0,.56)); head=Vector((.64,-.035,.86))
            legs=[((-.87,-.18,-.27),(-.48,-.16,.06)),
                  ((-.70,.13,-.22),(-.40,.18,.13))]
            arms=[((.36,-.22,.54),(.05,-.28,.39),(-.10,-.22,.38)),
                  ((.36,.22,.54),(.62,.29,.36),(.83,.24,.32))]
        elif kind == "seated":
            hip=Vector((-.10,0,.31)); chest=Vector((.04,0,.75)); head=Vector((.13,-.035,1.04))
            legs=[((.68,-.18,.30),(.33,-.20,.37)),
                  ((.41,.16,.21),(.19,.23,.62))]
            arms=[((.03,-.24,.73),(.24,-.32,.56),(.51,-.28,.47)),
                  ((.03,.24,.73),(-.17,.31,.51),(-.24,.33,.21))]
        else: # Braced standing figure, never an upright marching toy.
            hip=Vector((-.02,0,.76)); chest=Vector((.10,0,1.18)); head=Vector((.20,-.02,1.49))
            legs=[((-.32,-.13,-.08),(-.23,-.15,.36)),
                  ((.28,.12,.15),(.17,.14,.48))]
            arms=[((.10,-.24,1.16),(.37,-.34,.95),(.63,-.28,1.02)),
                  ((.10,.24,1.16),(-.07,.31,.94),(-.04,.25,.76))]
        return hip, chest, head, legs, arms

    # Two close pairs are helper/support (NN 03/04 and 09/10); the remaining
    # figures alternate climbing, exhausted low poses, and high silhouettes.
    specs = [
        (-5.70,-.05,"crawl",1.12), (-4.65,-.35,"reach",1.10),
        (-3.47,-.18,"support",1.08), (-2.69,.25,"helper",1.03),
        (-1.47,-.55,"recline",1.02), (-.36,.25,"kneel",1.02),
        (.76,-.40,"climb",1.08), (1.84,.35,"seated",1.04),
        (2.84,-.35,"support",1.08), (3.64,.40,"helper",1.05),
        (4.66,-.35,"crawl",1.08), (5.64,.35,"reach",1.06),
        (6.64,-.25,"kneel",1.08), (7.70,.55,"stand",1.04),
    ]

    roots = []
    for index, (world_x, world_y, kind, scale) in enumerate(specs, 1):
        root = bpy.data.objects.new("Sculpted figure %02d | %s" % (index, kind), None)
        collection.objects.link(root)
        root.parent = parent
        root.location = (world_x, world_y, surface_fn(world_x, world_y) - .025)
        root.scale = (scale, scale, scale)
        root["pose"] = kind
        root["original_geometry"] = True
        roots.append(root)
        hip, chest, head, legs, arms = pose_points(kind)
        verts, faces = [], []

        # Cloth torso is one irregular loft with a flared coat skirt, cinched
        # waist, broad sloped shoulder and narrow neck.  It reads as heavy
        # folded garments even before the detail strokes below are added.
        waist = hip.lerp(chest, .40)
        neck = chest.lerp(head, .55)
        hem = hip + Vector((-.025,0,-.12))
        append_loft(verts, faces, [hem,hip,waist,chest,neck],
                    [(.245,.17),(.22,.16),(.19,.155),(.275,.18),(.105,.11)],
                    14, phase=index*.35)
        append_loft(verts, faces, [neck,head-Vector((.015,0,.10))],
                    [(.105,.10),(.091,.083)], 12)

        # Head volume has a flattened face plane, jaw, brows and cheek volume
        # in the same remesh; no face-coloured inserts are used.
        h = head
        append_loft(verts, faces,
            [(h.x-.005,h.y,h.z-.17),(h.x+.015,h.y,h.z-.105),
             (h.x,h.y,h.z-.015),(h.x-.035,h.y,h.z+.095),
             (h.x-.048,h.y,h.z+.145)],
            [(.057,.074),(.085,.104),(.110,.122),(.098,.110),(.05,.065)],
            14, axis_hint=(0,1,0), phase=index)
        # Subtle projected nose and chin, melted into the head rather than
        # separate bead shapes; the profile is important in camera-side view.
        ellipsoid(verts,faces,(h.x+.125,h.y-.006,h.z-.015),(.067,.04,.052),6,10,.02)
        ellipsoid(verts,faces,(h.x+.083,h.y,h.z-.112),(.060,.065,.037),6,10,.02)

        for side, (foot, knee) in zip((-1,1), legs):
            foot = Vector(foot); knee = Vector(knee)
            # Bind each planted boot to the actual rock surface, including
            # local shape variations, and let the foot sink a few millimetres.
            foot.z = (surface_fn(world_x + foot.x*scale, world_y + foot.y*scale)
                      - root.location.z) / scale + .015
            thigh_start = hip + Vector((0,side*.115,-.015))
            ankle = foot + Vector((-.025,0,.065))
            append_loft(verts,faces,[thigh_start,thigh_start.lerp(knee,.44),knee,knee.lerp(ankle,.48),ankle],
                        [(.115,.13),(.125,.145),(.103,.11),(.090,.095),(.067,.065)],
                        12, phase=index+side)
            ellipsoid(verts,faces,(foot.x+.045,foot.y,foot.z+.060),(.17,.088,.074),7,12,.04)
            # A shallow irregular clay collar is part of the body union.  It
            # sinks into the measured rock surface and removes the visible
            # pin-gap that otherwise appears below a boot in white-film
            # close-ups.  Keeping it in the voxel union avoids another loose
            # rock object and adds only a few hundred source vertices per
            # figure.
            ellipsoid(verts,faces,(foot.x+.030,foot.y,foot.z-.032),
                      (.155,.096,.058),7,12,.055)
            # Puttee ridges, irregular and few, remain a relief on the shin.
            for frac in (.30,.46,.62):
                q = ankle.lerp(knee,frac)
                curve("Figure %02d | cloth leg binding"%index,
                    [(q.x-.02,q.y-.093,q.z-.016),(q.x+.085,q.y-.045,q.z),
                     (q.x+.087,q.y+.025,q.z+.019)],.014,root)

        for arm_index, (shoulder, elbow, hand) in enumerate(arms):
            shoulder,elbow,hand = Vector(shoulder),Vector(elbow),Vector(hand)
            # Shift shoulders with the coat, then taper from broad sleeve to
            # a flattened glove.  At least three continuous bands per limb.
            append_loft(verts,faces,[shoulder,shoulder.lerp(elbow,.5),elbow,elbow.lerp(hand,.55),hand],
                        [(.115,.115),(.12,.117),(.092,.103),(.074,.079),(.055,.049)],
                        12, axis_hint=(0,0,1), phase=index*.3+arm_index)
            ellipsoid(verts,faces,hand,(.088,.058,.050),7,12,.02)
            # Fingertip grooves are slim casts on a palm, not five sticks.
            for finger in range(3):
                yy = hand.y-.036+finger*.025
                curve("Figure %02d | glove crease"%index,
                      [(hand.x+.02,yy,hand.z+.041),(hand.x+.071,yy,hand.z+.024)],.007,root)

        body = union_body("Figure %02d | united clay body" % index,verts,faces,root)

        # Crushed angular service cap and sculpted brim, same clay.  Its crown
        # is a closed custom loft, not the ball + disk of the previous study.
        cv,cf=[],[]
        append_loft(cv,cf,[(h.x-.035,h.y,h.z+.080),(h.x-.052,h.y,h.z+.153),
                          (h.x-.07,h.y,h.z+.177)],
                    [(.124,.133),(.109,.122),(.070,.075)],12,phase=index*.5)
        cap=mesh("Figure %02d | crushed cloth cap"%index,cv,cf,root)
        brimv=[(h.x+.036,h.y-.12,h.z+.100),(h.x+.175,h.y-.091,h.z+.087),
               (h.x+.184,h.y+.078,h.z+.084),(h.x+.038,h.y+.116,h.z+.098),
               (h.x+.03,h.y-.11,h.z+.079),(h.x+.17,h.y-.08,h.z+.073),
               (h.x+.174,h.y+.072,h.z+.070),(h.x+.03,h.y+.106,h.z+.078)]
        mesh("Figure %02d | folded cap brim"%index,brimv,
             [(0,1,2,3),(4,7,6,5),(0,4,5,1),(1,5,6,2),(2,6,7,3),(3,7,4,0)],root)
        # Facial relief: brows, narrow mouth, cheek ridges and an ear visible
        # from the audience side.  All are monochrome and deliberately coarse.
        curve("Figure %02d | brow ridge"%index,
              [(h.x+.064,h.y-.091,h.z+.044),(h.x+.111,h.y-.074,h.z+.031),
               (h.x+.136,h.y-.038,h.z+.029)],.011,root)
        curve("Figure %02d | set mouth"%index,
              [(h.x+.11,h.y-.041,h.z-.084),(h.x+.121,h.y,h.z-.088),
               (h.x+.106,h.y+.035,h.z-.084)],.007,root)
        blob("Figure %02d | sculpted ear"%index,(h.x-.033,h.y-.111,h.z-.029),(.035,.020,.052),root)

        # Backpack: continuous lumpy sack plus rolled blanket.  Its shape
        # intersects the upper back, echoing cast clay in the museum reference.
        back = chest + Vector((-.235,0,-.065))
        pv,pf=[],[]
        append_loft(pv,pf,[back+Vector((-.025,0,-.23)),back+Vector((-.04,0,-.14)),
                           back+Vector((-.05,0,.12)),back+Vector((-.018,0,.205))],
                    [(.13,.074),(.198,.106),(.185,.11),(.12,.072)],12,phase=index)
        pack = mesh("Figure %02d | cast canvas pack"%index,pv,pf,root)
        rv,rf=[],[]
        append_loft(rv,rf,[back+Vector((-.035,-.245,.24)),back+Vector((-.04,-.18,.245)),
                           back+Vector((-.045,.18,.238)),back+Vector((-.025,.24,.225))],
                    [(.079,.076),(.087,.084),(.087,.084),(.06,.068)],12,
                    axis_hint=(0,0,1),phase=index)
        mesh("Figure %02d | rolled blanket"%index,rv,rf,root)
        for side in (-1,1):
            shoulder = chest+Vector((-.02,side*.18,.055))
            front = chest+Vector((.16,side*.17,-.07))
            lower = waist+Vector((.14,side*.15,-.03))
            curve("Figure %02d | shoulder strap"%index,[shoulder,front,lower],.022,root)
        curve("Figure %02d | blanket binding"%index,
              [back+Vector((.038,-.15,.245)),back+Vector((.045,-.15,.292)),
               back+Vector((-.063,-.15,.324)),back+Vector((-.128,-.15,.248))],.012,root)

        # Hand-cut fold ridges emphasize the direction of pull and the bent
        # spine.  These are shallow clay strokes, not high-contrast stripes.
        for k in range(5):
            frac=.18+k*.135
            c=hip.lerp(chest,frac)
            zoff=.015*math.sin(k*2+index)
            coords=[(c.x+.12,c.y-.22,c.z-.055+zoff),
                    (c.x+.155,c.y-.12,c.z-.018+zoff),
                    (c.x+.177,c.y-.02,c.z+.026+zoff)]
            curve("Figure %02d | pulled coat fold"%index,coords,.014 if k%2 else .018,root)
        # Coat skirt panels are triangular and broad; they merge visually into
        # the mountain at the lower silhouettes instead of floating above it.
        skv=[tuple(hem+Vector((.10,-.23,.04))),tuple(hem+Vector((-.17,-.20,-.10))),
             tuple(hem+Vector((-.26,.05,-.15))),tuple(hem+Vector((-.05,.24,-.06))),
             tuple(hip+Vector((.1,.22,.15)))]
        skirt=mesh("Figure %02d | torn coat hem"%index,skv,[(0,1,2),(0,2,3),(0,3,4)],root)
        thick=skirt.modifiers.new("Clay coat thickness","SOLIDIFY");thick.thickness=.025

        # Selective staff / slung equipment supplies the long diagonal accents
        # visible in the reference without bright flags or modern insignia.
        if kind in ("stand","reach","climb"):
            hand=Vector(arms[0][2])
            staff_bottom=Vector((hand.x+.09,hand.y-.015,0))
            staff_bottom.z=(surface_fn(world_x+staff_bottom.x*scale,world_y+staff_bottom.y*scale)-root.location.z)/scale-.02
            curve("Figure %02d | mountain staff"%index,
                  [staff_bottom,hand,hand+Vector((-.045,0,.25))],.019,root)
        if index in (2,7,10,14):
            # Anonymous period-equipment silhouette; no mechanism or emblem.
            curve("Figure %02d | slung long equipment"%index,
                  [back+Vector((-.15,.18,-.29)),back+Vector((-.13,.18,.45)),
                   back+Vector((-.10,.18,.71))],.020,root)
            blob("Figure %02d | equipment stock"%index,
                 back+Vector((-.15,.18,-.20)),(.046,.036,.18),root,.02)

    # Shared cast-clay connecting gestures across the two pairs: a reaching
    # sleeve overlaps the partner's shoulder so the figures read as support.
    for a,b in ((2,3),(8,9)):
        lower,upper=roots[a],roots[b]
        # Build at the top sculpture level in world coordinates.  Parenting to
        # the Sculpture root keeps all figures part of this one art object.
        start=lower.location+Vector((.50,-.31,1.03))*lower.scale.x
        end=upper.location+Vector((-.13,-.29,1.04))*upper.scale.x
        mid=start.lerp(end,.50)+Vector((0,-.035,.045))
        if (end-start).length < 1.0:
            curve("Sculpture | joined helping gesture",[start,mid,end],.036,parent)

    for ob in generated:
        ob["sculpture_component"] = "original monochrome human relief"
    print("SCULPTED_FIGURES_COMPLETE",len(roots),len(generated))
    return generated
