# Stock 128 KiB SBEC3: SCI/PIT diagnostic state machine

Scope: stock 04887050 (1996) and 05293013AC (1997) only. Do not extrapolate to 05293190AC (256 KiB), FCC or other images.

| Existing symbol | 04887050 | 05293013AC | Meaning |
|---|---|---|---|
| SciInterrupt | $1E464 | $186BC | SCI ISR body |
| ObdRequest | $1D904 | $17794 | PIT diagnostic state machine |
| SciTimer | $F824D | $F8268 | state index, not elapsed time |
| SciReplyState | $F8251 | $F826C | saturating service-call age, reset by SCI ISR |
| SciPointer | $F824F | $F826A | timeout countdown reloaded to $0AE7 |
| ObdRequestId | $F8253 | $F826D | received-byte count, not service identifier; saturates at 7 |
| Receive buffer | $F8254–$F825A | $F826E–$F8274 | seven slots; last overwritten after saturation |
| Scratch0 | $F81F0 | $F81F0 | shared scratch byte, also high byte of saved Y word |

Existing labels are retained for compatibility; this glossary disambiguates them. State $0D initializes receive, enables RIE and clears age/count; $0E waits for/dispatches a request. Each error-free SCI receive resets age and timeout. After the last receive, the first 12 allowed service calls wait; the 13th can dispatch if other gates pass. Successful clear advances to $0F. Invalid checksum or RefPeriod <= $30 returns to $0D; CrankFlags2.1 and DiagBusFlags.4 block service before incrementing age. 04887050 additionally gates ObdRequest on Options0325.6; 05293013AC does not have that entry gate. Both SCI and PIT are nominal IPL3. Same-level nesting is not required.

CrankFlags2.6 latches raw EngineRpm reaching $1900. Bit 1 is not a reliable current-RPM predicate after this latch: isolated stock timer tests yield $82/$C0/$C0 from $80 for below/at/below threshold.

## Conditional scratch conflict — open

Foreground ObdFaultProcess saves Y in Scratch0. PIT MonitorFlagsClear calls ObdRecordFlags, which leaves $0D in the high byte. PIT restores registers but not that byte. Conditional erroneous Y addresses for 13 descriptor offsets: $F0DAB–$F0DB7 / $F0DB3–$F0DBF. Not all row liveness is proven. No hardware defect or safe allocation claimed.

[Detailed pinned audit](https://github.com/DDex89/recore-sbec3/blob/a97cbced64ccabc62c4eed17a68cbaf1b05c6880/patches/spark/v2/INTEGRATION_GATE.md); [CI 45710722294](https://github.com/DDex89/recore-sbec3/actions/runs/45710722294) resource jobs [1996](https://github.com/DDex89/recore-sbec3/actions/runs/45710722294/job/139544225166) and [1997](https://github.com/DDex89/recore-sbec3/actions/runs/45710722294/job/139544225694) passed the exact-ROM synthetic receive-init, five received bytes and 13 service-call sequence and four negative controls each (checksum, period, crank and diagnostic blockers), plus isolated timer/clear tests. Physical handshake, IRQ delivery, actual foreground overlap and invalid-address behavior remain open. No production or calibration changes.

2026-11-26 follow-up: exact-ROM scripted state-0 initialization passed [CI 45713933073](https://github.com/DDex89/recore-sbec3/actions/runs/45713933073) in both images (1083/1268 service calls for two paths, four controls each). 1996 state 6 ($1DAF8) now named SciHandshakeSendKeyByte2 instead of misported IacTestToggle; actual IAC output test is $136C8. 1997 and reference IAC labels are unchanged. No hardware timing proof.

## SCI indexed RAM access — verified 2026-11-26

Scope remains exactly 04887050 and 05293013AC, with stock Z=$F8000.

| Access | 04887050 | 05293013AC |
|---|---|---|
| RX indexed write, inclusive | $F8254–$F825A | $F826E–$F8274 |
| TX indexed read, inclusive | $F825D–$F835B | $F8277–$F8375 |

The RX store uses the previous count for values 0–6; for count >=7 it overwrites slot 6 without normalizing the count. TX indexed access is read-only; the range above is a conservative bound across arbitrary byte index and limit, not the nominal frame length. Neither domain overlaps the reviewed scratch regions or ReCore candidate $F85F2–$F85FF under the stock Z premise.

[ReCore CI 45714450145](https://github.com/DDex89/recore-sbec3/actions/runs/45714450145), resource jobs [04887050](https://github.com/DDex89/recore-sbec3/actions/runs/45714450145/job/139557032063) and [05293013AC](https://github.com/DDex89/recore-sbec3/actions/runs/45714450145/job/139557032236), passed 768 isolated exact-ROM indexed cases per image (1536 total). All 30 jobs in that run completed successfully. See the SCI label and indexed access section of the [ReCore integration gate](https://github.com/DDex89/recore-sbec3/blob/dinofuel-128k/patches/spark/v2/INTEGRATION_GATE.md).

These are runtime RAM domains, not ROM calibration offsets; do not add them as editable stock XDF entries. Arbitrary Z, PIT/GPT computed writes, physical IRQ timing and global scratch/RAM ownership remain open. No stock code or calibration change.

## PIT response and fault-history bounds — 2026-11-26

| Stock ROM | Checksum write (inclusive) | Fault-list payload write (inclusive) |
|---|---|---|
| 04887050 | $F8261–$F8267 | $F8261–$F8266 |
| 05293013AC | $F827B–$F8281 | $F827B–$F8280 |

Checksum addresses are derived from the reviewed response lengths 5, 7, 8, 9, 10, 11 (not every byte in the envelope is a checksum destination). The two fault-list loops in each ROM initialize ObdWork to zero and bound repeated word stores to three entries while IPL is raised. [Consolidated exact-ROM CI 45716139993](https://github.com/DDex89/recore-sbec3/actions/runs/45716139993), [job log](https://github.com/DDex89/recore-sbec3/actions/runs/45716139993/job/139562557938): 18 checksum cases and two scan controls per ROM passed; full regression jobs were skipped by scope.

Both real ROM fault tables have 208 entries (00–CF). 04887050 primary scan checks CF; 05293013AC scans to byte wrap. In 1997 the extra groups D0/E0/F0 read $F8092–$F8097, after the 26-byte real fault bitmap and before the separate list at $F8098. A forced nonzero extra group can cause a read of a post-table attribute at $3D53; the machine fixture confirms the conditional read, not a field defect. Source review shows these six bytes are cleared by ClearFaultHistoryAndCurrentState/cold reset, retained by warm reset, included in NvChecksum, and outside all aligned real ReportFault history offsets. Their normal nonzero liveness and other computed writers remain unproven. Do not reserve them or treat them as calibration offsets.

[Detailed pinned ReCore audit](https://github.com/DDex89/recore-sbec3/blob/e919251fdc800c2d0ca603ea68405af3888f0330/patches/spark/v2/INTEGRATION_GATE.md). No stock executable or XDF calibration changes.

### Local exact-ROM follow-up

On 05293013AC, seeded bytes $F8092–$F8097 contributed to NvChecksum. Isolated execution of the reset branch and clear loop preserved the seed with the warm marker and cleared it with the cold marker. Calling ClearFaultHistoryAndCurrentState also cleared the six bytes. The reset test isolates those instructions from peripheral initialization. It leaves the source of a nonzero value during normal operation open.

FreezeFrameSelect on 05293013AC reads eight pointers from the Bank 1 list at $1F144 before its zero terminator. The final three pointers are $3BFC, $3C06 and $3C74. Isolated execution cleared a matching freeze frame for each of the eight IDs, preserved a nonmatching frame on that list path, and cleared a nonmatching frame for the direct row $F01A. On 04887050, three selected rows each cleared a matching frame and preserved a nonmatching one. These tests do not establish that a given row is reached from a stock drive cycle.

The final ObdFaultAging row's first word is $0042, and the Bank 1 byte at $10042 is $17 in both exact ROMs. The effect on reachable fault history still depends on the caller state.

An additional exact-ROM scan of decoded instructions found no fixed Z-relative or fixed absolute store covering $F8092–$F8097 in 05293013AC. The scan included word overlaps and fixed MOV destinations. It leaves indexed and pointer-computed writers open.

The aging search only follows the fault descriptor when its attribute has bit 3 set. The last row compares against $17 in both stock ROMs, but fault ID $17 has attribute $03. An isolated test of $17 took the earlier branch to mark the freeze frame for update and advance its counter. An eligible nonmatching ID reached the final read and left the counter unchanged. With a stable fault ID and stock table, the final row cannot match. The separate cleanup loop at count $50 has its own row and status guards.

A bounded trace of an earlier match (fault ID $77) reached the secondary-word load with YK still zero. 04887050 read $05E0 from Bank 0 at $0F10A, where the corresponding Bank 1 field is $00C2. 05293013AC read $2901 from Bank 0 at $0F110, where the Bank 1 field is $00CA. The trace stops before the subsequent Z-relative read. The resulting physical access and effect in a running ECU are unverified. CPU16's LDY loads the low 16 bits of Y and leaves YK unchanged (CPU16 Reference Manual, Table 5-26). [Reference manual](https://www.nxp.com/docs/en/reference-manual/CPU16RM.pdf)

In the 05293013AC F01A caller slice, ObdFaultProcess clears a nonmatching frame when primary status bit 4 is set, bit 5 is clear, and Scratch4 bit 7 is clear. Five cases cover the clear and the blocking controls. The F01A row has attribute bit 7 clear, so ObdResetInit skips its clear branch. The aging cleanup starts at F0A6 and does not visit F01A. The stock monitor sequence producing the seeded status at the caller is still open.

All four ConditionTable predicates ran locally against the masks and thresholds from the stock lists. There were 773 isolated cases for 04887050 and 768 for 05293013AC. The tests cover all-clear and all-set masks and strict unsigned comparisons above and below the threshold.

### Stock monitor gating and history producers

F01A is the second-bank catalyst row for 05293013AC. Selector $0006 dispatches to $1B9A6, and the primary status is MonStatusCatBank2 at Z+$00B4. The option record at $1F5D4 requires $032C.5, which is clear in stock. Six exact-ROM cases initialized the status with bit 7 set or clear. ObdRecordFlags cleared bit 7 in every case and the stock row scheduler skipped the monitor. The previously demonstrated direct frame-clear behavior requires a status already admitted to ObdFaultProcess. Stock re-arm and intact row state exclude that predecessor. A whole-vehicle trace and possible indirect status changes remain unverified.

ReportFault was run for all 208 aligned descriptors in each of 04887050 and 05293013AC with empty and primed pending states, for 832 calls. The history bit was set in 122 and 114 cases respectively. No tested 05293013AC call wrote $F8092–$F8097. The 80-byte EepromReadInit restore loop for 05293013AC also completed in the simulator with a successful mocked byte service. It left those six bytes intact. Other computed writers and asynchronous state remain open.

The earlier match in 04887050 uses bit 1 of PurgeVaporEstimate at $F85E0 to decide whether to advance the freeze-frame counter. Two isolated calls seeded that byte and the descriptor-selected status byte with opposite bit values. The counter followed PurgeVaporEstimate in both cases. This confirms the effect on the isolated 1996 path. The corresponding 1997 trace remains bounded before the computed read and its physical effect is unknown.

See [stock bench validation](sbec3-bench-validation.md) for the verified reset configuration, local exception coverage and evidence to collect on the available boards.

### Verified software paths and bench limits

On 04887050 and 05293013AC, each of 17 FaultListAdd cases covered a possible first match, empty slot or full window. Accesses stayed within the corresponding 11-byte list window (apart from the call stack). All 208 aligned ReportPass rows per ROM were tested with a primed pending expiry. Each path left the history bitmap intact. On 05293013AC both paths exclude $F8092–$F8097. These results close the regular list and report/pass producer checks for aligned stock descriptors and intact register state.

EepromReadInit was traced on 04887050 (51 byte destinations), 05293013AC (80), 05007038 (88) and 05293148AA (88). A supplied byte service modeled a successful restore and a carry-set failure at every possible read position, for 311 cases. Every failure left the failing and subsequent destinations untouched. The 1997 history padding, the 128 KiB ReCore RAM candidate on 04887050/05293013AC, and the two watched family C latch bytes were preserved in their respective cases. The tests stop before QSPI startup and leave peripheral behavior, other computed writers and asynchronous ownership open.

### Computed OBD record destinations

All 13 aligned ObdRecordClear entries per ROM were executed on 04887050, 05293013AC, 05007038 and 05293148AA. Each call zeroed exactly the three byte destinations selected by its secondary descriptor and balanced the stack. The four ROMs each have 16 distinct secondary clear destinations. The protected domains for this run were the 128 KiB ReCore candidate Z+$05F2–$05FF on A/B, history padding Z+$0092–$0097 on 05293013AC, and Z+$00B6/$02CF on the family C ROMs.

ObdResetInit preserved the applicable protected domain in 364 isolated cases per ROM (13 individual rows, seven primary status values, and four secondary counter values). ObdRecordFlags and clean-state ObdResetInit also preserved those bytes. The run covers these descriptor-driven paths with intact CPU state. An additional 1,248 cases per ROM covered every pair of rows with status $02/$22 and counter 0/3 on each row. All preserved the protected bytes. Larger combinations, other computed writers and asynchronous interrupt overlap remain open.
