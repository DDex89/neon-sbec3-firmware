# Fault report/pass state: seven-family follow-up

Reviewed ReportFault in seven representative images and FaultBitTest in four 256 KB images; ReportPass reviewed in A/B/C and reference 256 KB.

| Image | FaultTable | FaultMem Z offset | FaultSet Z offset | ReportFault |
|---|---:|---:|---:|---:|
| 04887050 | 3505 | 0077 | 0133 | 1BD48 |
| 05293013AC | 3530 | 0078 | 0163 | 1E68C |
| 05007038 | 385F | 014D | 021C | 19EE4 |
| 05269833AH | 3F88 | 0122 | 0500 | 245A8 |
| 05269833AI | 3F88 | 0122 | 0500 | 245D4 |
| 05032017AA | 45F9 | 0122 | 0500 | 245D6 |
| 05293190AC | 4052 | 0122 | 0500 | 245CC |

Addresses are hexadecimal. Bitmap bases derive from ReportFault instructions; the table addresses derive from image-local special table metadata. Four reviewed 256 KB FaultBitTest routines test FaultSet (not FaultMem) at Z+$0500 plus descriptor byte +5, using the mask at +4.

ReportFault requires attribute bit 7, checks the current bitmap, and returns the already-set path without incrementing pending counters. It chooses a matching pending index or free slot; if both slots are occupied by other indices it takes the failure return path. The counter increments and must reach descriptor byte +1 before the fault is recorded. A/B/C bypass this counter only when the descriptor threshold equals 1; the four 256 KB representatives bypass it when the threshold is unsigned <=1. Upon acceptance ReportFault sets FaultMem and FaultSet. MIL count increments only when the FaultMem bit was previously clear and descriptor bit 6 is set.

ReportPass (A/B/C and reference): if FaultBitTest indicates clear, return. Otherwise, if FaultPendingWork1 is empty, store the row index and load the descriptor +1 into FaultPendingWork2, then return. If the stored row matches, decrement Work2; on zero clear Work1 and clear the matching FaultSet bit. A nonmatching row returns without changes. ReportPass does not directly clear FaultMem. Work1/Work2 are therefore a single pass-recovery index/count pair, not a third failure pending slot. Threshold-zero and row-zero edge cases require reachability review.

FaultPendingAge in all four reviewed 256 KB bank2 listings is instruction-identical: decrement the two active pending failure counts, clear the respective index on zero; increment the pass-recovery count unless it would wrap, and clear the recovery pair if the count exceeds that row's threshold. Generated caller headers identify Reset in A/B/C versus MainLoop in the reference 256 KB image. Those headers alone do not establish call frequency: verify actual call sites, gating, reset retention and timing before assigning drive-cycle semantics.

Remaining: full OBD/MIL two-trip policy, EEPROM persistence/clearing, remaining individual table rows, generated ASM synchronization and full assembly verification. No firmware instructions changed; no CI invoked. The previous helper regression test execution is not independently verified in this follow-up.
