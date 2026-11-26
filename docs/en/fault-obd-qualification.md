# Pending fault timing and OBD two-failure qualification

## Periodic pending-counter service: families A and B

Direct call-site evidence in src/04887050/bank0.asm and src/05293013AC/bank0.asm overrides the generated "Called from: Reset" headers. The dispatch is inside MainLoop, after CamCrankSyncMonitor. It loads MainLoopCounter and performs eight LSRA operations with branches on carry. The first seven bits must be clear and bit 7 set to enter the branch that calls FaultPendingAge: (MainLoopCounter & $FF) == $80. This is a dispatch condition, not a verified time interval in seconds; the counter update cadence must be audited separately.

The counters in ReportFault, ReportPass and FaultPendingAge cannot be described as a two-drive-cycle mechanism. The periodic age service runs during the main loop. In the inspected routines, the failure path increments a counter until the descriptor threshold; the pass-recovery path decrements its separate count; the age service reverses these trends over time. Family C and remaining call sites still need direct scheduler verification.

## Independent OBD qualification mechanism (05293190AC)

ObdFaultReport searches a ten-byte descriptor array starting at $75FA; the row count is read from $7746. The reference special-table metadata identifies this as FaultTwoTripRows, 22 rows within FaultStatusMap. Individual row contents and exact count byte still require direct ROM verification.

For a matching fault index, the descriptor comprises a fault row pointer (+0), first RAM offset (+2), first mask (+5), second RAM offset (+6) and second mask (+9). The first pair holds the previous-failure state; the second pair holds the current test result. The code checks the referenced fault row attribute bit 7 and the current result bit.

- Enabled fault with result bit set, previous-failure bit already set: call ReportFault.
- Enabled fault with result bit set, previous-failure bit clear: set previous-failure bit; if descriptor attribute bit 6 is set, call FreezeFrameCapture with A=1 and B=fault row index.
- Result bit clear: conditionally call FreezeFrameStore when FreezeFrame00 < 3 and FreezeFrame01 matches the fault row; clear both descriptor bitmap bits.
- Disabled fault: clear both descriptor bitmap bits directly.
- Unmatched index: return without applying any descriptor.

The existing names MonFlags09D/09E/09F are consistent with the first-pair state; do not replace these with drive-cycle counters. A repeated invocation with the result set is sufficient at this routine boundary. The caller-specific once-per-trip gating and retention across reset have not yet been demonstrated. MonitorFlagsClear clears both prior-failure and result bytes. Its callers and invocation conditions must be traced before proving true two-trip behavior.

## Distinct monitor-data EEPROM path (reference)

MonEnableCheck clears MonEnableFlags2.7 when its fault/flag/mileage gates fail; when the gates allow and bit 7 was clear, it sets bit 7, clears bit 6, then calls MonDataReset. MonDataReset copies persistent shadow values to working monitor data, masks bits 7 of MonData646/647, clears MonData648 and sets bit 4.

MonDataStore is gated by bit 4. It compares working values with their EEPROM shadows and queues at most one differing byte per call, subject to EepromFlags.7. It sets MonEnableFlags2.5 on a detected mismatch and clears it when no eligible mismatch exists. The EepromShadowMap in bank3 confirms EEPROM $CC-$D0 -> Z+$064C-$0650 and EEPROM $80 -> Z+$0634. The comparison for $CE ignores bit 6 and preserves the shadow's bit 6 when queuing a changed value. This path stores monitor data, not proof of persistence of the first-failure bits MonFlags09D-09F or of the full DTC history.

## Misleading routine labels (reference, candidates only)

MilFaultIncrement actually calls MilRequest, clears Z+$0122 through $014C and Z+$0500 through $0523 inclusive, and clears MilFaultCount. MilRequest ($24210) clears MilRequestFlags mask $03, DiagStatusFlags masks $08/$80 and ControlFlagsC39 mask $10. Neither routine increments MilFaultCount. Candidate names: ClearFaultHistoryAndCurrentState and ClearMilRequestState, respectively. Do not rename automatically until cross-family caller/side-effect audit is complete.

## Scope

Direct source inspection only. No executable firmware instruction changed, no build or CI executed. Remaining: actual scheduler cadence, all OBD descriptor rows and caller-specific gating, reset retention, DTC history persistence, cross-family labels and ASM regeneration.
