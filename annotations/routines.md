# Routine notes (reference image 05293190AC)

Each `## ADDRESS Name` heading names a routine; the lines under it become the comment block above
the routine in the generated source. Keep the notes short and factual; mark guesses as such.

## 0D08C Reset
Reset entry (vector 0). Sets SK = ZK = $F, SP = $8FFE, Z = $F8000 (RAM base), EK = 0 so that
extended addresses read the calibration in bank 0. Then: SYNCR = $7F80 (16.78 MHz), SIMCR,
SRAM at $FF8000, PIT period 7 x 4 / 32768 Hz = 0.854 ms on level 3 vector $38, software watchdog
(SYPCR = $94), chip selects (CSBOOT/CS0 = flash, CS2 = 2 KB external device at $F9000), ports E/F,
GPT (ICR = $B340: level 3, vectors $40-$4B), counts the reset causes from RSR into $08/$09,Z, and
continues with the module and RAM initialisation before entering MainLoop.

## 0DC36 MainLoop
Background loop, one pass every 14 PIT ticks (about 12 ms). Each pass runs a fixed list of
routines, then one sub-loop group chosen by the lowest set bit of MainLoopCounter (group n runs
every 2^(n+1) passes), then a second fixed list. It then waits for LoopTickCounter to reach $0E,
calling MeasureLoopTime, clears the counter and starts again.

## 0C000 MainLoopCounters
Increments MainLoopCounter. Every 256 passes (3.06 s) increments the saturating Count3s and
decrements $0F24,Z; every 16 passes (191 ms) increments the saturating Count191ms. Stores in
MainLoopPhaseMask a mask of the trailing one bits of the counter: bit n is set once every
2^(n+1) passes, so routines test it to run at a slower rate.

## 08344 Isr_PIT
Periodic interrupt, every 0.854 ms. Increments PitTickCounter and LoopTickCounter (the main-loop
pacing) and runs work selected by the low bits of PitTickCounter: odd ticks every 1.71 ms; ticks
2 mod 4 start the next ADC conversion sequence (ADCTL1 = $24); ticks 4 mod 8 call Sub_0843A.
Every 24 ticks (20.5 ms) one of two routines chosen by calibration bit $032E.2 runs.

## 080B4 UnexpectedInterrupt
Common tail of the handlers for interrupts that should never occur (IRQ1, IRQ3, IRQ5-7, GPT OC1,
GPT PAOV). Each handler first disables its own source, then passes a bit in D; the bit is ORed
into UnexpectedIrqFlags and two words of the interrupted stack frame are saved at $02/$04,Z.

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
