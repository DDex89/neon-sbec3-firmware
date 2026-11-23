# Program architecture

This page describes the program skeleton of the reference image **05293190AC**: start-up, memory,
interrupts and the two schedulers. Names refer to the generated source in `src/05293190AC/` and to
`annotations/`. Routine numbers like `Sub_2CC42` are placeholders until the routine is identified.
The other families have the same structure at other addresses (stage 5).

## Hardware set-up (reset code)

`Reset` ($0D08C) configures the controller before anything else runs:

| Item | Setting | Result |
|---|---|---|
| Stack, Z, extension registers | SK = ZK = $F, SP = $8FFE, IZ = $8000, EK = 0 | Z = $F8000 (RAM start); extended addresses read bank 0 (calibration) |
| Clock | SYNCR = $7F80 | 16.78 MHz from the 32.768 kHz reference |
| Internal SRAM | RAMBAH/RAMBAL = $FF8000 | 4 KB at $F8000-$F8FFF |
| Periodic interrupt | PITR = 7, PICR = $0338 | every 7 x 4 / 32768 s = 0.854 ms, level 3, vector $38 |
| Software watchdog | SYPCR = $94 | serviced by `KickWatchdogs` |
| Chip selects | CSBOOT, CS0: base 0, 256 KB; CS2: base $F9000, 2 KB | flash; one external device at $F9000-$F97FF |
| GPT | ICR = $B340 | level 3, vectors $40-$4B; the pulse accumulator input is the adjusted channel |
| SCI / QSPI | QILR = $1B, QIVR = $FE | SCI vector $FE, QSPI vector $FF |

The external device on CS2 is reached as `$1000,Z`-`$17FF,Z`; the code uses 61 different
addresses there, most often `$1000,Z` and `$1012,Z` (`$100E,Z` is written in `Isr_IRQ2`). It is probably one of the Chrysler interface chips of the SBEC3 board; identifying it
is open.

Reset also counts the reset causes: the bits of the SIM reset status register RSR are added as
4-bit counters into `ResetCountsExtSw` ($08,Z: external reset, software watchdog) and
`ResetCountsHltPow` ($09,Z: halt monitor, power-on). `ResetCheckWord` ($06,Z) is rewritten by every
main-loop pass and checked at reset to tell a warm restart from a cold start.

## Memory map

| Address | Content | Reached as |
|---|---|---|
| $00000-$001FF | exception vectors | |
| $00200-$0FFFF | header, calibration, then code | `$xxxx` (EXT, EK = 0) for calibration |
| $10000-$3FFFF | code and tables | `JSR $xxxxx`, indexed with XK/YK |
| $F8000-$F8FFF | RAM (4 KB) | `$xxxx,Z` |
| $F9000-$F97FF | external device (CS2) | `$1xxx,Z` |
| $FF700-$FFDFF | module registers (ADC, MRM, GPT, SIM, SRAM, QSM) | `$7xxx,Z`, named in `00_equates.asm` |

Configuration bits of the calibration live around $0328-$0338 and are tested with `BRSET`/`BRCLR`
on extended addresses, for example `BRSET $032E,#$04,...` (see below). Their meaning is a stage 4
topic.

## Interrupts

| Vector | Handler | Function |
|---|---|---|
| $38 | `Isr_PIT` ($08344) | 0.854 ms time base, fast scheduler (below) |
| $40 | `Isr_GPT_PAI` ($0AAEA) | pulse accumulator: event counting, restarts timing state |
| $41 | `Isr_GPT_IC1` ($0A02E) | input capture 1, the largest handler (crank signal, to be confirmed) |
| $42 | `Isr_GPT_IC2` ($0ACD2) | input capture 2: starts a period measurement, clears `Ic2OverflowCount` |
| $43 | `Isr_GPT_IC3` ($080CA) | input capture 3: counts edges ($09CC,Z, $52,Z) |
| $45, $46, $47 | `Isr_GPT_OC2/3/4` | three identical output-compare channels (coil or injector timing, to be confirmed) |
| $48 | `Isr_GPT_IC4OC5` ($08A90) | input capture 4, enabled by calibration bit $0337.7; uses the table at $08A6C |
| $49 | `Isr_GPT_Overflow` ($0ACF0) | counts timer overflows in `Ic2OverflowCount` (saturating) |
| $12 | `Isr_IRQ2` ($089BE) | external interrupt from the CS2 device |
| $14 | `Isr_IRQ4` ($08A18) | external interrupt, calls `Sub_30C28` |
| $FE | `Isr_SCI` ($08A22) | serial line: diagnostics and reflash (`SciInterrupt`) |
| $FF | `Isr_QSPI` ($08A3E) | serial peripheral interface, calls `Sub_31E8C` |
| $11, $13, $15-$17, $44, $4A | `UnexpectedInterrupt` | should never occur (below) |
| all others | `Reset` | |

The handlers of the interrupts that should not occur (IRQ1, IRQ3, IRQ5-IRQ7, OC1, pulse
accumulator overflow) disable their own source and jump to `UnexpectedInterrupt`, which sets a bit
per source in `UnexpectedIrqFlags` ($00,Z) and saves two words of the interrupted stack frame at
$02,Z and $04,Z. That is a record for diagnosis, not a recovery.

## Fast scheduler: the PIT interrupt

`Isr_PIT` runs every 0.854 ms. Unless `$0550,Z` is set it increments `PitTickCounter` and
`LoopTickCounter` and then picks work by the low bits of `PitTickCounter`:

| Ticks | Period | Work |
|---|---|---|
| odd | 1.71 ms | `Sub_2DA18`, `Sub_33048`; `Sub_2F800` and `Sub_2FB1E` if calibration bits $0335.5 / $0335.7 are set |
| 2 mod 4 | 3.42 ms | starts an ADC conversion sequence (ADCTL1 = $24), then `Sub_08DD4` or `Sub_08520` (calibration bit $0338.1) |
| 4 mod 8 | 6.84 ms | `Sub_0843A` |
| 0 mod 8 | 6.84 ms | nothing |

After that, on every tick: `Sub_08D0C` if calibration bit $0334.4 is set, a counter for $0DC0,Z, and
every 24 ticks (20.5 ms) `Sub_3060E` or `Sub_317B6`, chosen by calibration bit $032E.2.

## Background scheduler: the main loop

`MainLoop` ($0DC36) makes one pass every 14 PIT ticks, about 12.0 ms:

1. 33 routines on every pass, starting with `KickWatchdogs` and `MainLoopCounters`.
2. One group of routines chosen by the lowest set bit of `MainLoopCounter`, the same scheme as in
   the FCC:

   | Lowest set bit | Period | Routines |
   |---|---|---|
   | 0 | 2 passes, 24 ms | 9 (`Sub_0EF76` ... `Sub_230B8`) |
   | 1 | 4 passes, 48 ms | 3 (`Sub_1BA5E`, `Sub_2D8E4`, `Sub_21D94`) |
   | 2 | 8 passes, 96 ms | 13 (`Sub_0F19E` ... `Sub_12D22`) |
   | 3 | 16 passes, 191 ms | 5 (`Sub_0EDB4` ... `Sub_22C1C`) |
   | 4 | 32 passes, 383 ms | 5 (`Sub_1DB14` ... `Sub_3ADFA`) |
   | 5 | 64 passes, 766 ms | 2 (`Sub_22CD8`, `Sub_22EA6`) |
   | 6 | 128 passes, 1.5 s | none |
   | 7 | 256 passes, 3.1 s | 6 (`Sub_2CC42` ... `Sub_0CC8A`) |

3. About 60 more routines on every pass; one of them is chosen by calibration bit $032E.2
   (`Sub_3017C`, or `Sub_3123A` and `Sub_31FA0`).
4. `CheckPowerDown`, then wait until `LoopTickCounter` reaches 14, calling `MeasureLoopTime`
   meanwhile; clear the counter and start again.

`MainLoopCounters` also keeps slower time bases: `Count3s` (every 256 passes) and `Count191ms`
(every 16 passes), both saturating at $FF, and `MainLoopPhaseMask` ($0C3B,Z). Bit n of
`MainLoopPhaseMask` is set once every 2^(n+1) passes; 127 instructions test it with
`BRCLR MainLoopPhaseMask,Z,#mask,...` to run part of a routine at a lower rate.

## Two communication variants

Calibration bit $032E.2 is tested in 30 places. In several of them it selects between two sets of
routines: in the main loop (see above), in the PIT interrupt (`CcdTransmit` / `Sub_317B6`), in
`Isr_IRQ2` (`Sub_30D58` / `Sub_31DF8`) and in the reset code. Reading the receive side confirms two
vehicle-bus interfaces:

- `CcdReceive` takes one-byte message IDs with up to two data bytes from two receive buffers
  ($89A2, $89A8). `CcdTransmit` sends a fixed rotation of messages built by small routines; each
  message is an ID, two data bytes and a checksum byte (the sum of the other three). The message
  set includes MAP, throttle with the speed control set or resume speed, coolant and battery
  temperature, battery and target voltage, engine rpm with the idle target, baro and air temperature, fuel used and
  distance pulses, and the VIN one character at a time (`Vin01`-`Vin17`).
- `PciReceive` takes frames of up to 11 bytes; the low bits of the first byte are tested as a
  header and the second byte selects the handler from a jump table at $3105A. Its handlers store
  the same values as the CCD ones. Together with the header byte this points to J1850 PCI, but
  the bus type is still an inference.

Both receive routines handle the SKIM (immobiliser) exchange: messages $0B and $C2 carry the
status and the key data (`SkimStatus`, `SkimData0`-`SkimData4`). `SkimKeyCheck` ($320D6) works out
the expected key from the VIN bytes, and a wrong key reports P1685.

## Diagnostics over the SCI line

`Isr_SCI` calls `SciInterrupt` ($3343C). The diagnostic commands are dispatched through the jump
tables at $35000, $3509C, $350CC, $350DC and $35BB0. Among them is a service that writes a received
routine byte by byte into RAM at $F8700-$F87FF (`DiagWriteRamByte`) and, after checking its length,
its checksum and the final `RTS`, runs it (`DiagRunRamCode`, `JMP $F8700`). A tester can therefore
run its own code in the controller without reflashing. This is separate from the bootstrap mode that
`third_party/SBECBootLoader` uses.

The same line also carries a high-speed logging mode (`SciLogReceive`): command bytes $F2 and
$F3-$F6 set the mode bits in `SciLogFlags` and $FE leaves the mode; after that, each received byte
selects a value that is sent back (from a RAM index list, or a word from a bank-3 page chosen by
$F3-$F5). `SciRequestReceive` takes the ordinary requests (`DiagCommand`,
`DiagParam1`-`DiagParam3`); a fixed byte sequence ($F8, $F7, $F5, $F3, $14), tracked in
`SciUnlockState`, switches to command $52.

## Open questions

- What the CS2 device at $F9000 is, and what IRQ2 and IRQ4 signal.
- Which input captures carry crank, cam and vehicle speed; which output compares drive coils and
  injectors.
- Whether the second bus variant is J1850 PCI (see above).
- Names of the scheduled routines: stage 4 (tables they read) and stage 5 (detailed annotation).
