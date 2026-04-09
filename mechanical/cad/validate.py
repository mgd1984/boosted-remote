from __future__ import annotations

from dataclasses import dataclass

from .params import RemoteProjectData
from .reference import board_outline_points, point_in_polygon


@dataclass(frozen=True)
class ValidationIssue:
    level: str
    message: str


def validate_project_data(project: RemoteProjectData) -> list[ValidationIssue]:
    mech = project.mechanical
    assumptions = project.assumptions
    outline = board_outline_points(project.root)
    issues: list[ValidationIssue] = []

    if mech.wall_thickness_mm <= 1.2:
        issues.append(ValidationIssue("warning", "Wall thickness is below a conservative FDM enclosure baseline."))
    if mech.split_gap_mm <= 0:
        issues.append(ValidationIssue("error", "Split gap must be positive."))
    if assumptions.pcb_thickness_mm <= 0:
        issues.append(ValidationIssue("error", "PCB thickness must be positive."))
    if assumptions.pcb_cavity_side_clearance_mm < 0.2:
        issues.append(ValidationIssue("warning", "PCB side clearance is tight for a first printed prototype."))
    if assumptions.shell_closure_clearance_mm < 0.15:
        issues.append(ValidationIssue("warning", "Shell closure clearance is unusually tight."))
    if mech.outer_width_top_mm <= mech.pcb_width_top_mm + 2 * mech.wall_thickness_mm:
        issues.append(ValidationIssue("error", "Top shell width does not leave enough room for PCB width plus walls."))
    if mech.outer_width_grip_mm <= mech.pcb_width_grip_mm + 2 * mech.wall_thickness_mm:
        issues.append(ValidationIssue("error", "Grip shell width does not leave enough room for PCB width plus walls."))
    if mech.outer_height_mm <= mech.pcb_height_mm + 2 * mech.wall_thickness_mm:
        issues.append(ValidationIssue("warning", "Outer height leaves little margin around the PCB envelope."))

    for hole in mech.pcb_mount_holes:
        if not point_in_polygon(hole.board_x_mm, hole.board_y_mm, outline):
            issues.append(ValidationIssue("error", f"Mount hole {hole.name} falls outside the PCB outline."))
        if hole.boss_outer_diameter_mm <= hole.pcb_drill_mm + 1.2:
            issues.append(ValidationIssue("warning", f"Mount hole {hole.name} boss wall is thin for printed hardware."))
        if hole.head_clearance_diameter_mm <= hole.pcb_drill_mm:
            issues.append(ValidationIssue("error", f"Mount hole {hole.name} head clearance must exceed the drill diameter."))

    return issues