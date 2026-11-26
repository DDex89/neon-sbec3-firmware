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
bench validation. The stock code contains four- and six-cylinder paths; changing the count byte
alone does not convert the Neon calibration to six cylinders.

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
the history initializer sets all six to FF. These are live scratch/history accesses, not a global alias or asynchronous
integrity proof.
The four-entry output pointers and the 12-byte stock per-cylinder event
table at $51F3 (four rows of three) require independent six-cylinder evidence.

Evidence: [1996 bank 0](../../src/04887050/bank0.asm),
[1997 bank 0](../../src/05293013AC/bank0.asm),
[1997 bank 1](../../src/05293013AC/bank1.asm),
[1997 equates](../../src/05293013AC/00_equates.asm).
No firmware bytes, RAM allocation, XDF, or simulator semantics changed.
Exact-ROM fixtures and hardware mapping remain pending.

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

The ported FuelEventOffset description retains a reference-image table address
$ABC3, not the actual 128 KB destination. For 04887050 the lookup curve at
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

Source-level findings only; exact-image execution and hardware verification pending.
