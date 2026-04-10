#!/usr/bin/env python3

from __future__ import annotations

import argparse
import subprocess
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FRONT_REFERENCE = ROOT / "mechanical" / "references" / "boosted_remote_pcb_front.png"
DEFAULT_BACK_REFERENCE = ROOT / "mechanical" / "references" / "boosted_remote_pcb_back.png"
DEFAULT_OUTPUT = ROOT / "mechanical" / "references" / "boosted_remote_pcb_outline_target.svg"

SVG_WIDTH_PX = 1297.0
SVG_HEIGHT_PX = 3086.0
SAMPLE_COUNT = 240
BACK_BLEND_CUTOFF = 0.72
BACK_TOP_WEIGHT = 0.45
LOWER_BODY_OUTLIER_START = 0.58
LOWER_BODY_WIDTH_DELTA = 0.055
CHAIKIN_ITERATIONS = 3
SIMPLIFY_TOLERANCE_PX = 2.4


@dataclass(frozen=True)
class SilhouetteMask:
    width_px: int
    height_px: int
    rows: tuple[tuple[int, ...], ...]
    spans_px: tuple[tuple[int, int], ...]

    def sample_normalized_span(self, t: float) -> tuple[float, float]:
        row_index = min(self.height_px - 1, max(0, round(t * (self.height_px - 1))))
        left_px, right_px = self.spans_px[row_index]
        return left_px / self.width_px, right_px / self.width_px


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Regenerate the PCB outline SVG target from reference PNG silhouettes.")
    parser.add_argument("--front", type=Path, default=DEFAULT_FRONT_REFERENCE, help="Front-side reference PNG.")
    parser.add_argument("--back", type=Path, default=DEFAULT_BACK_REFERENCE, help="Back-side reference PNG.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Output SVG path.")
    parser.add_argument(
        "--samples",
        type=int,
        default=SAMPLE_COUNT,
        help="Number of horizontal scanline samples used to reconstruct the outline.",
    )
    return parser.parse_args()


def _next_pbm_token(data: bytes, pos: int) -> tuple[bytes, int]:
    length = len(data)
    while pos < length:
        current = data[pos]
        if current == 35:
            while pos < length and data[pos] not in b"\r\n":
                pos += 1
        elif chr(current).isspace():
            pos += 1
        else:
            break

    start = pos
    while pos < length and not chr(data[pos]).isspace():
        pos += 1
    return data[start:pos], pos


def _load_mask_rows(reference_path: Path) -> tuple[int, int, list[list[int]]]:
    raw = subprocess.check_output(
        [
            "magick",
            str(reference_path),
            "-alpha",
            "extract",
            "-threshold",
            "1%",
            "-trim",
            "+repage",
            "pbm:-",
        ]
    )
    if not raw.startswith(b"P4"):
        raise RuntimeError(f"Unexpected PBM header for {reference_path}")

    pos = 2
    width_token, pos = _next_pbm_token(raw, pos)
    height_token, pos = _next_pbm_token(raw, pos)
    width_px = int(width_token)
    height_px = int(height_token)
    while pos < len(raw) and chr(raw[pos]).isspace():
        pos += 1

    row_bytes = (width_px + 7) // 8
    rows: list[list[int]] = []
    filled = 0
    for row_index in range(height_px):
        chunk = raw[pos + row_index * row_bytes : pos + (row_index + 1) * row_bytes]
        row: list[int] = []
        for byte in chunk:
            for bit_index in range(7, -1, -1):
                row.append(0 if ((byte >> bit_index) & 1) else 1)
        row = row[:width_px]
        rows.append(row)
        filled += sum(row)

    # PBM black/white polarity is easy to invert accidentally through the threshold
    # pipeline, so fall back to the opposite sense if the foreground is implausibly sparse.
    if filled < width_px * height_px * 0.1:
        rows = [[1 - value for value in row] for row in rows]

    return width_px, height_px, rows


def load_silhouette_mask(reference_path: Path, *, mirror_x: bool) -> SilhouetteMask:
    width_px, height_px, rows = _load_mask_rows(reference_path)
    if mirror_x:
        rows = [list(reversed(row)) for row in rows]
    spans: list[tuple[int, int]] = []
    for row in rows:
        xs = [index for index, value in enumerate(row) if value]
        if not xs:
            raise RuntimeError(f"Reference row in {reference_path} has no foreground pixels after thresholding")
        left_px = min(xs)
        right_px = max(xs)
        spans.append((left_px, right_px))
    return SilhouetteMask(
        width_px=width_px,
        height_px=height_px,
        rows=tuple(tuple(value for value in row) for row in rows),
        spans_px=tuple(spans),
    )


def back_blend_weight(t: float, front_span: tuple[float, float], back_span: tuple[float, float]) -> float:
    if t >= BACK_BLEND_CUTOFF:
        return 0.0

    front_width = front_span[1] - front_span[0]
    back_width = back_span[1] - back_span[0]
    if t >= LOWER_BODY_OUTLIER_START and abs(front_width - back_width) > LOWER_BODY_WIDTH_DELTA:
        return 0.0

    return max(0.0, BACK_TOP_WEIGHT * (1.0 - t / BACK_BLEND_CUTOFF))


def extract_boundary_points(mask: SilhouetteMask) -> list[tuple[float, float]]:
    edges: list[tuple[tuple[int, int], tuple[int, int]]] = []
    for y_px, row in enumerate(mask.rows):
        for x_px, value in enumerate(row):
            if not value:
                continue
            if y_px == 0 or not mask.rows[y_px - 1][x_px]:
                edges.append(((x_px, y_px), (x_px + 1, y_px)))
            if x_px == mask.width_px - 1 or not row[x_px + 1]:
                edges.append(((x_px + 1, y_px), (x_px + 1, y_px + 1)))
            if y_px == mask.height_px - 1 or not mask.rows[y_px + 1][x_px]:
                edges.append(((x_px + 1, y_px + 1), (x_px, y_px + 1)))
            if x_px == 0 or not row[x_px - 1]:
                edges.append(((x_px, y_px + 1), (x_px, y_px)))

    next_points: dict[tuple[int, int], list[tuple[int, int]]] = defaultdict(list)
    for start, end in edges:
        next_points[start].append(end)

    start = min(next_points, key=lambda point: (point[1], point[0]))
    contour: list[tuple[int, int]] = [start]
    current = start
    previous: tuple[int, int] | None = None
    for _ in range(len(edges) + 8):
        candidates = next_points[current]
        if not candidates:
            break
        if len(candidates) == 1:
            nxt = candidates[0]
        else:
            vx = current[0] - previous[0] if previous is not None else 1
            vy = current[1] - previous[1] if previous is not None else 0
            nxt = min(candidates, key=lambda point: -(vx * (point[0] - current[0]) + vy * (point[1] - current[1])))
        contour.append(nxt)
        previous, current = current, nxt
        if current == start:
            break

    reduced: list[tuple[float, float]] = []
    for point in contour:
        reduced.append((float(point[0]), float(point[1])))
        while len(reduced) >= 3:
            ax_px, ay_px = reduced[-3]
            bx_px, by_px = reduced[-2]
            cx_px, cy_px = reduced[-1]
            if (bx_px - ax_px) * (cy_px - by_px) == (by_px - ay_px) * (cx_px - bx_px):
                reduced.pop(-2)
            else:
                break
    if reduced[0] != reduced[-1]:
        reduced.append(reduced[0])
    return reduced


def warp_contour_with_back_reference(
    contour: list[tuple[float, float]],
    front: SilhouetteMask,
    back: SilhouetteMask,
) -> list[tuple[float, float]]:
    warped: list[tuple[float, float]] = []
    for x_px, y_px in contour:
        t = min(1.0, max(0.0, y_px / front.height_px))
        front_span = front.sample_normalized_span(t)
        back_span = back.sample_normalized_span(t)
        blend = back_blend_weight(t, front_span, back_span)
        if blend <= 0.0:
            warped.append((x_px, y_px))
            continue

        x_normalized = x_px / front.width_px
        front_midpoint = (front_span[0] + front_span[1]) * 0.5
        if x_normalized <= front_midpoint:
            delta_x = (back_span[0] - front_span[0]) * blend
        else:
            delta_x = (back_span[1] - front_span[1]) * blend
        warped.append((x_px + delta_x * front.width_px, y_px))
    return warped


def chaikin(points: list[tuple[float, float]], iterations: int) -> list[tuple[float, float]]:
    outline = points[:]
    if outline[0] != outline[-1]:
        outline.append(outline[0])
    for _ in range(iterations):
        refined: list[tuple[float, float]] = []
        for a_point, b_point in zip(outline, outline[1:]):
            refined.append((0.75 * a_point[0] + 0.25 * b_point[0], 0.75 * a_point[1] + 0.25 * b_point[1]))
            refined.append((0.25 * a_point[0] + 0.75 * b_point[0], 0.25 * a_point[1] + 0.75 * b_point[1]))
        refined.append(refined[0])
        outline = refined
    return outline


def point_segment_distance(point: tuple[float, float], start: tuple[float, float], end: tuple[float, float]) -> float:
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    if dx == 0.0 and dy == 0.0:
        return ((point[0] - start[0]) ** 2 + (point[1] - start[1]) ** 2) ** 0.5
    t = ((point[0] - start[0]) * dx + (point[1] - start[1]) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    nearest = (start[0] + t * dx, start[1] + t * dy)
    return ((point[0] - nearest[0]) ** 2 + (point[1] - nearest[1]) ** 2) ** 0.5


def rdp_open(points: list[tuple[float, float]], epsilon: float) -> list[tuple[float, float]]:
    if len(points) <= 2:
        return points[:]
    start = points[0]
    end = points[-1]
    max_distance = -1.0
    split_index = None
    for index, point in enumerate(points[1:-1], start=1):
        distance = point_segment_distance(point, start, end)
        if distance > max_distance:
            max_distance = distance
            split_index = index
    if split_index is not None and max_distance > epsilon:
        left = rdp_open(points[: split_index + 1], epsilon)
        right = rdp_open(points[split_index:], epsilon)
        return left[:-1] + right
    return [start, end]


def simplify_closed(points: list[tuple[float, float]], epsilon: float) -> list[tuple[float, float]]:
    outline = points[:-1] if points[0] == points[-1] else points[:]
    simplified = rdp_open(outline + [outline[0]], epsilon)
    if simplified[0] != simplified[-1]:
        simplified.append(simplified[0])
    return simplified


def build_outline_points(front: SilhouetteMask, back: SilhouetteMask, sample_count: int) -> list[tuple[float, float]]:
    del sample_count
    contour_px = extract_boundary_points(front)
    contour_px = warp_contour_with_back_reference(contour_px, front, back)
    contour_px = chaikin(contour_px, CHAIKIN_ITERATIONS)
    contour_px = simplify_closed(contour_px, SIMPLIFY_TOLERANCE_PX)

    points: list[tuple[float, float]] = []
    for x_px, y_px in contour_px:
        points.append((x_px * (SVG_WIDTH_PX / front.width_px), y_px * (SVG_HEIGHT_PX / front.height_px)))

    if points[0] != points[-1]:
        points.append(points[0])
    return points


def format_svg(points: list[tuple[float, float]]) -> str:
    path_tokens = [f"M {points[0][0]:.3f},{points[0][1]:.3f}"]
    path_tokens.extend(f"L {x_px:.3f},{y_px:.3f}" for x_px, y_px in points[1:])
    path_tokens.append("Z")
    path_data = " ".join(path_tokens)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{SVG_WIDTH_PX:.0f}" height="{SVG_HEIGHT_PX:.0f}" '
        f'viewBox="0 0 {SVG_WIDTH_PX:.0f} {SVG_HEIGHT_PX:.0f}">\n'
        f'  <path d="{path_data}" fill="none" stroke="black" stroke-width="1"/>\n'
        "</svg>\n"
    )


def main() -> int:
    args = parse_args()
    front = load_silhouette_mask(args.front, mirror_x=False)
    back = load_silhouette_mask(args.back, mirror_x=True)
    outline_points = build_outline_points(front, back, args.samples)
    args.output.write_text(format_svg(outline_points), encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
