# Pending fault timing and OBD two-failure qualification

## Periodic pending-counter service: families A, B and C

MainLoop calls MainLoopCounters before the phase dispatch in 04887050, 05293013AC, 05007038 and 05293148AA. Exact-ROM tests ran the real counter increment and all 256 dispatch phases on each image. The branch selects FaultPendingAge only at MainLoopCounter = $80, once per regular 256-pass rollover. The two unrelated calls immediately before FaultPendingAge were skipped in the dispatch test. Elapsed time in seconds depends on the main loop on the ECU.

ReportFault increments its pending count toward the descriptor threshold. FaultPendingAge decrements the two active pending counts and clears their IDs at zero. For the separate recovery state used by ReportPass, it increments the age and clears the pair when the incremented value exceeds the descriptor threshold. The 3,047 isolated age cases covered all aligned fault indices on the four images at and around those thresholds. Writes stayed in the six pending and recovery bytes. This mechanism runs periodically within a drive cycle. [Exact-ROM regression script](https://github.com/DDex89/recore-sbec3/blob/dinofuel-128k/patches/spark/v2/stock_obd_failure_audit.py)

## Independent OBD qualification mechanism (05293190AC)

ObdFaultReport searches 22 ten-byte descriptors starting at $75FA within FaultStatusMap ($758C). FaultTwoTripRows is the count byte ($16) at $7746. A separate cross-family audit verified the prior-failure and result offsets across the corresponding table on the 256 KiB images. [Diagnostic symbol canonicalization](diagnostic-symbol-canonicalization.md)

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

## Downstream oxygen and warm activity callers

The first downstream high/low failure for an enabled DTC sets the prior and current-result bits through O2DownCircuitCheck. The current-result bit blocks an immediate repeat. After a modeled warm reset, a fresh qualified failure records P0137 or P0138 on 05293190AC, 05269833AH, 05269833AI and 05269834AJ. P0157 and P0158 are disabled on all five images. On 05032017AA all four downstream circuit fault descriptors are disabled.

The tested high fault starts above raw $42 and the low fault starts below $04. Counting uses MainLoopPhaseMask $08 for high and $80 for low. The 1,280 phase checks confirm one selected high phase per 16 passes and one low phase per 256 passes. The fault-count thresholds are $96 high and $1C low, with a low threshold of $13 on 05032017AA. The pass thresholds are $4B high and $0A low. These are firmware counts. [Reference bank 2 source](../../src/05293190AC/bank2.asm)

A qualifying healthy sample with a retained prior failure sets a completion bit in MonFlags101 and its matching hold bit in O2DownFlags. O2DownResult waits while the hold bit is set. Warm reset preserves the completion and clears the hold. The next O2DownResult call clears the prior failure through ObdFaultReport without writing history. The cold controls cleared both the completion and prior flags.

In O2ActivityWarm, a running downstream P0140 test below speed threshold $50 takes a distinct branch on 05269833AH. At $4F, AH calls ObdFaultReport with a clear result and clears the supplied prior-failure flag. The other four ROMs cancel the test at that speed and leave the supplied flags intact. At speed $50 with raw below the bias threshold, all five take the clear path under the tested states. [AH bank 2 source](../../src/05269833AH/bank2.asm)

## Body bus, brake and park/neutral callers

BodyBusTimeout starts P1698 qualification at timeout count $C8. Only 05269834AJ and 05032017AA set the paired flags and accept a new qualified timeout after warm reset. On those two images, a supplied heard-module state below the timeout threshold sets MonFlags101.7 and O2DownFlags.7. The next warm reset keeps the former and clears the latter. BodyBusTimeout then clears the retained first failure through ObdFaultReport.

For P0703, the checked BrakeSwitchMonitor failure branch needs Options0340.5 and an enabled FaultTable descriptor. Only 05032017AA passes the option and its P0703 descriptor is disabled. 05269834AJ enables the descriptor and blocks the examined fault branch at the option. The successful-result path clears the paired bits. For P1899, the tested startup state reaches PnSwitchMonitor qualification only on 05269834AJ. A retained prior failure then records P1899. On 05032017AA the descriptor is enabled, Options0333.2 blocks the startup check, and Options0340.6 is clear, disabling the running check.

The local script ran 232 isolated caller invocations, 28 modeled resets and 1,280 phase selections on the five hash-verified ROMs. The model used stock checksum publication, supplied peripheral-ready states, and supplied sensor and bus inputs. [Exact-ROM caller script](https://github.com/DDex89/recore-sbec3/blob/dinofuel-128k/patches/spark/v2/stock_obd_caller_audit.py)

## Direct call inventory

The five exact ROMs contain 37 direct calls to ObdFaultReport each, with 34 on 05269833AH. All are in bank 2. The reference source maps them to 16 routines. The AH difference comes from EgrPositionMonitor, which has a single shared qualification call in that ROM.

| 05293190AC callers | Calls | Descriptor coverage |
|---|---:|---|
| O2ActivityWarm, O2DownCircuitCheck, O2DownResult, CatMonSwitchRatio | 9 | P0133, P0137, P0138, P0140, P0153, P0157, P0158, P0160 |
| EgrPositionMonitor | 4 | P0404 |
| TransMilRequest, BodyBusTimeout | 5 | P0700, P1698 |
| FuelSenderMonitor, ThermostatMonitor, ThermostatWarmCheck | 9 | P0460, P0462, P0463, P1281, P0125 |
| BrakeSwitchMonitor, PnSwitchMonitor, TccMonitor, IdleRpmMonitor, PspSwitchMonitor, VssMonitor | 10 | P0703, P1899, P0740, P1294, P0551, P0500 |

The inventory covers direct call sites. Full monitor traces for the remaining paths and physical timing remain open.

## Distinct monitor-data EEPROM path (reference)

MonEnableCheck clears MonEnableFlags2.7 when its fault/flag/mileage gates fail; when the gates allow and bit 7 was clear, it sets bit 7, clears bit 6, then calls MonDataReset. MonDataReset copies persistent shadow values to working monitor data, masks bits 7 of MonData646/647, clears MonData648 and sets bit 4.

MonDataStore is gated by bit 4. It compares working values with their EEPROM shadows and queues at most one differing byte per call, subject to EepromFlags.7. It sets MonEnableFlags2.5 on a detected mismatch and clears it when no eligible mismatch exists. The EepromShadowMap in bank3 confirms EEPROM $CC-$D0 -> Z+$064C-$0650 and EEPROM $80 -> Z+$0634. The comparison for $CE ignores bit 6 and preserves the shadow's bit 6 when queuing a changed value. These EEPROM shadows have separate destinations from the first-failure and result bytes.

## Fault history and MIL state clearing (05293190AC)

ClearFaultHistoryAndCurrentState calls ClearMilRequestState, clears Z+$0122 through $014C and Z+$0500 through $0523 inclusive, and zeroes MilFaultCount. ClearMilRequestState ($24210) clears MilRequestFlags mask $03, DiagStatusFlags masks $08/$80 and ControlFlagsC39 mask $10.

## Scope

The periodic service was checked on 128 KiB ROMs. The 256 KiB cases cover the modeled reset and tested routine states. Electrical standby-RAM retention through power loss, actual key timing, elapsed scheduler cadence, and the preceding state for other monitor callers remain open.
