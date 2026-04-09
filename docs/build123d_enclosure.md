# Build123d Enclosure Pipeline

This repo now has a code-first mechanical path in addition to the existing Blender generator.

## Source Of Truth

- `config/remote_params.json` remains the primary parameter contract.
- `electrical/scripts/generate_kicad_remote.py` remains the fallback board-outline source when the live board does not already define `Edge.Cuts`.
- `mechanical/cad/` contains the build123d-driven enclosure model, validation, and export logic.

## What This Generates

- front shell
- rear shell
- full shell
- a simplified PCB/component envelope for visual clearance checks

## Quick Start

Install the CAD dependency:

```bash
python -m pip install -r requirements-mechanical.txt
```

Validate the current parameter set without generating solids:

```bash
python mechanical/scripts/build_enclosure.py --validate-only
```

Refresh the exterior profile stations from the proxy reconstruction GLB:

```bash
/Applications/Blender.app/Contents/MacOS/Blender --background --python mechanical/scripts/analyze_proxy_glb.py -- --repo-root "$PWD" --glb "$PWD/history/mechanical/proxy/TewTCTh6nBM-A_J6JKsw__trellis2_0d811f951772406a86d5d8f20232885d.glb" --out "$PWD/outputs/tmp/proxy_sections.json" --slice-step-mm 8.0
```

Generate the first-pass build123d enclosure outputs:

```bash
python mechanical/scripts/build_enclosure.py --formats step stl
```

Outputs are written to `outputs/build123d/` by default.

## Current Scope

This first pass is intentionally focused on:

- shell proportions and split-line
- proxy-driven exterior station fitting from the reconstructed GLB
- PCB cavity envelope
- thumbwheel, USB, LED, and button openings
- mounting bosses and counterbores
- parameter validation for early prototype iterations

It does not yet attempt a metrology-grade match to an original remote shell.