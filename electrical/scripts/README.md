# Electrical Scripts

This folder keeps only the active live-board utilities at the top level.

Older one-off routing or migration helpers were moved to
`history/electrical/scripts/`.

## Primary Utilities

- `configure_netclasses.py`
  - Applies the project netclass layout.
- `export_jlc_bom.py`
  - Exports a JLCPCB-formatted BOM CSV filtered to the same placed parts as the CPL.
- `export_jlc_cpl.py`
  - Exports a JLCPCB-formatted CPL/pick-and-place CSV from the live KiCad board.
- `export_kicad_to_blender.py`
  - Regenerates PCB review assets for Blender.
- `import_kicad_blender_scene.py`
  - Blender-side importer used by the export script.
- `sync_board_outline.py`
  - Syncs the board outline from a chosen source contour layer. Defaults to the
    current `User.1` workflow.
- `update_pcb_outline_target.py`
  - Rebuilds `mechanical/references/boosted_remote_pcb_outline_target.svg`
    from the cleaned front/back PCB reference PNGs, mirroring the rear image and
    only blending it where the lower body is not occluded.

## Preferred Routing Flow

- `autoroute_iterate.py`
  - Primary routing automation path. Runs the KiCad DSN -> Freerouting -> SES
    -> DRC loop against a chosen board/report pair and only promotes an
    iteration when blocker-category counts do not regress and either opens or
    blocker counts improve. Use `--sync-outline-source pcb-svg` when the pass
    must route against `mechanical/references/boosted_remote_pcb_outline_target.svg`
    rather than whatever outline is already stored in the board file.

## Board Maintenance Utilities

- `sync_esp32_antenna_keepout.py`
  - Board-specific keepout normalization for the ESP32 module footprint.
- `sync_usb_footprint.py`
  - Board-specific re-sync of the generated local USB footprint onto the live
    board.

## Deterministic Manual Routing

- `manual_route_packets.py`
  - Deterministic packetized copper edits retained for explicit experiments and
    documented escape patterns. Prefer `autoroute_iterate.py` for normal routing
    passes.
- `rework_outline_candidate_nwx.py`
  - Candidate-board hotspot prep and deterministic reroute helper. Use
    `--ripup-only` when you want to clear edge-conflicting corridors before
    handing the board to `autoroute_iterate.py`.

## Baseline Generation

- `generate_kicad_remote.py`
  - Original project generator. Useful for reconstructing the baseline, but the
    live board is now manually maintained.
- `build_usb_mini_footprint.py`
  - Creates the local USB footprint variant used by the project.

Historical routing helpers now live under `history/electrical/scripts/`.
