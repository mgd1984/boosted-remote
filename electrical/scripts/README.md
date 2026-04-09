# Electrical Scripts

This folder keeps only the active live-board utilities at the top level.

Older one-off routing or migration helpers were moved to
`history/electrical/scripts/`.

## Primary Utilities

- `route_packets.py`
  - Main scripted routing helper for the current live board.
- `configure_netclasses.py`
  - Applies the project netclass layout.
- `export_kicad_to_blender.py`
  - Regenerates PCB review assets for Blender.
- `import_kicad_blender_scene.py`
  - Blender-side importer used by the export script.
- `sync_board_outline_from_user1.py`
  - Syncs board outline from the user contour source.
- `sync_esp32_antenna_keepout.py`
  - Normalizes the ESP32 antenna keepout.
- `sync_usb_footprint.py`
  - Re-syncs the generated USB footprint onto the live board.

## Specialized Routing Helpers

- `autoroute_iterate.py`
  - Runs the KiCad DSN -> Freerouting -> SES -> DRC loop and only promotes an
    iteration when it improves opens without introducing blocker DRC categories.

## Baseline Generation

- `generate_kicad_remote.py`
  - Original project generator. Useful for reconstructing the baseline, but the
    live board is now manually maintained.
- `build_usb_mini_footprint.py`
  - Creates the local USB footprint variant used by the project.

Historical routing helpers now live under `history/electrical/scripts/`.