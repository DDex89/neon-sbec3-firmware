# Routine notes (reference image 05293190AC)

Each `## ADDRESS Name` heading names a routine; the lines under it become the comment block above
the routine in the generated source. Keep the notes short and factual; mark guesses as such.

## 0D08C Reset
Reset entry (vector 0). Sets SK = ZK = $F, SP = $8FFE, Z = $F8000 (RAM base), EK = 0 so that
extended addresses read the calibration in bank 0. Then: SYNCR = $7F80 (16.78 MHz), SIMCR,
SRAM at $FF8000, PIT period 7 x 4 / 32768 Hz = 0.854 ms on level 3 vector $38, software watchdog
(SYPCR = $94), chip selects (CSBOOT/CS0 = flash, CS2 = 2 KB external device at $F9000), ports E/F,
GPT (ICR = $B340: level 3, vectors $40-$4B), counts the reset causes from RSR into $08/ResetCountsHltPow, and
continues with the module and RAM initialisation before entering MainLoop.

## 0DC36 MainLoop
Background loop, one pass every 14 PIT ticks (about 12 ms). Each pass runs a fixed list of
routines, then one sub-loop group chosen by the lowest set bit of MainLoopCounter (group n runs
every 2^(n+1) passes), then a second fixed list. It then waits for LoopTickCounter to reach $0E,
calling MeasureLoopTime, clears the counter and starts again.

## 0C000 MainLoopCounters
Increments MainLoopCounter. Every 256 passes (3.06 s) increments the saturating Count3s and
decrements FlexLearnStartCoolantValue; every 16 passes (191 ms) increments the saturating Count191ms. Stores in
MainLoopPhaseMask a mask of the trailing one bits of the counter: bit n is set once every
2^(n+1) passes, so routines test it to run at a slower rate.

## 08344 Isr_PIT
Periodic interrupt, every 0.854 ms. Increments PitTickCounter and LoopTickCounter (the main-loop
pacing) and runs work selected by the low bits of PitTickCounter: odd ticks every 1.71 ms; ticks
2 mod 4 start the next ADC conversion sequence (ADCTL1 = $24); ticks 4 mod 8 call IacStepperDrive.
Every 24 ticks (20.5 ms) one of two routines chosen by calibration bit $032E.2 runs.

## 080B4 UnexpectedInterrupt
Common tail of the handlers for interrupts that should never occur (IRQ1, IRQ3, IRQ5-7, GPT OC1,
GPT PAOV). Each handler first disables its own source, then passes a bit in D; the bit is ORed
into UnexpectedIrqFlags and two words of the interrupted stack frame are saved at $02/UnexpectedIrqStack6.

## 0C420 KickWatchdogs
Services both watchdogs: toggles PORTC bit 5 (external watchdog) and writes $55/$AA to SWSR
(software watchdog of the SIM).

## 35A4C DiagWriteRamByte
SCI diagnostic service: stores one received byte into the RAM buffer at $F8700-$F87FF.

## 35A98 DiagRunRamCode
SCI diagnostic service: checks the downloaded RAM routine (length byte, checksum, last word
$27F7 = RTS) and runs it with JMP $F8700. This is how a tester can execute its own code in the
ECU without reflashing.

## 3D000 EmptyHook
An RTS; called from several places, probably left for development or calibration variants.

## 0C08E Lookup2D
2D table lookup with linear interpolation. X = table, A = input; result in A and B and in
LookupResult. Table: n, flags, then n (x, y) byte pairs with x ascending. Inputs below the first
or above the last x give the first or last y. Flags: $80 unsigned, $20 signed y, $10 steps (no
interpolation), $40 a zero y counts as 256; with flags $00 the table address is kept in Lookup2DC56.

## 0C214 Lookup3D
3D table lookup with bilinear interpolation. X = table, A = row position 0-255 (usually the
result of a Lookup2D scale table), B = column input. Table: rows, columns, signed flag, the
column axis (one byte per column, ascending), then the values row by row.

## 0C28C Lookup3DNorm
As Lookup3D, but both inputs are positions 0-255 and the table has no column axis.

## 0C36A Lookup2DRev
2D lookup on a table whose pairs are stored as (y, x). Used twice.

## 11F40 CalcFuelPulse
Fuel pulse width, called from Isr_GPT_IC1 on every reference event. Base pulse width
(Map - MapOffset) * (256 + K) / 16, zero when MAP is below the offset; part-throttle or WOT
constants and tables are chosen by FuelModeFlags bit 5. The base is multiplied by 1 + v / 256, where v
is the signed value of PartThrottleFuel or WotFuel (rows by MAP through the scale table, columns
by the high byte of EngineRpm). BaroFuelAdder is added at the end; the result goes to FuelPulse and Temp4F6.

## 1105E ScaleByFraction
E = E * (1 + A / 256), saturating at $FFFF.

## 246A0 FaultListAdd
Called by ReportFault with the fault row index in A. The list of stored faults is $0142-FaultListLast
(newest in FaultListLast, $0149). An index already in the list is moved to the newest place, a new
one pushes the oldest out. FaultListInfo1-3 ($014C-$014A) hold one byte for each of the three newest
entries, cleared for a new entry.

## 24222 FaultListRemove
Removes the index in A from the list $0142-FaultListLast and shifts FaultListInfo1-3 with it.

## 242F2 MisfireFaultLookup
Looks for the misfire fault row ($45AC) among the three newest list entries and returns its
FaultListInfo byte in Scratch9. The third compare reads FaultList6 again instead of FaultList5, so the
third entry is never found; this looks like a slip in the original code.

## 1E418 UnusedCylSparkSet
Never runs: the BRA just before it ($1E416) always jumps over it, here and in families D and E.
Writes CylSparkOverride[CylinderIndex] (RAM $0D7A, one byte per cylinder) = CylSparkOverrideBase
($04A2, only with Options033D bit 0 set and FuelPulseOptFlags bit 1 clear; otherwise A as left by
the code before) + CylSparkOverrideValues[CylinderIndex] ($04A3), signed, held at -128/+127.
The block ends at $1E450; from L1E452 on the code belongs to SparkEventCalc again.

## 1E65C UnusedCylSparkOverride
Never called. Takes the cylinder number in A; if it is below the high nibble of BusInfoByte3, it
returns CylSparkOverride[cylinder] instead of SparkAdvanceD11, but only if the value lies between
$D6 and $62 (signed) and RefPeriodLow passes a limit ($4400 or $0C00 depending on the value);
otherwise SparkAdvanceD11. So the value replaces the spark advance of one cylinder on a request
from the bus, which looks like a test function. It has the same interface as GetSparkAdvance (cylinder
in A, spark advance back in A), and all three callers of GetSparkAdvance load CylinderIndex into A
first, which GetSparkAdvance ignores: GetSparkAdvance looks like the stand-in for this routine.

## 1E656 GetSparkAdvance
Returns SparkAdvanceD11 in A. Its callers (Isr_GPT_OC4, SparkOutputOc2, KnockCylinderRetard) load
CylinderIndex into A before the call, which this routine does not use; see UnusedCylSparkOverride.

## 30802 CcdTxA5FanStatus
CCD transmit slot: sets CcdTxId = $A5 and falls through into BusMsg91Build, which supplies the data
(fan status byte and the MAP-high bit).

## 30900 CcdTxA4SparkStatus
CCD transmit slot: sets CcdTxId = $A4 and falls through into BusTxSparkStatus, which supplies the data.

## 3096C CcdTxECSecurity
CCD transmit slot: sets CcdTxId = $EC and falls through into SecurityStatusCalc, which supplies the
data.
