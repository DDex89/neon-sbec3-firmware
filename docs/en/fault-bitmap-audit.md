# Fault bitmap and DTC audit

## Confirmed from ReportFault and image-local FaultTable metadata

| Image | FaultTable | FaultMem base (Z offset) | FaultSet base (Z offset) | ReportFault |
|---|---:|---:|---:|---:|
| 04887050 | $3505 | $0077 | $0133 | $1BD48 |
| 05293013AC | $3530 | $0078 | $0163 | $1E68C |
| 05007038 | $385F | $014D | $021C | $19EE4 |
| 05293190AC | $4052 | $0122 | $0500 | $245CC |

The fault descriptor is ten bytes: row index, trigger count, blink code, attributes, one-bit mask, bitmap byte offset, two P-code bytes, two remaining bytes. ReportFault adds byte +5 to each bitmap base and ORs byte +4 into it. Attribute bit 7 gates reporting; bit 6 increments MilFaultCount when the stored bit is newly set, and bit 5 requests the charge lamp. Bit 3 suppresses the freeze-frame path checked in this routine. The actual writer is not evidence that every row is reachable.

The two 128 KB tables above contain 208 sequential rows each; all 208 have unique bitmap positions and one-bit masks. 21 rows differ in at least one byte; six change P-code:

| Row | Bitmap offset/mask | 04887050 | 05293013AC |
|---|---|---|---|
| C0 | 19/01 | P0751 | P0133 |
| C1 | 19/02 | P0705 | P0153 |
| C2 | 19/04 | P0753 | P0139 |
| C3 | 19/08 | P0758 | P1484 |
| C8 | 18/01 | P0117 | no P-code |
| C9 | 18/02 | P0118 | no P-code |

The same bit position can therefore have different meanings in different images. P0000 is not a real code in these descriptors.

## Generator correction

Read the fault table address from the selected image's special-table annotations, bound the table by complete numbered rows, and use that same mapping in bitmap comments, fault maps, word tables and monitor descriptors. Invalid, unaligned, out-of-range and ambiguous mappings are not assigned invented P-codes. Without image-specific annotations the decoder does not fall back to the reference address.

Run the synthetic regression tests with `python3 tools/test_fault_helpers.py`. Four tests were run on the isolated helper implementation. Full source regeneration and byte-for-byte assembly verification remain outstanding; CI was not requested because of its quota limits. No firmware instructions have been edited by this change.

## Pending-report logic is not yet the two-trip MIL policy

ReportFault in the inspected families uses two pending index/count slots. It looks for a matching index or a free slot, increments its counter and compares it with descriptor byte +1 before setting the bitmaps. The 128 KB A/B and 05007038 routines bypass this on count == 1, whereas 05293190AC bypasses it for count <= 1. In 05293190AC, FaultPendingAge decrements the nonempty pending counters and clears a pending index when its count reaches zero. These counters cannot be named two-drive-cycle counters without checking the scheduling and OBD monitor state machine.

Still to audit: full two-trip MIL/readiness flow, ReportPass and OBD fault process; remaining family bitmap bases and row contents; MonEnableFlags2 producers/consumers; reference-specific constants.py fault-code inventory. Do not apply row meanings from one image to another.
