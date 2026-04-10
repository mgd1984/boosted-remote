from __future__ import annotations

import argparse
import re
import sys
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from mechanical.cad.params import load_project_data
from mechanical.cad.reference import horizontal_polygon_span, preferred_pcb_contour_points, user_layer_contour_points


EDGE_CUTS_WIDTH_MM = 0.15
USER_LAYER_CONTOUR_INSET_MM = 1.0

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


def parse_args(repo_root: Path) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync the live board outline from a source contour layer.")
    parser.add_argument(
        "--board",
        type=Path,
        default=repo_root / "electrical" / "kicad" / "boosted_remote.kicad_pcb",
        help="Board file to update.",
    )
    parser.add_argument(
        "--source",
        choices=("user-layer", "pcb-svg"),
        default="user-layer",
        help="Contour source to convert into Edge.Cuts.",
    )
    parser.add_argument(
        "--source-layer",
        default="User.1",
        help="Graphic layer containing the contour polygon when --source=user-layer.",
    )
    parser.add_argument(
        "--skip-live-adjustments",
        action="store_true",
        help="Disable the board-specific relief tweaks normally applied to the default User.1 contour.",
    )
    parser.add_argument(
        "--inset-mm",
        type=float,
        default=None,
        help="Optional inset override. By default, user-layer contours inset by 1.0 mm and pcb-svg contours inset by 0.0 mm.",
    )
    return parser.parse_args()


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

def _inset_contour(points: tuple[tuple[float, float], ...], inset_mm: float) -> list[tuple[float, float]]:
    inset: list[tuple[float, float]] = []
    for x_mm, y_mm in points:
        span = horizontal_polygon_span(y_mm, points)
        if span is None:
            inset.append((x_mm, y_mm))
            continue
        center_x_mm = (span[0] + span[1]) * 0.5
        delta_x_mm = x_mm - center_x_mm
        direction = -1.0 if delta_x_mm < 0 else 1.0
        inset.append((center_x_mm + direction * max(abs(delta_x_mm) - inset_mm, 0.6), y_mm))
    if inset[0] != inset[-1]:
        inset.append(inset[0])
    return inset


def _source_inset_mm(args: argparse.Namespace) -> float:
    if args.inset_mm is not None:
        return args.inset_mm
    if args.source == "pcb-svg":
        return 0.0
    return USER_LAYER_CONTOUR_INSET_MM


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


def _source_contour_points(repo_root: Path, args: argparse.Namespace) -> tuple[tuple[float, float], ...]:
    if args.source == "pcb-svg":
        return preferred_pcb_contour_points(repo_root)
    return user_layer_contour_points(repo_root, args.source_layer)


def main() -> None:
    repo_root = REPO_ROOT
    args = parse_args(repo_root)
    project = load_project_data(repo_root)
    contour = _source_contour_points(repo_root, args)
    inset = _inset_contour(contour, _source_inset_mm(args))
    live_points = [
        (x_mm + project.layout.offset_x_mm, y_mm + project.layout.offset_y_mm)
        for x_mm, y_mm in inset
    ]
    if args.source == "user-layer" and args.source_layer == "User.1" and not args.skip_live_adjustments:
        live_points = _apply_live_vertex_adjustments(live_points)

    edge_block = "\n".join(_format_edge_line(start, end) for start, end in zip(live_points, live_points[1:]))

    board_path = args.board
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
