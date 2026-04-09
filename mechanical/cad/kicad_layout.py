from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class BoardPlacement:
    ref: str
    x_mm: float
    y_mm: float
    rotation_deg: float
    layer: str


@dataclass(frozen=True)
class LiveBoardLayout:
    offset_x_mm: float
    offset_y_mm: float
    placements: dict[str, BoardPlacement]

    def canonical_position(self, ref: str, fallback: tuple[float, float, float] | None = None) -> tuple[float, float, float] | None:
        placement = self.placements.get(ref)
        if placement is None:
            return fallback
        return (
            placement.x_mm - self.offset_x_mm,
            placement.y_mm - self.offset_y_mm,
            placement.rotation_deg,
        )


_AT_RE = re.compile(r"\(at\s+([-0-9.]+)\s+([-0-9.]+)(?:\s+([-0-9.]+))?\)")
_REF_RE = re.compile(r'\(property\s+"Reference"\s+"([^"]+)"')
_LAYER_RE = re.compile(r'\(layer\s+"([^"]+)"\)')


def _footprint_blocks(board_text: str) -> list[str]:
    blocks: list[str] = []
    lines = board_text.splitlines()
    current: list[str] = []
    depth = 0
    in_block = False

    for line in lines:
        stripped = line.lstrip()
        if not in_block and stripped.startswith("(footprint "):
            in_block = True
            current = [line]
            depth = line.count("(") - line.count(")")
            if depth <= 0:
                blocks.append("\n".join(current))
                in_block = False
            continue

        if in_block:
            current.append(line)
            depth += line.count("(") - line.count(")")
            if depth <= 0:
                blocks.append("\n".join(current))
                in_block = False

    return blocks


def _parse_placement(block: str) -> BoardPlacement | None:
    ref_match = _REF_RE.search(block)
    at_match = _AT_RE.search(block)
    layer_match = _LAYER_RE.search(block)
    if ref_match is None or at_match is None or layer_match is None:
        return None
    rotation_deg = float(at_match.group(3) or 0.0)
    return BoardPlacement(
        ref=ref_match.group(1),
        x_mm=float(at_match.group(1)),
        y_mm=float(at_match.group(2)),
        rotation_deg=rotation_deg,
        layer=layer_match.group(1),
    )


def _expected_mount_hole_positions(mechanical: dict) -> dict[str, tuple[float, float]]:
    return {
        spec["name"]: (float(spec["board_x_mm"]), float(spec["board_y_mm"]))
        for spec in mechanical.get("pcb_mount_holes", [])
    }


def load_live_board_layout(repo_root: Path, mechanical: dict) -> LiveBoardLayout:
    board_path = repo_root / "electrical" / "kicad" / "boosted_remote.kicad_pcb"
    board_text = board_path.read_text(encoding="utf-8")
    placements = {
        placement.ref: placement
        for block in _footprint_blocks(board_text)
        if (placement := _parse_placement(block)) is not None
    }

    expected = _expected_mount_hole_positions(mechanical)
    offset_pairs: list[tuple[float, float]] = []
    for ref, (expected_x, expected_y) in expected.items():
        placement = placements.get(ref)
        if placement is None:
            continue
        offset_pairs.append((placement.x_mm - expected_x, placement.y_mm - expected_y))

    if offset_pairs:
        offset_x_mm = sum(pair[0] for pair in offset_pairs) / len(offset_pairs)
        offset_y_mm = sum(pair[1] for pair in offset_pairs) / len(offset_pairs)
    else:
        offset_x_mm = 0.0
        offset_y_mm = 0.0

    return LiveBoardLayout(
        offset_x_mm=offset_x_mm,
        offset_y_mm=offset_y_mm,
        placements=placements,
    )