import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def parse_args():
    argv = []
    if "--" in sys.argv:
        argv = sys.argv[sys.argv.index("--") + 1 :]
    parser = argparse.ArgumentParser(description="Sample cross sections from the Boosted remote proxy GLB.")
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--glb", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--slice-step-mm", type=float, default=8.0)
    parser.add_argument("--slice-band-mm", type=float, default=1.0)
    return parser.parse_args(argv)


def clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def load_params(repo_root: Path):
    params = json.loads((repo_root / "config" / "remote_params.json").read_text(encoding="utf-8"))
    return params["mechanical"]


def select_only(objects):
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]


def world_bounds(obj):
    corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    mins = Vector((min(v.x for v in corners), min(v.y for v in corners), min(v.z for v in corners)))
    maxs = Vector((max(v.x for v in corners), max(v.y for v in corners), max(v.z for v in corners)))
    return mins, maxs


def apply_transform(obj, *, apply_location=True):
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=apply_location, rotation=True, scale=True)


def align_top_center(obj):
    mins, maxs = world_bounds(obj)
    obj.location.x -= (mins.x + maxs.x) * 0.5
    obj.location.y -= (mins.y + maxs.y) * 0.5
    obj.location.z -= maxs.z
    apply_transform(obj)


def fit_proxy_to_target(obj, mech):
    mins, maxs = world_bounds(obj)
    dims_mm = (maxs - mins) * 1000.0
    target_dims = Vector((mech["outer_width_top_mm"], mech["outer_thickness_mm"], mech["outer_height_mm"]))
    obj.scale = (
        target_dims.x / dims_mm.x,
        target_dims.y / dims_mm.y,
        target_dims.z / dims_mm.z,
    )
    apply_transform(obj, apply_location=False)
    align_top_center(obj)


def import_proxy(glb_path: Path):
    bpy.ops.import_scene.gltf(filepath=str(glb_path))
    imported = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    if not imported:
        raise RuntimeError(f"No mesh objects imported from {glb_path}")
    if len(imported) > 1:
        select_only(imported)
        bpy.ops.object.join()
        obj = bpy.context.active_object
    else:
        obj = imported[0]
    obj.name = "proxy_body"
    return obj


def triangle_plane_points(mesh_obj, z_plane_m):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    eval_obj = mesh_obj.evaluated_get(depsgraph)
    mesh = eval_obj.to_mesh()
    mesh.calc_loop_triangles()
    vertices = [eval_obj.matrix_world @ vertex.co for vertex in mesh.vertices]
    points = []
    for tri in mesh.loop_triangles:
        tri_vertices = [vertices[index] for index in tri.vertices]
        intersections = []
        for start, end in ((tri_vertices[0], tri_vertices[1]), (tri_vertices[1], tri_vertices[2]), (tri_vertices[2], tri_vertices[0])):
            z1 = start.z - z_plane_m
            z2 = end.z - z_plane_m
            if abs(z1) < 1e-9 and abs(z2) < 1e-9:
                intersections.extend([start, end])
                continue
            if abs(z1) < 1e-9:
                intersections.append(start)
                continue
            if abs(z2) < 1e-9:
                intersections.append(end)
                continue
            if z1 * z2 > 0:
                continue
            t = (z_plane_m - start.z) / (end.z - start.z)
            intersections.append(start.lerp(end, t))
        if len(intersections) >= 2:
            points.extend(intersections[:2])
    eval_obj.to_mesh_clear()
    return points


def sample_sections(mesh_obj, mech, slice_step_mm, slice_band_mm):
    stations = []
    total_height = mech["outer_height_mm"]
    z_values = []
    z_mm = 0.0
    while z_mm <= total_height + 0.001:
        z_values.append(round(z_mm, 3))
        z_mm += slice_step_mm
    if z_values[-1] != total_height:
        z_values.append(float(total_height))
    for z_from_top_mm in z_values:
        z_world_m = -z_from_top_mm / 1000.0
        points = triangle_plane_points(mesh_obj, z_world_m)
        if len(points) < 2:
            continue
        xs = [point.x * 1000.0 for point in points]
        ys = [point.y * 1000.0 for point in points]
        stations.append(
            {
                "z_from_top_mm": round(z_from_top_mm, 3),
                "width_mm": round(max(xs) - min(xs), 3),
                "thickness_mm": round(max(ys) - min(ys), 3),
                "sample_count": len(points),
                "slice_band_mm": slice_band_mm,
            }
        )
    return stations


def main():
    args = parse_args()
    mech = load_params(args.repo_root)
    clear_scene()
    proxy = import_proxy(args.glb)
    fit_proxy_to_target(proxy, mech)
    mins, maxs = world_bounds(proxy)
    dims_mm = (maxs - mins) * 1000.0
    stations = sample_sections(proxy, mech, args.slice_step_mm, args.slice_band_mm)
    payload = {
        "proxy_glb": str(args.glb),
        "fitted_dims_mm": [round(value, 3) for value in dims_mm],
        "stations": stations,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(args.out)


if __name__ == "__main__":
    main()