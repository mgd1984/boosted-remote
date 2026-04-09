#!/usr/bin/env python3

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
KICAD_DIR = ROOT / "electrical" / "kicad"
LOCAL_FOOTPRINT_LIB = "boosted_remote"
USB_FOOTPRINT_NAME = "USB_Mini-B_Lumberg_2486_01_Horizontal"
SYSTEM_FOOTPRINT_ROOT = Path("/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints")
SYSTEM_USB_FOOTPRINT_PATH = SYSTEM_FOOTPRINT_ROOT / "Connector_USB.pretty" / f"{USB_FOOTPRINT_NAME}.kicad_mod"
LOCAL_FOOTPRINT_DIR = KICAD_DIR / f"{LOCAL_FOOTPRINT_LIB}.pretty"
LOCAL_USB_FOOTPRINT_PATH = LOCAL_FOOTPRINT_DIR / f"{USB_FOOTPRINT_NAME}.kicad_mod"


LAYER_NORMALIZATIONS = (
    (
        """\t(fp_line
\t\t(start -3.91 1.74)
\t\t(end -3.91 -1.49)
\t\t(stroke
\t\t\t(width 0.12)
\t\t\t(type solid)
\t\t)
\t\t(layer "F.SilkS")
\t\t(uuid "84ba77ce-3676-4ef0-8d6f-9440cdfdd172")
\t)
""",
        """\t(fp_line
\t\t(start -3.91 1.74)
\t\t(end -3.91 -1.49)
\t\t(stroke
\t\t\t(width 0.12)
\t\t\t(type solid)
\t\t)
\t\t(layer "F.Fab")
\t\t(uuid "84ba77ce-3676-4ef0-8d6f-9440cdfdd172")
\t)
""",
    ),
    (
        """\t(fp_line
\t\t(start -3.91 5.91)
\t\t(end -3.91 3.96)
\t\t(stroke
\t\t\t(width 0.12)
\t\t\t(type solid)
\t\t)
\t\t(layer "F.SilkS")
\t\t(uuid "15456037-537e-4ee5-84d9-d4c2a151ae0f")
\t)
""",
        """\t(fp_line
\t\t(start -3.91 5.91)
\t\t(end -3.91 3.96)
\t\t(stroke
\t\t\t(width 0.12)
\t\t\t(type solid)
\t\t)
\t\t(layer "F.Fab")
\t\t(uuid "15456037-537e-4ee5-84d9-d4c2a151ae0f")
\t)
""",
    ),
    (
        """\t(fp_line
\t\t(start 2.11 -3.41)
\t\t(end 3.19 -3.41)
\t\t(stroke
\t\t\t(width 0.12)
\t\t\t(type solid)
\t\t)
\t\t(layer "F.SilkS")
\t\t(uuid "46f14aab-10d6-46bc-b8be-1597dbef5fd7")
\t)
""",
        """\t(fp_line
\t\t(start 2.11 -3.41)
\t\t(end 3.19 -3.41)
\t\t(stroke
\t\t\t(width 0.12)
\t\t\t(type solid)
\t\t)
\t\t(layer "F.Fab")
\t\t(uuid "46f14aab-10d6-46bc-b8be-1597dbef5fd7")
\t)
""",
    ),
    (
        """\t(fp_line
\t\t(start 3.91 1.74)
\t\t(end 3.91 -1.49)
\t\t(stroke
\t\t\t(width 0.12)
\t\t\t(type solid)
\t\t)
\t\t(layer "F.SilkS")
\t\t(uuid "d16a88b2-779f-4a1a-86d0-4a2b3e858606")
\t)
""",
        """\t(fp_line
\t\t(start 3.91 1.74)
\t\t(end 3.91 -1.49)
\t\t(stroke
\t\t\t(width 0.12)
\t\t\t(type solid)
\t\t)
\t\t(layer "F.Fab")
\t\t(uuid "d16a88b2-779f-4a1a-86d0-4a2b3e858606")
\t)
""",
    ),
)


def build_repo_usb_footprint_text() -> str:
    text = SYSTEM_USB_FOOTPRINT_PATH.read_text()
    for old, new in LAYER_NORMALIZATIONS:
        if old not in text:
            raise RuntimeError("Expected USB footprint block not found during normalization")
        text = text.replace(old, new, 1)
    return text


def ensure_repo_usb_footprint() -> Path:
    text = build_repo_usb_footprint_text()
    LOCAL_FOOTPRINT_DIR.mkdir(parents=True, exist_ok=True)
    if not LOCAL_USB_FOOTPRINT_PATH.exists() or LOCAL_USB_FOOTPRINT_PATH.read_text() != text:
        LOCAL_USB_FOOTPRINT_PATH.write_text(text)
    return LOCAL_USB_FOOTPRINT_PATH


def main() -> int:
    print(ensure_repo_usb_footprint())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
