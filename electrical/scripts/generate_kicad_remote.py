#!/usr/bin/env python3

import json
import math
import os
import uuid
from dataclasses import dataclass
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
from build_usb_mini_footprint import LOCAL_FOOTPRINT_LIB, USB_FOOTPRINT_NAME, ensure_repo_usb_footprint


ROOT = Path(__file__).resolve().parents[2]
PARAMS = ROOT / "config" / "remote_params.json"
KICAD_DIR = ROOT / "electrical" / "kicad"
PROJECT = "boosted_remote"
SCH_PATH = KICAD_DIR / f"{PROJECT}.kicad_sch"
PCB_PATH = KICAD_DIR / f"{PROJECT}.kicad_pcb"
GRID = 2.54
SYSTEM_FOOTPRINT_ROOT = Path("/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints")

PCB_FOOTPRINT_PLACEMENTS = {
    "U3": (86.5, 101.5, 90),
    "R9": (88.0, 61.0, 90),
    "C3": (86.0, 105.5, 90),
    "C4": (89.5, 105.0, 90),
}
MOUNTING_HOLE_FOOTPRINT = ("MountingHole", "MountingHole_2.2mm_M2")
HALL_ENCODER_CENTER = (91.0, 28.0)
HALL_ENCODER_WHEEL_RADIUS = 15.5
HALL_ENCODER_MAGNET_RADIUS = 13.0
HALL_ENCODER_MAGNET_MARKER_RADIUS = 1.6
HALL_ENCODER_MAGNET_ANGLES_DEG = (-18.0, 18.0)
PCB_COPPER_LAYER_COUNT = 4
USB_MINI_POSITION = (98.5, 128.0)
USB_MINI_ROTATION_DEG = -21.909134


def power_button_board_position(params: dict) -> tuple[float, float, int]:
    mechanical = params["mechanical"]
    return (
        mechanical["pcb_shell_center_x_mm"] + mechanical["power_button_center_x_mm"],
        mechanical["power_button_center_z_from_top_mm"],
        90,
    )


def hall_sensor_board_position() -> tuple[float, float, int]:
    return (HALL_ENCODER_CENTER[0] + 17.0, HALL_ENCODER_CENTER[1], 90)


def u() -> str:
    return str(uuid.uuid4())


def mm(value: float) -> int:
    return pcbnew.FromMM(value)


def pt(x: float, y: float) -> pcbnew.VECTOR2I:
    return pcbnew.VECTOR2I(mm(x), mm(y))


def angle(deg: float) -> pcbnew.EDA_ANGLE:
    return pcbnew.EDA_ANGLE(deg, pcbnew.DEGREES_T)


def read_params() -> dict:
    return json.loads(PARAMS.read_text())


def mounting_hole_specs(params: dict) -> list:
    return params.get("mechanical", {}).get("pcb_mount_holes", [])


@dataclass
class PinSpec:
    number: str
    name: str
    side: str
    ptype: str = "passive"


@dataclass
class SymbolDef:
    lib_id: str
    ref_prefix: str
    value: str
    footprint: str
    description: str
    pins: list
    width: float
    height: float

    def pin_positions(self) -> dict:
        pin_len = 2.54
        sides = {"left": [], "right": [], "top": [], "bottom": []}
        for pin in self.pins:
            sides[pin.side].append(pin)

        positions = {}

        def spread(count: int) -> list:
            if count == 1:
                return [0.0]
            start = -((count - 1) / 2.0) * GRID
            return [start + i * GRID for i in range(count)]

        for side in ("left", "right"):
            ys = spread(len(sides[side]))
            for pin, y in zip(sides[side], ys):
                x = -self.width / 2.0 - pin_len if side == "left" else self.width / 2.0 + pin_len
                positions[pin.number] = (x, y, 0 if side == "left" else 180)

        for side in ("top", "bottom"):
            xs = spread(len(sides[side]))
            for pin, x in zip(sides[side], xs):
                y = -self.height / 2.0 - pin_len if side == "top" else self.height / 2.0 + pin_len
                positions[pin.number] = (x, y, 270 if side == "top" else 90)

        return positions

    def to_lib(self) -> str:
        pin_pos = self.pin_positions()
        lines = [
            f'\t\t(symbol "{self.lib_id}"',
            "\t\t\t(exclude_from_sim no)",
            "\t\t\t(in_bom yes)",
            "\t\t\t(on_board yes)",
            "\t\t\t(in_pos_files yes)",
            "\t\t\t(property \"Reference\" \"{}\"".format(self.ref_prefix),
            "\t\t\t\t(at 0 {:.2f} 0)".format(self.height / 2.0 + 5.08),
            "\t\t\t\t(effects",
            "\t\t\t\t\t(font",
            "\t\t\t\t\t\t(size 1.27 1.27)",
            "\t\t\t\t\t)",
            "\t\t\t\t)",
            "\t\t\t)",
            "\t\t\t(property \"Value\" \"{}\"".format(self.value),
            "\t\t\t\t(at 0 {:.2f} 0)".format(self.height / 2.0 + 2.54),
            "\t\t\t\t(effects",
            "\t\t\t\t\t(font",
            "\t\t\t\t\t\t(size 1.27 1.27)",
            "\t\t\t\t\t)",
            "\t\t\t\t)",
            "\t\t\t)",
            "\t\t\t(property \"Footprint\" \"{}\"".format(self.footprint),
            "\t\t\t\t(at 0 0 0)",
            "\t\t\t\t(hide yes)",
            "\t\t\t\t(effects",
            "\t\t\t\t\t(font",
            "\t\t\t\t\t\t(size 1.27 1.27)",
            "\t\t\t\t\t)",
            "\t\t\t\t)",
            "\t\t\t)",
            '\t\t\t(property "Datasheet" ""',
            "\t\t\t\t(at 0 0 0)",
            "\t\t\t\t(hide yes)",
            "\t\t\t\t(effects",
            "\t\t\t\t\t(font",
            "\t\t\t\t\t\t(size 1.27 1.27)",
            "\t\t\t\t\t)",
            "\t\t\t\t)",
            "\t\t\t)",
            '\t\t\t(property "Description" "{}"'.format(self.description),
            "\t\t\t\t(at 0 0 0)",
            "\t\t\t\t(hide yes)",
            "\t\t\t\t(effects",
            "\t\t\t\t\t(font",
            "\t\t\t\t\t\t(size 1.27 1.27)",
            "\t\t\t\t\t)",
            "\t\t\t\t)",
            "\t\t\t)",
            '\t\t\t(symbol "{}_1_1"'.format(self.lib_id.split(":")[-1]),
            "\t\t\t\t(rectangle",
            "\t\t\t\t\t(start {:.2f} {:.2f})".format(-self.width / 2.0, self.height / 2.0),
            "\t\t\t\t\t(end {:.2f} {:.2f})".format(self.width / 2.0, -self.height / 2.0),
            "\t\t\t\t\t(stroke",
            "\t\t\t\t\t\t(width 0.254)",
            "\t\t\t\t\t\t(type default)",
            "\t\t\t\t\t)",
            "\t\t\t\t\t(fill",
            "\t\t\t\t\t\t(type background)",
            "\t\t\t\t\t)",
            "\t\t\t\t)",
        ]
        for pin in self.pins:
            x, y, rot = pin_pos[pin.number]
            lines.extend(
                [
                    f"\t\t\t\t(pin {pin.ptype} line",
                    "\t\t\t\t\t(at {:.2f} {:.2f} {})".format(x, y, rot),
                    "\t\t\t\t\t(length 2.54)",
                    '\t\t\t\t\t(name "{}"'.format(pin.name),
                    "\t\t\t\t\t\t(effects",
                    "\t\t\t\t\t\t\t(font",
                    "\t\t\t\t\t\t\t\t(size 1.27 1.27)",
                    "\t\t\t\t\t\t\t)",
                    "\t\t\t\t\t\t)",
                    "\t\t\t\t\t)",
                    '\t\t\t\t\t(number "{}"'.format(pin.number),
                    "\t\t\t\t\t\t(effects",
                    "\t\t\t\t\t\t\t(font",
                    "\t\t\t\t\t\t\t\t(size 1.27 1.27)",
                    "\t\t\t\t\t\t\t)",
                    "\t\t\t\t\t\t)",
                    "\t\t\t\t\t)",
                    "\t\t\t\t)",
                ]
            )
        lines.extend(["\t\t\t)", "\t\t\t(embedded_fonts no)", "\t\t)"])
        return "\n".join(lines)


@dataclass
class SymbolInst:
    ref: str
    value: str
    lib_id: str
    footprint: str
    desc: str
    x: float
    y: float
    rotation: int = 0


def rotate(dx: float, dy: float, rot: int) -> tuple:
    rot = rot % 360
    if rot == 0:
        return dx, dy
    if rot == 90:
        return -dy, dx
    if rot == 180:
        return -dx, -dy
    if rot == 270:
        return dy, -dx
    raise ValueError(f"Unsupported rotation {rot}")


def symbol_block(root_uuid: str, inst: SymbolInst, defs: dict) -> str:
    sym = defs[inst.lib_id]
    pin_pos = sym.pin_positions()
    suid = u()
    lines = [
        "\t(symbol",
        '\t\t(lib_id "{}")'.format(inst.lib_id),
        "\t\t(at {:.2f} {:.2f} {})".format(inst.x, inst.y, inst.rotation),
        "\t\t(unit 1)",
        "\t\t(exclude_from_sim no)",
        "\t\t(in_bom yes)",
        "\t\t(on_board yes)",
        "\t\t(dnp no)",
        '\t\t(uuid "{}")'.format(suid),
        '\t\t(property "Reference" "{}"'.format(inst.ref),
        "\t\t\t(at {:.2f} {:.2f} 0)".format(inst.x - sym.width / 2.0, inst.y + sym.height / 2.0 + 5.08),
        "\t\t\t(effects",
        "\t\t\t\t(font",
        "\t\t\t\t\t(size 1.27 1.27)",
        "\t\t\t\t)",
        "\t\t\t)",
        "\t\t)",
        '\t\t(property "Value" "{}"'.format(inst.value),
        "\t\t\t(at {:.2f} {:.2f} 0)".format(inst.x, inst.y + sym.height / 2.0 + 2.54),
        "\t\t\t(effects",
        "\t\t\t\t(font",
        "\t\t\t\t\t(size 1.27 1.27)",
        "\t\t\t\t)",
        "\t\t\t)",
        "\t\t)",
        '\t\t(property "Footprint" "{}"'.format(inst.footprint),
        "\t\t\t(at {:.2f} {:.2f} 0)".format(inst.x, inst.y),
        "\t\t\t(hide yes)",
        "\t\t\t(effects",
        "\t\t\t\t(font",
        "\t\t\t\t\t(size 1.27 1.27)",
        "\t\t\t\t)",
        "\t\t\t)",
        "\t\t)",
        '\t\t(property "Datasheet" ""',
        "\t\t\t(at {:.2f} {:.2f} 0)".format(inst.x, inst.y),
        "\t\t\t(hide yes)",
        "\t\t\t(effects",
        "\t\t\t\t(font",
        "\t\t\t\t\t(size 1.27 1.27)",
        "\t\t\t\t)",
        "\t\t\t)",
        "\t\t)",
        '\t\t(property "Description" "{}"'.format(inst.desc),
        "\t\t\t(at {:.2f} {:.2f} 0)".format(inst.x, inst.y),
        "\t\t\t(hide yes)",
        "\t\t\t(effects",
        "\t\t\t\t(font",
        "\t\t\t\t\t(size 1.27 1.27)",
        "\t\t\t\t)",
        "\t\t\t)",
        "\t\t)",
    ]
    for pin in sym.pins:
        lines.extend(
            [
                '\t\t(pin "{}"'.format(pin.number),
                '\t\t\t(uuid "{}")'.format(u()),
                "\t\t)",
            ]
        )
    lines.extend(
        [
            "\t\t(instances",
            '\t\t\t(project "{}"'.format(PROJECT),
            '\t\t\t\t(path "/{}"'.format(root_uuid),
            '\t\t\t\t\t(reference "{}")'.format(inst.ref),
            "\t\t\t\t\t(unit 1)",
            "\t\t\t\t)",
            "\t\t\t)",
            "\t\t)",
            "\t)",
        ]
    )
    return "\n".join(lines)


def pin_point(inst: SymbolInst, defs: dict, pin_number: str) -> tuple:
    sym = defs[inst.lib_id]
    x, y, _ = sym.pin_positions()[pin_number]
    dx, dy = rotate(x, y, inst.rotation)
    return inst.x + dx, inst.y + dy


def pin_side(inst: SymbolInst, defs: dict, pin_number: str) -> str:
    sym = defs[inst.lib_id]
    side = {pin.number: pin.side for pin in sym.pins}[pin_number]
    return side


def wire(x1: float, y1: float, x2: float, y2: float) -> str:
    return (
        "\t(wire\n"
        "\t\t(pts\n"
        "\t\t\t(xy {:.2f} {:.2f}) (xy {:.2f} {:.2f})\n".format(x1, y1, x2, y2)
        + "\t\t)\n"
        + "\t\t(stroke\n\t\t\t(width 0)\n\t\t\t(type solid)\n\t\t)\n"
        + '\t\t(uuid "{}")\n'.format(u())
        + "\t)"
    )


def label(name: str, x: float, y: float, rot: int = 0, justify: str = "left bottom") -> str:
    return (
        '\t(label "{}"\n'.format(name)
        + "\t\t(at {:.2f} {:.2f} {})\n".format(x, y, rot)
        + "\t\t(effects\n\t\t\t(font\n\t\t\t\t(size 1.27 1.27)\n\t\t\t)\n"
        + "\t\t\t(justify {})\n".format(justify)
        + "\t\t)\n"
        + '\t\t(uuid "{}")\n'.format(u())
        + "\t)"
    )


def no_connect(x: float, y: float) -> str:
    return (
        "\t(no_connect\n"
        + "\t\t(at {:.2f} {:.2f})\n".format(x, y)
        + '\t\t(uuid "{}")\n'.format(u())
        + "\t)"
    )


def label_from_pin(inst: SymbolInst, defs: dict, pin: str, net: str, distance: float = 5.08) -> list:
    x, y = pin_point(inst, defs, pin)
    side = pin_side(inst, defs, pin)
    if side == "left":
        lx, ly, rot, just = x - distance, y, 0, "left bottom"
    elif side == "right":
        lx, ly, rot, just = x + distance, y, 180, "right bottom"
    elif side == "top":
        lx, ly, rot, just = x, y - distance, 90, "left bottom"
    else:
        lx, ly, rot, just = x, y + distance, 270, "right bottom"
    return [wire(x, y, lx, ly), label(net, lx, ly, rot, just)]


def build_symbol_defs() -> dict:
    defs = {}

    def add(sym: SymbolDef):
        defs[sym.lib_id] = sym

    add(
        SymbolDef(
            "boosted_remote:USB_MINI_5",
            "J",
            "USB_Mini-B",
            f"{LOCAL_FOOTPRINT_LIB}:{USB_FOOTPRINT_NAME}",
            "Mini-USB connector",
            [
                PinSpec("1", "VBUS", "left"),
                PinSpec("2", "D-", "left"),
                PinSpec("3", "D+", "left"),
                PinSpec("4", "ID", "left"),
                PinSpec("5", "GND", "left"),
            ],
            10.16,
            15.24,
        )
    )
    add(
        SymbolDef(
            "CONN_2",
            "J",
            "Conn_01x02",
            "Connector_JST:JST_PH_B2B-PH-K_1x02_P2.00mm_Vertical",
            "2-pin connector",
            [PinSpec("1", "1", "left"), PinSpec("2", "2", "left")],
            10.16,
            7.62,
        )
    )
    add(
        SymbolDef(
            "HDR_6",
            "J",
            "Conn_01x06",
            "Connector_PinHeader_1.27mm:PinHeader_1x06_P1.27mm_Vertical",
            "1x06 programming header",
            [
                PinSpec("1", "1", "left"),
                PinSpec("2", "2", "left"),
                PinSpec("3", "3", "left"),
                PinSpec("4", "4", "left"),
                PinSpec("5", "5", "left"),
                PinSpec("6", "6", "left"),
            ],
            10.16,
            17.78,
        )
    )
    add(
        SymbolDef(
            "MCP73831",
            "U",
            "MCP73831-2-OT",
            "Package_TO_SOT_SMD:SOT-23-5",
            "1S LiPo charger",
            [
                PinSpec("1", "STAT", "left"),
                PinSpec("2", "VSS", "left"),
                PinSpec("3", "VBAT", "left"),
                PinSpec("4", "VDD", "right"),
                PinSpec("5", "PROG", "right"),
            ],
            15.24,
            12.70,
        )
    )
    add(
        SymbolDef(
            "TLV75533",
            "U",
            "TLV75533PDBV",
            "Package_TO_SOT_SMD:SOT-23-5",
            "3.3V regulator",
            [
                PinSpec("1", "IN", "left"),
                PinSpec("2", "GND", "left"),
                PinSpec("3", "EN", "left"),
                PinSpec("4", "NC", "right", "no_connect"),
                PinSpec("5", "OUT", "right"),
            ],
            15.24,
            12.70,
        )
    )
    add(
        SymbolDef(
            "DRV5055",
            "U",
            "DRV5055A3xDBZxQ1",
            "Package_TO_SOT_SMD:SOT-23",
            "Linear hall sensor",
            [
                PinSpec("1", "VCC", "left"),
                PinSpec("2", "OUT", "right"),
                PinSpec("3", "GND", "bottom"),
            ],
            10.16,
            10.16,
        )
    )
    add(
        SymbolDef(
            "ESP32_C3",
            "U",
            "ESP32-C3-WROOM-02",
            "RF_Module:ESP32-C3-WROOM-02",
            "BLE MCU module",
            [
                PinSpec("1", "3V3", "top"),
                PinSpec("2", "EN", "left"),
                PinSpec("3", "IO4", "left", "bidirectional"),
                PinSpec("4", "IO5", "left", "bidirectional"),
                PinSpec("5", "IO6", "left", "bidirectional"),
                PinSpec("6", "IO7", "left", "bidirectional"),
                PinSpec("7", "IO8", "left", "bidirectional"),
                PinSpec("8", "IO9", "left", "bidirectional"),
                PinSpec("9", "GND", "bottom"),
                PinSpec("10", "IO10", "right", "bidirectional"),
                PinSpec("11", "RXD", "right", "bidirectional"),
                PinSpec("12", "TXD", "right", "output"),
                PinSpec("13", "IO18", "right", "bidirectional"),
                PinSpec("14", "IO19", "right", "bidirectional"),
                PinSpec("15", "IO3", "right", "bidirectional"),
                PinSpec("16", "IO2", "right", "bidirectional"),
                PinSpec("17", "IO1", "right", "bidirectional"),
                PinSpec("18", "IO0", "right", "bidirectional"),
                PinSpec("19", "GND", "bottom"),
            ],
            30.48,
            35.56,
        )
    )
    add(
        SymbolDef(
            "R_LOCAL",
            "R",
            "R",
            "Resistor_SMD:R_0603_1608Metric",
            "Resistor",
            [PinSpec("1", "1", "left"), PinSpec("2", "2", "right")],
            5.08,
            2.54,
        )
    )
    add(
        SymbolDef(
            "C_LOCAL",
            "C",
            "C",
            "Capacitor_SMD:C_0603_1608Metric",
            "Capacitor",
            [PinSpec("1", "1", "left"), PinSpec("2", "2", "right")],
            5.08,
            2.54,
        )
    )
    add(
        SymbolDef(
            "LED_LOCAL",
            "D",
            "LED",
            "LED_SMD:LED_0603_1608Metric",
            "LED",
            [PinSpec("1", "K", "left"), PinSpec("2", "A", "right")],
            5.08,
            2.54,
        )
    )
    add(
        SymbolDef(
            "SW_LOCAL",
            "SW",
            "SW_Push",
            "Button_Switch_SMD:SW_SPST_TL3305A",
            "Momentary switch",
            [PinSpec("1", "1", "left"), PinSpec("2", "2", "right")],
            5.08,
            2.54,
        )
    )
    add(
        SymbolDef(
            "Q_NPN_LOCAL",
            "Q",
            "Q_NPN_BEC",
            "Package_TO_SOT_SMD:SOT-23",
            "NPN transistor",
            [
                PinSpec("1", "B", "left", "input"),
                PinSpec("2", "E", "bottom", "passive"),
                PinSpec("3", "C", "top", "passive"),
            ],
            7.62,
            7.62,
        )
    )
    add(
        SymbolDef(
            "BUZZER_LOCAL",
            "BZ",
            "Buzzer",
            "Buzzer_Beeper:Buzzer_Murata_PKMCS0909E",
            "Piezo buzzer",
            [PinSpec("1", "+", "left"), PinSpec("2", "-", "right")],
            10.16,
            5.08,
        )
    )
    return defs


def build_schematic(params: dict):
    defs = build_symbol_defs()
    root_uuid = u()

    inst = {}
    sw2_x, sw2_y, sw2_rot = power_button_board_position(params)
    u4_x, u4_y, u4_rot = hall_sensor_board_position()

    def add(name: str, *args, **kwargs):
        inst[name] = SymbolInst(*args, **kwargs)

    add("J1", "J1", "USB_Mini-B", "boosted_remote:USB_MINI_5", f"{LOCAL_FOOTPRINT_LIB}:{USB_FOOTPRINT_NAME}", "Mini USB", 25.40, 152.40)
    add("J2", "J2", "Battery", "CONN_2", "Connector_JST:JST_PH_B2B-PH-K_1x02_P2.00mm_Vertical", "LiPo connector", 25.40, 121.92)
    add("J3", "J3", "UART", "HDR_6", "Connector_PinHeader_1.27mm:PinHeader_1x06_P1.27mm_Vertical", "Programming header", 35.56, 86.36)
    add("U2", "U2", "MCP73831-2-OT", "MCP73831", "Package_TO_SOT_SMD:SOT-23-5", "Charger", 71.12, 144.78)
    add("U3", "U3", "TLV75533PDBV", "TLV75533", "Package_TO_SOT_SMD:SOT-23-5", "Regulator", 71.12, 114.30)
    add("U4", "U4", "DRV5055A3xDBZxQ1", "DRV5055", "Package_TO_SOT_SMD:SOT-23", "Hall sensor", u4_x, u4_y)
    add("U1", "U1", "ESP32-C3-WROOM-02", "ESP32_C3", "RF_Module:ESP32-C3-WROOM-02", "BLE MCU", 134.62, 96.52)
    add("SW1", "SW1", "Deadman", "SW_LOCAL", "Button_Switch_SMD:SW_Push_1P1T-MP_NO_Horizontal_Alps_SKRTLAE010", "Deadman switch", 71.12, 83.82)
    add("SW2", "SW2", "Power", "SW_LOCAL", "Button_Switch_SMD:SW_SPST_TL3305A", "Power button", sw2_x, sw2_y, sw2_rot)
    add("Q1", "Q1", "Q_NPN_BEC", "Q_NPN_LOCAL", "Package_TO_SOT_SMD:SOT-23", "Buzzer transistor", 167.64, 144.78)
    add("BZ1", "BZ1", "Buzzer", "BUZZER_LOCAL", "Buzzer_Beeper:Buzzer_Murata_PKMCS0909E", "Buzzer", 190.50, 144.78)

    # Passives and indicators
    y_leds = [93.98, 104.14, 114.30, 124.46, 134.62]
    for idx, y in enumerate(y_leds, start=1):
        add(f"R{idx}", f"R{idx}", "330", "R_LOCAL", "Resistor_SMD:R_0603_1608Metric", "LED resistor", 170.18, y)
        add(f"D{idx}", f"D{idx}", "AMBER", "LED_LOCAL", "LED_SMD:LED_0603_1608Metric", "Bar LED", 190.50, y, 180)
    add("R6", "R6", "330", "R_LOCAL", "Resistor_SMD:R_0603_1608Metric", "Status resistor", 170.18, 40.64)
    add("D6", "D6", "GREEN", "LED_LOCAL", "LED_SMD:LED_0603_1608Metric", "Status LED", 190.50, 40.64, 180)
    add("R7", "R7", "330", "R_LOCAL", "Resistor_SMD:R_0603_1608Metric", "Status resistor", 170.18, 53.34)
    add("D7", "D7", "BLUE", "LED_LOCAL", "LED_SMD:LED_0603_1608Metric", "Status LED", 190.50, 53.34, 180)
    add("R8", "R8", "4.7k", "R_LOCAL", "Resistor_SMD:R_0603_1608Metric", "Charge current set", 96.52, 157.48, 90)
    add("R9", "R9", "10k", "R_LOCAL", "Resistor_SMD:R_0603_1608Metric", "EN pullup", 106.68, 58.42, 90)
    add("R10", "R10", "330k", "R_LOCAL", "Resistor_SMD:R_0603_1608Metric", "Battery sense top", 167.64, 165.10)
    add("R11", "R11", "100k", "R_LOCAL", "Resistor_SMD:R_0603_1608Metric", "Battery sense bottom", 182.88, 165.10)
    add("R12", "R12", "1k", "R_LOCAL", "Resistor_SMD:R_0603_1608Metric", "Base resistor", 147.32, 144.78)
    add("C1", "C1", "4.7u", "C_LOCAL", "Capacitor_SMD:C_0603_1608Metric", "VBUS bulk", 45.72, 162.56, 90)
    add("C2", "C2", "4.7u", "C_LOCAL", "Capacitor_SMD:C_0603_1608Metric", "VBAT bulk", 45.72, 129.54, 90)
    add("C3", "C3", "1u", "C_LOCAL", "Capacitor_SMD:C_0603_1608Metric", "LDO input cap", 48.26, 109.22, 90)
    add("C4", "C4", "4.7u", "C_LOCAL", "Capacitor_SMD:C_0603_1608Metric", "LDO output cap", 91.44, 109.22, 90)
    add("C5", "C5", "100n", "C_LOCAL", "Capacitor_SMD:C_0603_1608Metric", "MCU decoupler", 109.22, 35.56, 90)

    sections = []
    sections.append("(kicad_sch")
    sections.append("\t(version 20250114)")
    sections.append('\t(generator "codex")')
    sections.append('\t(generator_version "1.0")')
    sections.append('\t(uuid "{}")'.format(root_uuid))
    sections.append('\t(paper "A3")')
    sections.append('\t(title_block')
    sections.append('\t\t(title "Boosted Remote Reverse-Engineered First Pass")')
    sections.append('\t\t(company "Codex")')
    sections.append('\t\t(comment 1 "ESP32-C3 + DRV5055 + MCP73831 + TLV75533")')
    sections.append('\t)')
    sections.append("\t(lib_symbols")
    for sym in defs.values():
        sections.append(sym.to_lib())
    sections.append("\t)")

    for component in inst.values():
        sections.append(symbol_block(root_uuid, component, defs))

    # Network labels
    for obj in label_from_pin(inst["J1"], defs, "1", "VBUS"):
        sections.append(obj)
    sections.append(no_connect(*pin_point(inst["J1"], defs, "2")))
    sections.append(no_connect(*pin_point(inst["J1"], defs, "3")))
    sections.append(no_connect(*pin_point(inst["J1"], defs, "4")))
    for obj in label_from_pin(inst["J1"], defs, "5", "GND"):
        sections.append(obj)
    for obj in label_from_pin(inst["J2"], defs, "1", "VBAT"):
        sections.append(obj)
    for obj in label_from_pin(inst["J2"], defs, "2", "GND"):
        sections.append(obj)
    for obj in label_from_pin(inst["J3"], defs, "1", "V3P3"):
        sections.append(obj)
    for obj in label_from_pin(inst["J3"], defs, "2", "GND"):
        sections.append(obj)
    for obj in label_from_pin(inst["J3"], defs, "3", "UART_RX"):
        sections.append(obj)
    for obj in label_from_pin(inst["J3"], defs, "4", "UART_TX"):
        sections.append(obj)
    for obj in label_from_pin(inst["J3"], defs, "5", "EN"):
        sections.append(obj)
    for obj in label_from_pin(inst["J3"], defs, "6", "BOOT"):
        sections.append(obj)
    for obj in label_from_pin(inst["U2"], defs, "2", "GND"):
        sections.append(obj)
    for obj in label_from_pin(inst["U2"], defs, "3", "VBAT"):
        sections.append(obj)
    for obj in label_from_pin(inst["U2"], defs, "4", "VBUS"):
        sections.append(obj)
    for obj in label_from_pin(inst["U2"], defs, "1", "CHG_STAT"):
        sections.append(obj)
    sections.append(wire(*pin_point(inst["U2"], defs, "5"), *pin_point(inst["R8"], defs, "1")))

    # R8 to GND, manual because rotated
    x1, y1 = pin_point(inst["R8"], defs, "2")
    sections.append(wire(x1, y1, x1, y1 + 5.08))
    sections.append(label("GND", x1, y1 + 5.08, 90, "left bottom"))

    for obj in label_from_pin(inst["U3"], defs, "1", "VBAT"):
        sections.append(obj)
    for obj in label_from_pin(inst["U3"], defs, "2", "GND"):
        sections.append(obj)
    for obj in label_from_pin(inst["U3"], defs, "3", "VBAT"):
        sections.append(obj)
    for obj in label_from_pin(inst["U3"], defs, "5", "V3P3"):
        sections.append(obj)
    for obj in label_from_pin(inst["U4"], defs, "1", "V3P3"):
        sections.append(obj)
    for obj in label_from_pin(inst["U4"], defs, "2", "HALL_OUT"):
        sections.append(obj)
    for obj in label_from_pin(inst["U4"], defs, "3", "GND"):
        sections.append(obj)
    for obj in label_from_pin(inst["SW1"], defs, "1", "DEADMAN"):
        sections.append(obj)
    for obj in label_from_pin(inst["SW1"], defs, "2", "GND"):
        sections.append(obj)
    for obj in label_from_pin(inst["SW2"], defs, "1", "PWR_BTN"):
        sections.append(obj)
    for obj in label_from_pin(inst["SW2"], defs, "2", "GND"):
        sections.append(obj)

    mcu_nets = {
        "1": "V3P3",
        "2": "EN",
        "3": "HALL_OUT",
        "4": "DEADMAN",
        "5": "PWR_BTN",
        "6": "BUZZ_PWM",
        "7": "STATUS_G",
        "8": "STATUS_B",
        "9": "GND",
        "10": "LED1",
        "11": "UART_RX",
        "12": "UART_TX",
        "13": "LED2",
        "14": "LED3",
        "15": "LED4",
        "16": "LED5",
        "17": "BAT_SENSE",
        "18": "BOOT",
        "19": "GND",
    }
    for pin, net in mcu_nets.items():
        for obj in label_from_pin(inst["U1"], defs, pin, net):
            sections.append(obj)

    # KiCad's generated custom symbols are still slightly inconsistent for a few top/bottom pins.
    # Add explicit stitches at the exact ERC-reported coordinates so those nets are unambiguous.
    sections.append(wire(71.12, 38.10, 71.12, 43.18))
    sections.append(label("GND", 71.12, 43.18, 90, "left bottom"))
    sections.append(wire(81.28, 113.03, 86.36, 113.03))
    sections.append(label("V3P3", 86.36, 113.03, 180, "right bottom"))
    sections.append(wire(134.62, 116.84, 134.62, 111.76))
    sections.append(label("V3P3", 134.62, 111.76, 270, "right bottom"))
    sections.append(wire(133.35, 76.20, 133.35, 71.12))
    sections.append(label("GND", 133.35, 71.12, 270, "right bottom"))
    sections.append(wire(135.89, 76.20, 135.89, 71.12))
    sections.append(label("GND", 135.89, 71.12, 270, "right bottom"))

    # R9 EN pull-up
    x_en1, y_en1 = pin_point(inst["R9"], defs, "1")
    x_en2, y_en2 = pin_point(inst["R9"], defs, "2")
    sections.append(wire(x_en1, y_en1, x_en1, y_en1 + 5.08))
    sections.append(label("EN", x_en1, y_en1 + 5.08, 90, "left bottom"))
    sections.append(wire(x_en2, y_en2, x_en2, y_en2 - 5.08))
    sections.append(label("V3P3", x_en2, y_en2 - 5.08, 270, "right bottom"))

    # Power capacitors
    for cname, net in (("C1", "VBUS"), ("C2", "VBAT"), ("C3", "VBAT"), ("C4", "V3P3"), ("C5", "V3P3")):
        cx1, cy1 = pin_point(inst[cname], defs, "1")
        cx2, cy2 = pin_point(inst[cname], defs, "2")
        sections.append(wire(cx1, cy1, cx1, cy1 + 5.08))
        sections.append(label(net, cx1, cy1 + 5.08, 90, "left bottom"))
        sections.append(wire(cx2, cy2, cx2, cy2 - 5.08))
        sections.append(label("GND", cx2, cy2 - 5.08, 270, "right bottom"))

    # Battery divider
    sections.append(wire(*pin_point(inst["R10"], defs, "1"), pin_point(inst["R10"], defs, "1")[0], pin_point(inst["R10"], defs, "1")[1] + 5.08))
    sections.append(label("VBAT", pin_point(inst["R10"], defs, "1")[0], pin_point(inst["R10"], defs, "1")[1] + 5.08, 90, "left bottom"))
    sections.append(wire(*pin_point(inst["R10"], defs, "2"), *pin_point(inst["R11"], defs, "1")))
    midx = (pin_point(inst["R10"], defs, "2")[0] + pin_point(inst["R11"], defs, "1")[0]) / 2.0
    midy = pin_point(inst["R10"], defs, "2")[1]
    sections.append(wire(midx, midy, midx, midy - 5.08))
    sections.append(label("BAT_SENSE", midx, midy - 5.08, 270, "right bottom"))
    sections.append(wire(*pin_point(inst["R11"], defs, "2"), pin_point(inst["R11"], defs, "2")[0], pin_point(inst["R11"], defs, "2")[1] - 5.08))
    sections.append(label("GND", pin_point(inst["R11"], defs, "2")[0], pin_point(inst["R11"], defs, "2")[1] - 5.08, 270, "right bottom"))

    # Buzzer drive
    sections.append(wire(*pin_point(inst["R12"], defs, "1"), pin_point(inst["R12"], defs, "1")[0] - 5.08, pin_point(inst["R12"], defs, "1")[1]))
    sections.append(label("BUZZ_PWM", pin_point(inst["R12"], defs, "1")[0] - 5.08, pin_point(inst["R12"], defs, "1")[1], 0, "left bottom"))
    sections.append(wire(*pin_point(inst["R12"], defs, "2"), *pin_point(inst["Q1"], defs, "1")))
    for obj in label_from_pin(inst["Q1"], defs, "2", "GND"):
        sections.append(obj)
    q1c_x, q1c_y = pin_point(inst["Q1"], defs, "3")
    bz1n_x, bz1n_y = pin_point(inst["BZ1"], defs, "2")
    buzzer_escape_y = 170.18
    sections.append(wire(q1c_x, q1c_y, q1c_x, buzzer_escape_y))
    sections.append(wire(q1c_x, buzzer_escape_y, bz1n_x, buzzer_escape_y))
    sections.append(wire(bz1n_x, buzzer_escape_y, bz1n_x, bz1n_y))
    sections.append(wire(*pin_point(inst["BZ1"], defs, "1"), pin_point(inst["BZ1"], defs, "1")[0] - 5.08, pin_point(inst["BZ1"], defs, "1")[1]))
    sections.append(label("V3P3", pin_point(inst["BZ1"], defs, "1")[0] - 5.08, pin_point(inst["BZ1"], defs, "1")[1], 0, "left bottom"))

    # LED chains
    led_map = [
        ("R1", "D1", "LED1"),
        ("R2", "D2", "LED2"),
        ("R3", "D3", "LED3"),
        ("R4", "D4", "LED4"),
        ("R5", "D5", "LED5"),
        ("R6", "D6", "STATUS_G"),
        ("R7", "D7", "STATUS_B"),
    ]
    for rid, did, drv in led_map:
        r1x, r1y = pin_point(inst[rid], defs, "1")
        r2x, r2y = pin_point(inst[rid], defs, "2")
        d1x, d1y = pin_point(inst[did], defs, "1")
        d2x, d2y = pin_point(inst[did], defs, "2")
        sections.append(wire(r1x, r1y, r1x - 5.08, r1y))
        sections.append(label(drv, r1x - 5.08, r1y, 0, "left bottom"))
        sections.append(wire(r2x, r2y, d2x, d2y))
        sections.append(wire(d1x, d1y, d1x + 5.08, d1y))
        sections.append(label("GND", d1x + 5.08, d1y, 180, "right bottom"))

    sections.append(
        '\t(text "Reverse-engineered first-pass hardware recreation\\nBLE/firmware compatibility work is separate."'
    )
    sections.append('\t\t(at 18 20 0)')
    sections.append("\t\t(effects")
    sections.append("\t\t\t(font")
    sections.append("\t\t\t\t(size 1.27 1.27)")
    sections.append("\t\t\t)")
    sections.append("\t\t)")
    sections.append('\t\t(uuid "{}")'.format(u()))
    sections.append("\t)")
    sections.append("\t(sheet_instances")
    sections.append('\t\t(path "/"')
    sections.append('\t\t\t(page "1")')
    sections.append("\t\t)")
    sections.append("\t)")
    sections.append("\t(embedded_fonts no)")
    sections.append(")")

    SCH_PATH.write_text("\n".join(sections) + "\n")
    print(f"schematic: wrote {SCH_PATH}", flush=True)


def fp(lib: str, name: str):
    local_path = KICAD_DIR / f"{lib}.pretty"
    if local_path.exists():
        return str(local_path), name
    return str(SYSTEM_FOOTPRINT_ROOT / f"{lib}.pretty"), name


def load_fp(lib: str, name: str):
    lib_path, fp_name = fp(lib, name)
    footprint = pcbnew.FootprintLoad(lib_path, fp_name)
    if footprint is None:
        raise RuntimeError(f"Failed to load {lib}:{name}")
    return footprint


def add_fp(board, ref, value, lib, name, x, y, rot=0, side="F"):
    footprint = load_fp(lib, name)
    footprint.SetReference(ref)
    footprint.SetValue(value)
    footprint.SetPosition(pt(x, y))
    footprint.SetOrientation(angle(rot))
    board.Add(footprint)
    if side == "B":
        footprint.Flip(footprint.GetPosition(), False)
    return footprint


def normalize_usb_instance(footprint, rotation_deg: float):
    for pad in footprint.Pads():
        pad.SetOrientationDegrees(pad.GetOrientationDegrees() + rotation_deg)
    for field in footprint.GetFields():
        field.SetTextAngleDegrees(field.GetTextAngleDegrees() + rotation_deg)
    for item in footprint.GraphicalItems():
        if item.GetClass() == "PCB_TEXT":
            item.SetTextAngleDegrees(item.GetTextAngleDegrees() + rotation_deg)


def enabled_copper_layer_set(board):
    layers = pcbnew.LSET()
    for layer in board.GetEnabledLayers().Seq():
        if board.GetLayerName(layer).endswith(".Cu"):
            layers.AddLayer(layer)
    return layers


def normalize_antenna_keepout_to_all_copper(board, footprint):
    copper_layers = enabled_copper_layer_set(board)
    for zone in footprint.Zones():
        zone.SetLayerSet(copper_layers)


def add_net(board, name):
    net = pcbnew.NETINFO_ITEM(board, name)
    board.Add(net)
    return net


def padmap(footprint):
    pads = {}
    for p in footprint.Pads():
        pads.setdefault(p.GetNumber(), []).append(p)
    return pads


def set_pad_net(footprint, pad_number, net):
    for pad in padmap(footprint).get(str(pad_number), []):
        pad.SetNet(net)


def set_named_pad_net(footprint, pad_name, net):
    for pad in footprint.Pads():
        if pad.GetName() == pad_name:
            pad.SetNet(net)


def first_pad(footprint, pad_number):
    return padmap(footprint)[str(pad_number)][0]


def pad_xy(pad):
    center = pad.GetCenter()
    return pcbnew.ToMM(center.x), pcbnew.ToMM(center.y)


def add_track(board, net, start, end, width=0.25, layer=pcbnew.F_Cu):
    t = pcbnew.PCB_TRACK(board)
    t.SetNet(net)
    t.SetStart(start)
    t.SetEnd(end)
    t.SetWidth(mm(width))
    t.SetLayer(layer)
    board.Add(t)


def add_via(board, net, x, y, drill=0.3, diameter=0.6):
    via = pcbnew.PCB_VIA(board)
    via.SetNet(net)
    via.SetPosition(pt(x, y))
    via.SetDrill(mm(drill))
    via.SetWidth(mm(diameter))
    board.Add(via)
    return via


def route(board, net, points, width=0.25, layer=pcbnew.F_Cu):
    for a, b in zip(points, points[1:]):
        add_track(board, net, pt(*a), pt(*b), width, layer)


def connect_pads(board, net, pad_a, waypoints, pad_b, width=0.25, layer=pcbnew.F_Cu):
    points = [(pcbnew.ToMM(pad_a.GetCenter().x), pcbnew.ToMM(pad_a.GetCenter().y))]
    points.extend(waypoints)
    points.append((pcbnew.ToMM(pad_b.GetCenter().x), pcbnew.ToMM(pad_b.GetCenter().y)))
    route(board, net, points, width, layer)


def add_edge_segment(board, x1, y1, x2, y2):
    seg = pcbnew.PCB_SHAPE(board)
    seg.SetLayer(pcbnew.Edge_Cuts)
    seg.SetShape(pcbnew.SHAPE_T_SEGMENT)
    seg.SetStart(pt(x1, y1))
    seg.SetEnd(pt(x2, y2))
    seg.SetWidth(mm(0.15))
    board.Add(seg)


def add_user_rect(board, layer, x, y, width, height, line_width=0.12):
    left = x - width / 2.0
    right = x + width / 2.0
    top = y - height / 2.0
    bottom = y + height / 2.0
    for x1, y1, x2, y2 in [
        (left, top, right, top),
        (right, top, right, bottom),
        (right, bottom, left, bottom),
        (left, bottom, left, top),
    ]:
        seg = pcbnew.PCB_SHAPE(board)
        seg.SetLayer(layer)
        seg.SetShape(pcbnew.SHAPE_T_SEGMENT)
        seg.SetStart(pt(x1, y1))
        seg.SetEnd(pt(x2, y2))
        seg.SetWidth(mm(line_width))
        board.Add(seg)


def add_user_circle(board, layer, x, y, radius, line_width=0.12):
    circle = pcbnew.PCB_SHAPE(board)
    circle.SetLayer(layer)
    circle.SetShape(pcbnew.SHAPE_T_CIRCLE)
    circle.SetStart(pt(x, y))
    circle.SetEnd(pt(x + radius, y))
    circle.SetWidth(mm(line_width))
    board.Add(circle)


def add_user_text(board, layer, text, x, y, size=1.0):
    txt = pcbnew.PCB_TEXT(board)
    txt.SetText(text)
    txt.SetPosition(pt(x, y))
    txt.SetLayer(layer)
    txt.SetTextSize(pcbnew.VECTOR2I(mm(size), mm(size)))
    board.Add(txt)


def board_outline():
    return [
        (86.0, 17.0),
        (106.0, 17.0),
        (116.0, 20.0),
        (121.0, 28.0),
        (120.0, 40.0),
        (118.0, 54.0),
        (117.0, 68.0),
        (116.0, 84.0),
        (116.0, 100.0),
        (115.0, 114.0),
        (112.0, 126.0),
        (107.0, 134.0),
        (100.0, 137.0),
        (92.0, 136.0),
        (86.0, 130.0),
        (84.0, 120.0),
        (83.0, 108.0),
        (82.0, 94.0),
        (81.0, 80.0),
        (80.0, 66.0),
        (79.0, 52.0),
        (78.0, 40.0),
        (78.0, 29.0),
        (81.0, 21.0),
        (86.0, 17.0),
    ]


def add_outline(board):
    pts = board_outline()
    for a, b in zip(pts, pts[1:]):
        add_edge_segment(board, a[0], a[1], b[0], b[1])


def point_in_polygon(x, y, polygon):
    inside = False
    for (x1, y1), (x2, y2) in zip(polygon, polygon[1:]):
        if (y1 > y) != (y2 > y):
            intersect_x = (x2 - x1) * (y - y1) / (y2 - y1) + x1
            if x < intersect_x:
                inside = not inside
    return inside


def segment_distance(px, py, ax, ay, bx, by):
    dx = bx - ax
    dy = by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    qx = ax + t * dx
    qy = ay + t * dy
    return math.hypot(px - qx, py - qy)


def footprint_outline_clearance(fp, polygon):
    bbox = fp.GetBoundingBox()
    corners = [
        (pcbnew.ToMM(bbox.GetLeft()), pcbnew.ToMM(bbox.GetTop())),
        (pcbnew.ToMM(bbox.GetRight()), pcbnew.ToMM(bbox.GetTop())),
        (pcbnew.ToMM(bbox.GetRight()), pcbnew.ToMM(bbox.GetBottom())),
        (pcbnew.ToMM(bbox.GetLeft()), pcbnew.ToMM(bbox.GetBottom())),
    ]
    clearance = None
    for x, y in corners:
        edge_distance = min(segment_distance(x, y, a[0], a[1], b[0], b[1]) for a, b in zip(polygon, polygon[1:]))
        signed = edge_distance if point_in_polygon(x, y, polygon) else -edge_distance
        clearance = signed if clearance is None else min(clearance, signed)
    return clearance if clearance is not None else 0.0


def assert_footprints_within_outline(footprints, refs):
    outline = board_outline()
    outside = []
    for ref in refs:
        clearance = footprint_outline_clearance(footprints[ref], outline)
        if clearance <= 0:
            outside.append(f"{ref} clearance={clearance:.3f}mm")
    if outside:
        joined = ", ".join(outside)
        raise RuntimeError(f"PCB placement exceeds board outline: {joined}")


def add_gnd_zone(board, net, layer):
    zone = pcbnew.ZONE(board)
    zone.SetLayer(layer)
    zone.SetNet(net)
    zone.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
    zone.SetThermalReliefGap(mm(0.5))
    zone.SetThermalReliefSpokeWidth(mm(0.5))
    outline = zone.Outline()
    outline.NewOutline()
    for idx, (x, y) in enumerate(board_outline()[:-1]):
        outline.Append(mm(x), mm(y), -1 if idx == 0 else 0)
    board.Add(zone)


def add_copper_keepout(board, layer, polygon_pts):
    zone = pcbnew.ZONE(board)
    zone.SetLayer(layer)
    zone.SetIsRuleArea(True)
    zone.SetDoNotAllowZoneFills(True)
    zone.SetDoNotAllowTracks(False)
    zone.SetDoNotAllowVias(False)
    zone.SetDoNotAllowPads(False)
    zone.SetDoNotAllowFootprints(False)
    outline = zone.Outline()
    outline.NewOutline()
    for idx, (x, y) in enumerate(polygon_pts):
        outline.Append(mm(x), mm(y), -1 if idx == 0 else 0)
    board.Add(zone)


def add_reference_layout(board):
    layer = pcbnew.Dwgs_User
    add_user_circle(board, layer, 91.0, 28.0, 15.5)
    add_user_text(board, layer, "thumbwheel pack", 94.0, 13.5, 0.9)
    add_user_rect(board, layer, 99.0, 108.5, 29.0, 37.0)
    add_user_text(board, layer, "1S LiPo 500mAh", 99.0, 88.0, 0.9)
    add_user_rect(board, layer, 92.0, 50.0, 21.0, 22.0)
    add_user_text(board, layer, "ESP32-C3 module", 92.0, 63.0, 0.8)
    add_user_circle(board, layer, 100.0, 82.0, 6.5)
    add_user_text(board, layer, "buzzer", 100.0, 92.0, 0.8)
    add_user_rect(board, layer, 99.0, 129.0, 10.0, 6.0)
    add_user_text(board, layer, "mini-USB", 99.0, 122.5, 0.8)
    for spec in read_params()["mechanical"].get("pcb_mount_holes", []):
        add_user_circle(board, layer, spec["board_x_mm"], spec["board_y_mm"], spec["pcb_drill_mm"] / 2.0)
        add_user_text(board, layer, spec["name"], spec["board_x_mm"], spec["board_y_mm"] - 3.0, 0.7)


def add_hall_encoder_silkscreen(board):
    # Show the two adjacent opposing magnets used for hall encoder sensing.
    layer = pcbnew.B_SilkS
    cx, cy = HALL_ENCODER_CENTER
    wheel_r = HALL_ENCODER_WHEEL_RADIUS
    magnet_r = HALL_ENCODER_MAGNET_RADIUS
    add_user_circle(board, layer, cx, cy, wheel_r, 0.12)
    for deg in HALL_ENCODER_MAGNET_ANGLES_DEG:
        rad = math.radians(deg)
        mx = cx + magnet_r * math.cos(rad)
        my = cy + magnet_r * math.sin(rad)
        add_user_circle(board, layer, mx, my, HALL_ENCODER_MAGNET_MARKER_RADIUS, 0.12)
    add_user_text(board, layer, "HALL ENCODER", cx, cy - 18.2, 0.8)
    add_user_text(board, layer, "TWO OPPOSING MAGNETS IN WHEEL", cx, cy + 18.2, 0.7)


def build_pcb(params: dict):
    print("pcb: start", flush=True)
    board = pcbnew.BOARD()
    board.SetCopperLayerCount(PCB_COPPER_LAYER_COUNT)
    board.GetDesignSettings().m_MinThroughDrill = mm(0.2)
    board.SetTitleBlock(pcbnew.TITLE_BLOCK())
    board.GetTitleBlock().SetTitle("Boosted Remote Reverse-Engineered First Pass")
    add_outline(board)
    print("pcb: outline", flush=True)

    nets = {name: add_net(board, name) for name in [
        "GND", "VBUS", "VBAT", "V3P3", "EN", "BOOT", "UART_RX", "UART_TX",
        "HALL_OUT", "DEADMAN", "PWR_BTN", "BUZZ_PWM", "BUZZ_BASE", "BUZZ",
        "PROG", "CHG_STAT",
        "BAT_SENSE", "STATUS_G", "STATUS_G_A", "STATUS_B", "STATUS_B_A",
        "LED1", "LED1_A", "LED2", "LED2_A", "LED3", "LED3_A", "LED4", "LED4_A", "LED5", "LED5_A",
    ]}
    print("pcb: nets", flush=True)

    fpd = {}
    sw2_x, sw2_y, sw2_rot = power_button_board_position(params)
    u4_x, u4_y, u4_rot = hall_sensor_board_position()
    for spec in mounting_hole_specs(params):
        ref = spec["name"]
        fpd[ref] = add_fp(board, ref, "M2", *MOUNTING_HOLE_FOOTPRINT, spec["board_x_mm"], spec["board_y_mm"], 0)
    fpd["J1"] = add_fp(
        board,
        "J1",
        "USB_Mini-B",
        LOCAL_FOOTPRINT_LIB,
        USB_FOOTPRINT_NAME,
        USB_MINI_POSITION[0],
        USB_MINI_POSITION[1],
        USB_MINI_ROTATION_DEG,
    )
    normalize_usb_instance(fpd["J1"], USB_MINI_ROTATION_DEG)
    print("pcb: J1", flush=True)
    fpd["J2"] = add_fp(board, "J2", "Battery", "Connector_JST", "JST_PH_B2B-PH-K_1x02_P2.00mm_Vertical", 90, 87, 0)
    print("pcb: J2", flush=True)
    fpd["J3"] = add_fp(board, "J3", "UART", "Connector_PinHeader_1.27mm", "PinHeader_1x06_P1.27mm_Vertical", 82, 68, 0)
    print("pcb: J3", flush=True)
    fpd["U1"] = add_fp(board, "U1", "ESP32-C3-WROOM-02", "RF_Module", "ESP32-C3-WROOM-02", 92, 50, 0, "B")
    normalize_antenna_keepout_to_all_copper(board, fpd["U1"])
    print("pcb: U1", flush=True)
    fpd["U2"] = add_fp(board, "U2", "MCP73831-2-OT", "Package_TO_SOT_SMD", "SOT-23-5", 87, 97, 90, "B")
    print("pcb: U2", flush=True)
    fpd["U3"] = add_fp(board, "U3", "TLV75533PDBV", "Package_TO_SOT_SMD", "SOT-23-5", *PCB_FOOTPRINT_PLACEMENTS["U3"], "B")
    print("pcb: U3", flush=True)
    fpd["U4"] = add_fp(board, "U4", "DRV5055A3xDBZxQ1", "Package_TO_SOT_SMD", "SOT-23", u4_x, u4_y, u4_rot, "B")
    print("pcb: U4", flush=True)
    fpd["SW1"] = add_fp(board, "SW1", "Deadman", "Button_Switch_SMD", "SW_Push_1P1T-MP_NO_Horizontal_Alps_SKRTLAE010", 114, 55, 90, "B")
    print("pcb: SW1", flush=True)
    fpd["SW2"] = add_fp(board, "SW2", "Power", "Button_Switch_SMD", "SW_SPST_TL3305A", sw2_x, sw2_y, sw2_rot)
    print("pcb: SW2", flush=True)
    fpd["Q1"] = add_fp(board, "Q1", "MMBT3904", "Package_TO_SOT_SMD", "SOT-23", 111, 86, 180)
    print("pcb: Q1", flush=True)
    fpd["BZ1"] = add_fp(board, "BZ1", "Buzzer", "Buzzer_Beeper", "Buzzer_Murata_PKMCS0909E", 100, 82, 0, "B")
    print("pcb: BZ1", flush=True)

    for idx, y in enumerate([92, 99, 106, 113, 120], start=1):
        fpd[f"R{idx}"] = add_fp(board, f"R{idx}", "330", "Resistor_SMD", "R_0603_1608Metric", 104, y, 90)
        fpd[f"D{idx}"] = add_fp(board, f"D{idx}", "LED", "LED_SMD", "LED_0603_1608Metric", 109, y, 180)
    fpd["R6"] = add_fp(board, "R6", "330", "Resistor_SMD", "R_0603_1608Metric", 108, 66, 0)
    fpd["D6"] = add_fp(board, "D6", "GREEN", "LED_SMD", "LED_0603_1608Metric", 113, 66, 180)
    fpd["R7"] = add_fp(board, "R7", "330", "Resistor_SMD", "R_0603_1608Metric", 108, 74, 0)
    fpd["D7"] = add_fp(board, "D7", "BLUE", "LED_SMD", "LED_0603_1608Metric", 113, 74, 180)
    fpd["R8"] = add_fp(board, "R8", "4.7k", "Resistor_SMD", "R_0603_1608Metric", 96, 101, 90, "B")
    fpd["R9"] = add_fp(board, "R9", "10k", "Resistor_SMD", "R_0603_1608Metric", *PCB_FOOTPRINT_PLACEMENTS["R9"])
    fpd["R10"] = add_fp(board, "R10", "330k", "Resistor_SMD", "R_0603_1608Metric", 91, 93, 90, "B")
    fpd["R11"] = add_fp(board, "R11", "100k", "Resistor_SMD", "R_0603_1608Metric", 97, 93, 90, "B")
    fpd["R12"] = add_fp(board, "R12", "1k", "Resistor_SMD", "R_0603_1608Metric", 112, 93, 0)
    fpd["C1"] = add_fp(board, "C1", "4.7u", "Capacitor_SMD", "C_0603_1608Metric", 95, 121, 90, "B")
    fpd["C2"] = add_fp(board, "C2", "4.7u", "Capacitor_SMD", "C_0603_1608Metric", 91, 105, 90, "B")
    fpd["C3"] = add_fp(board, "C3", "1u", "Capacitor_SMD", "C_0603_1608Metric", *PCB_FOOTPRINT_PLACEMENTS["C3"], "B")
    fpd["C4"] = add_fp(board, "C4", "4.7u", "Capacitor_SMD", "C_0603_1608Metric", *PCB_FOOTPRINT_PLACEMENTS["C4"], "B")
    fpd["C5"] = add_fp(board, "C5", "100n", "Capacitor_SMD", "C_0603_1608Metric", 104, 63, 90)
    print("pcb: footprints", flush=True)
    assert_footprints_within_outline(fpd, ["R9", "U3", "C3", "C4"])

    # Net assignments
    set_pad_net(fpd["J1"], 1, nets["VBUS"])
    set_pad_net(fpd["J1"], 5, nets["GND"])
    set_named_pad_net(fpd["J1"], "SH", nets["GND"])
    set_pad_net(fpd["J2"], 1, nets["VBAT"])
    set_pad_net(fpd["J2"], 2, nets["GND"])
    for num, net in [(1, "V3P3"), (2, "GND"), (3, "UART_RX"), (4, "UART_TX"), (5, "EN"), (6, "BOOT")]:
        set_pad_net(fpd["J3"], num, nets[net])

    for num, net in [(1, "V3P3"), (2, "EN"), (3, "HALL_OUT"), (4, "DEADMAN"), (5, "PWR_BTN"),
                     (6, "BUZZ_PWM"), (7, "STATUS_G"), (8, "STATUS_B"), (9, "GND"), (10, "LED1"),
                     (11, "UART_RX"), (12, "UART_TX"), (13, "LED2"), (14, "LED3"), (15, "LED4"),
                     (16, "LED5"), (17, "BAT_SENSE"), (18, "BOOT"), (19, "GND")]:
        set_pad_net(fpd["U1"], num, nets[net])

    for num, net in [(1, "CHG_STAT"), (2, "GND"), (3, "VBAT"), (4, "VBUS"), (5, "PROG")]:
        if net:
            set_pad_net(fpd["U2"], num, nets[net])
    set_pad_net(fpd["U3"], 1, nets["VBAT"])
    set_pad_net(fpd["U3"], 2, nets["GND"])
    set_pad_net(fpd["U3"], 3, nets["VBAT"])
    set_pad_net(fpd["U3"], 5, nets["V3P3"])
    set_pad_net(fpd["U4"], 1, nets["V3P3"])
    set_pad_net(fpd["U4"], 2, nets["HALL_OUT"])
    set_pad_net(fpd["U4"], 3, nets["GND"])
    set_pad_net(fpd["SW1"], 1, nets["DEADMAN"])
    set_pad_net(fpd["SW1"], 2, nets["GND"])
    set_pad_net(fpd["SW2"], 1, nets["PWR_BTN"])
    set_pad_net(fpd["SW2"], 2, nets["GND"])
    set_pad_net(fpd["Q1"], 1, nets["BUZZ_BASE"])
    set_pad_net(fpd["Q1"], 2, nets["GND"])
    set_pad_net(fpd["Q1"], 3, nets["BUZZ"])
    set_pad_net(fpd["BZ1"], 1, nets["V3P3"])
    set_pad_net(fpd["BZ1"], 2, nets["BUZZ"])

    led_nets = [
        ("R1", "D1", "LED1", "LED1_A"),
        ("R2", "D2", "LED2", "LED2_A"),
        ("R3", "D3", "LED3", "LED3_A"),
        ("R4", "D4", "LED4", "LED4_A"),
        ("R5", "D5", "LED5", "LED5_A"),
        ("R6", "D6", "STATUS_G", "STATUS_G_A"),
        ("R7", "D7", "STATUS_B", "STATUS_B_A"),
    ]
    for rid, did, drv_net, led_net in led_nets:
        set_pad_net(fpd[rid], 1, nets[drv_net])
        set_pad_net(fpd[rid], 2, nets[led_net])
        set_pad_net(fpd[did], 1, nets["GND"])
        set_pad_net(fpd[did], 2, nets[led_net])

    set_pad_net(fpd["R8"], 1, nets["PROG"])
    set_pad_net(fpd["R8"], 2, nets["GND"])
    set_pad_net(fpd["R9"], 1, nets["EN"])
    set_pad_net(fpd["R9"], 2, nets["V3P3"])
    set_pad_net(fpd["R10"], 1, nets["VBAT"])
    set_pad_net(fpd["R10"], 2, nets["BAT_SENSE"])
    set_pad_net(fpd["R11"], 1, nets["BAT_SENSE"])
    set_pad_net(fpd["R11"], 2, nets["GND"])
    set_pad_net(fpd["R12"], 1, nets["BUZZ_PWM"])
    set_pad_net(fpd["R12"], 2, nets["BUZZ_BASE"])

    for cname, p1, p2 in [("C1", "VBUS", "GND"), ("C2", "VBAT", "GND"), ("C3", "VBAT", "GND"), ("C4", "V3P3", "GND"), ("C5", "V3P3", "GND")]:
        set_pad_net(fpd[cname], 1, nets[p1])
        set_pad_net(fpd[cname], 2, nets[p2])

    pads = {ref: padmap(fp) for ref, fp in fpd.items()}

    def p(ref, number, idx=0):
        return pads[ref][str(number)][idx]

    def connect(ref_a, pad_a, ref_b, pad_b, waypoints=None, width=0.25):
        connect_pads(
            board,
            p(ref_a, pad_a).GetNet(),
            p(ref_a, pad_a),
            waypoints or [],
            p(ref_b, pad_b),
            width,
            pcbnew.F_Cu,
        )

    def chain(net_name, points, width=0.25):
        route(board, nets[net_name], points, width, pcbnew.F_Cu)

    # Local same-net stitches inside duplicated-pin parts and exposed grounds.
    def stitch_duplicate_pads(ref, pad_number, net_name, width=0.3):
        pad_list = pads[ref].get(str(pad_number), [])
        if len(pad_list) >= 2:
            chain(net_name, [pad_xy(pad_list[0]), pad_xy(pad_list[1])], width)

    stitch_duplicate_pads("SW1", 1, "DEADMAN")
    stitch_duplicate_pads("SW1", 2, "GND")
    stitch_duplicate_pads("SW2", 1, "PWR_BTN")
    stitch_duplicate_pads("SW2", 2, "GND")
    chain("GND", [pad_xy(p("J1", 5)), pad_xy(p("J1", "SH", 2)), pad_xy(p("J1", "SH", 3))], 0.3)
    chain("GND", [pad_xy(p("J1", "SH", 0)), pad_xy(p("J1", "SH", 1))], 0.3)

    # ESP32 exposed-pad ground stitch.
    ep = [
        (91.86, 49.10), (92.41, 49.10), (92.96, 49.10), (93.51, 49.10),
        (94.06, 49.65), (94.06, 50.75), (93.51, 51.30), (92.96, 51.30),
        (92.41, 51.30), (91.86, 50.75), (91.86, 50.20), (92.41, 50.20),
        (92.96, 50.20), (93.51, 50.20),
    ]
    chain("GND", ep, 0.2)

    # Leave the charger/regulator cluster to the review routing pass.
    # The local packet above only contains repeated-pad and same-net closures.
    connect("R12", 2, "Q1", 1, [(112.825, 86.95)], 0.2)

    connect("Q1", 3, "BZ1", 2, [(110.062, 82.0)], 0.25)

    for idx, y in enumerate([92.0, 99.0, 106.0, 113.0, 120.0], start=1):
        chain(f"LED{idx}_A", [(104.0, y - 0.825), (107.0, y - 0.825), (107.0, y), (108.213, y)], 0.2)
    chain("STATUS_G_A", [(108.825, 66.0), (112.213, 66.0)], 0.2)
    chain("STATUS_B_A", [(108.825, 74.0), (112.213, 74.0)], 0.2)

    # Board labels
    add_user_text(board, pcbnew.F_SilkS, "BOOSTED REMOTE REV-A", 99, 73, 1.2)
    add_hall_encoder_silkscreen(board)
    add_reference_layout(board)
    print("pcb: local routing", flush=True)
    add_gnd_zone(board, nets["GND"], pcbnew.F_Cu)
    add_gnd_zone(board, nets["GND"], pcbnew.B_Cu)
    print("pcb: zones added", flush=True)
    print("pcb: routing complete", flush=True)

    pcbnew.SaveBoard(str(PCB_PATH), board)
    print(f"pcb: wrote {PCB_PATH}", flush=True)


def main():
    ensure_repo_usb_footprint()
    params = read_params()
    build_schematic(params)
    build_pcb(params)


if __name__ == "__main__":
    main()
