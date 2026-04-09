#!/usr/bin/env python3

import argparse
import shutil
import sys
from pathlib import Path

sys.path.append("/Applications/KiCad/KiCad.app/Contents/Frameworks/python/site-packages")
import wx  # type: ignore

WX_APP = wx.App(False)
import pcbnew  # type: ignore


ROOT = Path(__file__).resolve().parents[2]
KICAD = ROOT / "electrical" / "kicad"
SRC = KICAD / "boosted_remote.kicad_pcb"
DST = KICAD / "boosted_remote_packets.kicad_pcb"

REHOMED_PLACEMENTS = {
    "U3": (86.5, 101.5, 90),
    "R9": (88.0, 61.0, 90),
    "C3": (86.0, 105.5, 90),
    "C4": (89.5, 105.0, 90),
}


def mm(value: float) -> int:
    return pcbnew.FromMM(value)


def pt(x: float, y: float) -> pcbnew.VECTOR2I:
    return pcbnew.VECTOR2I(mm(x), mm(y))


def angle(degrees: float) -> pcbnew.EDA_ANGLE:
    return pcbnew.EDA_ANGLE(degrees, pcbnew.DEGREES_T)


def add_track(
    board: pcbnew.BOARD,
    net_name: str,
    a: tuple[float, float],
    b: tuple[float, float],
    width: float = 0.2,
    layer: int = pcbnew.F_Cu,
) -> None:
    track = pcbnew.PCB_TRACK(board)
    track.SetNetCode(board.GetNetcodeFromNetname(net_name))
    track.SetStart(pt(*a))
    track.SetEnd(pt(*b))
    track.SetWidth(mm(width))
    track.SetLayer(layer)
    board.Add(track)


def add_via(
    board: pcbnew.BOARD,
    net_name: str,
    x: float,
    y: float,
    drill: float = 0.3,
    diameter: float = 0.6,
) -> None:
    via = pcbnew.PCB_VIA(board)
    via.SetNetCode(board.GetNetcodeFromNetname(net_name))
    via.SetPosition(pt(x, y))
    via.SetDrill(mm(drill))
    via.SetWidth(mm(diameter))
    via.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    board.Add(via)


def route(
    board: pcbnew.BOARD,
    net_name: str,
    points: list[tuple[float, float]],
    width: float = 0.2,
    layer: int = pcbnew.F_Cu,
) -> None:
    for a, b in zip(points, points[1:]):
        add_track(board, net_name, a, b, width, layer)


def dogbone(
    board: pcbnew.BOARD,
    net_name: str,
    pad_pt: tuple[float, float],
    via_pt: tuple[float, float],
    width: float = 0.2,
) -> None:
    add_track(board, net_name, pad_pt, via_pt, width, pcbnew.F_Cu)
    add_via(board, net_name, *via_pt)


def move_footprint(board: pcbnew.BOARD, ref: str, x: float, y: float, rotation: float) -> None:
    footprint = board.FindFootprintByReference(ref)
    if footprint is None:
        raise RuntimeError(f"Missing footprint {ref}")
    footprint.SetPosition(pt(x, y))
    footprint.SetOrientation(angle(rotation))


def packet_rehome_offboard_parts(board: pcbnew.BOARD) -> None:
    for ref, (x, y, rotation) in REHOMED_PLACEMENTS.items():
        move_footprint(board, ref, x, y, rotation)


def item_in_box(item: pcbnew.BOARD_ITEM, xmin: float, xmax: float, ymin: float, ymax: float) -> bool:
    if isinstance(item, pcbnew.PCB_VIA):
        x = pcbnew.ToMM(item.GetX())
        y = pcbnew.ToMM(item.GetY())
        return xmin <= x <= xmax and ymin <= y <= ymax
    if isinstance(item, pcbnew.PCB_TRACK):
        x1 = pcbnew.ToMM(item.GetStartX())
        y1 = pcbnew.ToMM(item.GetStartY())
        x2 = pcbnew.ToMM(item.GetEndX())
        y2 = pcbnew.ToMM(item.GetEndY())
        return not (max(x1, x2) < xmin or min(x1, x2) > xmax or max(y1, y2) < ymin or min(y1, y2) > ymax)
    return False


def remove_local_copper(
    board: pcbnew.BOARD,
    net_names: set[str],
    boxes: list[tuple[float, float, float, float]],
) -> None:
    tracks = pcbnew.TRACKS(board.Tracks())
    all_tracks = [pcbnew.PCB_TRACK(tracks[idx]) for idx in range(tracks.size())]
    to_remove = []
    for item in all_tracks:
        if item.GetNetname() not in net_names:
            continue
        if any(item_in_box(item, xmin, xmax, ymin, ymax) for xmin, xmax, ymin, ymax in boxes):
            to_remove.append(item)
    for item in to_remove:
        board.Remove(item)


def packet_rehome_regulator_cluster(board: pcbnew.BOARD) -> None:
    packet_rehome_offboard_parts(board)


def packet_upper_gnd_sw1_u4(board: pcbnew.BOARD) -> None:
    add_via(board, "GND", 109.8, 28.7)
    add_via(board, "GND", 100.2, 25.5)
    route(board, "GND", [(108.0, 30.0625), (109.8, 28.7)], 0.2, pcbnew.F_Cu)
    route(board, "GND", [(109.8, 28.7), (104.0, 28.7), (100.2, 25.5)], 0.2, pcbnew.B_Cu)
    route(board, "GND", [(100.2, 25.5), (98.6, 24.0)], 0.2, pcbnew.F_Cu)


def packet_led2(board: pcbnew.BOARD) -> None:
    dogbone(board, "LED2", (100.75, 51.5), (102.0, 50.5))
    dogbone(board, "LED2", (104.0, 99.825), (102.7, 99.825))
    route(board, "LED2", [(102.0, 50.5), (102.35, 75.0), (102.7, 99.825)], 0.2, pcbnew.B_Cu)


def packet_bat_sense(board: pcbnew.BOARD) -> None:
    dogbone(board, "BAT_SENSE", (100.75, 45.5), (102.0, 44.3))
    dogbone(board, "BAT_SENSE", (97.0, 93.825), (98.2, 93.825))
    route(board, "BAT_SENSE", [(102.0, 44.3), (100.0, 58.0), (98.2, 93.825)], 0.2, pcbnew.B_Cu)


def packet_pwr_btn(board: pcbnew.BOARD) -> None:
    dogbone(board, "PWR_BTN", (91.4, 21.0), (89.8, 21.0))
    dogbone(board, "PWR_BTN", (83.25, 50.0), (81.7, 50.9))
    route(board, "PWR_BTN", [(89.8, 21.0), (86.0, 34.0), (81.7, 50.9)], 0.2, pcbnew.B_Cu)


def packet_gnd_j3_u1(board: pcbnew.BOARD) -> None:
    dogbone(board, "GND", (83.25, 56.0), (81.8, 56.8))
    route(board, "GND", [(82.0, 69.27), (80.8, 68.0), (80.8, 60.0), (81.8, 56.8)], 0.2, pcbnew.B_Cu)


def packet_gnd_j3_u1_alt(board: pcbnew.BOARD) -> None:
    dogbone(board, "GND", (83.25, 56.0), (84.4, 56.8))
    route(board, "GND", [(82.0, 69.27), (84.4, 69.27), (84.4, 56.8)], 0.2, pcbnew.B_Cu)


def packet_gnd_lower_cluster(board: pcbnew.BOARD) -> None:
    dogbone(board, "GND", (80.0, 99.1375), (78.6, 99.1375))
    dogbone(board, "GND", (87.0, 98.1375), (88.4, 98.1375))
    dogbone(board, "GND", (91.0, 104.225), (92.4, 104.225))
    dogbone(board, "GND", (96.0, 100.175), (97.4, 100.175))
    route(board, "GND", [(78.6, 99.1375), (84.0, 99.1375), (88.4, 98.1375), (92.4, 104.225)], 0.2, pcbnew.B_Cu)
    route(board, "GND", [(92.4, 104.225), (97.4, 100.175)], 0.2, pcbnew.B_Cu)


def packet_gnd_lower_cluster_alt(board: pcbnew.BOARD) -> None:
    dogbone(board, "GND", (80.0, 99.1375), (81.2, 100.2))
    dogbone(board, "GND", (87.0, 98.1375), (85.7, 97.0))
    dogbone(board, "GND", (91.0, 104.225), (92.2, 105.2))
    dogbone(board, "GND", (96.0, 100.175), (97.2, 99.0))
    route(board, "GND", [(81.2, 100.2), (84.0, 100.2), (85.7, 97.0), (90.5, 97.0), (92.2, 105.2)], 0.2, pcbnew.B_Cu)
    route(board, "GND", [(92.2, 105.2), (95.0, 102.5), (97.2, 99.0)], 0.2, pcbnew.B_Cu)


def packet_pwr_btn_alt(board: pcbnew.BOARD) -> None:
    dogbone(board, "PWR_BTN", (91.4, 21.0), (89.8, 21.0))
    dogbone(board, "PWR_BTN", (83.25, 50.0), (82.4, 49.8))
    route(board, "PWR_BTN", [(89.8, 21.0), (86.5, 33.0), (82.4, 49.8)], 0.2, pcbnew.B_Cu)


PACKETS = {
    "rehome_regulator_cluster": packet_rehome_regulator_cluster,
    "rehome_offboard_parts": packet_rehome_offboard_parts,
    "gnd_j3_u1": packet_gnd_j3_u1,
    "gnd_j3_u1_alt": packet_gnd_j3_u1_alt,
    "gnd_lower_cluster": packet_gnd_lower_cluster,
    "gnd_lower_cluster_alt": packet_gnd_lower_cluster_alt,
    "upper_gnd_sw1_u4": packet_upper_gnd_sw1_u4,
    "led2": packet_led2,
    "bat_sense": packet_bat_sense,
    "pwr_btn": packet_pwr_btn,
    "pwr_btn_alt": packet_pwr_btn_alt,
}


def attach_project_context(board_path: Path) -> None:
    for suffix in (".kicad_pro", ".kicad_prl"):
        src = (KICAD / "boosted_remote").with_suffix(suffix)
        if src.exists():
            shutil.copy2(src, board_path.with_suffix(suffix))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--src", type=Path, default=SRC)
    parser.add_argument("--dst", type=Path, default=DST)
    parser.add_argument("packets", nargs="*", choices=sorted(PACKETS))
    args = parser.parse_args()

    board = pcbnew.LoadBoard(str(args.src))
    names = args.packets or ["upper_gnd_sw1_u4"]
    for name in names:
        PACKETS[name](board)

    board.BuildConnectivity()
    pcbnew.SaveBoard(str(args.dst), board)
    attach_project_context(args.dst)
    print(args.dst)
    print("packets:", ",".join(names))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
