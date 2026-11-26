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

## Follow-up: recovery, two separate learning arrays, reset initialization

Source comparison confirms matching MainLoop call sites and control structure for KnockLearnUpdate (1996 1D27E) and Sub_153E0 (1997 153E0); proposed port label KnockLearnUpdate. Existing caller comment "Reset" is imprecise: explicit JSR in MainLoop. The byte F8373/F838D is a recovery delay counter (candidate KnockLearnRecoveryCounter). It is cleared on coolant/MAP gate failure or sufficient nonzero knock signal/event count; insufficient nonzero signal/events leave it unchanged. When KnockSignalLearn is zero with gates satisfied, increment and compare unsigned with ROM 1CD7/1CEF; on reaching threshold clear and visit ten signed learned-retard cells F8067..F8070 / F8068..F8071. Cells more negative than saturated negation of ROM 1CDA/1CF2 are advanced by ROM 1CD9/1CF1 with signed target clamp. Exact machine arithmetic, including pathological calibration values, remains pending.

KnockRpmBand producer: Scratch6 starts zero; two increments per iteration, with X moving from 1CCB to 1CCF / 1CE3 to 1CE7. Final one or two decrements select 0..9. Prior KnockLearnCellIndex influences RPM/MAP hysteresis; even/odd low/high MAP selection depends on comparison. Under normal registers this bounds KnockLearn indexed access to the same ten-byte learned-retard array. KnockLearnDecayFlag also visits all ten bytes once when its flags allow, moving negative cells toward zero. CalcSpark calls KnockLearn and stores the returned byte in KnockRetard (F8604/F8612); this is distinct from the per-cylinder slots and the five background-noise bytes. Confirm all producer paths and async Scratch6/index integrity; no global allocation conclusion.

### Incorrect EGR naming in the exact 128 KB images

Reset initializes five background-noise bytes from contiguous ROM bytes:

| | 1996 | 1997 |
|---|---|---|
| ROM initialization | 1CF9..1CFD | 1D11..1D15 |
| RAM learned noise | F8011..F8015 | F8013..F8017 |
| bytes | 1C 1C 1C 3A 3A | 1C 1C 1C 3A 3A |

The first byte of each ROM/RAM range is currently labeled EgrZeroPositionInit/EgrZeroPos. Direct source references in each bank0/bank1 pair show EgrZeroPos only written at Reset; KnockThresholdCalc reads the five-byte array and KnockCylinderRetard updates it by RPM-band selection. Candidate names KnockNoiseInit0 / KnockLearnedNoise0 and array KnockLearnedNoise[5]. This is a confirmed knock role; exclusive ownership and other family EGR semantics require indirect-access and variant review. Do not globally rename all EgrZeroPos symbols. Check XDF/category/hand annotations for the mislabeled first ROM byte and four neighboring unlabeled bytes; document stock initializer values without changing them. Distinguish these positive background-noise samples from the ten signed retard cells.

- [ ] Verify reset cold/warm branch entry and indirect aliases, including diagnostic descriptors and EEPROM/NV lifecycle for both arrays.
- [ ] Check all KnockRpmBand callers and Scratch6 interrupt liveness; add exact-ROM counter threshold, recovery/clamp, index 0..9 and noise initialization/read/update fixtures to the consolidated pending test batch. CI held.
- [ ] Reconcile candidate recovery symbols, EGR mislabels, and both arrays with exact-ROM annotation/EN/RU/XDF/Turbonator Wiki documentation; preserve stock bytes and options.

## Follow-up: NV checksum, reset and EEPROM descriptor ownership

The Reset branch checks the 16-bit additive NvChecksum (unsigned byte sum modulo 65536) against ResetCheckWord F8006, stores marker 4AB5 on match or 4AB6 on mismatch, then selects a different clear start at 0CAFE/0CC34. The terms warm/cold below mean valid/invalid retained-RAM checksum, not coolant temperature or physical power state.

| Exact stock image | 04887050 | 05293013AC |
|---|---|---|
| NvChecksum entry | 0E6BC | 0E7BC |
| Checked byte range inclusive | F8008..F8109 (258) | F8008..F8139 (306) |
| Result scratch word | F83B0 | F82FE |
| Valid-checksum branch skips noise init; clear range | F810A..F86FF | F813A..F8725 |
| Invalid-checksum branch initializes noise; clear range | F8032..F86FF | F8034..F8725 |

Both five-byte background-noise and ten-byte signed learned-retard arrays are inside the checksummed retention region. A valid checksum bypasses the explicit initializer and the clearing loop preserves both arrays; a failed checksum loads noise bytes 1C 1C 1C 3A 3A and zeroes the learned-retard array. All six current retard slots, recovery counter and raw/filtered signal bytes are in the ordinary reset clear domain in both cases. These statements concern the traced Reset branch/loop, not every subsequent asynchronous or diagnostic writer. CheckPowerDown calculates and stores NvChecksum before power removal and again on its restart path. Hardware retention across battery loss is not established. Candidate F85F2..F85FF is reset-cleared on both paths, not persistent NV RAM.

EepromReadInit/EepromWriteQueue share paired word tables. Parsed contiguous dc.b data after EepromReadByte RTS from each bank1 source (204/320 bytes, 51/80 pairs, respectively). 1996 source word table 13F84..13FE9 and destination offset table 13FEA..1404F; 1997 171A6..17245 and 17246..172E5. All destination words unique; ranges of offsets 0062..04B8 and 0353..0723, respectively. Zero entries target either knock learning array or F85F2..F85FF. Thus these ordinary table-driven EEPROM paths do not directly reload either knock learning array. No claim about arbitrary diagnostic writes, other indirect paths or physical retention. Exact binary fetch via roms/<PN>.bin returned 404; this is source-data extraction, not independent binary verification.

## Follow-up: activation and downstream dependency

Both reviewed stock images contain ROM 031F=B0 (mask C0 active, bit 6 clear): KnockSample, KnockCylinderRetard and the foreground knock preparation block are enabled, with channel 1 selected for KnockSignal and the channel-2 filtered diagnostic branch bypassed. Both raw ADC bytes are still captured. MainLoop calls KnockNoiseCalc, KnockLearnDecayFlag, KnockRetardMaxCalc, KnockThresholdCalc, KnockRpmBand in that order before CalcSpark. KnockEnrichment in bank0 reads the signed negative KnockRetard magnitude and the maximum signed per-cylinder slot (under mask ORP 00E0, then ANDP FF1F), adds with overflow clamp, multiplies by ROM 0F58/0F6B, and combines additional spark correction-derived terms. Thus changing knock semantics can affect fuel as well as spark; do not alter stock behavior. Verify caller mask restoration assumptions and exact arithmetic in pending fixtures.

Correction to earlier source-audit TODO wording: KnockRetardMaxCalc uses MAP lookup after coolant and minimum-RPM gates if throttle is BELOW its threshold OR RPM is AT/ABOVE the second threshold. Otherwise (throttle at/above threshold AND RPM below second threshold) it uses KnockRetardMaxLow. This follows CMPB/BCS to MAP, then CMPA/BCS to Low. For both stock images the two RPM thresholds have the same value (23/1C), so after the minimum-RPM gate the Low branch is unreachable under the stable input assumption. Existing XDF prose and scalar descriptions need reconciliation; no calibration changes.

- [ ] Verify all remaining reset/monitor/diagnostic computed writers, EEPROM table provenance against original bytes, and IRQ/Scratch6/mask timing. Add retained/invalid NV checksum branch, reset bounds, activation and enrichment controls to consolidated pending fixtures; no CI due to quota.

## Follow-up: Scratch6/7 ownership and foreground/ISR publication

Both ROMs map Scratch6/Scratch7 to F81F6/F81F7. A host source scan expanded named and numeric fixed Z-relative writes and overlapping words across both banks: 45 write sites in 04887050 and 46 in 05293013AC. These are shared foreground temporaries (O2, IAC, fuel, surge, diagnostics, knock); not free RAM. A conservative source control-flow traversal of all 20 named ISR roots per image found no direct writes to these two bytes in the traversed paths. The traversal follows both branch outcomes and direct calls, stopping at returns, and assumes valid Z; it is not a CPU16 machine trace.

Expanded normal table entries: IC1 0481A (4 entries both); PIT OBD state table 1D8BC/1774C (18); CCD transmit 145B6/18EEC (18); IC4 05E38/05E44 (9). After expansion, IC1 visited 4791/4947 source instruction nodes, PIT 2096/2071, IC4 245/309; no fixed direct overlap in these reached sets. Still unresolved in this traversal: IC1 ConditionTable dispatch 1F938/1FA06 (offsets 0,6,C,12; fourth target requires raw decode); PIT secondary PID dispatch 1D800/1D884 (33/14 slots) and 17B3A/17DCC/18086 (33/14/25 slots). These table counts are source-derived; no invalid-state reachability claim. Computed memory addresses, context/stack and temporal behavior remain separate. IC1 explicitly ORP 0060 and PSHM D,E,X,Y,K with matching PULM/RTI at common exit 0492C. This establishes explicit save/restore structure only; actual hardware exception frame, all exits and higher-priority interference still require proof.

Foreground lifetimes: KnockRpmBand uses Scratch6 from initial CLR through final LDAB and publishes KnockLearnCellIndex. KnockThresholdCalc stores interpolated noise into Scratch6, calls Lookup2D, then adds Scratch6 and publishes KnockThresholdNow. Neither local sequence masks interrupts. No fixed direct ISR Scratch6/7 writer identified in reviewed paths; this is not an alias/liveness closure.

KnockLearn and IC1 KnockSample share the six slot bytes. Foreground sum reads individually, and foreground decay loop L1D1D4..L1D1DC / L15336..L1533E executes a load/decrement/store without a local IRQ mask. Conditional interleaving: if IC1 updates the same slot between load and store, foreground can overwrite the newer value with its old decremented value. Multi-slot sums can also combine different observation times. This is a source-level possible interleaving, not measured occurrence, not a proven stock defect; actual interrupt recognition, caller IPL, slot selection and liveness must be tested. Do not patch it in the documentation audit.

KnockThresholdCalc similarly reads noise cells multiple times during interpolation (IC1 KnockCylinderRetard can write a cell); publication of a single byte is distinct from a coherent multi-read snapshot. Verify actual timing and caller IPL. KnockEnrichment explicitly masks IPL via ORP 00E0 before reading the slot maximum and clears mask via ANDP FF1F after, rather than saving/restoring previous IPL. It is called from MainLoop before the later knock preparation and CalcSpark in the same foreground pass, so its KnockRetard input is the previously published value (subject to startup or other writers). Do not assume spark/fuel snapshots are simultaneous. No stock code or calibration changes.

- [ ] Resolve remaining ConditionTable/PIT dispatches, computed aliases and actual caller/ISR IPL/stack timing. Add pending exact-ROM normal and forced-interleave controls for foreground slot decay and noise interpolation, and compare masked KnockEnrichment behavior. Preserve stock scheduling and behavior, document differences only. CI held.

## Follow-up: ConditionTable raw decode and expanded ISR graph (2026-11-26)

The fourth ConditionTable case is executable code emitted as dc.b, not a data record. Using repository tools/cpu16_isa.json, FA is JSR EXT20, 58 is CMPA IND8,Y, B4 is BCC REL8 (branch base instruction address+6). 1996 dispatch 1F94A raw FA 01 F9 76 calls 1F976; 1997 dispatch 1FA18 raw FA 01 FA 44 calls 1FA44. Both return to the ordinary BNE test. At 1F976/1FA44, bytes 58 03 B4 00 mean CMPA $03,Y; BCC failure (1F97E/1FA4C), otherwise fall through to CLRA. Proposed label ConditionBelow. Do not globally rename or reassemble during this documentation pass.

The list is count byte followed by four-byte descriptors (RAM offset word, operator byte, mask/threshold byte). Dispatch ROM word offsets 0,6,C,12 correspond to operator bytes 0,2,4,6. Zero flag means success; fail on first nonzero comparison. Existing labels ConditionBitSet (1F966/1FA34) pass if (value & mask)==0; ConditionBitsClear (1F96A/1FA38) pass if (value & mask)==mask; ConditionAbove (1F970/1FA3E) passes unsigned value > threshold; ConditionBelow passes unsigned value < threshold. Proposed semantic aliases ConditionRequireBitsClear, ConditionRequireBitsSet, ConditionAbove, ConditionBelow. Verify equivalent definitions in other families and EN/RU/XDF annotations. The named direct O2-heater lists (2D7D/2D40, 2DA8/2D6B) and second misfire lists (302E/3059) have zero entries in these images; first misfire lists 2FF1/301C have eight entries (four clear-bit and four above-threshold tests). Existing source comments in these lists already encode success polarity. Other descriptor consumers still need provenance.

Extended the prior source CFG through all nominal entries of ConditionTable (four including raw JSR/CMPA/BCC), OBD mode 01 tables 1D800/17B3A (33), mode 02 tables 1D884/17DCC (14), and 1997 mode 06 table 18086 (25). All 20 named ISR roots per ROM now have zero unresolved control-transfer edges in this source model of nominal table destinations. IC1 reached 4817/4973 source nodes, PIT 2392/2632, IC4 245/309. No reached fixed Z-relative writer overlaps F81F6/F81F7. Inventory identified 163/164 X/Y-indexed or E,Z write sites in this conservative reachable union. These counts are source-parser results, not executed machine paths or proof of all computed destinations. Raw bytes only decoded for identified fourth condition case; invalid table indices, arbitrary Z, indirect memory stores, stack/IRQ timing and exception paths remain open.

### 1997 mode 06 descriptor boundary observation

At 18054..18085 the source contains 25 (test ID, dispatch byte offset) pairs; offsets 00,04,..,60. The lookup loop increments X by 2 and exits on CPX 8086 / LBHI, rather than equality, so it may compare the first byte of the subsequent JMP table at 18086 when no descriptor matched. CPU16 ISA encodes that EXT20 JMP as 7A 01 81 32 (target 18132). Under a forced matching test-ID state at this boundary, the second opcode byte 01 is read as an offset; the <64 guard does not check four-byte alignment, producing a conditional non-entry dispatch. This is a static boundary observation, not a proven reachable field failure. Confirm stock binary bytes, request parser reachability, CPU16 alignment semantics and error behavior in isolated non-vehicle fixtures. The normal 25 descriptors all select aligned in-table entries. Do not change stock firmware or infer a usable diagnostic procedure.

- [ ] Reconcile ConditionBelow and success-polarity labels across metadata, engineering docs and relevant XDF descriptions; verify other condition families independently.
- [ ] Verify 1997 mode 06 boundary in exact-ROM isolated fixtures, including normal descriptor matches and rejection of unsupported values; no hardware testing of malformed requests. Continue bounded indexed-write provenance, prioritizing unreviewed PIT/OBD stores. CI held.
