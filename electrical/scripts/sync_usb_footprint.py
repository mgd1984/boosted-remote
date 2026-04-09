#!/usr/bin/env python3

import argparse
import os
from pathlib import Path
import sys

KICAD_FRAMEWORKS = "/Applications/KiCad/KiCad.app/Contents/Frameworks"
KICAD_PYTHON = "/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/bin/python3.9"
KICAD_SITE_PACKAGES = "/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/lib/python3.9/site-packages"

if Path(sys.executable) != Path(KICAD_PYTHON) and os.environ.get("BOOSTED_REMOTE_KICAD_PYTHON") != "1":
    env = os.environ.copy()
    env["BOOSTED_REMOTE_KICAD_PYTHON"] = "1"
    env["DYLD_FRAMEWORK_PATH"] = KICAD_FRAMEWORKS
    env["DYLD_LIBRARY_PATH"] = KICAD_FRAMEWORKS
    os.execvpe(KICAD_PYTHON, [KICAD_PYTHON, *sys.argv], env)

sys.path.append(KICAD_SITE_PACKAGES)
import wx  # type: ignore

WX_APP = wx.App(False)
import pcbnew  # type: ignore

from build_usb_mini_footprint import LOCAL_FOOTPRINT_DIR, USB_FOOTPRINT_NAME, ensure_repo_usb_footprint


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BOARD = ROOT / "electrical" / "kicad" / "boosted_remote.kicad_pcb"


def find_footprint(board: pcbnew.BOARD, reference: str) -> pcbnew.FOOTPRINT:
    for footprint in board.GetFootprints():
        if footprint.GetReference() == reference:
            return footprint
    raise RuntimeError(f"Footprint {reference} not found")


def sorted_pad_groups(footprint: pcbnew.FOOTPRINT) -> dict[tuple[str, str], list[pcbnew.PAD]]:
    groups: dict[tuple[str, str], list[pcbnew.PAD]] = {}
    for pad in footprint.Pads():
        key = (pad.GetNumber(), pad.GetName())
        groups.setdefault(key, []).append(pad)
    for pads in groups.values():
        pads.sort(key=lambda pad: (pad.GetCenter().x, pad.GetCenter().y, pad.GetSizeX(), pad.GetSizeY()))
    return groups


def sync_usb_footprint(board_path: Path, reference: str) -> None:
    ensure_repo_usb_footprint()
    board = pcbnew.LoadBoard(str(board_path))
    old = find_footprint(board, reference)
    new = pcbnew.FootprintLoad(str(LOCAL_FOOTPRINT_DIR), USB_FOOTPRINT_NAME)
    if new is None:
        raise RuntimeError("Failed to load generated USB footprint")

    new.SetReference(old.GetReference())
    new.SetValue(old.GetValue())
    new.SetPosition(old.GetPosition())
    new.SetOrientation(old.GetOrientation())
    if old.IsFlipped():
        new.Flip(old.GetPosition(), False)
    new.SetAttributes(old.GetAttributes())

    for old_field, new_field in zip(old.GetFields(), new.GetFields()):
        new_field.SetTextAngle(old_field.GetTextAngle())

    old_pad_groups = sorted_pad_groups(old)
    new_pad_groups = sorted_pad_groups(new)
    if set(old_pad_groups) != set(new_pad_groups):
        raise RuntimeError("USB footprint pad groups changed unexpectedly")

    for key, old_pads in old_pad_groups.items():
        new_pads = new_pad_groups[key]
        if len(old_pads) != len(new_pads):
            raise RuntimeError(f"USB footprint pad multiplicity changed for {key}")
        for old_pad, new_pad in zip(old_pads, new_pads):
            new_pad.SetNet(old_pad.GetNet())
            new_pad.SetOrientation(old_pad.GetOrientation())

    old_text_items = [item for item in old.GraphicalItems() if item.GetClass() == "PCB_TEXT"]
    new_text_items = [item for item in new.GraphicalItems() if item.GetClass() == "PCB_TEXT"]
    if len(old_text_items) != len(new_text_items):
        raise RuntimeError("USB footprint text item count changed unexpectedly")
    for old_text, new_text in zip(old_text_items, new_text_items):
        new_text.SetTextAngle(old_text.GetTextAngle())

    board.Remove(old)
    board.Add(new)
    pcbnew.SaveBoard(str(board_path), board)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--board", type=Path, default=DEFAULT_BOARD)
    parser.add_argument("--reference", default="J1")
    args = parser.parse_args()
    sync_usb_footprint(args.board, args.reference)
    print(args.board)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
