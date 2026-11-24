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
