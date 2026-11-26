# Stock 128 KB knock subsystem — source audit (2026-11-26)

Scope: exact stock 04887050 (1996) and 05293013AC (1997). Source-level evidence, not machine/bench validation. No production code, calibration values, option states or RAM allocation changes. Sources: [1996 bank 0](../../src/04887050/bank0.asm), [bank 1](../../src/04887050/bank1.asm), [equates](../../src/04887050/00_equates.asm); [1997 bank 0](../../src/05293013AC/bank0.asm), [bank 1](../../src/05293013AC/bank1.asm), [equates](../../src/05293013AC/00_equates.asm).

## RAM dependencies and proposed names

| Existing label | 1996 | 1997 | Source-level role / suggested name |
|---|---|---|---|
| KnockSample6CE | F8161 | F8197 | channel 1 filtered byte; KnockChannel1Filtered |
| KnockSample6CF | F8162 | F8198 | channel 2 filtered byte; KnockChannel2Filtered |
| KnockSample6D0 | F8163 | F8199 | low-load check countdown, reload on high load; KnockSensorCheckCounter |
| KnockSampleA89 | F8320 | F8337 | RJURR1_L sample; KnockChannel1Raw |
| KnockSampleA8A | F8321 | F8338 | RJURR2_L sample; KnockChannel2Raw |
| KnockSignal | F8322 | F8339 | channel 1, or unsigned maximum of both when ROM 031F bit 6 is set |
| KnockThresholdNow | F8323 | F833A | learned noise plus table threshold (saturating) |
| KnockMapThreshold | F836E | F8388 | MAP gating threshold; produced by misleadingly named KnockSensorCheckRpm |
| KnockWindowFactor | F836F | F8389 | learned-noise blend coefficient, produced by KnockWindowRpm |
| KnockNoiseDA6 | F8370 | F838A | upper learned-noise clamp; produced by KnockNoiseMax |
| KnockNoiseDA7 | F8371 | F838B | lower learned-noise clamp; produced by misleadingly named KnockNoiseLearnWeight |
| KnockEventCount | F8372 | F838C | event/decay counter |
| KnockRetardMax | F8374 | F838E | limit produced by KnockRetardMaxCalc |
| KnockSampleDAC..DB1 | F8376..F837B | F8390..F8395 | six byte retard slots; proposed KnockRetardSlot0..5, not physical cylinder identifiers |
| KnockRetard | F8604 | F8612 | downstream retard |
| SparkAdvanceD11 | F8612 | F8620 | spark angle input to timer calculation |
| KnockSensorCheck | F837D | F8397 | lower filtered-signal diagnostic threshold; produced by misleadingly named KnockRetardMaxRpm |

Direct symbol cross-references in both bank0/bank1 sources: raw and filtered bytes and countdown accessed by KnockSample; limits written by KnockNoiseCalc and read by KnockCylinderRetard. Slot bytes cleared explicitly by KnockSample and accessed via indexed operations by KnockSample and KnockLearn (clear, sum with signed-overflow clamp, decrement toward zero). Filter update is ADD B followed by ROR B, i.e. floor((raw+old)/2) with carry retained. Countdown value 1 is not written back on the check path: repeated checks can occur until high-load reload. Fault flags and indirect aliases need lifecycle review. Names are proposals, not changes to symbols.

## Indexed domains

KnockSample 1D48A/155EC: selector tables A 1D47C/155DE = [1,0,2,3], C 1D480/155E2 = [0,2,3,1], B 1D484/155E6 = [5,0,1,2,3,4]. Options031D & 83 selects A; otherwise & 78 selects B; otherwise C. Both exact stock Options031D=02, CylinderCount=04 (ROM 51D3/51DF), Options0325=08/28, bit 4 clear. Thus under valid CylinderIndex 0..3, stock A selects 0..3; subsequent broadcast writes four bytes F8376..F8379 / F8390..F8393. Bit 4 set skips broadcast. Six-slot physical storage does not establish arbitrary option/count compatibility. Preserve 4/6-cylinder code; verify selector provenance, valid index and Z/X/Y/K integrity and forced invalid controls before closing the global gate.

KnockCylinderRetard 1D5FC/1575E: five RPM words 2000,3700,3700,3700,3700 (hex), 1C75..1C7D / 1C8D..1C95 word starts. TZY plus offset 11/13 leads to conditional five-byte learning window F8011..F8015 / F8013..F8017 with normal Z=F8000. KnockThresholdCalc reads same five bytes. RPM band tests can select fewer cells due to duplicate RPM points; exact reachability pending. No overlap of these conditional normal domains with F85F2..F85FF. No global ownership proof; do not allocate.

1997 adds CLRA before the second timer multiply (before LDAB Temp4F2 and SUBB 1D0F); 1996 uses SUBB 1CF7 without CLRA. Different D operand, not a proven stock bug. Additional learning inhibit: 1996 0144,Z bit 7; 1997 FaultSet06 bit 4 (F8169). Verify 1996 underlying fault identity and timer operand using exact CPU16 execution. Timer stores F884A/F884C (words); scratch F80F0 word, F80F2/F80F6/F80FE bytes. ADC poll has no local timeout; timing and asynchronous scratch preservation remain open.

## Confirmed documentation discrepancies / TODO

- [ ] Correct KnockRetardMaxMap descriptions in per-ROM annotations/catalogues/XDF; stale 24A5/24A6 reference in both target XDFs. Exact thresholds: RPM minimum 1CAF/1CC7, throttle 1CB0/1CC8, second RPM 1CB1/1CC9. Code: return zero if coolant or RPM below minimum; otherwise use MAP lookup if throttle below threshold OR RPM at/above second threshold; else use KnockRetardMaxLow. Note actual comparisons and stock threshold values before renaming. Preserve all addresses of editable data, formulas and stock values unless separately verified metadata error.
- [ ] Review misleading table names KnockSensorCheckRpm (1C63/1C7B, produces MAP threshold), KnockNoiseLearnWeight (1C8B/1CA3, lower clamp), KnockRetardMaxRpm (3DAD/3DD8, lower diagnostic threshold), and KnockWindowRpm coefficient description. Trace lookup input/output encoding and other family consumers before rename; sync EN/RU, hand/ported metadata, XDF and Turbonator Wiki.
- [ ] Compare 1996 KnockLearnUpdate (1D27E) with unnamed 1997 Sub_153E0; matching source structure and countdown at F8373/F838D support a candidate ported routine name and variable description. Verify exact ROM and all references before renaming.
- [ ] Verify indirect/overlapping accesses, reset initialization, diagnostics, IRQ and shared scratch lifecycle, per-cylinder mapping, calibration units, RPM-cell reachability, exact-ROM CPU16 fixtures and physical timing. CI held due to quota; no new machine test claim.

## Follow-up: learned-retard recovery, reset and persistent aliases

Source cross-reference pass (bank0, bank1 and equates of both exact target part numbers): 1996 KnockLearnUpdate 1D27E and 1997 Sub_153E0 have equivalent instruction structure and matching MainLoop scheduling branch (first seven low counter bits clear, bit 7 set). Candidate 1997 name KnockLearnUpdate; do not alter executable source. The unsigned byte F8373/F838D is a recovery counter. Coolant/MAP below gates or insufficient nonzero knock signal/count reset it; zero KnockSignalLearn under qualifying conditions increments it. At or above the calibrated threshold the counter clears and ten signed learned-retard cells F8067..F8070 / F8068..F8071 are conditionally stepped toward the limit. Proposed names KnockLearnRecoveryCounter, KnockLearnRecoveryDelay (1CD7/1CEF, stock 22 hex), KnockLearnRecoveryStep (1CD9/1CF1, stock 01), KnockLearnRecoveryLimit (1CDA/1CF2, stock 00; code negates it with saturation). No exact clock cadence established; verify scheduler and interrupt liveness. KnockLearnDecayFlag separately visits the same ten bytes once when SparkFlags.5 is set and ControlFlagsC33.7 is clear; negative cells are incremented by 1C62/1C7A, nonnegative results cleared. KnockLearn fault path clears all ten bytes. Learned-retard array is distinct from five learned-noise bytes.

Reset directly initializes learned-noise bytes F8011..F8015 / F8013..F8017 from EgrZeroPositionInit plus four adjacent ROM bytes (1996 1CF9..1CFD / 1997 1D11..1D15), stock 1C,1C,1C,3A,3A. First byte is currently named EgrZeroPos in both equate files: explicit alias, not free RAM; check EGR/knock configuration gates and all indirect consumers before changing names. Stock ROM 031F=B0 in both, knock gate C0 nonzero, bit 6 clear; Options0325 bit 6 clear in both. Reset checksum covers F8008..F8109 / F8008..F8139 inclusive, including both learned arrays. Valid checksum path clears from F810A/F813A; checksum-failure path sets X=8032/8034 and clears from there to F86FF/F8725. Thus five noise bytes retain state on valid checksum and are explicitly initialized on failed checksum; ten retard bytes retain on valid checksum and clear on failed checksum (conditional on normal bank/register state). Recovery counter cleared by both reset bulk paths. Need verify actual checksum update call sites, EGR feature coexistence, diagnostic writes and asynchronous state.

Correction of preceding KnockRetardMaxMap note: after coolant/RPM minimum guards, throttle BELOW threshold branches to MAP lookup; otherwise RPM BELOW second threshold branches to KnockRetardMaxLow; otherwise falls through to MAP lookup. Thus MAP lookup when throttle below threshold OR RPM at/above second threshold. Earlier "RPM below" wording was incorrect. With stock equal minimum/second RPM thresholds the low branch cannot be reached after minimum guard under stable sampled inputs. Verify metadata accordingly.

Remaining: exact-ROM fixtures for recovery counter boundary, signed learned cell clamp, reset valid/invalid checksum, alias/feature state and scratch integrity. No CI, source-level only.
