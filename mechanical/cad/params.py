from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .kicad_layout import LiveBoardLayout, load_live_board_layout


@dataclass(frozen=True)
class MountHoleSpec:
    name: str
    board_x_mm: float
    board_y_mm: float
    pcb_drill_mm: float
    boss_outer_diameter_mm: float
    head_clearance_diameter_mm: float
    front_counterbore_depth_mm: float


@dataclass(frozen=True)
class MechanicalAssumptions:
    pcb_thickness_mm: float = 1.6
    pcb_cavity_side_clearance_mm: float = 0.6
    pcb_cavity_depth_clearance_mm: float = 0.8
    shell_closure_clearance_mm: float = 0.3
    thumbwheel_radial_clearance_mm: float = 0.75
    trigger_travel_mm: float = 7.0
    button_travel_mm: float = 1.5
    hall_sensor_air_gap_mm: float = 2.0
    max_component_height_front_mm: float = 4.5
    max_component_height_rear_mm: float = 6.0


@dataclass(frozen=True)
class MechanicalParams:
    outer_height_mm: float
    outer_width_top_mm: float
    outer_width_grip_mm: float
    outer_thickness_mm: float
    wall_thickness_mm: float
    split_gap_mm: float
    top_bulb_height_mm: float
    grip_height_mm: float
    pcb_height_mm: float
    pcb_width_top_mm: float
    pcb_width_grip_mm: float
    pcb_bottom_radius_mm: float
    thumbwheel_opening_diameter_mm: float
    thumbwheel_center_z_from_top_mm: float
    thumbwheel_center_x_mm: float
    thumbwheel_diameter_mm: float
    thumbwheel_width_mm: float
    usb_port_width_mm: float
    usb_port_height_mm: float
    led_window_diameter_mm: float
    status_led_pitch_mm: float
    bar_led_pitch_mm: float
    button_hole_diameter_mm: float
    power_button_center_x_mm: float
    power_button_center_z_from_top_mm: float
    pcb_shell_center_x_mm: float
    pcb_mount_holes: tuple[MountHoleSpec, ...]


@dataclass(frozen=True)
class RemoteProjectData:
    root: Path
    raw: dict
    mechanical: MechanicalParams
    assumptions: MechanicalAssumptions
    layout: LiveBoardLayout


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_project_data(repo_root: Path) -> RemoteProjectData:
    params_path = repo_root / "config" / "remote_params.json"
    raw = _load_json(params_path)
    mechanical = raw["mechanical"]
    assumptions = MechanicalAssumptions(**raw.get("mechanical_assumptions", {}))
    layout = load_live_board_layout(repo_root, mechanical)
    mount_holes = []
    for spec in mechanical["pcb_mount_holes"]:
        canonical = layout.canonical_position(spec["name"])
        if canonical is None:
            mount_holes.append(MountHoleSpec(**spec))
            continue
        board_x_mm, board_y_mm, _ = canonical
        mount_holes.append(
            MountHoleSpec(
                name=spec["name"],
                board_x_mm=board_x_mm,
                board_y_mm=board_y_mm,
                pcb_drill_mm=spec["pcb_drill_mm"],
                boss_outer_diameter_mm=spec["boss_outer_diameter_mm"],
                head_clearance_diameter_mm=spec["head_clearance_diameter_mm"],
                front_counterbore_depth_mm=spec["front_counterbore_depth_mm"],
            )
        )
    mount_holes = tuple(mount_holes)
    mech_data = MechanicalParams(
        outer_height_mm=mechanical["outer_height_mm"],
        outer_width_top_mm=mechanical["outer_width_top_mm"],
        outer_width_grip_mm=mechanical["outer_width_grip_mm"],
        outer_thickness_mm=mechanical["outer_thickness_mm"],
        wall_thickness_mm=mechanical["wall_thickness_mm"],
        split_gap_mm=mechanical["split_gap_mm"],
        top_bulb_height_mm=mechanical["top_bulb_height_mm"],
        grip_height_mm=mechanical["grip_height_mm"],
        pcb_height_mm=mechanical["pcb_height_mm"],
        pcb_width_top_mm=mechanical["pcb_width_top_mm"],
        pcb_width_grip_mm=mechanical["pcb_width_grip_mm"],
        pcb_bottom_radius_mm=mechanical["pcb_bottom_radius_mm"],
        thumbwheel_opening_diameter_mm=mechanical["thumbwheel_opening_diameter_mm"],
        thumbwheel_center_z_from_top_mm=mechanical["thumbwheel_center_z_from_top_mm"],
        thumbwheel_center_x_mm=mechanical["thumbwheel_center_x_mm"],
        thumbwheel_diameter_mm=mechanical["thumbwheel_diameter_mm"],
        thumbwheel_width_mm=mechanical["thumbwheel_width_mm"],
        usb_port_width_mm=mechanical["usb_port_width_mm"],
        usb_port_height_mm=mechanical["usb_port_height_mm"],
        led_window_diameter_mm=mechanical["led_window_diameter_mm"],
        status_led_pitch_mm=mechanical["status_led_pitch_mm"],
        bar_led_pitch_mm=mechanical["bar_led_pitch_mm"],
        button_hole_diameter_mm=mechanical["button_hole_diameter_mm"],
        power_button_center_x_mm=mechanical["power_button_center_x_mm"],
        power_button_center_z_from_top_mm=mechanical["power_button_center_z_from_top_mm"],
        pcb_shell_center_x_mm=mechanical["pcb_shell_center_x_mm"],
        pcb_mount_holes=mount_holes,
    )
    return RemoteProjectData(root=repo_root, raw=raw, mechanical=mech_data, assumptions=assumptions, layout=layout)