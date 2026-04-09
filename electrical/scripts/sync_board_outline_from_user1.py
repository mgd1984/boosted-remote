from __future__ import annotations

import re
import uuid
from pathlib import Path

from mechanical.cad.params import load_project_data
from mechanical.cad.reference import horizontal_polygon_span, user1_contour_points


EDGE_CUTS_WIDTH_MM = 0.15
BOARD_CONTOUR_INSET_MM = 1.0

# Empirical live-board relief tweaks after the shell/body contour is inset.
# The traced silhouette slightly over-pinches the USB tail and right LED shoulder
# when converted into the PCB edge, so keep those local lobes a touch fuller.
LIVE_VERTEX_ADJUSTMENTS_MM: dict[tuple[float, float], tuple[float, float]] = {
    (97.205869, 97.052030): (98.055869, 97.052030),
    (97.424482, 95.748295): (98.574482, 95.748295),
    (97.915615, 94.659538): (99.065615, 94.659538),
    (98.820161, 93.889269): (99.470161, 93.889269),
    (73.719224, 163.840469): (73.339224, 163.840469),
    (74.923075, 164.468523): (74.443075, 164.468523),
}


def _format_edge_line(start: tuple[float, float], end: tuple[float, float]) -> str:
    return (
        "\t(gr_line\n"
        f"\t\t(start {start[0]:.6f} {start[1]:.6f})\n"
        f"\t\t(end {end[0]:.6f} {end[1]:.6f})\n"
        "\t\t(stroke\n"
        f"\t\t\t(width {EDGE_CUTS_WIDTH_MM:.2f})\n"
        "\t\t\t(type default)\n"
        "\t\t)\n"
        "\t\t(layer \"Edge.Cuts\")\n"
        f"\t\t(uuid \"{uuid.uuid4()}\")\n"
        "\t)"
    )

def _inset_contour(points: tuple[tuple[float, float], ...]) -> list[tuple[float, float]]:
    inset: list[tuple[float, float]] = []
    for x_mm, y_mm in points:
        span = horizontal_polygon_span(y_mm, points)
        if span is None:
            inset.append((x_mm, y_mm))
            continue
        center_x_mm = (span[0] + span[1]) * 0.5
        delta_x_mm = x_mm - center_x_mm
        direction = -1.0 if delta_x_mm < 0 else 1.0
        inset.append((center_x_mm + direction * max(abs(delta_x_mm) - BOARD_CONTOUR_INSET_MM, 0.6), y_mm))
    if inset[0] != inset[-1]:
        inset.append(inset[0])
    return inset


def _apply_live_vertex_adjustments(points: list[tuple[float, float]], tolerance_mm: float = 1e-6) -> list[tuple[float, float]]:
    adjusted: list[tuple[float, float]] = []
    for x_mm, y_mm in points:
        replacement = None
        for (src_x_mm, src_y_mm), target in LIVE_VERTEX_ADJUSTMENTS_MM.items():
            if abs(x_mm - src_x_mm) <= tolerance_mm and abs(y_mm - src_y_mm) <= tolerance_mm:
                replacement = target
                break
        adjusted.append(replacement if replacement is not None else (x_mm, y_mm))
    return adjusted


def _remove_existing_edge_cuts(board_text: str) -> str:
    kept_blocks: list[str] = []
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
                if '(layer "Edge.Cuts")' not in block:
                    kept_blocks.append(block)
                in_block = False
            continue

        if in_block:
            current.append(line)
            depth += line.count("(") - line.count(")")
            if depth <= 0:
                block = "\n".join(current)
                if '(layer "Edge.Cuts")' not in block:
                    kept_blocks.append(block)
                in_block = False
            continue

        kept_blocks.append(line)

    return "\n".join(kept_blocks) + "\n"


def main() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    project = load_project_data(repo_root)
    contour = user1_contour_points(repo_root)
    inset = _inset_contour(contour)
    live_points = [
        (x_mm + project.layout.offset_x_mm, y_mm + project.layout.offset_y_mm)
        for x_mm, y_mm in inset
    ]
    live_points = _apply_live_vertex_adjustments(live_points)

    edge_block = "\n".join(_format_edge_line(start, end) for start, end in zip(live_points, live_points[1:]))

    board_path = repo_root / "electrical" / "kicad" / "boosted_remote.kicad_pcb"
    board_text = board_path.read_text(encoding="utf-8")
    board_text = _remove_existing_edge_cuts(board_text)

    insert_match = re.search(r"\n\t\(gr_(?:circle|line|poly|text)", board_text)
    if insert_match is None:
        raise RuntimeError("Unable to locate insertion point for Edge.Cuts graphics")

    insertion = f"\n{edge_block}\n"
    board_text = board_text[: insert_match.start()] + insertion + board_text[insert_match.start() :]
    board_path.write_text(board_text, encoding="utf-8")


if __name__ == "__main__":
    main()
