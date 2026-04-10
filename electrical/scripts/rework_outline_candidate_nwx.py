#!/usr/bin/env python3

from __future__ import annotations

import argparse
import sys
from pathlib import Path


KICAD_PYTHON_CANDIDATES = [
    "/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/lib/python3.9/site-packages",
    "/Applications/KiCad/KiCad.app/Contents/Frameworks/python/site-packages",
]

for candidate in KICAD_PYTHON_CANDIDATES:
    if candidate not in sys.path and Path(candidate).exists():
        sys.path.append(candidate)

import wx  # type: ignore

WX_APP = wx.App(False)

import pcbnew  # type: ignore


ROOT = Path(__file__).resolve().parents[2]
KICAD_DIR = ROOT / "electrical" / "kicad"
BOARD_PATH = KICAD_DIR / "boosted_remote_pcb_outline_candidate.kicad_pcb"
NET_CODES: dict[str, int] = {}


def mm(value: float) -> int:
    return pcbnew.FromMM(value)


def to_mm(value: int) -> float:
    return pcbnew.ToMM(value)


def pt(x: float, y: float) -> pcbnew.VECTOR2I:
    return pcbnew.VECTOR2I(mm(x), mm(y))


def angle(degrees: float) -> pcbnew.EDA_ANGLE:
    return pcbnew.EDA_ANGLE(degrees, pcbnew.DEGREES_T)


def route(
    board: pcbnew.BOARD,
    net_name: str,
    points: list[tuple[float, float]],
    *,
    layer: int,
    width: float = 0.2,
) -> None:
    for a, b in zip(points, points[1:]):
        track = pcbnew.PCB_TRACK(board)
        track.SetNetCode(NET_CODES[net_name])
        track.SetLayer(layer)
        track.SetWidth(mm(width))
        track.SetStart(pt(*a))
        track.SetEnd(pt(*b))
        board.Add(track)


def add_via(
    board: pcbnew.BOARD,
    net_name: str,
    x: float,
    y: float,
    *,
    drill: float = 0.3,
    diameter: float = 0.6,
) -> None:
    via = pcbnew.PCB_VIA(board)
    via.SetNetCode(NET_CODES[net_name])
    via.SetPosition(pt(x, y))
    via.SetDrill(mm(drill))
    via.SetWidth(mm(diameter))
    via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    board.Add(via)


def find_footprint(board: pcbnew.BOARD, ref: str):
    for footprint in board.Footprints():
        if footprint.GetReference() == ref:
            return footprint
    raise RuntimeError(f"Missing footprint {ref}")


def move_footprint(board: pcbnew.BOARD, ref: str, x: float, y: float, rotation: float):
    footprint = find_footprint(board, ref)
    footprint.SetPosition(pt(x, y))
    footprint.SetOrientation(angle(rotation))
    return footprint


def item_in_box(item: pcbnew.BOARD_ITEM, xmin: float, xmax: float, ymin: float, ymax: float) -> bool:
    if isinstance(item, pcbnew.PCB_VIA):
        x = to_mm(item.GetX())
        y = to_mm(item.GetY())
        return xmin <= x <= xmax and ymin <= y <= ymax
    if isinstance(item, pcbnew.PCB_TRACK):
        x1 = to_mm(item.GetStartX())
        y1 = to_mm(item.GetStartY())
        x2 = to_mm(item.GetEndX())
        y2 = to_mm(item.GetEndY())
        return not (max(x1, x2) < xmin or min(x1, x2) > xmax or max(y1, y2) < ymin or min(y1, y2) > ymax)
    return False


def remove_local_copper(
    board: pcbnew.BOARD,
    net_names: set[str],
    boxes: list[tuple[float, float, float, float]],
) -> None:
    to_remove: list[pcbnew.BOARD_ITEM] = []
    for item in board.AllConnectedItems():
        if not isinstance(item, (pcbnew.PCB_TRACK, pcbnew.PCB_VIA)):
            continue
        if item.GetNetname() not in net_names:
            continue
        if any(item_in_box(item, *box) for box in boxes):
            to_remove.append(item)
    for item in to_remove:
        board.Remove(item)


def prepare_footprints(board: pcbnew.BOARD) -> None:
    move_footprint(board, "J3", 65.841, 99.949, 0.0)
    move_footprint(board, "R7", 87.412, 105.949, 0.0)
    move_footprint(board, "SW1", 93.341, 86.949, 90.0)
    move_footprint(board, "J1", 81.641, 159.949, -21.909)


def clear_hotspot_copper(board: pcbnew.BOARD) -> None:
    remove_local_copper(
        board,
        {"V3P3", "GND", "UART_RX", "UART_TX", "EN", "BOOT"},
        [(61.0, 68.2, 74.5, 107.0)],
    )
    remove_local_copper(
        board,
        {"BAT_SENSE", "LED4", "HALL_OUT", "PWR_BTN", "BUZZ_PWM"},
        [
            (61.5, 71.0, 79.5, 124.5),
            (81.5, 89.5, 48.0, 80.0),
            (88.8, 92.8, 81.0, 149.0),
        ],
    )
    remove_local_copper(
        board,
        {"STATUS_B", "STATUS_B_A", "DEADMAN", "GND"},
        [(84.0, 99.0, 84.0, 108.5)],
    )
    remove_local_copper(
        board,
        {"VBUS", "GND"},
        [(71.5, 86.5, 151.0, 166.0)],
    )


def reroute_j3(board: pcbnew.BOARD) -> None:
    pad1 = (65.841, 99.949)
    pad2 = (65.841, 101.219)
    pad3 = (65.841, 102.489)
    pad4 = (65.841, 103.759)
    pad5 = (65.841, 105.029)
    pad6 = (65.841, 106.299)

    route(board, "V3P3", [pad1, (66.6, 99.1), (67.68, 98.511)], layer=pcbnew.B_Cu)
    route(board, "GND", [pad2, (64.8, 100.178), (64.8, 76.5), (65.641, 75.199)], layer=pcbnew.B_Cu)
    route(board, "UART_RX", [pad3, (65.926, 102.404), (65.926, 86.179)], layer=pcbnew.B_Cu)
    route(board, "UART_TX", [pad4, (65.2, 103.118), (65.2, 84.949), (64.591, 84.949)], layer=pcbnew.B_Cu)
    route(board, "EN", [pad5, (66.869, 104.001), (66.869, 99.113)], layer=pcbnew.B_Cu)
    route(board, "BOOT", [pad6, (65.2, 105.658), (65.2, 75.949), (64.591, 75.949)], layer=pcbnew.B_Cu)


def reroute_left_edge_spines(board: pcbnew.BOARD) -> None:
    route(board, "BAT_SENSE", [(66.611, 79.629), (68.3, 81.318), (68.3, 123.0), (66.441, 123.601)], layer=pcbnew.F_Cu)
    route(board, "LED4", [(64.591, 80.449), (64.8, 80.658), (64.8, 86.4), (69.0, 90.6), (69.0, 94.666), (71.317, 94.666)], layer=pcbnew.B_Cu)
    route(board, "HALL_OUT", [(88.391, 49.167), (90.2, 50.976), (90.2, 74.0), (83.77, 78.949)], layer=pcbnew.B_Cu)
    route(board, "PWR_BTN", [(82.091, 81.949), (88.6, 81.949), (88.6, 139.4), (78.8, 139.4)], layer=pcbnew.B_Cu)
    route(board, "PWR_BTN", [(88.6, 148.0), (81.6, 148.0)], layer=pcbnew.B_Cu)
    route(board, "PWR_BTN", [(88.6, 139.4), (88.6, 148.0)], layer=pcbnew.B_Cu)
    route(board, "BUZZ_PWM", [(89.416, 108.243), (90.8, 109.627), (90.8, 124.949), (92.516, 124.949)], layer=pcbnew.F_Cu)


def reroute_right_shoulder(board: pcbnew.BOARD) -> None:
    r7_pad1 = (86.587, 105.949)
    r7_pad2 = (88.237, 105.949)
    sw1_pad1 = (94.241, 85.724)
    sw1_gnd = (94.241, 86.949)

    route(board, "STATUS_B", [r7_pad1, (86.587, 104.019), (86.587, 88.439)], layer=pcbnew.F_Cu)
    route(board, "STATUS_B_A", [r7_pad2, (93.554, 105.949)], layer=pcbnew.F_Cu)
    route(board, "DEADMAN", [(82.091, 80.449), (92.6, 80.449), (92.6, 85.724), sw1_pad1], layer=pcbnew.B_Cu)
    route(board, "GND", [sw1_gnd, (92.4, 86.949), (90.016, 91.367)], layer=pcbnew.B_Cu)
    route(board, "GND", [(95.129, 97.949), (93.0, 97.949), (90.016, 94.317)], layer=pcbnew.F_Cu)
    route(board, "GND", [(95.129, 105.949), (93.0, 105.949), (93.0, 97.949)], layer=pcbnew.F_Cu)


def reroute_j1(board: pcbnew.BOARD) -> None:
    pad_vbus = (81.164, 156.847)
    pad_gnd = (84.133, 158.041)
    left_lower = (78.483, 155.876)
    left_upper = (76.449, 160.932)
    right_lower = (86.74, 159.197)
    right_upper = (84.706, 164.253)

    add_via(board, "VBUS", 79.9, 155.1)
    route(board, "VBUS", [(71.8, 156.2), (79.9, 156.2), (79.9, 155.1)], layer=pcbnew.B_Cu)
    route(board, "VBUS", [(79.9, 155.1), pad_vbus], layer=pcbnew.F_Cu)

    add_via(board, "GND", 79.2, 153.2)
    route(board, "GND", [(76.341, 152.174), (79.2, 152.174), (79.2, 153.2)], layer=pcbnew.B_Cu)
    route(board, "GND", [left_lower, left_upper, right_upper, right_lower, left_lower], layer=pcbnew.F_Cu)
    route(board, "GND", [left_lower, (79.2, 153.2)], layer=pcbnew.F_Cu)
    route(board, "GND", [pad_gnd, right_lower], layer=pcbnew.F_Cu)


def refill_zones(board: pcbnew.BOARD) -> None:
    filler = pcbnew.ZONE_FILLER(board)
    filler.Fill(board.Zones())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--board", type=Path, default=BOARD_PATH)
    parser.add_argument(
        "--ripup-only",
        action="store_true",
        help="Only clear hotspot copper and normalize placement. Leave rerouting to a follow-on autorouter pass.",
    )
    args = parser.parse_args()

    board = pcbnew.LoadBoard(str(args.board))
    global NET_CODES
    NET_CODES = {name: board.GetNetcodeFromNetname(name) for name in {
        "BAT_SENSE",
        "BOOT",
        "BUZZ_PWM",
        "DEADMAN",
        "EN",
        "GND",
        "HALL_OUT",
        "LED4",
        "PWR_BTN",
        "STATUS_B",
        "STATUS_B_A",
        "UART_RX",
        "UART_TX",
        "VBUS",
        "V3P3",
    }}

    clear_hotspot_copper(board)
    prepare_footprints(board)
    if not args.ripup_only:
        reroute_j3(board)
        reroute_left_edge_spines(board)
        reroute_right_shoulder(board)
        reroute_j1(board)
    refill_zones(board)
    board.BuildConnectivity()
    pcbnew.SaveBoard(str(args.board), board)
    print(args.board)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
