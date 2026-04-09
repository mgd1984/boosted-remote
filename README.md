# Boosted Remote Reverse-Engineering Starter

This repo contains a first-pass reverse-engineered hardware recreation of the Boosted Boards thumbwheel remote:

- a Blender-generated enclosure
- a KiCad schematic
- a KiCad PCB
- documented assumptions tying the mechanical and electrical work back to source material

This is not a firmware-complete clone. The hardware is designed to match the known control architecture and packaging constraints while using currently accessible parts and a reproducible scripted workflow.

## Source Anchors

- Boosted USA product page for the later thumbwheel remote exterior reference:
  - <https://boostedusa.com/products/boosted-remote>
- Beam Break BLE reverse-engineering notes confirming later remote BLE behavior and pairing model:
  - <https://beambreak.org/articles/remote_ble_ids/>
- XR General Hospital replacement PCBA product confirming that a retrofit board in the original enclosure is practical:
  - <https://www.xrgeneralhospital.com/beta/p/remote-controller-pcba>

## Generated Assets

- Active enclosure blend: `outputs/blender/boosted_remote_enclosure.blend`
- Active PCB review blend: `outputs/blender/boosted_remote_pcb_all_layers.blend`
- Build123d CAD package: `mechanical/cad/`
- Build123d generator CLI: `mechanical/scripts/build_enclosure.py`
- Proxy-section extractor: `mechanical/scripts/analyze_proxy_glb.py`
- KiCad project: `electrical/kicad/boosted_remote.kicad_pro`
- Live board and schematic: `electrical/kicad/boosted_remote.kicad_pcb`, `electrical/kicad/boosted_remote.kicad_sch`
- Routing packet script: `electrical/scripts/route_packets.py`
- Netclass configurator: `electrical/scripts/configure_netclasses.py`
- Blender export path: `electrical/scripts/export_kicad_to_blender.py`
- Shared parameters: `config/remote_params.json`
- Reverse-engineering notes: `docs/reverse_engineering_notes.md`
- Build123d pipeline notes: `docs/build123d_enclosure.md`
- Repo navigation map: `docs/repo_map.md`

## Where To Work Now

- Mechanical source of truth: `mechanical/cad/`
- Generated Blender outputs: `outputs/blender/`
- Mechanical build entry point: `mechanical/scripts/build_enclosure.py`
- Shared parameter contract: `config/remote_params.json`
- Active KiCad project: `electrical/kicad/boosted_remote.kicad_pro`
- Active board and schematic: `electrical/kicad/boosted_remote.kicad_pcb`, `electrical/kicad/boosted_remote.kicad_sch`
- Electrical utilities and routing helpers: `electrical/scripts/`
- Mechanical utilities: `mechanical/scripts/`
- Historical electrical scripts: `history/electrical/scripts/`
- Historical mechanical scripts and studies: `history/mechanical/`
- Historical utilities: `history/utilities/`

## Repo Shape

- `electrical/kicad/`: live KiCad project only
- `electrical/scripts/`: active live-board utilities only
- `mechanical/cad/`: code-first enclosure source of truth
- `mechanical/scripts/`: active enclosure utilities only
- `mechanical/references/`: supporting 2D outline reference assets used by the CAD pipeline
- `outputs/`: generated Blender scenes, renders, and scratch outputs
- `history/electrical/`: older routing and migration helpers
- `history/mechanical/`: non-canonical lineage, experiments, displaced scenes, and older scripts
- `history/utilities/`: historical support scripts and geometry probes
- `config/`: shared project configuration and parameter contracts
- `docs/`: workflow notes plus `docs/repo_map.md` for a quick navigation guide

## Current Scope

- Boosted-style ergonomic shell with split enclosure
- thumbwheel opening and internal hall sensor location
- mini-USB charge-port cutout for external visual fidelity
- 1S LiPo power, charger, LDO, BLE MCU, LEDs, buzzer, deadman trigger, programming header
- first-pass PCB shaped to the enclosure cavity
- first-pass build123d enclosure generation for STEP/STL prototype outputs

## Verification Status

- Schematic ERC is down to warnings only on the generated custom-library setup.
- The promoted live PCB checkpoint is:
  - `electrical/kicad/boosted_remote.kicad_pcb`
  - 3 DRC warnings, all silkscreen-only
  - 25 unconnected items remaining
- The live board now includes validated packetized routing improvements over the original generator baseline.
  - Clean promoted packets so far: upper `SW1 -> U4` ground stitch and `PWR_BTN` escape/routing packet
- Experimental routing passes are only promoted when they reduce the open count without introducing blocker DRC categories.

## Known Gaps

- No firmware is included
- Dimensions are inferred and should be validated against a physical remote before fabrication
- The BLE protocol implementation required to pair with an original board is outside this repo
- The trigger and thumbwheel mechanism are mechanically approximated, not metrology-matched
