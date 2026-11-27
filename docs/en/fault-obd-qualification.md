# Pending fault timing and OBD two-failure qualification

## Periodic pending-counter service: families A, B and C

MainLoop calls MainLoopCounters before the phase dispatch in 04887050, 05293013AC, 05007038 and 05293148AA. Exact-ROM tests ran the real counter increment and all 256 dispatch phases on each image. The branch selects FaultPendingAge only at MainLoopCounter = $80, once per regular 256-pass rollover. The two unrelated calls immediately before FaultPendingAge were skipped in the dispatch test. Elapsed time in seconds depends on the main loop on the ECU.

ReportFault increments its pending count toward the descriptor threshold. FaultPendingAge decrements the two active pending counts and clears their IDs at zero. For the separate recovery state used by ReportPass, it increments the age and clears the pair when the incremented value exceeds the descriptor threshold. The 3,047 isolated age cases covered all aligned fault indices on the four images at and around those thresholds. Writes stayed in the six pending and recovery bytes. This mechanism runs periodically within a drive cycle. [Exact-ROM regression script](https://github.com/DDex89/recore-sbec3/blob/dinofuel-128k/patches/spark/v2/stock_obd_failure_audit.py)

## Independent OBD qualification mechanism (05293190AC)

ObdFaultReport searches 22 ten-byte FaultTwoTripRows starting at $75FA. The count is read from $7746. A separate cross-family audit verified the prior-failure and result offsets across the corresponding table on the 256 KiB images. [Diagnostic symbol canonicalization](diagnostic-symbol-canonicalization.md)

For a matching fault index, the descriptor comprises a fault row pointer (+0), first RAM offset (+2), first mask (+5), second RAM offset (+6) and second mask (+9). The first pair holds the previous-failure state; the second pair holds the current test result. The code checks the referenced fault row attribute bit 7 and the current result bit.

- Enabled fault with result bit set, previous-failure bit already set: call ReportFault.
- Enabled fault with result bit set, previous-failure bit clear: set previous-failure bit; if descriptor attribute bit 6 is set, call FreezeFrameCapture with A=1 and B=fault row index.
- Result bit clear: conditionally call FreezeFrameStore when FreezeFrame00 < 3 and FreezeFrame01 matches the fault row; clear both descriptor bitmap bits.
- Disabled fault: clear both descriptor bitmap bits directly.
- Unmatched index: return without applying any descriptor.

The first-pair bytes are named ObdPriorFailSwitch, ObdPriorFailO2 and ObdPriorFailMisc. A repeated invocation with the result set is sufficient at this routine boundary. MonitorFlagsClear clears both prior-failure and result bytes. Caller-specific once-per-trip gating and retention across reset remain open.

## Distinct monitor-data EEPROM path (reference)

MonEnableCheck clears MonEnableFlags2.7 when its fault/flag/mileage gates fail; when the gates allow and bit 7 was clear, it sets bit 7, clears bit 6, then calls MonDataReset. MonDataReset copies persistent shadow values to working monitor data, masks bits 7 of MonData646/647, clears MonData648 and sets bit 4.

MonDataStore is gated by bit 4. It compares working values with their EEPROM shadows and queues at most one differing byte per call, subject to EepromFlags.7. It sets MonEnableFlags2.5 on a detected mismatch and clears it when no eligible mismatch exists. The EepromShadowMap in bank3 confirms EEPROM $CC-$D0 -> Z+$064C-$0650 and EEPROM $80 -> Z+$0634. The comparison for $CE ignores bit 6 and preserves the shadow's bit 6 when queuing a changed value. This path stores monitor data, not proof of persistence of the first-failure bits MonFlags09D-09F or of the full DTC history.

## Fault history and MIL state clearing (05293190AC)

ClearFaultHistoryAndCurrentState calls ClearMilRequestState, clears Z+$0122 through $014C and Z+$0500 through $0523 inclusive, and zeroes MilFaultCount. ClearMilRequestState ($24210) clears MilRequestFlags mask $03, DiagStatusFlags masks $08/$80 and ControlFlagsC39 mask $10.

## Scope

The periodic service was checked in the 128 KiB CPU16 model with local ROMs. The 256 KiB reference qualification and persistence descriptions are based on source and table inspection. Elapsed scheduler cadence, caller-specific trip gating, reset retention and DTC persistence remain open.
