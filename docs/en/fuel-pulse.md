# CalcFuelPulse: the base fuel pulse

`CalcFuelPulse` turns MAP and rpm into the base injector pulse once per reference event. Every
other fuel correction (dead time, coolant, transient, closed loop, adaptive) is applied after it,
to the value it leaves in `FuelPulse`. A patch that replaces the way the base pulse is found
(a 16-bit table, a VE model) replaces this routine and keeps the rest. This page is the contract
such a patch has to keep, for the 1996, 1997 and 1999 programs.

## Where it is

| | 04887050/51 (1996) | 05293013AC/14AC (1997) | 05293190AC (1999) |
|---|---|---|---|
| `CalcFuelPulse` | $07D62, 222 bytes | $07D82, 222 bytes | $11F40, 234 bytes |
| Call site (`JSR` in `Isr_GPT_IC1`) | $050D0 | $050D0 | $0AAAC |
| `Lookup2D` / `Lookup3D` | $0E400 / $0E54E | $0E500 / $0E64E | $0C08E / $0C214 |
| `ScaleByFraction` | $07342 | $0735A | $1105E |
| `PartThrottleMapScale` / `WotMapScale` | $048F / $0483 | $04A1 / $0495 | $08F8 / $0904 |
| `PartThrottleFuel` / `WotFuel` (17 x 17 / 9 x 17, signed) | $07C2 / $0715 | $07D5 / $0728 | $0BF6 / $0F6C |
| Part-throttle offset, K / WOT offset, K | $0657, $0656 / $0655, $0654 | $066A, $0669 / $0668, $0667 | $0B93, $0B92 / $0B95, $0B94 |
| MAP hold option | `Options0323` bit 0 | `Options0323` bit 0 | `Options0337` bit 2 |
| RAM `Map`, `EngineRpm`, `FuelModeFlags` | $032B, $0306, $055B | $0345, $031D, $056A | $0A7E, $0C4C, $0771 |
| RAM `WotTimeEnrich`, `BaroFuelAdder` | $05B3, $0596 | $05C3, $05A6 | $07AA, $080E |
| RAM `FuelPulse`, `CalcFuel432` | $05BA, $03BF | $05CA, $03D7 | $07E2, $0432 |

The routine of 1996 and 1997 is the same code at another address (it differs only in the address
of the MAP hold constant, $0491 and $04A3). The 1999 routine is 12 bytes longer because it takes
`TipIn802` from the row position of the table instead of from MAP. The four calibration bytes
(offsets and K) have the same values in all three images.

The 2D and 3D table formats and `Lookup3D` are described in [calibration.md](calibration.md).

## What it computes

1. `T` = MAP. In part throttle, with the MAP hold option, `T` is at least the first MAP point of
   `PartThrottleMapScale` (MAP below it counts as that point).
2. Offset and K are the part-throttle or the WOT pair (`FuelModeFlags` bit 5 = WOT mode). If
   `T` is below the offset, the pulse is 0 (no baro adder either) and the routine ends.
3. Base `L = (T - offset) x (256 + K) / 16`: linear in MAP (kept in `LookupResult`).
4. Row position = `PartThrottleMapScale` (or `WotMapScale`) of `T`; factor `f` = `Lookup3D` of
   `PartThrottleFuel` (or `WotFuel`) at that row and `EngineRpm`. The table is signed: the pulse
   is `L x (256 + f) / 256` (f = 0 is 1.0, +127 about 1.5, -128 is 0.5).
5. `CalcFuel432` = that pulse / 2.
6. In WOT mode with `FuelModeFlags` bit 0 and `WotTimeEnrich` not 0: pulse x (1 + WotTimeEnrich /
   256).
7. Plus `BaroFuelAdder`, saturating at $FFFF: the result goes to `FuelPulse` and `Temp4F6`.

`tools/simtest.py` checks this description against the routine itself in the simulator (next
section): over 2,494 cases per image the two agree to within 2 counts (rounding) in 05293190AC,
05293013AC, 04887050, 05007038 and 05269833AH.

## The contract

**Called from** `Isr_GPT_IC1` only, once per reference event, after `EventCorrections` and before
`FuelEventSchedule`. It runs inside the interrupt: its time counts against every other interrupt.
In the simulator it runs 15 to 367 instructions in 05293190AC and 15 to 328 in 04887050, and
uses up to 34 and 24 bytes of stack. This includes the 4-byte return frame.

**Inputs:** `Map`, `EngineRpm`, `FuelModeFlags` bits 0 and 5, `WotTimeEnrich`, `BaroFuelAdder`
and the calibration above.

**Outputs and who reads them:**

| Output | Read by | Note |
|---|---|---|
| `FuelPulse` | `FinishFuelPulse` (all fuel corrections) | the result |
| `CalcFuel432` | `PurgeVaporLearn` (1996, 1997), `PurgeRampCalc` (1999) | base pulse before WOT and baro, / 2; the purge code uses it as engine load |
| `TipIn802` | no direct reader found | MAP sample (with `AccelFuelOptions` bit 7); also written by `TipInFuelControl` |
| `Temp4F6`, `LookupResult` | many routines | work cells shared with other code, not outputs |

**Registers:** the caller and `FuelEventSchedule` after it expect nothing in the registers. The
routine leaves D, E, X and Y changed and the stack balanced.

## Room for a replacement

Erased flash checked in the code: no instruction, table or pointer uses it. The pointer loads that
look like they point into these areas take another bank (XK/YK from PK or from Z). The header and
the checksum correction byte are outside them.

| Image | Bank 0 | Bank 1 |
|---|---|---|
| 04887050/51 | $0434D-$047FF (1,203 bytes, between the calibration tables), $0F94A-$0FFFF (1,718) | $1E4DA-$1EFFF (2,854) |
| 05293013AC | $04374-$047FF (1,164, between the tables), $0FC04-$0FFFF (1,020), $06056-$063FF (938) | 116 at most |
| 05293190AC | (see [revision.md](revision.md)) | $12D9C-$13FFF (4,708) |

Points for a replacement:

- **Keep the outputs.** Write `FuelPulse` (and `Temp4F6`) and also `CalcFuel432`, or the purge
  code works from a stale value.
- **Table banks.** `Lookup3D` and `Lookup2D` clear XK, so tables read through them must be in
  bank 0. A routine that reads its own tables sets XK itself; in 05293013AC bank 1 has no room
  for them.
- **Hook.** Either point the `JSR` at the call site to the new routine, or put a `JMP` at the
  entry of `CalcFuelPulse`. The `JMP` keeps the call site and leaves the stock body in place, so
  the new code can fall back to it on an option bit.
- **Checksum.** Run `tools/fixsum.py --fix` afterwards.

## The simulator

`tools/cpu16sim.py` runs single routines of an image instruction by instruction. There are no
peripherals and no timing: RAM and registers are set by the caller and read back after the
routine returns, so the stock routine and a patch can be compared over any grid of inputs.
`tools/simtest.py` checks the simulator against independent models of `Lookup3D` (within 1
count) and of `CalcFuelPulse` (above), and runs in CI on 05293190AC and 04887050.

## Downstream injection and cylinder-count audit (1996/1997)

Source-level evidence for 04887050 and 05293013AC; not an exact-ROM execution or
bench validation. Preserve both four- and six-cylinder architecture in ReCore;
initial production targets remain the stock four-cylinder Neon. Changing the
count byte alone does not convert this calibration to six cylinders.

- Both images have `CylinderCount = $04`. The IC1 cylinder counter and fuel
  scheduler wrap at this count. `FuelEventCalc` explicitly tests count == 6
  before writing `IoInjector4/5` in addition to 0..3. Startup and hardware
  checks also cover those registers; key-off clears all six in the 1997 image.
- In 05293013AC, `IoInjector0..5` are 16-bit registers at $F8856, $F8858,
  $F885A, $F885C, $F885E, $F8860. Hardware-check identifiers $0049..$004E
  correspond to these registers; these are internal codes, not OBD DTCs.
- `StartInjectorPulse` ($077E6 / $07810) uses a separate four-entry output
  pointer table at $4808 in the Neon calibration: $8830, $8828, $8824, $882C
  (Z-derived bank F). `Options031D = $02` selects the DECB / ANDB #$03
  transformation in both images. The table entries are not the injector
  configuration registers above. Six-cylinder pin mapping, compatible option
  bytes, firing order, crank/cam synchronization and calibration remain open.
- `FinishFuelPulse` ($078B2 / $078E8) selects its two correction factors and
  final pulse bank by injector index bit 0. Both factor producers include
  oxygen adaptation and short-term trim. Normalizing symbolic operands and
  branch labels yields 177 / 174 instruction lines; 1996 has three additional
  instructions testing EventSparkFlags bit 5, loading $1D30, and calling
  ScaleByFraction before the FinishFuel6D4 store. Preserve this variant.
  This is textual source comparison, not a binary equivalence proof.
- In both images the six-byte hot-enrichment mask rows at $6409, $640F,
  $6415 are respectively 04 08 10 20 01 02; 02 01 04 08 10 20;
  01 04 08 02 10 20. These are masks, not physical firing order.

| Symbol | 04887050 | 05293013AC |
|---|---|---|
| CylinderIndex | $F83A4 | $F83BE |
| InjectorIndex | $F8570 | $F857F |
| FuelPulse | $F85BA | $F85CA |
| FuelPulseBank1/2 | $F857A/$F857C | $F858A/$F858C |
| FinishFuel78C/796 | $F85A3/$F85AA | $F85B3/$F85BA |
| FinishFuel6D4 | $F8169 | $F819F |
| FlexFuelFactor | $F8578 | $F8588 |
| FuelPulseAdder | $F858B | $F859B |
| AccelFuel | $F85BC | $F85CC |
| HotEnrich | $F85D8 | $F85E8 |

### 1997 event-history and indirect accesses

`CylinderBit` ($086EA) explicitly sets XK=1. Reconstructing the trailing
18 data bytes immediately before SciRequestReceive ($15B8E) gives:
$15B7C = 03 02 00 01 FF FF; $15B82 = 02 01 03 00 FF FF;
$15B88 = 04 05 00 01 02 03. The stock option $02 selects the first
row. The first two rows contain four valid zero-based indices and FF padding;
the third is a six-index permutation. Equivalent bytes exist at
$129A8/$129AE/$129B4 in the 1996 image, but the same consumers are not
established there. The 1996 StartInjectorPulse lacks the 1997 call to
EventFuelScaleApply; do not transplant the 1997 path unconditionally.

CylinderBit scans without a bound and shifts an eight-bit mask. The
IC4/OC5 history consumer rejects FF before calling it, but EventFuelScaleApply
uses InjectorIndex directly. A missing value can cause a scan beyond the
selected row; a zero mask can make the subsequent LSRB loop nonterminating.
Reachability for stock valid indices is not a demonstrated failure.
A future bounded implementation needs an explicit invalid-index policy and
caller validation; do not silently clamp or wrap.

In 1997 the IC4/OC5 history scan and counter initialization, EventFuelScaleApply
and EventTableCheck address $F8700..$F8705 (count-dependent counters) and
$F8706..$F870B (history). EventHistoryShift shifts four or six entries;
the history initializer sets all six to FF. For valid indices and supported
table rows, these accesses are outside candidate $F85F2..$F85FF; that is
not a global alias or asynchronous integrity proof. Keep the entire
$F8700..$F87FF page excluded from persistent allocation.
The four-entry output pointers and the 12-byte stock per-cylinder event
table at $51F3 (four rows of three) require independent six-cylinder evidence.

Evidence: [1996 bank 0](../../src/04887050/bank0.asm),
[1997 bank 0](../../src/05293013AC/bank0.asm),
[1997 bank 1](../../src/05293013AC/bank1.asm),
[1997 equates](../../src/05293013AC/00_equates.asm).
No firmware bytes, RAM allocation, XDF, or simulator semantics changed.
Exact-ROM fixtures and hardware mapping remain pending; CI held per AGENTS.md.

### Injector output accounting and event-offset correction

`InjectorFuelAccount` ($06DDA / $06DF2) has 48 identical symbolic instruction
lines in both images after branch-label normalization. Called by TipInFuelControl,
it adjusts the selected output timer for tip-in enrichment, accounting for dead
time and the output status bit, and updates the 24-bit fuel-used accumulator
(`FuelUsedAccum:FuelUsedWord`, saturating at $FFFFFF). It is not a measurement
of physical fuel flow. The caller makes three cyclic channel calls for count 4,
four otherwise. The table reads in bank 0 and output pointers in bank F are
distinct: $4800 = 08 02 01 04 (IoStatus3 masks); $4804 = 20 08 04 10
(OutputDriverFaults masks); $4808 = 8830 8828 8824 882C (16-bit pointers).
Both images share these bytes. The stock $02 option remaps the incoming index
as (B-1) & 3. This cannot independently address six channels.

FuelEventCalc uses a per-image table address. For 04887050 the lookup curve at
$51F3 feeds the table at $51E7; for 05293013AC the curve at $51FF feeds $51F3.
Both curves contain pairs (6,0), (36,1), (66,2); FuelEventCylFactor = 3 at
$51FB/$5207. Both 12-byte tables are
01 02 03 / 02 03 00 / 03 00 01 / 00 01 02.
Index = 3*CylinderIndex + lookup result (the latter is 0..2 for the stock
curve); only the four stock rows are present. No evidence supports extending
the index into the following table header.

In 1997 EventFuelScaleApply consumes the RAM InjectorIndex, while
StartInjectorPulse takes the requested channel in B, including calls from
FuelEventCalc which need not write InjectorIndex first. Its scaling path is
gated by FuelModeFlags bit 3, set in IC4/OC5 and cleared by EventTableCheck
once the counters are zero. Whether a stale index is reachable with this
flag set is still open. 1996 lacks these consumers in the reviewed paths.

See the exact-ROM group pulse and IC4/OC5 checks below.

### Injector index lifecycle and CCD fuel accounting

05293013AC has 14 pulse-call sites: eight calls through StartPulseCurrent
(loads RAM InjectorIndex into B), one direct FuelEventSchedule call immediately
after STAB InjectorIndex, and five direct FuelEventCalc sites. The latter may
supply B without updating RAM InjectorIndex. In the forced four-channel group
model (B=3,2,1,0 with a fixed RAM index 0..3), 12 of 16 B/index pairs differ.
This is an arithmetic model, not a reachable-state or exact-ROM trace.

The 1997 scaling path is gated by FuelModeFlags bit 3. The reviewed direct
setter at IC4/OC5 L05FBC is bypassed by BRCLR Options0323,#$80 at ISR entry
in stock 05293013AC ($05); the reset clears the flag. No normal setter has
been established; indirect/diagnostic writers and asynchronous integrity
remain open. The family calibration diff records $81 for 05293014AC, so this
gate conclusion must not be applied to that sibling. 04887050 has $81 but
lacks the same EventFuelScaleApply call path; no automatic extrapolation.

Both ROMs also contain CcdTx84FuelUsed in bank 1. It reads the overlapping
16-bit word beginning at FuelUsedAccum (F8463/F847D), masks with $FFF8,
caps at $07F8, subtracts this quantity from that word, and reports the
quantity divided by eight (0..255) in the high payload byte. It reads and
clears DistancePulses for the other byte. The lowest byte of the 24-bit
accumulator (F8465/F847F) is not modified by this operation. Named writes to
FuelUsedAccum/FuelUsedWord occur in InjectorFuelAccount, StartInjectorPulse,
and this overlapping CCD builder in both ROMs. No claim of exhaustive
computed-writer coverage.

InjectorFuelAccount has a single direct parent TipInFuelControl in each
ROM; the latter has one named MainLoop call. It raises IPL to 7 with ORP
#$00E0 before the timer read/modify/write and accumulator update, then
clears IPL with ANDP #$FF1F (not a saved-mask restore). Table selection and
loading the additive pulse precede that critical section. Trace the CCD
dispatch/mask context and check temporal consistency of the foreground
and ISR writers before claiming atomicity. Do not infer a live race from
the overlapping access alone.

Host arithmetic enumeration: all 65,536 possible upper words for the CCD
quantize/cap/subtract operation, and 8,960 combinations of accumulator
high byte, five low-word boundaries and seven addition boundaries for the
24-bit saturating add model; zero mismatches against the corresponding
integer invariants. No CPU16 execution or timing proof in this pass.

### Exact-ROM injector accounting and event index

On `04887050` and `05293013AC`, 432 isolated InjectorFuelAccount calls covered
the four requested channels, the running-timer boundary at $0005, the pulse
adjustment boundary and 24-bit carry and saturation. The stock paths only wrote
the chosen timer word or left it untouched. A further 160 TipInFuelControl calls
used stock lookup tables and a supplied neutral flex factor. The selected
throttle delta $02 was ignored. With a delta of $03 and a nonzero FuelPulseBank1,
the caller reached three successive channels modulo four. With FuelPulseBank1
zero, it calculated TipInFuel and skipped timer writes and accounting.

Sixteen group cranking cases on `05293013AC` issued B=3,2,1,0 while the
stored InjectorIndex remained fixed. With the scaling flag supplied, the
routine repeatedly selected the counter addressed by the fixed RAM index.
With the flag clear, the counter stayed unchanged. EventTableCheck cleared
the scaling flag when the counters were exhausted. Sixteen IC4/OC5 cases on
`05293013AC` and `05293014AC` used the stock handler through RTI. For the
supplied second-edge state, the $05 option on 05293013AC blocked the setter.
The $81 option on 05293014AC admitted it with the engine flag, elapsed-count
and pending-edge guards satisfied. The tests model these states individually.
Their order and overlap during ordinary operation remain open.
[Exact-ROM fuel audit](https://github.com/DDex89/recore-sbec3/blob/dinofuel-128k/patches/spark/v2/stock_fuel_distance_audit.py)

From the ReCore checkout, run `python patches/spark/v2/stock_fuel_distance_audit.py`
with `04887050.bin`, `05293013AC.bin` and `05293014AC.bin` in `roms/`.

### CCD $84 scheduler, local interrupt exclusion, and possible sample loss

Source audit of 04887050 and 05293013AC. Isr_PIT ($0541A/$05426) calls
CcdTransmit ($14A72/$193BC) only after ORP #$00E0 sets IPL 7, then executes
ANDP #$FF7F to return to IPL 3. The countdown reload is $18 (24 active PIT
ticks); O2HeaterSample bypasses this scheduler branch. PITR=$0007 and
PICR=$0338 match the documented nominal 28/32768-second tick.

The contiguous 256-byte schedule preceding the 18-entry jump table
is at $144B6/$18DEC; the jump table is at $145B6/$18EEC.
Reconstructed all 128 schedule words in each source: CcdTx84FuelUsed
($14B98/$194E2) appears at zero-based slots 1,17,33,49,65,81,97,113.
The index arithmetic uses the low byte of 2*(index+1); thus the schedule
address wraps within its 256-byte window, even for arbitrary raw index bytes.
Nominal builder interval: 16*24 PIT ticks = 328.125 ms (~3.048 Hz),
not a measured delivery interval. The builder jump slots are $145C2/$18EF8.

DistancePulses is a byte at $F8466/$F8480. Isr_GPT_IC3 increments it after
a pin-level check; the CCD builder reads and clears it. No saturation
guard on the INC is present: increments wrap modulo 256. Physical
pulses per kilometre and fuel units remain unverified.
Each fuel payload count represents 2048 raw accumulator counts
(8 units of the upper 16-bit word); the cap of 255 leaves excess fuel
counts in the accumulator, not in the payload. Frame layout is
ID $84, fuel byte, distance byte, additive checksum modulo 256.

CcdTransmit invokes the builder before checking whether any of the
three queue buffers is free (CcdRxFlags bits 4,3,2).

The local CPU16 audit executed 512 cases on each ROM across all eight $84
schedule slots, all eight queue occupancy masks and eight accumulator boundary
values. It verified the first free buffer, the frame and checksum, the fuel
remainder, and the cleared distance byte. With all three buffers occupied,
the queue stayed byte-identical after the builder deducted fuel and cleared
distance. The test kept the transmitter busy to stop before BusTxStart.
[Exact-ROM queue audit](https://github.com/DDex89/recore-sbec3/blob/dinofuel-128k/patches/spark/v2/stock_bus_reference_audit.py)

Local mask evidence: CCD builder runs with IPL7; the foreground
InjectorFuelAccount raises IPL7 before its timer/accumulator RMW;
IC1 runs at IPL3 (same nominal priority as PIT), and IC3 increments
distance with IPL7. Ordinary maskable interrupt preemption between
these reviewed accumulator operations is excluded under their
entry/mask invariants. IRQ7, exception behavior, computed aliases,
foreground caller-mask contract, and actual bus timing are not
established by this local proof.

### VSS distance delta versus service-mileage retention (128 KB)

The same qualified IC3 event increments both the byte DistancePulses
and a separate retained 16-bit event word ($F8032/$F8034). The latter
sets $F830E.2/$F8325.2 on natural wrap or when the option-dependent
threshold $8333 is exceeded. Its low byte is also the running reset-key
source; it is not a separate RAM variable. The foreground mileage task
(SriMileageStore $121B8 / Sub_120DC $120DC) services the latch once per
256 main-loop passes, deferring while EEPROM request bit 7 is set.
It examines four QSPI receive words at $FFD18..$FFD1F, picks the largest
unsigned word having a circular predecessor exactly one smaller modulo
65536, and queues the next word to a cyclic EEPROM slot (0/2/4/6).
SriMileage is updated at request time, not after confirmed durable write.
The latch can coalesce events; this ring is not a lossless trip-distance
source. Physical distance per event remains uncalibrated. The CCD $84
schedule and loss limitations above still apply. Exact-ROM ring fixtures
are pending; stock code and calibration remain unchanged.

An exact-ROM check ran 80 complete IC3 handlers with already-accepted
interrupt frames and supplied pin and capture values. A high pin left
DistancePulses alone. A low pin incremented the byte, including $FF to $00.
The independent event word and its mileage flag followed the stock $8333
threshold. Each RTI restored the interrupted context in the frame model.
[Exact-ROM distance audit](https://github.com/DDex89/recore-sbec3/blob/dinofuel-128k/patches/spark/v2/stock_fuel_distance_audit.py)

