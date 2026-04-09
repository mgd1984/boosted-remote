from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from mechanical.cad.enclosure import build_enclosure
from mechanical.cad.exporters import export_shape_set
from mechanical.cad.params import load_project_data
from mechanical.cad.validate import validate_project_data


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate the Boosted remote enclosure with build123d.")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=REPO_ROOT / "outputs" / "build123d",
        help="Directory for generated STEP/STL/GLB files.",
    )
    parser.add_argument(
        "--formats",
        nargs="+",
        default=("step", "stl"),
        choices=("step", "stl", "glb"),
        help="Export formats to generate.",
    )
    parser.add_argument("--validate-only", action="store_true", help="Check inputs and skip CAD generation.")
    parser.add_argument("--force", action="store_true", help="Generate even if validation reports errors.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project = load_project_data(args.repo_root)
    issues = validate_project_data(project)

    for issue in issues:
        print(f"[{issue.level}] {issue.message}")

    has_errors = any(issue.level == "error" for issue in issues)
    if args.validate_only:
        return 1 if has_errors else 0
    if has_errors and not args.force:
        print("Refusing to generate geometry while validation errors are present. Use --force to override.")
        return 1

    artifacts = build_enclosure(project)
    written = export_shape_set(artifacts, args.out_dir, tuple(args.formats))
    print("Generated files:")
    for path in written:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())