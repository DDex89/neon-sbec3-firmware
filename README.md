# neon-sbec3-firmware

Analysis of the Chrysler **SBEC3** engine controller firmware (Motorola 68HC16, 1996 and later),
with the goal of an annotated, rebuildable source and editor definitions (TunerPro XDF) for the
calibration. The main target is the 1996+ Dodge / Plymouth Neon; the 2G Mitsubishi Eclipse / Eagle
Talon with the 420A engine uses the same controller family and helps as a reference.

[Русская версия](README.ru.md)

Companion project: [neon-fcc-firmware](https://github.com/DDex89/neon-fcc-firmware), the fully
rebuilt and annotated firmware of the 1995 Neon controller (FCC, 68HC11). Much of the SBEC3 control
logic and the units of its values descend from it.

## Status

Stage 1 of 6: survey of the images.

| Stage | Content | |
|---|---|---|
| 1 | Survey: images, memory layout, checksum, families | done, see [docs/en/images.md](docs/en/images.md) |
| 2 | Tools: CPU16 disassembler, assembler, source generator, byte-identical build, CI | next |
| 3 | Program skeleton: reset, interrupts, main loop, scheduler, communication | |
| 4 | Calibration: table formats, finding and naming the tables | |
| 5 | Detailed annotation, documentation in English and Russian, porting to the other families | |
| 6 | Editor definitions: TunerPro XDF generated from the annotations | |

## Layout

```
docs/en, docs/ru        documentation
tools/survey.py         image survey (vectors, header block, checksum, build stamp)
roms/                   place for the flash images (not distributed, see roms/README.md)
third_party/            SBECBootLoader by Dino Yancey: reading and reflashing on the bench
```

## Reading and reflashing a controller

`third_party/SBECBootLoader` contains Dino Yancey's reflash kernels and scripts. They load a small
kernel through the SCI line in bootstrap mode (voltage on SCI RX at power-on) and can then read and
write the flash and the EEPROM. Programming needs 20 V on SCI RX. See its
[README](third_party/SBECBootLoader/README.md) for the wiring and the commands.

## Credits and legal

- Original firmware and calibrations: (c) 1995-1998 Chrysler Corporation.
- SBECBootLoader: Dino Yancey (dino2gnt), included with the author's permission.
- Table addresses and unit conventions were checked against the 2GNT calibration pages and table
  viewer (https://www.2gnt.com).

This is a non-commercial, educational and interoperability project for owners of these cars. The
project's own tools and documentation are released under the MIT license (see [LICENSE](LICENSE));
that license does not apply to the firmware content or to `third_party/`. See [NOTICE](NOTICE).
Rights holders who object can open an issue and the material will be removed.

Modifying engine controller firmware can damage an engine and may affect emissions compliance. Use
at your own risk.
