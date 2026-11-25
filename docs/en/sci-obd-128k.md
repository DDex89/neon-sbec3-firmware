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
