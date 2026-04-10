#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import subprocess
import tempfile
from decimal import Decimal, InvalidOperation
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BOARD = REPO_ROOT / "electrical" / "kicad" / "boosted_remote.kicad_pcb"
DEFAULT_OUTPUT = REPO_ROOT / "electrical" / "kicad" / "boosted_remote_jlc_cpl.csv"
RAW_FIELDS = ("Ref", "PosX", "PosY", "Rot", "Side")
JLC_FIELDS = ("Designator", "Mid X", "Mid Y", "Layer", "Rotation")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export a JLCPCB-formatted CPL CSV from the live KiCad board.")
    parser.add_argument("--board", type=Path, default=DEFAULT_BOARD, help="KiCad board file to export.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="JLC-formatted CPL CSV to write.")
    parser.add_argument(
        "--include-through-hole",
        action="store_true",
        help="Keep through-hole footprints in the placement export.",
    )
    parser.add_argument(
        "--include-dnp",
        action="store_true",
        help="Keep DNP footprints in the placement export.",
    )
    parser.add_argument(
        "--use-drill-file-origin",
        action="store_true",
        help="Export coordinates relative to the board drill/aux origin.",
    )
    return parser.parse_args()


def run_kicad_pos_export(board: Path, raw_csv: Path, args: argparse.Namespace) -> None:
    command = [
        "kicad-cli",
        "pcb",
        "export",
        "pos",
        "--format",
        "csv",
        "--units",
        "mm",
        "--output",
        str(raw_csv),
    ]
    if not args.include_dnp:
        command.append("--exclude-dnp")
    if not args.include_through_hole:
        command.append("--exclude-fp-th")
    if args.use_drill_file_origin:
        command.append("--use-drill-file-origin")
    command.append(str(board))
    subprocess.run(command, check=True)


def format_mm(value: str) -> str:
    try:
        number = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"Invalid numeric position value: {value}") from exc
    text = format(number.normalize(), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return f"{text}mm"


def format_rotation(value: str) -> str:
    try:
        number = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"Invalid numeric rotation value: {value}") from exc
    text = format(number.normalize(), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def format_layer(value: str) -> str:
    side = value.strip().lower()
    if side == "top":
        return "Top"
    if side == "bottom":
        return "Bottom"
    raise ValueError(f"Unexpected side value: {value}")


def convert_to_jlc(raw_csv: Path, output_csv: Path) -> None:
    with raw_csv.open(newline="", encoding="utf-8") as infile:
        reader = csv.DictReader(infile)
        missing = [field for field in RAW_FIELDS if field not in (reader.fieldnames or [])]
        if missing:
            joined = ", ".join(missing)
            raise ValueError(f"KiCad position export missing expected columns: {joined}")

        rows = []
        for row in reader:
            rows.append(
                {
                    "Designator": row["Ref"],
                    "Mid X": format_mm(row["PosX"]),
                    "Mid Y": format_mm(row["PosY"]),
                    "Layer": format_layer(row["Side"]),
                    "Rotation": format_rotation(row["Rot"]),
                }
            )

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", newline="", encoding="utf-8") as outfile:
        writer = csv.DictWriter(outfile, fieldnames=JLC_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    args = parse_args()
    with tempfile.TemporaryDirectory(prefix="boosted_remote_cpl_") as tmp_dir:
        raw_csv = Path(tmp_dir) / "kicad_pos.csv"
        run_kicad_pos_export(args.board, raw_csv, args)
        convert_to_jlc(raw_csv, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())