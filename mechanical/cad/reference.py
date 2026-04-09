from __future__ import annotations

import ast
import json
import re
import xml.etree.ElementTree as ET
from functools import lru_cache
from pathlib import Path

from .kicad_layout import load_live_board_layout
from .params import MechanicalParams


SVG_OUTLINE_PATH = Path("mechanical/references/boosted_remote_outline_smooth_pixels.svg")


@lru_cache(maxsize=4)
def board_outline_points(repo_root: Path) -> tuple[tuple[float, float], ...]:
    board_path = repo_root / "electrical" / "kicad" / "boosted_remote.kicad_pcb"
    board_text = board_path.read_text(encoding="utf-8")
    params_path = repo_root / "config" / "remote_params.json"
    mechanical = json.loads(params_path.read_text(encoding="utf-8"))["mechanical"]
    layout = load_live_board_layout(repo_root, mechanical)
    edge_points = _edge_cuts_outline_points(board_text, layout.offset_x_mm, layout.offset_y_mm)
    if edge_points is not None:
        return edge_points

    source_path = repo_root / "electrical" / "scripts" / "generate_kicad_remote.py"
    module = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    for node in module.body:
        if isinstance(node, ast.FunctionDef) and node.name == "board_outline":
            for statement in node.body:
                if isinstance(statement, ast.Return):
                    points = ast.literal_eval(statement.value)
                    return tuple((float(x), float(y)) for x, y in points)
    raise RuntimeError("Unable to locate board_outline() in electrical/scripts/generate_kicad_remote.py")


def _edge_cuts_outline_points(board_text: str, offset_x_mm: float, offset_y_mm: float) -> tuple[tuple[float, float], ...] | None:
    blocks: list[str] = []
    current: list[str] = []
    depth = 0
    in_block = False
    for line in board_text.splitlines():
        stripped = line.lstrip()
        if not in_block and stripped.startswith("(gr_line"):
            in_block = True
            current = [line]
            depth = line.count("(") - line.count(")")
            if depth <= 0:
                block = "\n".join(current)
                if '(layer "Edge.Cuts")' in block:
                    blocks.append(block)
                in_block = False
            continue
        if in_block:
            current.append(line)
            depth += line.count("(") - line.count(")")
            if depth <= 0:
                block = "\n".join(current)
                if '(layer "Edge.Cuts")' in block:
                    blocks.append(block)
                in_block = False

    if not blocks:
        return None

    points: list[tuple[float, float]] = []
    for index, block in enumerate(blocks):
        start_match = re.search(r"\(start\s+([-0-9.]+)\s+([-0-9.]+)\)", block)
        end_match = re.search(r"\(end\s+([-0-9.]+)\s+([-0-9.]+)\)", block)
        if start_match is None or end_match is None:
            continue
        start = (float(start_match.group(1)) - offset_x_mm, float(start_match.group(2)) - offset_y_mm)
        end = (float(end_match.group(1)) - offset_x_mm, float(end_match.group(2)) - offset_y_mm)
        if index == 0:
            points.append(start)
        points.append(end)

    if len(points) < 4:
        return None
    if points[0] != points[-1]:
        points.append(points[0])
    return tuple(points)


@lru_cache(maxsize=4)
def user1_contour_points(repo_root: Path) -> tuple[tuple[float, float], ...]:
    params_path = repo_root / "config" / "remote_params.json"
    mechanical = json.loads(params_path.read_text(encoding="utf-8"))["mechanical"]
    layout = load_live_board_layout(repo_root, mechanical)
    board_path = repo_root / "electrical" / "kicad" / "boosted_remote.kicad_pcb"
    board_text = board_path.read_text(encoding="utf-8")

    block_lines: list[str] = []
    current: list[str] = []
    depth = 0
    in_block = False
    for line in board_text.splitlines():
        stripped = line.lstrip()
        if not in_block and stripped.startswith("(gr_poly"):
            in_block = True
            current = [line]
            depth = line.count("(") - line.count(")")
            if depth <= 0:
                candidate = "\n".join(current)
                if '(layer "User.1")' in candidate:
                    block_lines = current
                    break
                in_block = False
            continue

        if in_block:
            current.append(line)
            depth += line.count("(") - line.count(")")
            if depth <= 0:
                candidate = "\n".join(current)
                if '(layer "User.1")' in candidate:
                    block_lines = current
                    break
                in_block = False

    if not block_lines:
        raise RuntimeError("Unable to locate User.1 contour polygon in electrical/kicad/boosted_remote.kicad_pcb")

    points = [
        (float(x_mm) - layout.offset_x_mm, float(y_mm) - layout.offset_y_mm)
        for line in block_lines
        for x_mm, y_mm in re.findall(r"\(xy\s+([-0-9.]+)\s+([-0-9.]+)\)", line)
    ]
    if len(points) < 4:
        raise RuntimeError("User.1 contour polygon does not contain enough points")
    if points[0] != points[-1]:
        points.append(points[0])
    return tuple(points)


@lru_cache(maxsize=4)
def user1_shell_contour_points(repo_root: Path, pcb_shell_center_x_mm: float) -> tuple[tuple[float, float], ...]:
    return tuple((x_mm - pcb_shell_center_x_mm, -y_mm) for x_mm, y_mm in user1_contour_points(repo_root))


def _parse_svg_path_points(path_data: str) -> tuple[tuple[float, float], ...]:
    tokens = re.findall(r"[MLZ]|-?\d+(?:\.\d+)?", path_data)
    points: list[tuple[float, float]] = []
    index = 0
    command = None
    while index < len(tokens):
        token = tokens[index]
        if token in {"M", "L", "Z"}:
            command = token
            index += 1
            if command == "Z":
                break
            continue
        if command not in {"M", "L"}:
            raise RuntimeError("Unsupported SVG path command sequence in outline")
        if index + 1 >= len(tokens):
            raise RuntimeError("Malformed SVG path data in outline")
        x_mm = float(tokens[index])
        y_mm = float(tokens[index + 1])
        points.append((x_mm, y_mm))
        index += 2
    if len(points) < 4:
        raise RuntimeError("SVG outline path does not contain enough points")
    if points[0] != points[-1]:
        points.append(points[0])
    return tuple(points)


@lru_cache(maxsize=4)
def svg_outline_points(repo_root: Path) -> tuple[tuple[float, float], ...] | None:
    svg_path = repo_root / SVG_OUTLINE_PATH
    if not svg_path.exists():
        return None
    root = ET.fromstring(svg_path.read_text(encoding="utf-8"))
    path_node = root.find(".//{http://www.w3.org/2000/svg}path")
    if path_node is None:
        raise RuntimeError(f"Unable to locate SVG path in {svg_path}")
    path_data = path_node.attrib.get("d")
    if not path_data:
        raise RuntimeError(f"SVG path in {svg_path} does not contain path data")
    return _parse_svg_path_points(path_data)


@lru_cache(maxsize=4)
def svg_shell_contour_points(repo_root: Path, outer_height_mm: float) -> tuple[tuple[float, float], ...] | None:
    points = svg_outline_points(repo_root)
    if points is None:
        return None
    min_x_mm = min(x_mm for x_mm, _ in points)
    max_x_mm = max(x_mm for x_mm, _ in points)
    min_y_mm = min(y_mm for _, y_mm in points)
    max_y_mm = max(y_mm for _, y_mm in points)
    length_mm = max_x_mm - min_x_mm
    center_y_mm = (min_y_mm + max_y_mm) * 0.5
    if length_mm <= 0:
        raise RuntimeError("SVG outline has invalid length")
    scale = outer_height_mm / length_mm
    scaled = [((y_mm - center_y_mm) * scale, -(max_x_mm - x_mm) * scale) for x_mm, y_mm in points]
    if scaled[0] != scaled[-1]:
        scaled.append(scaled[0])
    return tuple(scaled)


def preferred_shell_contour_points(repo_root: Path, mech: MechanicalParams) -> tuple[tuple[float, float], ...]:
    svg_points = svg_shell_contour_points(repo_root, mech.outer_height_mm)
    if svg_points is not None:
        return svg_points
    return user1_shell_contour_points(repo_root, mech.pcb_shell_center_x_mm)


def horizontal_polygon_span(y_mm: float, polygon: tuple[tuple[float, float], ...], tolerance: float = 1e-6) -> tuple[float, float] | None:
    intersections: list[float] = []
    for (x1, y1), (x2, y2) in zip(polygon, polygon[1:]):
        if abs(y1 - y2) <= tolerance:
            if abs(y_mm - y1) <= tolerance:
                intersections.extend([x1, x2])
            continue
        if (y1 <= y_mm < y2) or (y2 <= y_mm < y1):
            x_mm = x1 + (y_mm - y1) * (x2 - x1) / (y2 - y1)
            intersections.append(x_mm)

    if len(intersections) < 2:
        return None
    intersections.sort()
    return intersections[0], intersections[-1]


def shell_xz_from_board(mech: MechanicalParams, board_x_mm: float, board_y_mm: float) -> tuple[float, float]:
    return board_x_mm - mech.pcb_shell_center_x_mm, -board_y_mm


def _point_on_segment(x_mm: float, y_mm: float, ax_mm: float, ay_mm: float, bx_mm: float, by_mm: float, tolerance: float = 1e-6) -> bool:
    cross = (x_mm - ax_mm) * (by_mm - ay_mm) - (y_mm - ay_mm) * (bx_mm - ax_mm)
    if abs(cross) > tolerance:
        return False
    dot = (x_mm - ax_mm) * (bx_mm - ax_mm) + (y_mm - ay_mm) * (by_mm - ay_mm)
    if dot < -tolerance:
        return False
    length_sq = (bx_mm - ax_mm) ** 2 + (by_mm - ay_mm) ** 2
    if dot - length_sq > tolerance:
        return False
    return True


def point_in_polygon(x_mm: float, y_mm: float, polygon: tuple[tuple[float, float], ...]) -> bool:
    inside = False
    for (x1, y1), (x2, y2) in zip(polygon, polygon[1:]):
        if _point_on_segment(x_mm, y_mm, x1, y1, x2, y2):
            return True
        if (y1 > y_mm) != (y2 > y_mm):
            intersect_x = (x2 - x1) * (y_mm - y1) / (y2 - y1) + x1
            if x_mm < intersect_x:
                inside = not inside
    return inside