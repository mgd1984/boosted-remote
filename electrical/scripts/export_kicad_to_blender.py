from __future__ import annotations

import argparse
import subprocess
import shutil
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BOARD = REPO_ROOT / "electrical" / "kicad" / "boosted_remote.kicad_pcb"
DEFAULT_OUT_DIR = REPO_ROOT / "outputs" / "blender"
DEFAULT_PREFIX = "boosted_remote_pcb"
DEFAULT_SHELL_GLB = REPO_ROOT / "outputs" / "build123d" / "boosted_remote_full_shell.glb"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export the KiCad board and all plot layers into Blender assets.")
    parser.add_argument("--board", type=Path, default=DEFAULT_BOARD)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--prefix", default=DEFAULT_PREFIX)
    parser.add_argument("--blender", default="blender")
    parser.add_argument("--with-shell", dest="with_shell", action="store_true", default=True)
    parser.add_argument("--without-shell", dest="with_shell", action="store_false")
    return parser.parse_args()


def read_board_layers(board_path: Path) -> list[str]:
    layers: list[str] = []
    in_layers = False
    for raw_line in board_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line == "(layers":
            in_layers = True
            continue
        if not in_layers:
            continue
        if line == ")":
            break
        if not line.startswith("("):
            continue
        parts = line.split('"')
        if len(parts) >= 2:
            layers.append(parts[1])
    return layers


def run(command: list[str]) -> None:
    print("+", " ".join(str(part) for part in command), flush=True)
    subprocess.run(command, check=True)


def resolve_blender(executable: str) -> str:
    candidate = shutil.which(executable)
    if candidate:
        return candidate

    fallback_paths = [
        Path("/Applications/Blender.app/Contents/MacOS/Blender"),
        Path.home() / "Applications" / "Blender.app" / "Contents" / "MacOS" / "Blender",
    ]
    for fallback in fallback_paths:
        if fallback.exists():
            return str(fallback)

    raise FileNotFoundError(f"Unable to find Blender executable: {executable}")


def main() -> None:
    args = parse_args()
    board_path = args.board.resolve()
    out_dir = args.out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    prefix = args.prefix
    board_glb = out_dir / f"{prefix}.glb"
    board_step = out_dir / f"{prefix}.step"
    board_vrml = out_dir / f"{prefix}.wrl"
    layer_dir = out_dir / f"{prefix}_layers"
    blend_path = out_dir / f"{prefix}_all_layers.blend"
    shell_glb = DEFAULT_SHELL_GLB if args.with_shell else None

    layer_dir.mkdir(parents=True, exist_ok=True)
    layers = read_board_layers(board_path)
    layer_list = ",".join(layers)
    blender_executable = resolve_blender(args.blender)

    run(
        [
            "kicad-cli",
            "pcb",
            "export",
            "glb",
            "--force",
            "--output",
            str(board_glb),
            "--include-tracks",
            "--include-pads",
            "--include-zones",
            "--include-silkscreen",
            "--include-soldermask",
            str(board_path),
        ]
    )
    run(
        [
            "kicad-cli",
            "pcb",
            "export",
            "step",
            "--force",
            "--output",
            str(board_step),
            "--include-tracks",
            "--include-pads",
            "--include-zones",
            "--include-silkscreen",
            "--include-soldermask",
            str(board_path),
        ]
    )
    run(
        [
            "kicad-cli",
            "pcb",
            "export",
            "vrml",
            "--force",
            "--output",
            str(board_vrml),
            str(board_path),
        ]
    )
    run(
        [
            "kicad-cli",
            "pcb",
            "export",
            "svg",
            "--mode-multi",
            "--output",
            str(layer_dir),
            "--layers",
            layer_list,
            "--page-size-mode",
            "2",
            "--exclude-drawing-sheet",
            "--fit-page-to-board",
            "--check-zones",
            str(board_path),
        ]
    )
    if args.with_shell:
        run(
            [
                sys.executable,
                str(REPO_ROOT / "mechanical" / "scripts" / "build_enclosure.py"),
                "--formats",
                "glb",
            ]
        )
    run(
        [
            blender_executable,
            "--background",
            "--python",
            str(REPO_ROOT / "electrical" / "scripts" / "import_kicad_blender_scene.py"),
            "--",
            "--board-glb",
            str(board_glb),
            "--layers-dir",
            str(layer_dir),
            "--blend-out",
            str(blend_path),
        ]
        + (["--shell-glb", str(shell_glb)] if shell_glb is not None else [])
    )

    print("Generated files:", flush=True)
    print(board_glb)
    print(board_step)
    print(board_vrml)
    print(layer_dir)
    if shell_glb is not None:
        print(shell_glb)
    print(blend_path)


if __name__ == "__main__":
    main()