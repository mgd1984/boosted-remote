import argparse
import re
from collections import Counter
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


LAYER_FALLBACK_COLORS: dict[str, tuple[float, float, float, float]] = {
    "F_Cu": (0.784, 0.682, 0.161, 1.0),
    "B_Cu": (0.769, 0.090, 0.114, 1.0),
    "F_Silkscreen": (0.949, 0.929, 0.631, 1.0),
    "B_Silkscreen": (0.949, 0.929, 0.631, 1.0),
    "F_Mask": (0.129, 0.357, 0.278, 0.72),
    "B_Mask": (0.129, 0.357, 0.278, 0.72),
    "F_Paste": (0.772, 0.772, 0.772, 0.82),
    "B_Paste": (0.772, 0.772, 0.772, 0.82),
    "F_Adhesive": (0.733, 0.200, 0.800, 0.75),
    "B_Adhesive": (0.733, 0.200, 0.800, 0.75),
    "F_Courtyard": (1.000, 0.329, 0.961, 0.70),
    "B_Courtyard": (1.000, 0.329, 0.961, 0.70),
    "F_Fab": (0.830, 0.830, 0.830, 0.55),
    "B_Fab": (0.830, 0.830, 0.830, 0.55),
    "Edge_Cuts": (0.930, 0.930, 0.930, 1.0),
    "Margin": (0.650, 0.650, 0.650, 0.45),
    "User_Drawings": (0.500, 0.800, 1.000, 0.55),
    "User_Comments": (0.650, 0.650, 0.650, 0.45),
    "User_Eco1": (0.700, 1.000, 0.700, 0.50),
    "User_Eco2": (0.700, 1.000, 0.700, 0.50),
    "User_1": (0.950, 0.950, 0.950, 0.45),
    "User_2": (0.800, 0.900, 1.000, 0.45),
    "User_3": (1.000, 0.850, 0.650, 0.45),
    "User_4": (0.850, 1.000, 0.850, 0.45),
}

BOARD_3D_COLORS: dict[str, tuple[float, float, float, float]] = {
    "front_copper": (0.784, 0.682, 0.161, 1.0),
    "back_copper": (0.769, 0.090, 0.114, 1.0),
    "side_copper": (0.600, 0.350, 0.120, 1.0),
    "silkscreen": (0.949, 0.929, 0.631, 1.0),
    "soldermask": (0.080, 0.200, 0.140, 0.72),
    "substrate": (0.420, 0.450, 0.290, 1.0),
}


def layer_name_from_svg(svg_path: Path) -> str:
    stem = svg_path.stem
    return stem.split("-", 1)[1] if "-" in stem else stem


def hex_to_rgba(hex_color: str, alpha: float = 1.0) -> tuple[float, float, float, float]:
    value = hex_color.lstrip("#")
    return (
        int(value[0:2], 16) / 255.0,
        int(value[2:4], 16) / 255.0,
        int(value[4:6], 16) / 255.0,
        alpha,
    )


def infer_svg_rgba(svg_path: Path, layer_name: str) -> tuple[float, float, float, float]:
    svg_text = svg_path.read_text(encoding="utf-8")
    colors = [
        color.upper()
        for color in re.findall(r"#[0-9A-Fa-f]{6}", svg_text)
        if color.upper() != "#000000"
    ]
    if colors:
        dominant = Counter(colors).most_common(1)[0][0]
        alpha = LAYER_FALLBACK_COLORS.get(layer_name, (0.85, 0.85, 0.85, 1.0))[3]
        return hex_to_rgba(dominant, alpha=alpha)
    return LAYER_FALLBACK_COLORS.get(layer_name, (0.85, 0.85, 0.85, 1.0))


def layer_material(layer_name: str, rgba: tuple[float, float, float, float]) -> bpy.types.Material:
    material_name = f"KiCad::{layer_name}"
    material = bpy.data.materials.get(material_name)
    if material is None:
        material = bpy.data.materials.new(name=material_name)

    if hasattr(material, "use_nodes"):
        material.use_nodes = True
    material.diffuse_color = rgba
    if hasattr(material, "blend_method"):
        material.blend_method = "BLEND" if rgba[3] < 1.0 else "OPAQUE"
    if hasattr(material, "shadow_method"):
        material.shadow_method = "NONE"

    principled = None
    if material.use_nodes and material.node_tree is not None:
        principled = material.node_tree.nodes.get("Principled BSDF")
    if principled is not None:
        if "Base Color" in principled.inputs:
            principled.inputs["Base Color"].default_value = rgba
        if "Roughness" in principled.inputs:
            principled.inputs["Roughness"].default_value = 0.35
        if "Metallic" in principled.inputs:
            principled.inputs["Metallic"].default_value = 0.0
        if "Alpha" in principled.inputs:
            principled.inputs["Alpha"].default_value = rgba[3]

    return material


def rgba_socket_value(rgba: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    return rgba


def simple_board_material(
    material_name: str,
    rgba: tuple[float, float, float, float],
    *,
    metallic: float,
    roughness: float,
) -> bpy.types.Material:
    material = bpy.data.materials.get(material_name)
    if material is None:
        material = bpy.data.materials.new(name=material_name)
    if hasattr(material, "use_nodes"):
        material.use_nodes = True
    material.diffuse_color = rgba
    if hasattr(material, "blend_method"):
        material.blend_method = "BLEND" if rgba[3] < 1.0 else "OPAQUE"

    if material.node_tree is None:
        return material

    nodes = material.node_tree.nodes
    links = material.node_tree.links
    nodes.clear()

    output = nodes.new(type="ShaderNodeOutputMaterial")
    output.location = (300, 0)
    principled = nodes.new(type="ShaderNodeBsdfPrincipled")
    principled.location = (0, 0)
    principled.inputs["Base Color"].default_value = rgba_socket_value(rgba)
    principled.inputs["Metallic"].default_value = metallic
    principled.inputs["Roughness"].default_value = roughness
    if "Alpha" in principled.inputs:
        principled.inputs["Alpha"].default_value = rgba[3]
    links.new(principled.outputs[0], output.inputs[0])
    return material


def directional_copper_material() -> bpy.types.Material:
    material_name = "KiCad3D::Copper"
    material = bpy.data.materials.get(material_name)
    if material is None:
        material = bpy.data.materials.new(name=material_name)
    if hasattr(material, "use_nodes"):
        material.use_nodes = True
    material.diffuse_color = BOARD_3D_COLORS["front_copper"]
    if hasattr(material, "blend_method"):
        material.blend_method = "OPAQUE"

    if material.node_tree is None:
        return material

    nodes = material.node_tree.nodes
    links = material.node_tree.links
    nodes.clear()

    output = nodes.new(type="ShaderNodeOutputMaterial")
    output.location = (450, 0)
    principled = nodes.new(type="ShaderNodeBsdfPrincipled")
    principled.location = (150, 0)
    geometry = nodes.new(type="ShaderNodeNewGeometry")
    geometry.location = (-650, 0)
    separate_xyz = nodes.new(type="ShaderNodeSeparateXYZ")
    separate_xyz.location = (-450, 0)
    map_range = nodes.new(type="ShaderNodeMapRange")
    map_range.location = (-250, 0)
    color_ramp = nodes.new(type="ShaderNodeValToRGB")
    color_ramp.location = (-50, 0)

    map_range.inputs["From Min"].default_value = -1.0
    map_range.inputs["From Max"].default_value = 1.0
    map_range.inputs["To Min"].default_value = 0.0
    map_range.inputs["To Max"].default_value = 1.0
    map_range.clamp = True

    color_ramp.color_ramp.elements[0].position = 0.0
    color_ramp.color_ramp.elements[0].color = rgba_socket_value(BOARD_3D_COLORS["back_copper"])
    middle = color_ramp.color_ramp.elements.new(0.5)
    middle.color = rgba_socket_value(BOARD_3D_COLORS["side_copper"])
    color_ramp.color_ramp.elements[1].position = 1.0
    color_ramp.color_ramp.elements[1].color = rgba_socket_value(BOARD_3D_COLORS["front_copper"])

    principled.inputs["Metallic"].default_value = 0.75
    principled.inputs["Roughness"].default_value = 0.32

    links.new(geometry.outputs["Normal"], separate_xyz.inputs[0])
    links.new(separate_xyz.outputs["Z"], map_range.inputs[0])
    links.new(map_range.outputs[0], color_ramp.inputs[0])
    links.new(color_ramp.outputs["Color"], principled.inputs["Base Color"])
    links.new(principled.outputs[0], output.inputs[0])
    return material


def assign_material(obj: bpy.types.Object, material: bpy.types.Material) -> None:
    if not hasattr(obj.data, "materials"):
        return
    obj.data.materials.clear()
    obj.data.materials.append(material)


def style_board_meshes(objects: list[bpy.types.Object]) -> None:
    copper = directional_copper_material()
    silkscreen = simple_board_material(
        "KiCad3D::Silkscreen",
        BOARD_3D_COLORS["silkscreen"],
        metallic=0.0,
        roughness=0.55,
    )
    soldermask = simple_board_material(
        "KiCad3D::Soldermask",
        BOARD_3D_COLORS["soldermask"],
        metallic=0.0,
        roughness=0.40,
    )
    substrate = simple_board_material(
        "KiCad3D::Substrate",
        BOARD_3D_COLORS["substrate"],
        metallic=0.0,
        roughness=0.85,
    )

    for obj in objects:
        if obj.type != "MESH":
            continue
        mesh_name = obj.data.name
        if mesh_name in {"boosted_remote_copper", "boosted_remote_pad", "boosted_remote_via"}:
            assign_material(obj, copper)
        elif mesh_name.startswith("boosted_remote_silkscreen"):
            assign_material(obj, silkscreen)
        elif mesh_name.startswith("boosted_remote_soldermask"):
            assign_material(obj, soldermask)
        elif mesh_name == "boosted_remote_PCB":
            assign_material(obj, substrate)


def apply_layer_style(objects: list[bpy.types.Object], svg_path: Path) -> None:
    layer_name = layer_name_from_svg(svg_path)
    rgba = infer_svg_rgba(svg_path, layer_name)
    material = layer_material(layer_name, rgba)

    for obj in objects:
        obj.color = rgba
        if obj.type == "CURVE":
            obj.data.dimensions = "2D"
            obj.data.fill_mode = "BOTH"
        if hasattr(obj.data, "materials"):
            obj.data.materials.clear()
            obj.data.materials.append(material)


def configure_viewports() -> None:
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type != "VIEW_3D":
                continue
            for space in area.spaces:
                if space.type != "VIEW_3D":
                    continue
                space.shading.type = "MATERIAL"
                space.shading.color_type = "MATERIAL"


def import_glb(board_glb: Path, collection: bpy.types.Collection) -> list[bpy.types.Object]:
    before = set(bpy.data.objects.keys())
    bpy.ops.import_scene.gltf(filepath=str(board_glb))
    imported = imported_objects(before)
    relink_objects(imported, collection)
    style_board_meshes(imported)
    return imported


def import_svg(svg_path: Path, collection: bpy.types.Collection, z_offset: float) -> list[bpy.types.Object]:
    before = set(bpy.data.objects.keys())
    bpy.ops.import_curve.svg(filepath=str(svg_path))
    imported = imported_objects(before)
    for obj in imported:
        obj.location.z = z_offset
    relink_objects(imported, collection)
    apply_layer_style(imported, svg_path)
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

    configure_viewports()

    args.blend_out.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(args.blend_out))


if __name__ == "__main__":
    main()