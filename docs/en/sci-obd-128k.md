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
