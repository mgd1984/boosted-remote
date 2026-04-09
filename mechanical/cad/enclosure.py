from __future__ import annotations

import importlib.util
import json
import sys
import types
from dataclasses import dataclass
from pathlib import Path

from .params import MechanicalParams, RemoteProjectData
from .reference import board_outline_points, horizontal_polygon_span, preferred_shell_contour_points, shell_xz_from_board


USB_PORT_CUT_CENTER_OFFSET_MM = 3.5


@dataclass(frozen=True)
class EnclosureArtifacts:
    outer_body: object
    full_shell: object
    front_shell: object
    rear_shell: object
    pcb_envelope: object


def _subtract_all(base_shape, cutters, part_factory=None):
    result = base_shape
    for cutter in cutters:
        result = result - cutter
        if part_factory is not None and hasattr(result, "wrapped"):
            result = part_factory(result.wrapped)
    return result


def _import_build123d():
    try:
        if importlib.util.find_spec("ezdxf.acc") is None:
            acc_module = types.ModuleType("ezdxf.acc")
            acc_module.USE_C_EXT = False
            sys.modules["ezdxf.acc"] = acc_module
        from ezdxf.entities.xdict import ExtensionDict
        from build123d import Box, Circle, Cylinder, Locations, Plane, Polyline, Pos, Rectangle, Rot, Sketch
        from build123d import CounterBoreHole, Hole, Mode, Part, extrude, fillet, loft, make_face, offset
        _ = ExtensionDict
        return {
            "Box": Box,
            "Circle": Circle,
            "CounterBoreHole": CounterBoreHole,
            "Cylinder": Cylinder,
            "Hole": Hole,
            "Locations": Locations,
            "Mode": Mode,
            "Part": Part,
            "Plane": Plane,
            "Polyline": Polyline,
            "Pos": Pos,
            "Rectangle": Rectangle,
            "Rot": Rot,
            "Sketch": Sketch,
            "extrude": extrude,
            "fillet": fillet,
            "loft": loft,
            "make_face": make_face,
            "offset": offset,
        }
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "build123d is required for enclosure generation. Install requirements-mechanical.txt first."
        ) from exc


def _rounded_profile(api, width_mm: float, thickness_mm: float, radius_mm: float):
    Rectangle = api["Rectangle"]
    fillet = api["fillet"]
    sketch = Rectangle(width_mm, thickness_mm)
    return fillet(sketch.vertices(), radius_mm)


def _default_profile_stations(mech: MechanicalParams) -> list[tuple[float, float, float, float, float]]:
    body_end = -mech.outer_height_mm
    return [
        (0.0, 0.0, mech.outer_width_top_mm * 0.76, mech.outer_thickness_mm * 0.74, 5.5),
        (-mech.top_bulb_height_mm * 0.42, 0.0, mech.outer_width_top_mm, mech.outer_thickness_mm, 8.0),
        (-mech.top_bulb_height_mm, 0.0, mech.outer_width_top_mm * 0.88, mech.outer_thickness_mm * 0.92, 7.0),
        (-(mech.top_bulb_height_mm + mech.grip_height_mm * 0.45), 0.0, mech.outer_width_grip_mm * 1.08, mech.outer_thickness_mm * 0.86, 6.2),
        (-(mech.top_bulb_height_mm + mech.grip_height_mm * 0.82), 0.0, mech.outer_width_grip_mm * 0.94, mech.outer_thickness_mm * 0.78, 5.2),
        (body_end + 12.0, 0.0, mech.outer_width_grip_mm * 0.72, mech.outer_thickness_mm * 0.58, 4.2),
        (body_end, 0.0, mech.outer_width_grip_mm * 0.52, mech.outer_thickness_mm * 0.42, 3.2),
    ]


def _proxy_sections_path(root: Path) -> Path:
    return root / "tmp" / "proxy_sections.json"


def _radius_for_station(width_mm: float, thickness_mm: float) -> float:
    return max(min(thickness_mm * 0.42, width_mm * 0.24, 8.5), 1.8)


def _proxy_profile_stations(project: RemoteProjectData) -> list[tuple[float, float, float, float, float]] | None:
    path = _proxy_sections_path(project.root)
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    stations = []
    for entry in payload.get("stations", []):
        width_mm = float(entry["width_mm"])
        thickness_mm = float(entry["thickness_mm"])
        z_from_top_mm = float(entry["z_from_top_mm"])
        if width_mm < 8.0 or thickness_mm < 4.0:
            continue
        stations.append(
            (
                -z_from_top_mm,
                0.0,
                width_mm,
                thickness_mm,
                _radius_for_station(width_mm, thickness_mm),
            )
        )

    if len(stations) < 5:
        return None

    # Add small cap stations so the loft closes more naturally at the nose and tail.
    first_z, _, first_width, first_thickness, _ = stations[0]
    last_z, _, last_width, last_thickness, _ = stations[-1]
    nose_station = (first_z + 6.0, 0.0, max(first_width * 0.88, 18.0), max(first_thickness * 0.55, 6.0), _radius_for_station(max(first_width * 0.88, 18.0), max(first_thickness * 0.55, 6.0)))
    tail_station = (-project.mechanical.outer_height_mm, 0.0, max(last_width * 0.45, 10.0), max(last_thickness * 0.45, 4.0), _radius_for_station(max(last_width * 0.45, 10.0), max(last_thickness * 0.45, 4.0)))
    return [nose_station, *stations, tail_station]


def _apply_user1_contour_to_stations(project: RemoteProjectData, stations: list[tuple[float, float, float, float, float]]) -> list[tuple[float, float, float, float, float]]:
    contour = preferred_shell_contour_points(project.root, project.mechanical)
    shaped: list[tuple[float, float, float, float, float]] = []
    for z_mm, x_center_mm, width_mm, thickness_mm, radius_mm in stations:
        span = horizontal_polygon_span(z_mm, contour)
        if span is None:
            shaped.append((z_mm, x_center_mm, width_mm, thickness_mm, radius_mm))
            continue
        min_x_mm, max_x_mm = span
        contour_width_mm = max_x_mm - min_x_mm
        contour_center_mm = (min_x_mm + max_x_mm) * 0.5
        shaped.append(
            (
                z_mm,
                contour_center_mm,
                max(contour_width_mm + 1.2, width_mm),
                thickness_mm,
                _radius_for_station(max(contour_width_mm, width_mm), thickness_mm),
            )
        )
    return shaped


def _profile_stations(project: RemoteProjectData) -> list[tuple[float, float, float, float, float]]:
    proxy = _proxy_profile_stations(project)
    base = proxy if proxy is not None else _default_profile_stations(project.mechanical)
    return _apply_user1_contour_to_stations(project, base)


def _build_lofted_body(api, stations: list[tuple[float, float, float, float, float]]):
    Plane = api["Plane"]
    Pos = api["Pos"]
    Sketch = api["Sketch"]
    loft = api["loft"]

    profiles = Sketch() + [
        Plane.XY.offset(z_mm) * Pos(x_center_mm, 0, 0) * _rounded_profile(api, width_mm, thickness_mm, radius_mm)
        for z_mm, x_center_mm, width_mm, thickness_mm, radius_mm in stations
    ]
    return loft(profiles)


def _build_user1_contour_prism(api, project: RemoteProjectData):
    Plane = api["Plane"]
    Polyline = api["Polyline"]
    extrude = api["extrude"]
    make_face = api["make_face"]
    mech = project.mechanical
    contour = preferred_shell_contour_points(project.root, mech)
    face = make_face(Plane.XZ * Polyline(*contour))
    return extrude(face, amount=mech.outer_thickness_mm * 2.5, both=True)


def _build_outer_body(api, mech: MechanicalParams):
    raise RuntimeError("_build_outer_body now requires project context")


def _build_inner_body(api, project: RemoteProjectData):
    mech = project.mechanical
    assumptions = project.assumptions
    Part = api["Part"]
    inner_stations = []
    for z_mm, x_center_mm, width_mm, thickness_mm, radius_mm in _profile_stations(project):
        inner_width = max(width_mm - 2 * mech.wall_thickness_mm, mech.pcb_width_grip_mm + 2 * assumptions.pcb_cavity_side_clearance_mm)
        inner_thickness = max(
            thickness_mm - 2 * mech.wall_thickness_mm,
            assumptions.pcb_thickness_mm + assumptions.max_component_height_front_mm + assumptions.max_component_height_rear_mm + assumptions.pcb_cavity_depth_clearance_mm,
        )
        inner_stations.append((z_mm + 0.5, x_center_mm, inner_width, inner_thickness, max(radius_mm - mech.wall_thickness_mm * 0.55, 1.5)))
    inner = _build_lofted_body(api, inner_stations)
    contour_prism = _build_user1_contour_prism(api, project)
    return Part((inner & contour_prism).wrapped)


def _build_outer_body(api, project: RemoteProjectData):
    Part = api["Part"]
    lofted = _build_lofted_body(api, _profile_stations(project))
    contour_prism = _build_user1_contour_prism(api, project)
    return Part((lofted & contour_prism).wrapped)


def _cut_common_features(api, shell, project: RemoteProjectData):
    Box = api["Box"]
    Cylinder = api["Cylinder"]
    Part = api["Part"]
    Pos = api["Pos"]
    Rot = api["Rot"]
    mech = project.mechanical
    assumptions = project.assumptions

    sw2_x_mm, sw2_y_mm, _ = project.layout.canonical_position(
        "SW2",
        (
            mech.pcb_shell_center_x_mm + mech.power_button_center_x_mm,
            mech.power_button_center_z_from_top_mm,
            0.0,
        ),
    )
    sw2_shell_x, sw2_shell_z = shell_xz_from_board(mech, sw2_x_mm, sw2_y_mm)

    j1_x_mm, j1_y_mm, _ = project.layout.canonical_position("J1", (mech.pcb_shell_center_x_mm, 128.5, 0.0))
    usb_shell_x, usb_shell_z = shell_xz_from_board(mech, j1_x_mm, j1_y_mm + USB_PORT_CUT_CENTER_OFFSET_MM)

    wheel_cut = Pos(mech.thumbwheel_center_x_mm, 0, -mech.thumbwheel_center_z_from_top_mm) * Rot(X=90) * Cylinder(
        radius=mech.thumbwheel_opening_diameter_mm * 0.5 + assumptions.thumbwheel_radial_clearance_mm,
        height=mech.outer_thickness_mm * 2.4,
    )
    button_cut = Pos(sw2_shell_x, 0, sw2_shell_z) * Rot(X=90) * Cylinder(
        radius=mech.button_hole_diameter_mm * 0.5,
        height=mech.outer_thickness_mm * 2.4,
    )
    usb_cut = Pos(usb_shell_x, 0, usb_shell_z) * Box(
        mech.usb_port_width_mm,
        mech.outer_thickness_mm * 2.0,
        mech.usb_port_height_mm,
    )
    return _subtract_all(shell, [wheel_cut, button_cut, usb_cut], Part)


def _shell_positions_for_refs(project: RemoteProjectData, refs: tuple[str, ...]) -> list[tuple[float, float]]:
    positions: list[tuple[float, float]] = []
    for ref in refs:
        canonical = project.layout.canonical_position(ref)
        if canonical is None:
            continue
        board_x_mm, board_y_mm, _ = canonical
        positions.append(shell_xz_from_board(project.mechanical, board_x_mm, board_y_mm))
    return positions


def _cut_front_features(api, shell, project: RemoteProjectData):
    Cylinder = api["Cylinder"]
    Part = api["Part"]
    Pos = api["Pos"]
    Rot = api["Rot"]
    mech = project.mechanical
    cuts = [
        Pos(shell_x_mm, 0, shell_z_mm) * Rot(X=90) * Cylinder(
            radius=mech.led_window_diameter_mm * 0.5,
            height=mech.outer_thickness_mm * 2.0,
        )
        for shell_x_mm, shell_z_mm in _shell_positions_for_refs(project, ("D1", "D2", "D3", "D4", "D5", "D6", "D7"))
    ]
    return _subtract_all(shell, cuts, Part)


def _cut_rear_features(api, shell):
    Box = api["Box"]
    Pos = api["Pos"]
    trigger_cut = Pos(0, -8.5, -92.0) * Box(22.0, 14.0, 10.0)
    return shell - trigger_cut


def _add_mounting_system(api, front_shell, rear_shell, project: RemoteProjectData):
    Cylinder = api["Cylinder"]
    Part = api["Part"]
    Pos = api["Pos"]
    Rot = api["Rot"]
    mech = project.mechanical

    front = front_shell
    rear = rear_shell
    for hole in mech.pcb_mount_holes:
        shell_x, shell_z = shell_xz_from_board(mech, hole.board_x_mm, hole.board_y_mm)
        boss = Pos(shell_x, -3.3, shell_z) * Rot(X=90) * Cylinder(radius=hole.boss_outer_diameter_mm * 0.5, height=5.6)
        rear = Part((rear + boss).wrapped)
        rear = Part((rear - (Pos(shell_x, -3.3, shell_z) * Rot(X=90) * Cylinder(radius=hole.pcb_drill_mm * 0.5, height=mech.outer_thickness_mm))).wrapped)
        front = Part((front - (Pos(shell_x, 3.3, shell_z) * Rot(X=90) * Cylinder(radius=hole.pcb_drill_mm * 0.5, height=mech.outer_thickness_mm))).wrapped)
        front = Part((front - (Pos(shell_x, 7.3, shell_z) * Rot(X=90) * Cylinder(
            radius=hole.head_clearance_diameter_mm * 0.5,
            height=hole.front_counterbore_depth_mm,
        ))).wrapped)
    return front, rear


def _half_space_cutters(api, mech: MechanicalParams):
    Box = api["Box"]
    Pos = api["Pos"]
    half_width = 80.0
    split_offset = half_width * 0.5 + mech.split_gap_mm * 0.5
    z_center = -mech.outer_height_mm * 0.5
    front_half_cut = Pos(0, split_offset, z_center) * Box(200.0, half_width, mech.outer_height_mm + 30.0)
    rear_half_cut = Pos(0, -split_offset, z_center) * Box(200.0, half_width, mech.outer_height_mm + 30.0)
    return front_half_cut, rear_half_cut


def _build_pcb_envelope(api, project: RemoteProjectData):
    Plane = api["Plane"]
    Polyline = api["Polyline"]
    extrude = api["extrude"]
    make_face = api["make_face"]
    mech = project.mechanical
    assumptions = project.assumptions
    outline = board_outline_points(project.root)
    outline_shell = [shell_xz_from_board(mech, x_mm, y_mm) for x_mm, y_mm in outline]
    face = make_face(Plane.XZ * Polyline(*outline_shell))
    return extrude(
        face,
        amount=assumptions.pcb_thickness_mm + assumptions.max_component_height_front_mm + assumptions.max_component_height_rear_mm,
        both=True,
    )


def build_enclosure(project: RemoteProjectData) -> EnclosureArtifacts:
    api = _import_build123d()
    Part = api["Part"]
    outer = _cut_common_features(api, _build_outer_body(api, project), project)
    inner = _build_inner_body(api, project)
    shell = Part((outer - inner).wrapped)

    front_half_cut, rear_half_cut = _half_space_cutters(api, project.mechanical)
    front_shell = _cut_front_features(api, Part((shell - rear_half_cut).wrapped), project)
    rear_shell = _cut_rear_features(api, Part((shell - front_half_cut).wrapped))
    front_shell, rear_shell = _add_mounting_system(api, front_shell, rear_shell, project)

    return EnclosureArtifacts(
        outer_body=outer,
        full_shell=shell,
        front_shell=front_shell,
        rear_shell=rear_shell,
        pcb_envelope=_build_pcb_envelope(api, project),
    )