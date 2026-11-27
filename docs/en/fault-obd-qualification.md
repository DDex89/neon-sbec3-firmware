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

The first-pair bytes are named ObdPriorFailSwitch, ObdPriorFailO2 and ObdPriorFailMisc. A repeated invocation with the result set is sufficient at this routine boundary.

## Reset retention on the five stock 256 KiB images

The same 22-row mechanism was exercised on 05293190AC, 05269833AH, 05269833AI, 05269834AJ and 05032017AA. Its row block and count move to $7629/$7775 on 05032017AA. The prior-failure bytes are $F809D–$F809F on the first four and $F809E–$F80A0 on 05032017AA. The corresponding current-result bytes are $F8658–$F865A throughout.

The tests executed the end of CheckPowerDown, including the stock NvChecksum call, the store to ResetCheckWord, and the jump to Reset. NvChecksum sums $F800A–$F82ED. It includes the prior-failure bytes. The current-result bytes lie beyond the checked range. With the saved checksum intact, Reset chose marker $4AB5. All three prior bytes survived through ObdResetInit to MainLoop, and all three result bytes cleared. With a deliberately mismatched saved checksum, Reset chose $4AB6 and cleared both groups. The ten startup runs supplied peripheral-ready status and zero QSPI receive data. The 513 distinct-per-image EEPROM restore destinations and their fixed service-byte stores exclude both groups. [CPU16 reference manual](https://www.nxp.com/docs/en/reference-manual/CPU16RM.pdf)

Across 550 direct qualification calls, every row was checked for an initial failure, a repeat, a successful result, and a new failure after each reset path. The enabled rows numbered 12, 12, 12, 16 and 6 in the ROM order above. A repeat with retained first-failure state called ReportFault and set its history bit. With cold-reset state, the same supplied failure set the prior bit on enabled rows. In 15 separate calls across three clear routines, MonitorFlagsClear zeroed both groups, while ObdClearCodes and ClearFaultHistoryAndCurrentState preserved them individually. The stock OBD, SCI and diagnostic clear paths in bank 3 call the three routines in sequence.

## Verified qualification at two monitor entry points

SwitchMonitors selects VssMonitor at counter phases $1F, $3F, $5F, $7F, $9F, $BF, $DF and $FF on all five images. The 1,280 phase checks ran MainLoopCounters and the actual branch to the VSS call. In 30 isolated VssMonitor calls with eligible inputs, a first qualified P0500 failure set the prior and result bits. The same failure sample with the result bit already set skipped ObdFaultReport. After warm reset cleared the result and preserved the prior flag, a new qualified failure wrote the history bit. After cold reset it began qualification again. A qualifying nonzero-speed sample cleared the paired bits.

The 25 isolated TransMilRequest calls checked its guards and two P0700 paths. The direct branch reached ReportFault without a prior-failure flag when a newly received transmission status satisfied its guards. The exact 05269834AJ and 05032017AA descriptors accepted it and recorded P0700. The other three descriptors rejected it. A separate transmission-status branch entered ObdFaultReport for first-failure qualification.

Run `python patches/spark/v2/stock_obd_reset_retention_audit.py` from ReCore with the five 256 KiB ROMs in `roms/`. [Exact-ROM regression script](https://github.com/DDex89/recore-sbec3/blob/dinofuel-128k/patches/spark/v2/stock_obd_reset_retention_audit.py)

## Distinct monitor-data EEPROM path (reference)

MonEnableCheck clears MonEnableFlags2.7 when its fault/flag/mileage gates fail; when the gates allow and bit 7 was clear, it sets bit 7, clears bit 6, then calls MonDataReset. MonDataReset copies persistent shadow values to working monitor data, masks bits 7 of MonData646/647, clears MonData648 and sets bit 4.

MonDataStore is gated by bit 4. It compares working values with their EEPROM shadows and queues at most one differing byte per call, subject to EepromFlags.7. It sets MonEnableFlags2.5 on a detected mismatch and clears it when no eligible mismatch exists. The EepromShadowMap in bank3 confirms EEPROM $CC-$D0 -> Z+$064C-$0650 and EEPROM $80 -> Z+$0634. The comparison for $CE ignores bit 6 and preserves the shadow's bit 6 when queuing a changed value. These EEPROM shadows have separate destinations from the first-failure and result bytes.

## Fault history and MIL state clearing (05293190AC)

ClearFaultHistoryAndCurrentState calls ClearMilRequestState, clears Z+$0122 through $014C and Z+$0500 through $0523 inclusive, and zeroes MilFaultCount. ClearMilRequestState ($24210) clears MilRequestFlags mask $03, DiagStatusFlags masks $08/$80 and ControlFlagsC39 mask $10.

## Scope

The periodic service was checked on 128 KiB ROMs. The 256 KiB cases cover the modeled reset and tested routine states. Electrical standby-RAM retention through power loss, actual key timing, elapsed scheduler cadence, and the preceding state for other monitor callers remain open.
