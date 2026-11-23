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
- **Constants**, read directly: 1,448 different addresses, mostly with `CMPA`/`CMPB` (thresholds),
  `LDAA`/`LDAB` and `LDD`/`CPD` (16-bit values). Configuration bits at $0328-$0340 are tested
  with `BRSET`/`BRCLR`. See [constants and option bits](#constants-and-option-bits).

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

All 410 tables of the reference image are named by hand from the code (and checked against 2GNT
where it has them). The name says what the table does; the description in
`annotations/tables.json` (and in the catalogue and the XDF) says which routine reads it, its inputs
and where the result goes. Where the meaning of a RAM variable is still open, the name keeps its
address (`FlexLearnLimitV006B`), and readings that rest only on how the code uses a value say
"probably".

| Category | Tables | Main prefixes |
|---|---|---|
| Fuel | 115 | `Fuel`, `PartThrottleFuel`, `AccelFuel`, `AfterStartFuel`, `CrankFuel`, `FuelCut`, `Flex`, `FlexLearn` |
| Idle | 92 | `IdleTarget`, `Idle`, `Iac`, `IdleMap`, `ShiftIdle`, `ThrottleClose` |
| Spark | 78 | `Spark`, `Surge`, `TipInRetard`, `SpeedDamp`, `AcSpark`, `EgrSpark`, `Dwell` |
| Diagnostics | 36 | `Misfire`, `ExpectedMap`, `LimpRpm`, `FuelSys`, `Diag` |
| Sensors | 20 | sensor curves, `BattTemp`, `ChargeVolts`, `MapHigh`, `BaroUpdate` |
| EVAP purge | 15 | `Purge` (probable) |
| Knock | 11 | `Knock` |
| Speed control | 11 | `SpeedCtl` (probable) |
| EGR | 8 | `Egr` |
| Closed loop | 7 | `O2` |
| Cooling fan | 6 | `Fan` |
| A/C | 4 | `AcThrottle` |
| Other | 4 | `FieldRampFactor`, `RpmFilterAboveIdle`, `EventTimingLimit`, ... |
| Startup | 3 | `ResetCoolant` |

`tools/autoname.py` merges the hand names (`python3 tools/autoname.py hand.json`) and still gives a
**structural name** to any table found later without a hand name: the subsystem prefix (taken from
the routine that reads the table and the scheduled routine above it), then the inputs (`Coolant`,
`Rpm`, `Map`, `V0A91` for an unnamed RAM variable, ...) and a number when the name repeats. Such
entries are marked `"auto": true` and get a * in the catalogue.

## Idle and spark control

The idle air valve is driven by several routines that all end in the step routine `Sub_1A54A`:

| Routine | What it does | Tables |
|---|---|---|
| `Sub_1B182` | idle target ($0300,Z): coolant table (P/N variant), additions for an rpm dip in gear, hot intake air, and a ramped target against battery temperature and run time | `IdleTargetRpm*`, `IdleTargetDip*`, `IdleTargetHotAirAdder`, `IdleBattTemp*` |
| `Sub_1908C` | closed loop on rpm: error term (coarse/fine, P/N), rate filter, deadband from MAP and coolant, integrator that takes opening or closing IAC steps | `IdleErrorTerm*`, `IdleRateFilterCoolant`, `IdleDeadband*`, `IdleStep*` |
| `Sub_1AC64` | closed loop on MAP: idle MAP target ($031E,Z) from base, time, coolant, rpm and baro, then IAC steps against the MAP error | `IdleMap*`, `IacMap*Step*` |
| `Sub_1AFDE` | base IAC position against baro and idle target, coasting target, generator field duty, A/C engagement | `IacBase*`, `IacCoast*`, `IacFieldDuty*`, `IacAcEngageAdder` |
| `Sub_19808`, `Sub_2D086` | events: gear change (delay, duration, step; A/C and P/N variants), rpm droop and dip kicks, A/C clutch kick, rolling target | `IacGear*`, `IacDroop*`, `IacDipKick*`, `IacAcKick*`, `IacRoll*`, `ShiftIdle*` |
| `Sub_1A5CA` | extra air when the battery voltage stays below the charging target | `IacChargeStep` |
| `Sub_1AE22` | IAC position while cranking and in start mode | `IacCrankCoolant`, `IacRunUpCoolant` |

Spark corrections besides the base tables:

| Routine | What it does | Tables |
|---|---|---|
| `Sub_1DEDC`, `Sub_1E14E` | driveline surge: a staged retard from rpm acceleration and jerk (band-passed segment rpm), weighted by gear (rpm/speed ratio), MAP rise and coolant | `Surge*` |
| `Sub_1D5EC` | tip-in retard near idle against throttle rise and air temperature | `TipInRetard*` |
| `Sub_1DC20` | low-speed surge damping: P, D and I terms on the deviation of rpm from an expected rpm for the vehicle speed | `SpeedRpmRef*`, `SpeedDamp*` |
| `Sub_1E76A` | idle spark against the idle rpm error | `IdleSpark*` |
| `Sub_1D822`, `Sub_1D8F0` | spark compensation around A/C clutch engagement | `AcEngageSpark*`, `AcClutchSpark*`, `AcSpark*` |
| `Sub_1D36A` | spark change against the short-term fuel trim deviation | `O2SparkTrim*` |
| `Sub_1DA26` | addition with EGR active (17x17) | `EgrSpark` |
| `Sub_1E582` | coil dwell against battery voltage | `DwellBattery*` |

Knock control learns a noise level per rpm band (`KnockNoise*`), runs above a MAP threshold
(`KnockMapThreshold*`) and limits the retard by rpm and MAP (`KnockRetardMax*`, `KnockRetardLimit`).

Several of these readings rest on how the code uses a variable rather than on a document: the
battery temperature ($0A5A,Z, used for the charging target), the generator field duty ($032E,Z,
a duty count of CS2 input $106E bit 5) and the A/C sensor ($0A88,Z, probably A/C
pressure) are inferred this way.

## Constants and option bits

`tools/constants.py` finds every byte or word the code reads directly with extended addressing and
that is not part of a table: 1,448 of them in 05293190AC (1,263 bytes, 181 words, 4 longs), among
them 21 option bytes tested with `BRSET`/`BRCLR` (120 bits used). They are kept with the tables in
the `scalars` of `annotations/tables.json`, so the sources show `CMPA >IdleCoolantMin` instead of
`CMPA $2853`, the catalogue lists them with value and physical value, the XDF has them as constants
(and every option bit as a flag), and the port carries them to the other images (from 239 in family
A to 1,404 in family E).

For each constant the script looks at how it is used: what the register held before the compare,
add or subtract (`LDAA >CoolantTemp,Z` then `CMPA $2853`), or what a loaded value is compared with
or stored into. That gives the unit (temperature, rpm, kPa, volts) and a structural name: the
prefix of the tables of the same routine or the subsystem, the variable, and the role (`Thresh` for
a compare, `Adder`, `Offset`, `Factor`, `Init` for a value stored into RAM, `Value` otherwise),
numbered when repeated. 555 constants have hand names from the code read so far (idle, spark,
knock, EGR, fan, A/C, diagnostics, the fuel constants and limits); the rest keep the structural
name with * in the catalogue. Word rpm values use the unit `rpmw` (rpm = x / 8).

The option bytes at $0328-$0340 are global configuration. The bits identified so far, with their
state in 05293190AC:

| Byte | Bit | Name | Set |
|---|---|---|---|
| $032B | $20 | `SparkCalcHookOn` | 0 |
| $032B | $40 | `DwellBatteryOn` | 0 |
| $032C | $40 | `FlexFuelOn` | 0 |
| $032D | $20 | `AcClutchLogicOn` | 1 |
| $032E | $40 | `ManualTransmission` | 1 |
| $0330 | $01 | `BattTempModelOn` | 0 |
| $0330 | $04 | `BattTempCurveAlt` | 0 |
| $0330 | $20 | `TipInAirTempCheck` | 1 |
| $0331 | $80 | `AcPressureSensor` | 0 |
| $0335 | $04 | `EgrSparkScaled` | 0 |
| $0337 | $01 | `IdleDipKickMode` | 0 |
| $0337 | $10 | `SurgeSparkOn` | 1 |
| $0337 | $20 | `SpeedLimitOn` | 0 |
| $0337 | $40 | `SpeedDampOn` | 0 |
| $0337 | $80 | `EventSparkOn` | 0 |
| $0338 | $02 | `FieldControlAlt` | 0 |
| $0338 | $04 | `FuelEventOffsetAlt` | 0 |
| $0339 | $01 | `TipInRetardHold` | 0 |
| $0339 | $04 | `PurgeDutyAltClosed` | 0 |
| $0339 | $08 | `PurgeDutyAltOther` | 1 |
| $033A | $10 | `AcSparkOn` | 0 |
| $033D | $08 | `IacCoastOff` | 0 |

`ManualTransmission` set means the P/N switch is ignored (the idle and spark P/N variants are never
used), which fits the manual 05293190AC.

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

- Some table names rest only on how the code uses a value (battery temperature, generator field
  duty, the A/C sensor, $019C,Z as probably the fuel level; purge, EGR and speed control as
  subsystems), and several RAM variables are still named by address (`V0335`, `V006B`). Checking
  them on a running car would settle them.
- 893 constants have structural names only, and about 270 RAM variables are still known by
  address.
- The seven lookups whose table address comes from a pointer, not from `LDX #` (for example at
  $146E4 and $1974A), are not followed yet.
