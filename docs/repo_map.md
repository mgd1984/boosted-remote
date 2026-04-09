# Repo Map

This repo is easier to navigate if you treat it as three layers: live sources,
active working files, and exploratory lineage.

## Live Sources

- `electrical/kicad/boosted_remote.kicad_pcb`
  - Current live board. This is the electrical source of truth.
- `electrical/kicad/boosted_remote.kicad_sch`
  - Current live schematic.
- `electrical/kicad/boosted_remote.kicad_pro`
  - Current KiCad project file.
- `electrical/kicad/boosted_remote.pretty/`
  - Custom footprint library used by the live board.
- `mechanical/cad/`
  - Current code-first enclosure model and validation logic.
- `mechanical/references/`
  - Supporting reference outlines consumed by the mechanical CAD package.
- `config/remote_params.json`
  - Shared geometry and packaging parameter contract.

## Active Working Areas

- `outputs/blender/boosted_remote_enclosure.blend`
  - Current enclosure output scene.
- `outputs/blender/boosted_remote_pcb_all_layers.blend`
  - Current PCB visualization / fit-check output scene.
- `mechanical/scripts/build_enclosure.py`
  - Main entry point for build123d enclosure generation.
- `electrical/scripts/export_kicad_to_blender.py`
  - Refresh the PCB review blend from the live KiCad board.
- `electrical/scripts/route_packets.py`
  - Main scripted routing helper for the live board.
- `electrical/scripts/configure_netclasses.py`
  - Applies netclass structure to the live project.
- `electrical/scripts/autoroute_iterate.py`
  - Specialized DSN -> Freerouting -> SES loop for automated routing passes.
- `mechanical/scripts/analyze_proxy_glb.py`
  - Samples proxy sections for the current enclosure workflow.

## Exploratory / Reference Areas

- `history/electrical/scripts/`
  - Older electrical routing and migration helpers retained for reference.
- `history/mechanical/`
  - Non-canonical geometry studies, displaced Blender scenes, and older mechanical scripts.
- `history/utilities/`
  - Historical support scripts and geometry probes.
- `outputs/renders/`
  - Output visuals, not a source directory.
- `outputs/tmp/`
  - Disposable generated intermediate data.

## Electrical Script Tiers

### Use most often

- `electrical/scripts/route_packets.py`
- `electrical/scripts/configure_netclasses.py`
- `electrical/scripts/export_kicad_to_blender.py`
- `electrical/scripts/sync_board_outline_from_user1.py`
- `electrical/scripts/sync_esp32_antenna_keepout.py`
- `electrical/scripts/sync_usb_footprint.py`

### Specialized live-board helpers

- `electrical/scripts/autoroute_iterate.py`
  - Use this when you want the DSN -> Freerouting -> SES iteration loop instead
    of manual packet routing.

### Baseline generators / setup

- `electrical/scripts/generate_kicad_remote.py`
- `electrical/scripts/build_usb_mini_footprint.py`

### Older packet experiments and migration helpers

- `history/electrical/scripts/manual_finish_route.py`
- `history/electrical/scripts/manual_route_signals.py`
- `history/electrical/scripts/rework_negative_bottom_cluster.py`
- `history/electrical/scripts/rework_to_two_layer.py`
- `history/electrical/scripts/rewrite_negative_bottom_cluster.py`

If a task touches the live board, start in `electrical/kicad/` and only reach for
the older helpers when a doc explicitly points to them.