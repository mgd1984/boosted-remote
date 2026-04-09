from __future__ import annotations

from pathlib import Path


def export_shape_set(artifacts, out_dir: Path, formats: tuple[str, ...]) -> list[Path]:
    from build123d import Unit, export_gltf, export_step, export_stl

    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    shape_map = {
        "front_shell": artifacts.front_shell,
        "rear_shell": artifacts.rear_shell,
        "full_shell": artifacts.full_shell,
        "pcb_envelope": artifacts.pcb_envelope,
    }
    for label, shape in shape_map.items():
        for fmt in formats:
            target = out_dir / f"boosted_remote_{label}.{fmt}"
            if fmt == "step":
                export_step(shape, target, unit=Unit.MM)
            elif fmt == "stl":
                export_stl(shape, target)
            elif fmt == "glb":
                export_gltf(shape, target, unit=Unit.MM, binary=True)
            else:
                raise ValueError(f"Unsupported export format: {fmt}")
            written.append(target)
    return written