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


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BOARD = ROOT / "electrical" / "kicad" / "boosted_remote.kicad_pcb"


def enabled_copper_layer_set(board: pcbnew.BOARD) -> pcbnew.LSET:
    layers = pcbnew.LSET()
    for layer in board.GetEnabledLayers().Seq():
        if board.GetLayerName(layer).endswith(".Cu"):
            layers.AddLayer(layer)
    return layers


def sync_keepout(board_path: Path, reference: str) -> None:
    board = pcbnew.LoadBoard(str(board_path))
    footprint = next(fp for fp in board.GetFootprints() if fp.GetReference() == reference)
    layers = enabled_copper_layer_set(board)
    for zone in footprint.Zones():
        zone.SetLayerSet(layers)
    pcbnew.SaveBoard(str(board_path), board)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--board", type=Path, default=DEFAULT_BOARD)
    parser.add_argument("--reference", default="U1")
    args = parser.parse_args()
    sync_keepout(args.board, args.reference)
    print(args.board)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
