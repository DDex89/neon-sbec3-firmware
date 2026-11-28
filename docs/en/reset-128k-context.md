# A/B reset and exception record semantics (2026-11-26)

Scope: 04887050 and 05293013AC, source review. The two context words have distinct path-dependent meanings. At F8002, historical UnexpectedIrqStack4 is now UnexpectedEventContextWord0; at F8004, historical UnexpectedIrqStack6 is now UnexpectedEventContextWord1. Both 16-bit words. Ordinary unexpected IRQ pushes D,X,K, TSX sees D at +4, CCR/PK at +6; copies these words respectively then RTI. Exception entry does not push those registers: TSX +0 is saved CCR/PK, +2 raw low PC, stored respectively, then shared reset continuation. Six named stores per ROM (two per ordinary IRQ, exception, cold reset copy); no direct named reads in reviewed banks. Raw PC is not necessarily faulting instruction or bus address. Cold copy transfers Scratch0/2/4 to flags/word1/word0, replacing accumulated flags; normal reset initializes scratch to zero. Warm branch skips that copy. Physical exception behavior and complete indirect reader inventory not proven.

ResetCheckWord F8006 holds the running VSS low byte and complement, the
shutdown NvChecksum or the transient reset marker 4AB4/5/6. Normal Reset
compares NvChecksum. Exception processing checks the VSS complement.
Marker 4AB5 selects warm startup, 4AB4 bypasses one diagnostic setup and 4AB6
selects the IacResetBaro path. Ordinary IRQ and exception processing OR a mask
into UnexpectedIrqFlags F8000. The cold copy can replace it.

Migration: stock [24d85a8](https://github.com/DDex89/neon-sbec3-firmware/commit/24d85a866641cb2b62ab62d8bbc44cacae9d8ff5), ReCore [7e585ad](https://github.com/DDex89/recore-sbec3/commit/7e585ad43d1ddc24b0a951d6cc6898a37fb0cc8d). Twelve direct source operands migrated, four port maps and two hand overlays, equates unchanged in value; exact inverse name substitution restored banks/equates. No binary or XDF edits, no new ROM execution.

## O2SwitchState address context

The four A/B images switch ZK to bank 0 before the five zero-offset reads.
XGDZ loads the first calibration pointer into IZ and the four LDZ instructions
load the remaining addresses. PULM restores Z, Y and their bank context.
The generator uses numeric $00,Z operands only in the verified ranges.

| Images | Context range, end excluded |
|---|---|
| 04887050, 04887051 | $097C0–$097F6 |
| 05293013AC, 05293014AC | $098BC–$098F2 |

An exact-ROM test exercised two descriptor bases, four rows and both
condition flags on each image. All 64 cases read five bytes from bank 0,
published their expected values and restored the saved context. $F8000
remained outside the access footprint. The hand analysis entries flow through
port.py to both images of each family. Existing IRQ and reset references retain
UnexpectedIrqFlags. [Context regression](https://github.com/DDex89/recore-sbec3/blob/dinofuel-128k/patches/spark/v2/stock_o2_context_audit.py) · [CPU16 reference manual](https://www.nxp.com/docs/en/reference-manual/CPU16RM.pdf)

## Service-mileage restore

On the four family A/B images, the cold path refreshes the EEPROM ring
and publishes its first word to SriMileage. The $4AB5 branch bypasses
this copy. On the next mileage event the foreground applies the separate
circular predecessor rule. The exact-ROM audit covers four slot positions
and supplied whole-word and mixed-byte outcomes. Actual persistence after
power loss remains a bench check. [EEPROM and SRI results](eeprom-128k-audit.md#sri-restart-at-a-write-boundary)

The SRI scan's live Scratch0/1 pair survived 768 supplied ordinary PIT
interleavings across the four ROMs. The separate ordinary EEPROM queue
test confirmed 19 readback destinations in the family B upper RAM page.
Include these bytes in the global stack and reset ownership review.
[PIT and readback results](eeprom-128k-audit.md#pit-during-sri-ring-selection)

## RAM clear boundaries

Executed the stock marker check and the complete zeroing loop from four
exact ROMs. Marker $4AB5 enters the warm path. The audit verified the
$4AB4 and $4AB6 fall-through and resumed at the final cold setup after
the intervening initialization. Both paths clear consecutive words.

| ROMs | Warm clear, inclusive | Cold clear, inclusive |
|---|---|---|
| 04887050, 04887051 | $F810A–$F86FF | $F8032–$F86FF |
| 05293013AC, 05293014AC | $F813A–$F8725 | $F8034–$F8725 |

All 16 slices cleared $F85F2–$F85FF and preserved the bytes immediately
outside the corresponding clear range. The test supplies the marker and
bank context, and ends before the following reset actions. It establishes
initialization coverage. Runtime ownership of the range remains open.
[Exact-ROM reset regression](https://github.com/DDex89/recore-sbec3/blob/dinofuel-128k/patches/spark/v2/reset_validity_audit.py)
