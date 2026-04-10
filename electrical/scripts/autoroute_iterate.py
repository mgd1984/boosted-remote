#!/usr/bin/env python3

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.append("/Applications/KiCad/KiCad.app/Contents/Frameworks/python/site-packages")
import wx  # type: ignore

WX_APP = wx.App(False)
import pcbnew  # type: ignore


ROOT = Path(__file__).resolve().parents[2]
KICAD = ROOT / "electrical" / "kicad"
DEFAULT_BOARD = KICAD / "boosted_remote.kicad_pcb"
DEFAULT_REPORT = KICAD / "drc.rpt"
DEFAULT_PROJECT_STEM = KICAD / "boosted_remote"
PCB_OUTLINE_TARGET_SVG = ROOT / "mechanical" / "references" / "boosted_remote_pcb_outline_target.svg"
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
OUTLINE_CANDIDATE_NET_NAMES = {
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
}


@dataclass(frozen=True)
class ReportSummary:
    violations: int
    unconnected: int
    category_counts: dict[str, int]

    @classmethod
    def from_path(cls, report_path: Path) -> "ReportSummary":
        text = report_path.read_text()
        viol_match = re.search(r"\*\* Found (\d+) DRC violations \*\*", text)
        unc_match = re.search(r"\*\* Found (\d+) unconnected pads \*\*", text)
        if not viol_match or not unc_match:
            raise RuntimeError(f"Unable to parse DRC summary from {report_path}")

        counts: dict[str, int] = {}
        for match in re.finditer(r"^\[([a-z_]+)\]:", text, flags=re.M):
            category = match.group(1)
            counts[category] = counts.get(category, 0) + 1

        return cls(
            violations=int(viol_match.group(1)),
            unconnected=int(unc_match.group(1)),
            category_counts=counts,
        )

    def count(self, category: str) -> int:
        return self.category_counts.get(category, 0)

    def blocker_total(self) -> int:
        return sum(self.count(category) for category in BLOCKER_CATEGORIES)

    def describe(self) -> str:
        nonzero = [
            f"{category}={self.count(category)}"
            for category in sorted(self.category_counts)
            if self.count(category)
        ]
        category_text = ", ".join(nonzero) if nonzero else "none"
        return (
            f"violations={self.violations} "
            f"unconnected={self.unconnected} "
            f"blockers={self.blocker_total()} "
            f"categories=[{category_text}]"
        )


def run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=ROOT, check=check, text=True, capture_output=True)


def mm(value: float) -> int:
    return pcbnew.FromMM(value)


def to_mm(value: int) -> float:
    return pcbnew.ToMM(value)


def pt(x: float, y: float) -> pcbnew.VECTOR2I:
    return pcbnew.VECTOR2I(mm(x), mm(y))


def angle(degrees: float) -> pcbnew.EDA_ANGLE:
    return pcbnew.EDA_ANGLE(degrees, pcbnew.DEGREES_T)


def ensure_board(board_obj):
    if hasattr(board_obj, "BuildConnectivity"):
        return board_obj
    return pcbnew.Cast_to_BOARD(board_obj)


def load_board(board_path: Path):
    return ensure_board(pcbnew.LoadBoard(str(board_path)))


def export_dsn(board_path: Path, dsn_path: Path) -> None:
    board = load_board(board_path)
    pcbnew.ExportSpecctraDSN(board, str(dsn_path))


def import_session(base_board: Path, ses_path: Path, out_path: Path) -> None:
    board = load_board(base_board)
    pcbnew.ImportSpecctraSES(board, str(ses_path))
    board.BuildConnectivity()
    pcbnew.SaveBoard(str(out_path), board)


def normalize_board(src: Path, dst: Path) -> None:
    board = load_board(src)
    board.BuildConnectivity()
    pcbnew.SaveBoard(str(dst), board)


def attach_project_context(board_path: Path, project_stem: Path) -> None:
    for suffix in (".kicad_pro", ".kicad_prl"):
        src = project_stem.with_suffix(suffix)
        if src.exists():
            shutil.copy2(src, board_path.with_suffix(suffix))


def drc_report(board_path: Path, report_path: Path, project_stem: Path) -> bool:
    attach_project_context(board_path, project_stem)
    first = run([KICAD_CLI, "pcb", "drc", "--output", str(report_path), str(board_path)], check=False)
    if first.returncode == 0:
        return True
    run([KICAD_CLI, "pcb", "upgrade", str(board_path)], check=False)
    second = run([KICAD_CLI, "pcb", "drc", "--output", str(report_path), str(board_path)], check=False)
    return second.returncode == 0


def sync_board_to_pcb_outline_target(board_path: Path) -> None:
    run(
        [
            sys.executable,
            str(ROOT / "electrical" / "scripts" / "sync_board_outline.py"),
            "--board",
            str(board_path),
            "--source",
            "pcb-svg",
        ]
    )


def run_freerouting(dsn_path: Path, ses_path: Path, timeout: str) -> subprocess.CompletedProcess:
    cmd = [
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
    ]
    hard_timeout_seconds = parse_timeout_string(timeout) + 30
    try:
        return subprocess.run(
            cmd,
            cwd=ROOT,
            check=False,
            text=True,
            capture_output=True,
            timeout=hard_timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        return subprocess.CompletedProcess(
            cmd,
            124,
            exc.stdout or "",
            exc.stderr or "",
        )


def promote(src: Path, dst: Path) -> None:
    shutil.copy2(src, dst)


def find_footprint(board: pcbnew.BOARD, ref: str):
    for footprint in board.Footprints():
        if footprint.GetReference() == ref:
            return footprint
    raise RuntimeError(f"Missing footprint {ref}")


def move_footprint(board: pcbnew.BOARD, ref: str, x: float, y: float, rotation: float) -> None:
    footprint = find_footprint(board, ref)
    footprint.SetPosition(pt(x, y))
    footprint.SetOrientation(angle(rotation))


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
) -> int:
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
    return len(to_remove)


def refill_zones(board: pcbnew.BOARD) -> None:
    filler = pcbnew.ZONE_FILLER(board)
    filler.Fill(board.Zones())


def prepare_outline_candidate_board(src: Path, dst: Path) -> int:
    board = load_board(src)
    move_footprint(board, "J3", 65.841, 99.949, 0.0)
    move_footprint(board, "R7", 87.412, 105.949, 0.0)
    move_footprint(board, "SW1", 93.341, 86.949, 90.0)
    move_footprint(board, "J1", 81.641, 159.949, -21.909)

    removed = 0
    removed += remove_local_copper(
        board,
        {"V3P3", "GND", "UART_RX", "UART_TX", "EN", "BOOT"},
        [(61.0, 68.2, 74.5, 107.0)],
    )
    removed += remove_local_copper(
        board,
        {"BAT_SENSE", "LED4", "HALL_OUT", "PWR_BTN", "BUZZ_PWM"},
        [
            (61.5, 71.0, 79.5, 124.5),
            (81.5, 89.5, 48.0, 80.0),
            (88.8, 92.8, 81.0, 149.0),
        ],
    )
    removed += remove_local_copper(
        board,
        {"STATUS_B", "STATUS_B_A", "DEADMAN", "GND"},
        [(84.0, 99.0, 84.0, 108.5)],
    )
    removed += remove_local_copper(
        board,
        {"VBUS", "GND"},
        [(71.5, 86.5, 151.0, 166.0)],
    )

    refill_zones(board)
    board.BuildConnectivity()
    pcbnew.SaveBoard(str(dst), board)
    return removed


def prepare_board(src: Path, dst: Path, recipe: str | None) -> int:
    if recipe is None:
        if src != dst:
            shutil.copy2(src, dst)
        return 0
    if recipe == "outline-candidate":
        return prepare_outline_candidate_board(src, dst)
    raise ValueError(f"Unknown prepare recipe: {recipe}")


def resolve_project_stem(board_path: Path, explicit_project_stem: Path | None) -> Path:
    if explicit_project_stem is not None:
        return explicit_project_stem
    sibling_stem = board_path.with_suffix("")
    if sibling_stem.with_suffix(".kicad_pro").exists():
        return sibling_stem
    return DEFAULT_PROJECT_STEM


def compare_summaries(best: ReportSummary, candidate: ReportSummary) -> tuple[list[str], list[str]]:
    regressions: list[str] = []
    improvements: list[str] = []

    if candidate.unconnected > best.unconnected:
        regressions.append(f"unconnected {best.unconnected}->{candidate.unconnected}")
    elif candidate.unconnected < best.unconnected:
        improvements.append(f"unconnected {best.unconnected}->{candidate.unconnected}")

    for category in sorted(BLOCKER_CATEGORIES):
        best_count = best.count(category)
        candidate_count = candidate.count(category)
        if candidate_count > best_count:
            regressions.append(f"{category} {best_count}->{candidate_count}")
        elif candidate_count < best_count:
            improvements.append(f"{category} {best_count}->{candidate_count}")

    return regressions, improvements


def parse_timeout_string(value: str) -> int:
    parts = value.split(":")
    if len(parts) != 3:
        raise ValueError(f"Expected HH:MM:SS timeout string, got {value!r}")
    hours, minutes, seconds = (int(part) for part in parts)
    return hours * 3600 + minutes * 60 + seconds


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run DSN -> Freerouting -> SES -> DRC iterations on a chosen KiCad board."
    )
    parser.add_argument("--board", type=Path, default=DEFAULT_BOARD, help="Board file to iterate on.")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT, help="Baseline/final DRC report path.")
    parser.add_argument(
        "--project-stem",
        type=Path,
        default=None,
        help="Project stem used to supply .kicad_pro/.kicad_prl context for DRC scratch boards.",
    )
    parser.add_argument("--iterations", type=int, default=4, help="Maximum routing iterations to try.")
    parser.add_argument(
        "--prepare-recipe",
        choices=["outline-candidate"],
        default=None,
        help="Optional board prep applied to a scratch copy before each autorouter pass.",
    )
    parser.add_argument(
        "--sync-outline-source",
        choices=["pcb-svg"],
        default=None,
        help="Optional outline source to resync onto a scratch board before prep/routing.",
    )
    parser.add_argument(
        "--timeout",
        default="00:01:00",
        help="Freerouting job timeout string, e.g. 00:01:00.",
    )
    parser.add_argument(
        "--work-prefix",
        type=Path,
        default=None,
        help="Prefix for DSN/SES/scratch iteration files. Defaults beside the board.",
    )
    args = parser.parse_args()

    board_path = args.board.resolve()
    report_path = args.report.resolve()
    project_stem = resolve_project_stem(board_path, args.project_stem.resolve() if args.project_stem else None)
    work_prefix = args.work_prefix.resolve() if args.work_prefix else board_path.with_name(f"{board_path.stem}_route_iter")

    if not report_path.exists():
        ok = drc_report(board_path, report_path, project_stem)
        if not ok:
            raise SystemExit("Unable to produce baseline DRC report")

    best_summary = ReportSummary.from_path(report_path)
    best_board = board_path
    print(f"baseline {best_summary.describe()}")

    for idx in range(1, args.iterations + 1):
        stem = work_prefix.with_name(f"{work_prefix.name}_{idx}")
        outline_board = stem.with_name(f"{stem.name}_outline.kicad_pcb")
        prep_board = stem.with_name(f"{stem.name}_prep.kicad_pcb")
        dsn_path = stem.with_suffix(".dsn")
        ses_path = stem.with_suffix(".ses")
        raw_board = stem.with_name(f"{stem.name}_raw.kicad_pcb")
        norm_board = stem.with_name(f"{stem.name}_norm.kicad_pcb")
        iter_report = stem.with_name(f"{stem.name}.rpt")

        prep_source = best_board
        if args.sync_outline_source == "pcb-svg":
            shutil.copy2(best_board, outline_board)
            attach_project_context(outline_board, project_stem)
            sync_board_to_pcb_outline_target(outline_board)
            prep_source = outline_board
            print(
                f"iteration {idx}: synced scratch outline from pcb target svg "
                f"{PCB_OUTLINE_TARGET_SVG}"
            )

        removed = prepare_board(prep_source, prep_board, args.prepare_recipe)
        attach_project_context(prep_board, project_stem)
        if args.prepare_recipe:
            print(f"iteration {idx}: prepared scratch board with recipe={args.prepare_recipe} removed_items={removed}")

        export_dsn(prep_board, dsn_path)
        fr = run_freerouting(dsn_path, ses_path, args.timeout)
        print(fr.stdout)
        if fr.stderr:
            print(fr.stderr)
        if fr.returncode == 124:
            print(f"iteration {idx}: freerouting exceeded hard timeout for {args.timeout}")
            break
        if not ses_path.exists():
            print(f"iteration {idx}: no session file")
            break

        import_session(prep_board, ses_path, raw_board)
        normalize_board(raw_board, norm_board)

        if not drc_report(norm_board, iter_report, project_stem):
            print(f"iteration {idx}: DRC load failed")
            break

        summary = ReportSummary.from_path(iter_report)
        regressions, improvements = compare_summaries(best_summary, summary)
        print(f"iteration {idx}: {summary.describe()}")
        if regressions:
            print(f"iteration {idx}: rejected due to regressions: {', '.join(regressions)}")
            break
        if not improvements:
            print(f"iteration {idx}: no improvement")
            break

        promote(norm_board, board_path)
        promote(iter_report, report_path)
        best_board = board_path
        best_summary = summary
        print(f"iteration {idx}: promoted ({', '.join(improvements)})")

        if best_summary.unconnected == 0 and best_summary.blocker_total() == 0:
            break

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
