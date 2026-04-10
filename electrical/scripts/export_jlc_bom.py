#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import re
import subprocess
import tempfile
from collections import defaultdict
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCHEMATIC = REPO_ROOT / "electrical" / "kicad" / "boosted_remote.kicad_sch"
DEFAULT_BOARD = REPO_ROOT / "electrical" / "kicad" / "boosted_remote.kicad_pcb"
DEFAULT_OUTPUT = REPO_ROOT / "electrical" / "kicad" / "boosted_remote_jlc_bom.csv"
RAW_BOM_FIELDS = ("Designator", "Comment", "Footprint")
RAW_POS_FIELDS = ("Ref",)
JLC_FIELDS = ("Comment", "Designator", "Footprint", "JLCPCB Part # (optional)")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export a JLCPCB-formatted BOM CSV from the live KiCad project.")
    parser.add_argument("--schematic", type=Path, default=DEFAULT_SCHEMATIC, help="KiCad schematic file to export.")
    parser.add_argument("--board", type=Path, default=DEFAULT_BOARD, help="KiCad board file used to filter placed parts.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="JLC-formatted BOM CSV to write.")
    parser.add_argument(
        "--include-through-hole",
        action="store_true",
        help="Keep through-hole footprints in the BOM export.",
    )
    parser.add_argument(
        "--include-dnp",
        action="store_true",
        help="Keep DNP symbols in the BOM export.",
    )
    return parser.parse_args()


def run_kicad_bom_export(schematic: Path, raw_csv: Path, include_dnp: bool) -> None:
    command = [
        "kicad-cli",
        "sch",
        "export",
        "bom",
        "--output",
        str(raw_csv),
        "--fields",
        "Reference,Value,Footprint",
        "--labels",
        "Designator,Comment,Footprint",
        str(schematic),
    ]
    if not include_dnp:
        command.insert(-1, "--exclude-dnp")
    subprocess.run(command, check=True)


def run_kicad_pos_export(board: Path, raw_csv: Path, include_through_hole: bool, include_dnp: bool) -> None:
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
    if not include_dnp:
        command.append("--exclude-dnp")
    if not include_through_hole:
        command.append("--exclude-fp-th")
    command.append(str(board))
    subprocess.run(command, check=True)


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as infile:
        return list(csv.DictReader(infile))


def validate_fields(rows: list[dict[str, str]], expected_fields: tuple[str, ...], label: str) -> None:
    if not rows:
        return
    fields = set(rows[0].keys())
    missing = [field for field in expected_fields if field not in fields]
    if missing:
        joined = ", ".join(missing)
        raise ValueError(f"{label} export missing expected columns: {joined}")


def normalize_footprint(value: str) -> str:
    return value.rsplit(":", 1)[-1].strip()


def designator_sort_key(value: str) -> tuple[str, int, str]:
    match = re.fullmatch(r"([A-Za-z]+)(\d+)([A-Za-z]*)", value.strip())
    if match is None:
        return (value, -1, "")
    prefix, number, suffix = match.groups()
    return (prefix, int(number), suffix)


def collect_placement_refs(rows: list[dict[str, str]]) -> set[str]:
    validate_fields(rows, RAW_POS_FIELDS, "KiCad position")
    return {row["Ref"].strip() for row in rows if row.get("Ref", "").strip()}


def build_grouped_rows(bom_rows: list[dict[str, str]], placement_refs: set[str]) -> list[dict[str, str]]:
    validate_fields(bom_rows, RAW_BOM_FIELDS, "KiCad BOM")
    grouped: dict[tuple[str, str], list[str]] = defaultdict(list)

    for row in bom_rows:
        designator = row["Designator"].strip()
        if designator not in placement_refs:
            continue
        comment = row["Comment"].strip()
        footprint = normalize_footprint(row["Footprint"])
        grouped[(comment, footprint)].append(designator)

    output_rows = []
    for (comment, footprint), designators in grouped.items():
        sorted_designators = sorted(designators, key=designator_sort_key)
        output_rows.append(
            {
                "Comment": comment,
                "Designator": ",".join(sorted_designators),
                "Footprint": footprint,
                "JLCPCB Part # (optional)": "",
            }
        )

    output_rows.sort(key=lambda row: tuple(designator_sort_key(part) for part in row["Designator"].split(",")))
    return output_rows


def write_jlc_bom(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as outfile:
        writer = csv.DictWriter(outfile, fieldnames=JLC_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    args = parse_args()
    with tempfile.TemporaryDirectory(prefix="boosted_remote_bom_") as tmp_dir:
        temp_dir = Path(tmp_dir)
        raw_bom = temp_dir / "kicad_bom.csv"
        raw_pos = temp_dir / "kicad_pos.csv"

        run_kicad_bom_export(args.schematic, raw_bom, include_dnp=args.include_dnp)
        run_kicad_pos_export(
            args.board,
            raw_pos,
            include_through_hole=args.include_through_hole,
            include_dnp=args.include_dnp,
        )

        bom_rows = read_rows(raw_bom)
        pos_rows = read_rows(raw_pos)
        placement_refs = collect_placement_refs(pos_rows)
        grouped_rows = build_grouped_rows(bom_rows, placement_refs)
        write_jlc_bom(args.output, grouped_rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())