# Revision: 05293190AC, 05007038, 04887050/51

This page is about what an improvement of these programs can build on: the size of the main maps,
the places where new code would go, the code that does nothing in a given calibration, and the
free flash and RAM. The numbers come from `tools/revision.py` (run it on any image); the
classification behind them is explained in its header. Nothing here has been changed in the
images.

| Image | Family | Flash | RAM | Routines | Instructions |
|---|---|---|---|---|---|
| 05293190AC | F (reference) | 256 KB, 4 banks | 4 KB | 690 | 44,048 |
| 05007038 (same code: 05293148AA) | C | 128 KB, 2 banks | 2 KB | 468 | 33,139 |
| 04887050, 04887051 | A | 128 KB, 2 banks | 2 KB | 401 | 30,371 |

## Main maps

All three programs use the same table formats and lookup routines. The 3D maps have a stored
column axis (one byte per column, engine rpm / 32) and take the row as a position 0-255; for the
part-throttle and WOT maps the row comes from MAP through `PartThrottleMapScale` and `WotMapScale`.
A 17 x 17 map takes 309 bytes (3 header bytes, 17 axis bytes, 289 values).

| Map | 05293190AC | 05007038 | 04887050 |
|---|---|---|---|
| PartThrottleFuel (per fuel event) | 17 x 17, $0BF6 | 17 x 17, $08B4 | 17 x 17, $07C2 |
| PartThrottleFuelMain (main loop) | 17 x 17, $0D2B | 17 x 17, $09E9 | none (see below) |
| WotFuel | 9 x 17, $0F6C | 9 x 17, $0C29 | 9 x 17, $0715 |
| PartThrottleSpark | 17 x 17, $1BFA | 17 x 17, $1772 | 17 x 17, $1544 |
| WotSpark | 9 x 17, $1FAF | 9 x 17, $1B27 | 9 x 17, $1497 |
| EgrSpark | 17 x 17, $1D2F | 17 x 17, $18A7 | 17 x 17, $180B |
| FlexSparkMapRpm | 17 x 17, $22DA | none | 17 x 17, $16D6 |
| KnockRetardLimit | 9 x 9, $24E5 | 9 x 9, $1FD9 | none |
| CrankBasePulse | 9 x 9, $0A91 | 9 x 9, $0764 | 9 x 9, $05BC |
| Warm-up maps (9 x 9) | 4 | 4 | 3 (AfterStartDecay, $0954, $08F7) |

Rpm axes: in 05293190AC and 04887050 the part-throttle and WOT maps run from 512 to 7,200 rpm (96
rpm steps at the low end); family C uses other axes: in 05293148AA most of them end at 6,496 rpm, and 05007038 moves the end
of the spark, WOT and per-event fuel axes up to 6,976 rpm (`PartThrottleFuelMain` ends at 6,016 rpm
in both). 04887050 has no `PartThrottleFuelMain`: its main-loop fuel code
(`FuelCorrections`, with what later programs call as subroutines all inline) reads a 17 x 17 map
only while the EGR solenoid is on (`EgrFuelCorrection`), whose rpm axis is exactly that of
`PartThrottleFuelMain` in 05293190AC. 04887050 also has the flex-fuel maps; 05007038 keeps only
the neutral flex factors (`FlexFactorDefaults`).

`Lookup3D` clears XK before it reads the table: every 3D map has to sit in bank 0. A larger map
therefore needs room in bank 0, or a lookup routine that keeps the bank of the caller.

## Free flash

Free means erased ($FF) runs of at least 16 bytes outside code, tables and constants. "Other" is
data that is none of these (unrecognised tables, lists, padding with other values); it is not
counted as free.

| Image | Bank 0 | Bank 1 | Bank 2 | Bank 3 | Total | Largest runs |
|---|---|---|---|---|---|---|
| 05293190AC | 26,421 | 18,236 | 23,146 | 22,231 | 90,034 | $04AE4 9,500; $26206 7,674; $1BB44 5,308 |
| 05007038 | 526 | 348 | - | - | 874 | $1FEC0 320; $00204 252; $04198 104 |
| 04887050/51 | 5,791 | 4,940 | - | - | 10,731 | $1E4DA 2,854; $0F94A 1,718; $0434D 1,203 |

05007038 is nearly full: bank 1 holds 61,448 bytes of code in 64 KB, and bank 0 (tables and the
rest of the code) has 526 bytes left. The room for new code there comes mainly from code the
calibration does not use (next section): the development port alone is 1,768 bytes.

## Free RAM

The RAM is at $F8000 (Z); the stack starts at the last word and grows down. "Unreferenced" means
no instruction reads or writes the byte directly, no pointer in the code points near it and no
calibration list holds its address. Buffers reached only through computed pointers can still be in
these runs, so each one has to be checked in the code before it is used.

| Image | Size | Referenced | Unreferenced | In runs of 8 or more | Stack area (unreferenced top) | Largest runs |
|---|---|---|---|---|---|---|
| 05293190AC | 4,096 | 2,485 | 1,437 | 1,283 | $0F52-$0FFF | $0E13 237; $0B5B 165; $0481 111; $0281 109 |
| 05007038 | 2,048 | 1,725 | 206 | 88 | $078B-$07FF | $05DB 21; $03DE 18; $0505 17 |
| 04887050/51 | 2,048 | 1,533 | 415 | 301 | $079C-$07FF | $0724 104; $04C4 60; $01BE 50 |

In 05007038 the development port uses $0732-$075E (45 bytes) and nothing else does; with the port
code removed this block is free too.

## Code that does nothing in these calibrations

**Unreached** (no call, jump or vector leads there): 05293190AC has 14 routines, 1,472 bytes
(`UnusedCylSparkSet`, `UnusedCylSparkOverride`, `UnusedFlexLearnMain`, `UnusedFlexLearn2` and
others, see [architecture.md](architecture.md)). This search was done on the reference only; the
128 KB images have not been searched for unreached code yet.

**Stubs** (RTS only, called from fixed places): 05293190AC `EmptyHook`, `SpareHook3F000`;
05007038 eight (`EmptyHook08872` in the fuel code, six in the main loop, `EmptyHook0AE60` in the
PIT); 04887050 none. A stub is a ready call site: new code can be placed behind it without
touching the caller.

**Off here**: routines whose first instruction skips the body on an option bit this calibration
leaves clear.

| Image | Routines (bytes) |
|---|---|
| 05293190AC | PwmC18Main 240, PwmC18CircuitCheck 150, SpeedDampControl 538, EventSparkControl 156, CamSignalCheck 112, WotLeanMonitor 188, CatTempMonitor 178, PciPitTick 170, PciLinkCheck 90, PciStateSet1 16, StarterCut 128, TuneValve2CircuitCheck 90, ChargeDeficitCalc 80, KnockWindowInit 24, KnockWindowUpdate 78, OutputTest3 42, OutputTestB 30, FanTestToggle2 22 |
| 05007038 | DevPortInit 104, DevPortService 224, DevPortChannel1-8 8 x 180, SpeedDampControl 522, CatTempMonitor 174, CamSignalCheck 68 |
| 05293148AA | as 05007038, plus LdpMonitor 1,432, PurgeFlowTest 1,212, LdpPurgedCheck 162 |
| 04887050 | AcCutControl 332, TccMonitor 408, FanOutputControl 388, SurgeSparkControl 316, SpeedCtlRpmJumpCheck 172, WotLeanMonitor 166 |
| 04887051 | as 04887050 without SpeedCtlRpmJumpCheck, plus PnSwitchMonitor 124, PnSwitchMonitor2 126, EventSparkControl 156 |

So 05007038 turns on the leak detection pump monitor and the purge flow test that 05293148AA,
with the same code, leaves off (Options0335 bits 1 and 5). The list only covers routines switched
off at their entry; branches switched off inside a routine are not counted.

**The development port in 05007038 and 05293148AA.** Chip select 1 is set up for a 16 KB device
at $20000 (the 256 KB families have flash there). With Options0331 bit 4 the program exchanges
RAM with it: eight channels take lists of RAM addresses from the device and either write the
device's values into RAM or copy RAM to the device, and `FinishFuelPulse`, `StartInjectorPulse`
and `SparkEventCalc` write per-injector and per-event values to it. This looks like the interface
of a calibration tool (live RAM override and logging). The bit is clear in both images, so the
port is off; its routines (1,768 bytes), the branches in the fuel and spark code and the RAM at
$0732-$075E are the largest piece of unused code in family C.

## Where an improvement would go

- **Main maps**: `CalcFuelPulse` (base pulse per event, its contract in [fuel-pulse.md](fuel-pulse.md)) / `PartThrottleFuelCalc` (fuel) and `CalcBaseSpark` (spark) pick
  the maps. As far as the lookup goes, a map of another size needs only the new table in bank 0:
  `Lookup3D` reads rows, columns and the column axis from the table header, and the row comes as a
  position 0-255 whatever the number of rows.
- **Per injector and per event**: `FinishFuelPulse` (per injector, with `InjectorIndex`) and
  `SparkEventCalc` (per spark event). In 05007038 both already have a branch per injector or event
  for the development port, behind one option bit: the natural place for a per-cylinder trim.
  05293190AC has the unreached per-cylinder spark code (`UnusedCylSparkSet`,
  `UnusedCylSparkOverride`, see [open-questions.md](open-questions.md)).
- **Main loop**: the stubs above (05007038, 05293190AC), or a call added to the main loop list in
  `Reset` (05007038, 04887050) or `MainLoop` (05293190AC).
- **Room**: 05293190AC has about 88 KB of flash and over 1 KB of RAM to spare; 04887050 about
  10 KB of flash and 300 bytes of RAM; 05007038 under 1 KB of flash and under 100 bytes of RAM,
  unless the development port is removed (1.8 KB of flash, 45 bytes of RAM).

Any change has to keep the checksum (`tools/fixsum.py`) and is checked by rebuilding the source;
see [tools.md](tools.md).
