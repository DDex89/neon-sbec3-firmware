# Reference 05293190AC: two-failure descriptor and retained RAM audit

Source baseline: Original 2ea6622a586fbc570bf0a9c801b98a5a0414f7f0; bank0 blob 67f1e935715d6cbfa0b02a37a71406c3b43f15bf. ReCore follows the same annotated stock reference. All values below hexadecimal except row indices in the first column.

## FaultTwoTripRows decoded directly from bank0

FaultStatusMap begins at $758C. FaultStatusMapRows contains $2C (44); FaultTwoTripRows at $7746 contains $16 (22). ObdFaultReport at $244E2 scans rows 11–32 inclusive, beginning at $75FA. Each pointer was resolved against the actual 256 sequential ten-byte FaultTable descriptors at $4052, not just the comments.

| Map row | Fault pointer | Fault index | DTC | Pending Z offset | Result Z offset | Mask | Attributes |
|---:|---:|---:|---|---:|---:|---:|---:|
|11|47DC|C1|P0153|009E|0659|02|03|
|12|47D2|C0|P0133|009E|0659|01|C3|
|13|461A|94|P0740|009D|0658|80|03|
|14|44C6|72|P1899|009D|0658|40|03|
|15|4642|98|P0703|009D|0658|20|03|
|16|41B0|23|P0500|009D|0658|10|C3|
|17|45B6|8A|P1294|009D|0658|08|C3|
|18|4552|80|P0125|009D|0658|04|C3|
|19|419C|21|P1281|009D|0658|02|83|
|20|44D0|73|P0551|009D|0658|01|C3|
|21|453E|7E|P0138|009E|0659|80|C3|
|22|4548|7F|P0158|009E|0659|40|03|
|23|455C|81|P0140|009E|0659|20|C3|
|24|4566|82|P0160|009E|0659|10|03|
|25|466A|9C|P0137|009E|0659|08|C3|
|26|476E|B6|P0157|009E|0659|04|03|
|27|462E|96|P0463|009F|065A|80|83|
|28|4624|95|P0462|009F|065A|40|83|
|29|4638|97|P0460|009F|065A|20|83|
|30|45AC|89|P0700|009F|065A|10|03|
|31|48B8|D7|P0404|009F|065A|08|03|
|32|4412|60|P1698|009F|065A|04|03|

All 22 have trigger count 1. The report gate (attribute bit 7) is set for 12 entries and clear for 10 entries in this image's embedded descriptors; the latter follow the clear-both-bits path of ObdFaultReport. Presence in the map does not prove that a fault is enabled for this calibration or that its monitor executes. Attribute bit 6 is an additional MIL/freeze-frame gate, not the primary report enable.

## Retained RAM versus EEPROM

NvChecksum clears $F80F0–$F80FF, then sums bytes $F800A through $F82ED inclusive into a 16-bit accumulator. Reset compares the result with ResetCheckWord. On match it selects marker $4AB5 and initializes RAM starting at $F82EE; on mismatch it selects $4AB6, calls EepromReadStartup and ObdClearCodes, then initializes RAM from $F8050. The common zero-fill loop writes words through $F8FFE. Thus the ordinary valid-checksum reset preserves the first-failure bytes Z+$009D–009F and stored fault bitmap Z+$0122–013D, while clearing the current result bytes Z+$0658–065A and current fault bitmap Z+$0500–051B. NvChecksum itself clears the separate $00F0–00FF subrange before summation.

CheckPowerDown calls NvChecksum and saves ResetCheckWord before its key-off wait and again before jumping to Reset when the key returns. This demonstrates software retention across that controlled restart, conditional on the retained RAM being valid. It does not demonstrate hardware retention after disconnecting battery power. The inspected EepromShadowMap does not map these prior-failure bytes or FaultMem to individual EEPROM addresses.

MonitorFlagsClear ($2457A) explicitly clears first-failure and result bytes. Three direct calls in bank3 follow MilFaultIncrement and ObdClearCodes in diagnostic-clear paths, rather than the ordinary reset path. ObdResetInit ($20D4A) operates on monitor descriptor status bytes, including clearing per-cycle status bits, but does not directly clear MonFlags09D–09F. Indirect writes and full per-monitor qualification must still be audited.

## Scheduler and naming

The reference MainLoop directly calls FaultPendingAge when MainLoopCounter & $FF == $80, the same dispatch condition as the two inspected 128 KB representatives. The period in real time is not yet established.

Proposed labels, pending all-family cross-reference review and regeneration:
- MonFlags09D/09E/09F -> ObdPriorFailSwitch / ObdPriorFailO2 / ObdPriorFailMisc.
- MonFlags65A -> ObdResultMisc.
- MilFaultIncrement -> ClearFaultHistoryAndCurrentState.
- MilRequest -> ClearMilRequestState.

Do not equate prior-failure flags to confirmed consecutive trips for every caller: ObdFaultReport itself does not enforce an ignition cycle boundary. The retained state and fresh current result state explain how two-trip qualification can work. Individual monitor once-per-trip gating and remaining families are not yet proven.

Documentation only; no binary instruction changes, no regenerated ASM and no build/CI verification.
