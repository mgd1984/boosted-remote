#!/usr/bin/env python3

import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.append("/Applications/KiCad/KiCad.app/Contents/Frameworks/python/site-packages")
import wx  # type: ignore

WX_APP = wx.App(False)
import pcbnew  # type: ignore


ROOT = Path(__file__).resolve().parents[2]
KICAD = ROOT / "electrical" / "kicad"
PROJECT = KICAD / "boosted_remote"
JAVA = "/Library/Java/JavaVirtualMachines/temurin-21.jdk/Contents/Home/bin/java"
FREEROUTING = ROOT / "tools" / "freerouting-2.1.0.jar"
KICAD_CLI = "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli"
BLOCKER_CATEGORIES = {
    "shorting_items",
    "clearance",
    "tracks_crossing",
    "copper_edge_clearance",
    "via_diameter",
    "drill_out_of_range",
    "starved_thermal",
    "solder_mask_bridge",
    "track_dangling",
}


def run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=ROOT, check=check, text=True, capture_output=True)


def export_dsn(board_path: Path, dsn_path: Path) -> None:
    board = pcbnew.LoadBoard(str(board_path))
    pcbnew.ExportSpecctraDSN(board, str(dsn_path))


def import_session(base_board: Path, ses_path: Path, out_path: Path) -> None:
    board = pcbnew.LoadBoard(str(base_board))
    pcbnew.ImportSpecctraSES(board, str(ses_path))
    board.BuildConnectivity()
    pcbnew.SaveBoard(str(out_path), board)


def normalize_board(src: Path, dst: Path) -> None:
    board = pcbnew.LoadBoard(str(src))
    board.BuildConnectivity()
    pcbnew.SaveBoard(str(dst), board)


def attach_project_context(board_path: Path) -> None:
    for suffix in (".kicad_pro", ".kicad_prl"):
        src = PROJECT.with_suffix(suffix)
        if src.exists():
            shutil.copy2(src, board_path.with_suffix(suffix))


def drc_report(board_path: Path, report_path: Path) -> bool:
    attach_project_context(board_path)
    first = run([KICAD_CLI, "pcb", "drc", "--output", str(report_path), str(board_path)], check=False)
    if first.returncode == 0:
        return True
    run([KICAD_CLI, "pcb", "upgrade", str(board_path)], check=False)
    second = run([KICAD_CLI, "pcb", "drc", "--output", str(report_path), str(board_path)], check=False)
    return second.returncode == 0


def parse_report(report_path: Path) -> tuple[int, int, set[str]]:
    text = report_path.read_text()
    viol_match = re.search(r"\*\* Found (\d+) DRC violations \*\*", text)
    unc_match = re.search(r"\*\* Found (\d+) unconnected pads \*\*", text)
    categories = set(re.findall(r"^\[([a-z_]+)\]:", text, flags=re.M))
    return int(viol_match.group(1)), int(unc_match.group(1)), categories


def run_freerouting(dsn_path: Path, ses_path: Path, timeout: str) -> subprocess.CompletedProcess:
    return run(
        [
            JAVA,
            "-jar",
            str(FREEROUTING),
            "-de",
            str(dsn_path),
            "-do",
            str(ses_path),
            "--guiSettings.isEnabled=false",
            "--guiSettings.exitWhenFinished=true",
            "--routerSettings.enabled=true",
            "--routerSettings.optimizer.enabled=false",
            f"--routerSettings.jobTimeoutString={timeout}",
        ],
        check=False,
    )


def promote(src: Path, dst: Path) -> None:
    shutil.copy2(src, dst)


def main() -> int:
    live_board = KICAD / "boosted_remote.kicad_pcb"
    live_report = KICAD / "drc.rpt"

    if not live_report.exists():
        ok = drc_report(live_board, live_report)
        if not ok:
            raise SystemExit("Unable to produce baseline DRC report")

    _, best_unconnected, best_categories = parse_report(live_report)
    if best_categories & BLOCKER_CATEGORIES:
        raise SystemExit("Baseline board still has blocker DRC categories")

    best_board = live_board
    print(f"baseline unconnected={best_unconnected}")

    for idx in range(1, 5):
        stem = KICAD / f"route_iter_{idx}"
        dsn_path = stem.with_suffix(".dsn")
        ses_path = stem.with_suffix(".ses")
        raw_board = stem.with_name(f"{stem.name}_raw.kicad_pcb")
        norm_board = stem.with_name(f"{stem.name}_norm.kicad_pcb")
        report_path = stem.with_name(f"{stem.name}.rpt")

        export_dsn(best_board, dsn_path)
        fr = run_freerouting(dsn_path, ses_path, "00:01:00")
        print(fr.stdout)
        if not ses_path.exists():
            print(f"iteration {idx}: no session file")
            break

        import_session(best_board, ses_path, raw_board)
        normalize_board(raw_board, norm_board)

        if not drc_report(norm_board, report_path):
            print(f"iteration {idx}: DRC load failed")
            break

        _, unconnected, categories = parse_report(report_path)
        blockers = categories & BLOCKER_CATEGORIES
        print(f"iteration {idx}: unconnected={unconnected} blockers={sorted(blockers)}")
        if blockers:
            print(f"iteration {idx}: rejected")
            break
        if unconnected >= best_unconnected:
            print(f"iteration {idx}: no improvement")
            break

        promote(norm_board, live_board)
        promote(report_path, live_report)
        best_board = live_board
        best_unconnected = unconnected
        print(f"iteration {idx}: promoted")

        if best_unconnected == 0:
            break

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
