# Reverse-Engineering Notes

## What the sources support

The public source material is enough to establish the broad architecture of the later Boosted remote:

- The production remote uses a thumbwheel-driven control scheme and a compact hand-held enclosure.
- The community reverse-engineering work documents BLE-based communication and pairing behavior for the later remote family.
- Third-party replacement PCBAs exist that are intended to fit the original enclosure, which strongly suggests the packaging is simple enough to reproduce with a single custom board and a split shell.

## What is inferred here

The exact original board stack, component values, and enclosure dimensions are not fully public, so this repo makes explicit engineering assumptions:

- Enclosure style: Boosted-inspired later-generation remote, not the older trigger-only remote
- Exterior size: approximately 136 mm tall, 54 mm max width, 20 mm thick
- Shell construction: front and rear printed halves with screw bosses and a single internal PCB
- Battery: 1S LiPo in the 400 mAh to 600 mAh range
- Charging: mini-USB retained for exterior fidelity
- Logic/radio: ESP32-C3 module used as a practical BLE-capable stand-in
- Throttle sensing: linear hall sensor aligned to a thumbwheel magnet
- Safety input: rear deadman switch
- Indicators: five battery LEDs plus two status LEDs

## Why the hardware is modernized

Several original parts are either unknown, inconvenient to source, or tightly coupled to proprietary firmware. The design therefore substitutes accessible parts while preserving the same functional block diagram:

- `ESP32-C3-WROOM-02` replaces the unknown original radio/MCU
- `MCP73831-2-OT` provides simple 1S charging
- `TLV75533PDBV` provides clean 3.3 V regulation from the LiPo rail
- `DRV5055A3xDBZxQ1` provides a 3.3 V linear hall sensor suitable for wheel position sensing

## Mechanical intent

The enclosure is intentionally parametric and script-generated:

- the same parameter file drives the shell proportions and PCB cavity assumptions
- the thumbwheel pocket and hall sensor location are aligned by design
- the PCB outline is narrower than the outer shell so the printed enclosure can absorb final fit tweaks

## Internal layout target

An internal reference photo now anchors the first-order packaging assumptions:

- thumbwheel mechanism occupies the upper head volume, with the hall sensor placed just below and to the right of the wheel axis
- BLE/radio module sits in the upper-left third of the main PCB
- buzzer sits near the middle of the grip section
- LiPo pouch cell occupies most of the lower half of the enclosure
- mini-USB sits on the tail centerline

The current KiCad placement and Blender reference bodies are tuned toward that arrangement rather than a generic handheld remote.

## Validation standard for this pass

This first pass is considered successful if:

- the Blender enclosure opens cleanly and shows the intended shell split and cutouts
- the KiCad schematic opens without format errors
- the KiCad PCB opens, shows the expected footprint population, and passes a first DRC pass or at least reports a bounded set of remaining issues

Anything beyond that should be treated as prototype iteration work, not historical certainty.
