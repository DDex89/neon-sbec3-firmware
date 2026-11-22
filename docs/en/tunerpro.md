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
| Fuel | `PartThrottleFuel`, `WotFuel` (shown as % change of the MAP-based pulse width), MAP scales, `InjectorDeadTime`, `BaroFuel`, `ReturnlessFuelScale`, fuel K and MAP offset constants |
| Spark | `PartThrottleSpark`, `WotSpark` (degrees), coolant corrections, `KnockThreshold` |
| Idle | `IdleTargetRpm` |
| Sensors | thermistor curves, throttle limp-in |
| Limits | `RevLimit`, `RevLimitAlt`, speed limiter |
| Faults | `FaultTable`: one row per fault, P-code in the row label |
| Unidentified | every other table, grouped by the routine that reads it when that routine has a name |

The named set depends on the family (see [porting.md](porting.md)): 17 tables in families D, E and
F, 13 in G, 11 in A, B and C. All tables are present in every XDF; the unnamed ones carry their
address and inputs in the description, and get units from their inputs where those are known (rpm,
deg C, kPa, volts).

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
