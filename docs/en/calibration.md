# Calibration

How the calibration of the reference image **05293190AC** is organised: where it lies, the table
formats and the lookup routines that read them, the units, and how the fuel pulse width is built.
The full list of tables is in the generated catalogue
[docs/catalogue/05293190AC.md](../catalogue/05293190AC.md); in the source every table is laid out as
a commented block (header, axis, one line per row).

## Where the calibration lies

The calibration is in bank 0, between the header at $00202 and the start of the code at $08000. The
reset code sets EK = 0, so the code reads it with plain extended addresses (`CMPA $19DC`). Nothing
in the code writes there: the area is read-only.

The code refers to it in two ways:

- **Tables**, passed in X to one of four lookup routines (`LDX #table`, `JSR Lookup2D`). The lookup
  routines force XK = 0, so every table is in bank 0. 411 tables are found this way, between $0398
  and $ABD7 (two small ones lie among the bank 0 code).
- **Constants**, read directly: 1,455 different addresses, mostly with `CMPA`/`CMPB` (thresholds),
  `LDAA`/`LDAB` and `LDD`/`CPD` (16-bit values). Configuration bits around $0328-$0338 are tested
  with `BRSET`/`BRCLR`. Only the constants confirmed so far are named.

## Table formats

All values are bytes. The formats follow from the lookup routines:

| Format | Routine | Layout | 2GNT type |
|---|---|---|---|
| 2D | `Lookup2D` ($0C08E) | n, flags, then n pairs (x, y), x ascending | C |
| 2D (y, x) | `Lookup2DRev` ($0C36A) | n, unused, then n pairs (y, x) | |
| 3D | `Lookup3D` ($0C214) | rows, columns, signed flag, column axis (one byte per column), values row by row | A |
| 3D, no axis | `Lookup3DNorm` ($0C28C) | rows, columns, signed flag, values row by row | B |

Fault table: see below (2GNT type D).

**2D.** The input is compared with the x values; between two points the result is interpolated
linearly, outside the range it is the first or last y. The flags byte selects the arithmetic: $80
unsigned (320 of the 353 tables), $20 signed y, $10 steps without interpolation, $40 a zero y counts
as 256. Many 2D tables are followed by unused bytes up to a 12-byte slot (five points); whether a
table may be lengthened into that space has to be checked per table.

**3D.** The row input is a *position* 0-255 spread evenly over the rows (row = position x (rows-1)
/ 256). It usually comes from a 2D scale table that converts MAP into that position: the part-throttle
tables use `PartThrottleMapScale`, the WOT tables `WotMapScale`. The column input is searched on the
stored column axis (`Lookup3D`) or is also a position 0-255 (`Lookup3DNorm`). The result is
interpolated in both directions. Sizes in this image: 17 x 17, 9 x 17, 9 x 9, 5 x 9 and 5 x 5.

The signed flag ($FF) makes the values two's complement; the source shows them as negative decimals.

## Units

The unit names in `annotations/tables.json` and in the source comments:

| Unit | Conversion |
|---|---|
| rpm32 | rpm = x * 32 |
| rpm8 | rpm = x * 8 |
| kpa | kPa = x / 2.428 (2GNT: torr = x / 0.3237) |
| spark | degrees BTDC = x / 2 |
| tempc | deg C = x - 128 (deg F = (x - 128) * 1.8 + 32) |
| volt16 | volts = x / 16.19 |
| volt51 | volts = x / 51 |
| pwus32 | microseconds = x * 32 |
| mult256 | factor = x / 256 |
| pos256 | position 0-255 over the rows of a 3D table |
| fuelcorr | fuel factor = 1 + x / 256, x signed: -128 gives 0.5, +127 gives 1.496 |

These are the same as in the 1995 FCC controller and as on the 2GNT pages.

## Known tables and constants

| Address | Name | Content |
|---|---|---|
| $08F8 | PartThrottleMapScale | MAP to row position, part throttle (spark and fuel) |
| $0904 | WotMapScale | MAP to row position, WOT (spark and fuel) |
| $1BFA | PartThrottleSpark | 17 x 17, rpm x MAP, spark |
| $1FAF | WotSpark | 9 x 17, signed |
| $0BF6 | PartThrottleFuel | 17 x 17, signed, fuel correction |
| $0F6C | WotFuel | 9 x 17, signed, fuel correction |
| $0B92, $0B93 | PartThrottleFuelK, PartThrottleFuelMapOffset | base pulse width constants, part throttle |
| $0B94, $0B95 | WotFuelK, WotFuelMapOffset | the same for WOT |
| $0B76 | InjectorDeadTime | battery voltage to dead time |
| $0B9E | ReturnlessFuelScale | fuel multiplier of the returnless fuel system |
| $24AB | KnockThreshold | knock sensor threshold against rpm |
| $2684 | IdleTargetRpm | target idle speed against coolant temperature |
| $19DC, $19DE | RevLimit, RevLimitAlt | two rev limits (6,048 and 7,008 rpm), chosen by $0C31,Z bit 5 |
| $19E1, $19E3 | SpeedLimit, SpeedLimitMinRpm | speed limiter, enabled by calibration bit $0337.5 |
| $4052 | FaultTable | 256 fault rows |

All of these were checked against the code: each is read where 2GNT says, with the format above. One
correction: 2GNT shows the rev limit as two cells starting at $19DB (resume and limit), but $19DB
holds $FF and is never read; the code compares rpm with $19DC or with $19DE.
The 2GNT page calls the fuel tables "msec"; the code shows that they are corrections applied to a
pulse width computed from MAP (next section).

## Table names

Every table of the reference image has a name. 142 are named by hand from the code (and checked
against 2GNT where it has them), among them the whole fuel path described below, the spark
corrections, dwell, idle targets and the sensor curves. The other 268 have **structural names** made by `tools/autoname.py` and marked `"auto": true` in
`annotations/tables.json` (and with * in the catalogue):

- the prefix is the subsystem, taken from the routine that reads the table and the scheduled routine
  above it;
- then the inputs: `Coolant`, `AirTemp`, `Rpm`, `SegRpm`, `Map`, `Baro`, `Vacuum`, `Throttle`,
  `Speed`, `Volts`, `StartCoolant`, `Time`, `IdleTarget`, `Trim`, `O2`; `V0A91` for a RAM variable
  without a name yet, `Cal` for a calibration constant, `Scaled` for the result of a scale table;
- a number when the same name repeats.

So `AccelFuelCoolant2` is the second acceleration-enrichment table read against coolant
temperature. The description of each table says which routine reads it, its inputs and where the
result goes. A structural name tells where a table belongs and what it depends on, not yet what it
does exactly.

| Prefix | Subsystem | Category | Tables |
|---|---|---|---|
| Fuel, FuelEvent | fuel calculation in the main loop and per reference event | Fuel | |
| FuelCut | fuel cut-off: rev and speed limits, deceleration | Fuel | |
| AccelFuel | acceleration enrichment (throttle and MAP rate) | Fuel | |
| AfterStartFuel | after-start enrichment (time since start x coolant) | Fuel | |
| CrankFuel | cranking fuel | Fuel | 102 in all |
| O2 | oxygen-sensor closed loop and adaptive fuel | Closed loop | 7 |
| Idle | idle speed control | Idle | 89 |
| Spark, Knock | spark advance and knock control | Spark | 89 |
| Misfire, Diag | misfire monitor (crankshaft segment times) and other OBD monitors | Diagnostics | 36 |
| Sensor | sensor processing | Sensors | 21 |
| SpeedCtl | speed control (cruise); probable | Speed control | 11 |
| Start | initialisation at reset | Startup | 6 |
| Event, Pit, Sys<address> | not identified yet; named after the top routine | Other | 49 |

The subsystems were identified from the code: for example the idle group writes and uses the idle
target ($0300,Z, from `IdleTargetRpm`), the misfire group keeps the per-cylinder segment times, the
knock group reads `KnockThreshold`, the closed-loop group owns the short-term trims. Speed control is
inferred from its state machine on vehicle speed and rpm and is marked probable.

Re-running `python3 tools/autoname.py` after naming more RAM variables or routines refreshes the
structural names; hand names (entries without `"auto"`, and the overrides in the script) stay.

## Fuel pulse width

`CalcFuelPulse` ($11F40) runs from the input-capture 1 interrupt, that is on every reference
event:

1. Part throttle or WOT is chosen by `$0771,Z` bit 5; this selects the constants, the scale table
   and the fuel table.
2. Base pulse width = (Map - MapOffset) x (256 + K) / 16, or zero if MAP is below the offset. With
   calibration bit $0337.2 set, MAP is first raised to the lowest point of the part-throttle scale.
3. The fuel table gives a signed value v (rows by MAP through the scale table, columns by
   `EngineRpm`, whose high byte is rpm / 32); the base is multiplied by 1 + v / 256.
4. `$080E,Z` is added and the result is stored in `FuelPulse` ($07E2,Z) and `$04F6,Z`.

So the fuel tables work like a volumetric-efficiency correction on a linear MAP model, with the
two constants setting the slope and the zero point. Dead time, temperature and other corrections
are applied elsewhere (stage 5).

`InjectorDeadTime` is looked up with `$0A51,Z` as input. 2GNT lists a fix that changes this to
`$0A50,Z` (`BatteryVolts`); who writes $0A51 has not been checked yet.

## Fuel corrections

Besides the base pulse, the code builds these corrections (names as in the source):

| Part | Routine | Tables | Result |
|---|---|---|---|
| Warm-up enrichment | `Sub_10D5E` | `WarmupMapCoolant` (MAP x coolant), `WarmupMapCoolantLowSpeed` (below a vehicle speed), `WarmupRpmCoolantIdle` (throttle closed), `WarmupCoolantAdder` (WOT), factors for baro, run time and rpm | `WarmupFuelFactor` ($07E4,Z) |
| After-start decay | `Sub_10D5E` | `AfterStartTimeScale`, `AfterStartDecay` (time since start x cranking coolant) | part of the warm-up factor |
| Cold-soak | `Sub_10D5E` | `ColdSoakMapCoolant`, used when the coolant at start is close to $0A5E,Z | `$07E7,Z` |
| Cranking | `Sub_123C0` | `CrankBasePulse` (ethanol x cranking coolant), reductions against rpm, $0769,Z and baro, each weighted by coolant; `CrankVacuumFactor` | `CrankPulse` ($0766,Z) |
| Throttle tip-in | `Sub_107EA` | `TipInMatrix` (9 x 9, rows by throttle opening, columns by throttle step), coolant, air temperature and baro factors | `TipInFuel` ($07C6,Z) |
| MAP-rate and throttle-rate enrichment | `Sub_106EC` | `AccelMapGainCoolant`, `AccelTpsRateLimit`, `AccelTpsCoolantFactor`, baro terms, `AccelRpmFactor` | `AccelMapGain`, `AccelTpsFuel`, `AccelFactor` |
| Deceleration enleanment | `Sub_12142` | `DecelLeanAirflow` (rpm x throttle), coolant, time, rpm, MAP and baro factors | `DecelLeanFuel` ($07C2,Z) |
| Deceleration fuel cut-off | `Sub_10036` | `DecelCutMapThreshold`, `DecelCutDelay`, minimum rpm against coolant; rev and speed limits | `$0770,Z` flags, `DecelCutRpmFactor` |
| Deceleration fuel reduction | `Sub_104AE` | `DecelMapRpmLimit` (MAP x rpm) | `DecelFuelFactor` ($077A,Z) |
| WOT enrichment over time | `Sub_102FE` | `WotTimeEnrichMax` | `WotTimeEnrich` ($07AA,Z) |
| Idle enrichment | `Sub_11074` | run time, ethanol x start air temperature, engine-off time | `IdleEnrichFactor` ($07DA,Z) |
| Hot-engine enrichment | `Sub_111E0` | `HotEngineEnrich` | `$0811,Z` |
| Air temperature | `Sub_10AEC` | `FuelAirTempCorr` with rpm and MAP weights | multiplies the fuel |
| MAP and throttle filters | `Sub_1204A` | filter coefficients for rising and falling MAP and throttle against start coolant | `MapFilterCoef`, `TpsFilterCoef` |

**Flex fuel.** The program supports flexible-fuel vehicles: `Sub_2C7FE` watches the fuel level
(`FuelLevel`, $0A8E,Z) for a refill and the flex-fuel learning code (`FlexLearn...`, around
`Sub_17000`) learns the ethanol content from the oxygen-sensor trims (`FlexEthanolLearned` $0197,Z,
0-170, and `FlexEthanol` $0198,Z). The ethanol content then selects rows in the `Flex...` fuel and
spark tables and in the cranking table. Calibration bit $032C.6 enables it; in 05293190AC (a
gasoline car) the flex tables are neutral.

## Fault table

`FaultTable` ($4052) has 256 rows of 10 bytes:

| Byte | Content |
|---|---|
| 0 | row number |
| 1 | trigger count |
| 2 | blink code (BCD, as flashed by the check-engine lamp) |
| 3 | attribute bits |
| 4, 5 | mask and byte offset of the fault bit in the fault bit array |
| 6, 7 | P-code (BCD): $03 $40 = P0340 |
| 8, 9 | unused (zero) |

83 rows carry a P-code; the list is in the catalogue. Codes for cylinders 5 and 6 (P0205, P0206,
P0355) are present, so the program also covers six-cylinder engines.

## Tools

```sh
python3 tools/caltables.py roms/05293190AC.bin        # list the tables found
python3 tools/catalogue.py roms/05293190AC.bin docs/catalogue/05293190AC.md
```

`tools/caltables.py` finds the lookup routines by the bytes of their code, so it also works on the
other 256 KB images: 397 tables in 05269833AH, 404 in 05269833AI and 05269834AJ, 462 in
05032017AA. The 128 KB families use different
lookup code and are a stage 5 topic. Names and units come from `annotations/tables.json`, which
applies only to the reference image.

## Open points

- 268 tables have structural names only; giving them exact names means reading each routine.
- The 1,455 directly read constants are not catalogued one by one yet.
- The seven lookups whose table address comes from a pointer, not from `LDX #` (for example at
  $146E4 and $1974A), are not followed yet.
