import argparse
from pathlib import Path

import bpy


def parse_args() -> argparse.Namespace:
    argv = []
    if "--" in __import__("sys").argv:
        argv = __import__("sys").argv[__import__("sys").argv.index("--") + 1 :]
    parser = argparse.ArgumentParser(description="Import KiCad board assets into a Blender scene.")
    parser.add_argument("--board-glb", type=Path, required=True)
    parser.add_argument("--layers-dir", type=Path, required=True)
    parser.add_argument("--blend-out", type=Path, required=True)
    parser.add_argument("--shell-glb", type=Path)
    return parser.parse_args(argv)


def ensure_addon(module: str) -> None:
    try:
        bpy.ops.preferences.addon_enable(module=module)
    except Exception:
        pass


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)

    for datablock_collection in (
        bpy.data.meshes,
        bpy.data.curves,
        bpy.data.materials,
        bpy.data.cameras,
        bpy.data.lights,
        bpy.data.images,
    ):
        for datablock in list(datablock_collection):
            if datablock.users == 0:
                datablock_collection.remove(datablock)


def new_collection(name: str) -> bpy.types.Collection:
    collection = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(collection)
    return collection


def relink_objects(objects: list[bpy.types.Object], collection: bpy.types.Collection) -> None:
    for obj in objects:
        for existing in list(obj.users_collection):
            existing.objects.unlink(obj)
        collection.objects.link(obj)


def imported_objects(before_names: set[str]) -> list[bpy.types.Object]:
    return [obj for obj in bpy.data.objects if obj.name not in before_names]


def import_glb(board_glb: Path, collection: bpy.types.Collection) -> list[bpy.types.Object]:
    before = set(bpy.data.objects.keys())
    bpy.ops.import_scene.gltf(filepath=str(board_glb))
    imported = imported_objects(before)
    relink_objects(imported, collection)
    return imported


def import_svg(svg_path: Path, collection: bpy.types.Collection, z_offset: float) -> list[bpy.types.Object]:
    before = set(bpy.data.objects.keys())
    bpy.ops.import_curve.svg(filepath=str(svg_path))
    imported = imported_objects(before)
    for obj in imported:
        obj.location.z = z_offset
    relink_objects(imported, collection)
    return imported


def main() -> None:
    args = parse_args()
    ensure_addon("io_scene_gltf2")
    ensure_addon("io_curve_svg")

    bpy.ops.wm.read_factory_settings(use_empty=True)
    clear_scene()

    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0

    board_collection = new_collection("Board3D")
    layers_root = new_collection("KiCadLayers")
    shell_collection = new_collection("Enclosure")

    import_glb(args.board_glb, board_collection)

    if args.shell_glb is not None and args.shell_glb.exists():
        import_glb(args.shell_glb, shell_collection)

    layer_paths = sorted(args.layers_dir.glob("*.svg"))
    for index, svg_path in enumerate(layer_paths):
        layer_collection = bpy.data.collections.new(svg_path.stem)
        layers_root.children.link(layer_collection)
        import_svg(svg_path, layer_collection, z_offset=0.001 * (index + 1))

    args.blend_out.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(args.blend_out))


if __name__ == "__main__":
    main()