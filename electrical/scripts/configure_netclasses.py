#!/usr/bin/env python3

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "electrical" / "kicad" / "boosted_remote.kicad_pro"
PROJECT_LOCAL = ROOT / "electrical" / "kicad" / "boosted_remote.kicad_prl"
PCB = ROOT / "electrical" / "kicad" / "boosted_remote.kicad_pcb"


DEFAULT_CLASS = {
    "bus_width": 12,
    "clearance": 0.2,
    "diff_pair_gap": 0.25,
    "diff_pair_via_gap": 0.25,
    "diff_pair_width": 0.2,
    "line_style": 0,
    "microvia_diameter": 0.3,
    "microvia_drill": 0.1,
    "name": "Default",
    "pcb_color": "rgba(0, 0, 0, 0.000)",
    "priority": 2147483647,
    "schematic_color": "rgba(0, 0, 0, 0.000)",
    "track_width": 0.2,
    "tuning_profile": "",
    "via_diameter": 0.6,
    "via_drill": 0.3,
    "wire_width": 6,
}


CLASS_SPECS = [
    {
        "name": "GND_RETURN",
        "priority": 1,
        "clearance": 0.2,
        "track_width": 0.3,
        "via_diameter": 0.7,
        "via_drill": 0.35,
        "pcb_color": "rgba(80, 80, 80, 0.800)",
        "nets": ["GND"],
    },
    {
        "name": "RAW_POWER",
        "priority": 2,
        "clearance": 0.2,
        "track_width": 0.3,
        "via_diameter": 0.7,
        "via_drill": 0.35,
        "pcb_color": "rgba(210, 70, 50, 0.800)",
        "nets": ["VBAT", "VBUS"],
    },
    {
        "name": "REGULATED_3V3",
        "priority": 3,
        "clearance": 0.2,
        "track_width": 0.25,
        "via_diameter": 0.6,
        "via_drill": 0.3,
        "pcb_color": "rgba(230, 150, 20, 0.800)",
        "nets": ["V3P3"],
    },
    {
        "name": "CHARGER_SENSE",
        "priority": 4,
        "clearance": 0.2,
        "track_width": 0.2,
        "via_diameter": 0.6,
        "via_drill": 0.3,
        "pcb_color": "rgba(200, 110, 30, 0.800)",
        "nets": ["BAT_SENSE", "CHG_STAT", "PROG"],
    },
    {
        "name": "SENSOR_ANALOG",
        "priority": 5,
        "clearance": 0.2,
        "track_width": 0.2,
        "via_diameter": 0.6,
        "via_drill": 0.3,
        "pcb_color": "rgba(30, 150, 170, 0.800)",
        "nets": ["HALL_OUT"],
    },
    {
        "name": "PROGRAMMING_IO",
        "priority": 6,
        "clearance": 0.2,
        "track_width": 0.2,
        "via_diameter": 0.6,
        "via_drill": 0.3,
        "pcb_color": "rgba(60, 120, 220, 0.800)",
        "nets": ["BOOT", "EN", "UART_RX", "UART_TX"],
    },
    {
        "name": "USB_SIGNAL",
        "priority": 7,
        "clearance": 0.2,
        "track_width": 0.2,
        "via_diameter": 0.6,
        "via_drill": 0.3,
        "pcb_color": "rgba(40, 160, 220, 0.800)",
        "nets": ["USB_D+", "USB_D-", "USB_ID"],
    },
    {
        "name": "USER_INPUTS",
        "priority": 8,
        "clearance": 0.2,
        "track_width": 0.2,
        "via_diameter": 0.6,
        "via_drill": 0.3,
        "pcb_color": "rgba(80, 180, 110, 0.800)",
        "nets": ["DEADMAN", "PWR_BTN"],
    },
    {
        "name": "ACTUATOR_DRIVE",
        "priority": 9,
        "clearance": 0.2,
        "track_width": 0.25,
        "via_diameter": 0.6,
        "via_drill": 0.3,
        "pcb_color": "rgba(180, 40, 120, 0.800)",
        "nets": ["BUZZ", "BUZZ_BASE", "BUZZ_PWM"],
    },
    {
        "name": "LED_DRIVE",
        "priority": 10,
        "clearance": 0.2,
        "track_width": 0.2,
        "via_diameter": 0.6,
        "via_drill": 0.3,
        "pcb_color": "rgba(110, 80, 210, 0.800)",
        "nets": [
            "LED1",
            "LED1_A",
            "LED2",
            "LED2_A",
            "LED3",
            "LED3_A",
            "LED4",
            "LED4_A",
            "LED5",
            "LED5_A",
            "STATUS_B",
            "STATUS_B_A",
            "STATUS_G",
            "STATUS_G_A",
        ],
    },
]


def build_class(spec: dict) -> dict:
    return {
        "bus_width": 12,
        "clearance": spec["clearance"],
        "diff_pair_gap": 0.25,
        "diff_pair_via_gap": 0.25,
        "diff_pair_width": spec["track_width"],
        "line_style": 0,
        "microvia_diameter": 0.3,
        "microvia_drill": 0.1,
        "name": spec["name"],
        "pcb_color": spec["pcb_color"],
        "priority": spec["priority"],
        "schematic_color": spec["pcb_color"],
        "track_width": spec["track_width"],
        "tuning_profile": "",
        "via_diameter": spec["via_diameter"],
        "via_drill": spec["via_drill"],
        "wire_width": 6,
    }


def load_board_nets() -> list[str]:
    if not PCB.exists():
        return []
    text = PCB.read_text(encoding="utf-8")
    nets = sorted(set(re.findall(r'\(net\s+"([^"]+)"\)', text)))
    return nets


def build_patterns(board_nets: list[str]) -> list[dict]:
    known_specs = {net_name: spec["name"] for spec in CLASS_SPECS for net_name in spec["nets"]}
    patterns = []
    for spec in CLASS_SPECS:
        for net_name in spec["nets"]:
            if board_nets and net_name not in board_nets:
                continue
            patterns.append({"netclass": spec["name"], "pattern": net_name})
    uncovered = [net_name for net_name in board_nets if net_name not in known_specs]
    if uncovered:
        joined = ", ".join(uncovered)
        raise RuntimeError(f"Unclassified PCB nets: {joined}")
    return patterns


def update_project_local_settings() -> None:
    if not PROJECT_LOCAL.exists():
        return
    project_local = json.loads(PROJECT_LOCAL.read_text(encoding="utf-8"))
    for key in ("net_inspector_panel", "netInspector"):
        net_inspector = project_local.get(key)
        if isinstance(net_inspector, dict):
            net_inspector["filter_by_netclass"] = True
            net_inspector["group_by_netclass"] = True
    PROJECT_LOCAL.write_text(json.dumps(project_local, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    project = json.loads(PROJECT.read_text(encoding="utf-8"))
    net_settings = project["net_settings"]
    board_nets = load_board_nets()

    net_settings["classes"] = [DEFAULT_CLASS] + [build_class(spec) for spec in CLASS_SPECS]
    net_settings["netclass_assignments"] = None
    net_settings["netclass_patterns"] = build_patterns(board_nets)

    PROJECT.write_text(json.dumps(project, indent=2) + "\n", encoding="utf-8")
    update_project_local_settings()
    print(f"Configured {len(net_settings['classes']) - 1} custom netclasses across {len(net_settings['netclass_patterns'])} live nets.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
