# TunerPro definitions

`xdf/<part number>.xdf` is a TunerPro definition for each of the eleven images, generated from
the annotations by `tools/xdf.py`. Open the matching `.bin` in TunerPro and select the XDF of the
same part number: addresses differ between families, and the row labels are computed from that
image.

**Status: generated, not yet tried in TunerPro.** The files are well-formed XML (checked by CI) and
follow the XDF 1.60 layout that other generators use, but the layout of the 2D tables (interleaved
x/y pairs, read with a 16-bit stride) and the category numbering have not been checked in the
program yet. Please report what does not open or shows wrong values.

## What is in it

| Category | Content |
|---|---|
| Fuel | main and WOT fuel tables (as % change of the MAP-based pulse width), MAP scales, dead time, baro and air-temperature corrections, acceleration, after-start and cranking enrichment, fuel cut-off |
| Spark | main and WOT spark (degrees), corrections, knock control |
| Idle | idle speed control, including `IdleTargetRpm` |
| Closed loop | oxygen-sensor feedback |
| Sensors | thermistor curves, throttle limp-in, sensor processing |
| Diagnostics | misfire monitor and other OBD monitors |
| Speed control | cruise control (probable) |
| Startup | values set at reset |
| Limits | rev and speed limits |
| Faults | `FaultTable`: one row per fault, P-code in the row label |
| Other | tables of subsystems not identified yet |

In the reference image every table has a name: 142 exact ones and 268 structural ones (subsystem +
inputs, see [calibration.md](calibration.md#table-names)); the description of each says which routine
reads it, its inputs and where the result goes. The other images get the names that the port can
carry over (from 131 tables in family A to 403 in family E); the rest keep their generated `Tab...`
name. Units come from the annotations or from the inputs where those are known (rpm, deg C, kPa,
volts).

## Axes

- 3D tables with a stored column axis: the axis is read from the image and editable (usually rpm).
- Rows of 3D tables are not stored: the row comes from a MAP scale table (`PartThrottleMapScale`,
  `WotMapScale`). The XDF labels each row with the MAP value that selects it, computed from the scale
  table **at generation time**. If you change a scale table, the row labels stay old until the XDF is
  generated again (`python3 tools/xdf.py roms/<PN>.bin xdf/<PN>.xdf`).
- 3D tables without a stored axis show positions 0-255.
- 2D tables: the x values are an editable axis, the y values the data column.

## Units

As in [calibration.md](calibration.md): rpm = x * 32, kPa = x / 2.428, spark = x / 2 degrees,
deg C = x - 128, volts = x / 16.19 (battery) or x / 51 (knock), dead time in microseconds = x * 32.
Fuel tables are shown as the percentage change they apply, (x / 256) * 100, signed.

## Checksum

TunerPro does not correct the SBEC3 checksum. After saving an edited image run

```sh
python3 tools/fixsum.py edited.bin --fix
```

which sets the correction byte (header + 13) so that the 8-bit sum of the image equals the last byte
of the part number again. Without `--fix` it only checks.
