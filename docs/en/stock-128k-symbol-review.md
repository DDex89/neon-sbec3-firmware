# Stock A/B engineering symbol and dependency review (2026-11-26)

Scope: 04887050 and 05293013AC only. Stock SBEC3 and ReCore had identical bank0, bank1 and equates blobs at stock 144e67b3f76e6778c25573dfe24e663c129fc501 and ReCore 221e73e1fc4c627cca8dbc5c80eba22840d83419. All eleven stock XDF blobs matched. ReCore-specific XDFs are separate. Preserve calibration, RAM addresses and executable instructions. Confirmed EEPROM, retained ethanol and VSS names are canonical in A/B after the migrations below; other descriptive candidates remain aliases.

| Historical or existing symbol | Canonical name or interpretation | A address | B address | Dependency |
|---|---|---|---|---|
| EepromAddr | EEPROM byte address word | F8486 | F84A2 | Valid below 0200 |
| EepromWrite947 | EepromAddrLow | F8487 | F84A3 | Alignment mask 03 |
| EepromData | Payload word | F8488 | F84A4 | High byte used for byte write |
| EepromWrite949 | EepromDataLow | F8489 | F84A5 | Second payload byte |
| EepromFlags | Service flags | F848A | F84A6 | 7 request, 6 word, 5 in progress, 4 split continuation; 1 readback-table work, not retry count |
| EepromWrite94B | EepromReadbackTableOffset | F848B | F84A7 | FE initial, 66/A0 terminal |
| PowerDownCount | StoredFlexEthanol | F8344 | F835E | EEPROM 00C; compared to FlexEthanol at shutdown; zero tests queue clearing |
| Unnamed VSS event word | VssQualifiedEventCounter | F8032 | F8034 | IC3; low byte feeds ResetCheckWord |
| VSS event low byte | VssQualifiedEventCounterLow | F8033 | F8035 | Alias of word, read by MainLoop |
| DistancePulses | CCD distance delta | F8466 | F8480 | Byte modulo 256, cleared before queue admission |
| SriMileage | Service-mileage ring request | F801E | F8020 | Updated before durable commit, not absolute odometer |
| RpmForBus / QSPI RX | Context-dependent receive word | FFD18 | FFD18 | MMIO, also used for SRI at reset |
| Scratch0/1 | Shared temporary / SRI slot indices | F81F0/F81F1 | F81F0/F81F1 | PIT overlap under review |
| UnexpectedIrqStack4 | Path-dependent record | F8002 | F8002 | Original D in IRQ, CCR/PK in exception |
| UnexpectedIrqStack6 | Path-dependent record | F8004 | F8004 | CCR/PK in IRQ, raw low PC in exception |
| ResetCheckWord | Running byte/complement or reset-mode marker | F8006 | F8006 | Not live checksum |
| LookupResult (NvChecksum) | Shared additive 16-bit sum | F83B0 | F82FE | Not CRC |

NvChecksum $0E6BC/$0E7BC sums F8008..F8109/F8139 inclusive (258/306 bytes). Warm clear F810A..F86FF/F813A..F8725; cold clear F8032..F86FF/F8034..F8725. Candidate F85F2..F85FF is cleared on both paths; ownership unproved. Reset 4AB5 selects warm path, mismatch yields 4AB6; exception bypasses checksum, uses 4AB5 or 4AB4 based on complement. Ordinary IRQ returns via RTI; exception resets stack and branches to reset continuation. Raw PC is not necessarily faulting instruction or bus address. OBD/PIT conditional pointer escape envelopes F0DAB..F0DB7 / F0DB3..F0DBF, no demonstrated physical fault. SIM decoding differs from flat simulator.

See [EEPROM](eeprom-128k-audit.md), [architecture](architecture.md), [SCI/PIT](sci-obd-128k.md), [fuel/CCD](fuel-pulse.md), [knock](knock-128k-audit.md) and [pinned audit](https://github.com/DDex89/recore-sbec3/blob/9487c2b6824d02828ec1d43fd88ece8300a50ef1/patches/spark/v2/INTEGRATION_GATE.md). Split-word invalidation and readback carry cases remain hypotheses; later exact-ROM fixtures pending, no new CI. Bit 0 of EepromFlags not established by reviewed A/B write service. Do not propagate names to unreviewed ROMs or convert RAM/MMIO to editable XDF addresses. Generated comments/catalogues and canonical renames require regeneration and ROM reproducibility verification. Turbonator Wiki source synchronization started; static export pending.

## Canonical A/B symbol migration

Stock [4e9cfff](https://github.com/DDex89/neon-sbec3-firmware/commit/4e9cfff96a3018d99b125c0ed9bff58f129408b8) and ReCore [9359bc6](https://github.com/DDex89/recore-sbec3/commit/9359bc64a21efbc3de45fe4bc227277b33c38f82) migrate EepromWrite947 -> EepromAddrLow, EepromWrite949 -> EepromDataLow, EepromWrite94B -> EepromReadbackTableOffset in the A/B hand overlays, four port RAM/bit maps, and both checked-in bank1/equates sources. Addresses remain fixed; all 16 changed file blobs match between repositories. Nine instruction references and three stale inline bit comments per ROM updated. Inverse-name normalized source comparison and JSON parsing passed; no ROM/XDF changes. Full generator/build and exact-ROM regression remain pending. Other families retain legacy identifiers until independently audited.

PowerDownCount follow-up: all direct named zero-test consumers reviewed. RunModeSwitch $15200/$124E0 and B-only MonTaskB $1894E test nonzero RAM, defer while EepromFlags.7 is set, otherwise queue zero to EEPROM $00C. Together with EepromReadInit mapping $00C -> $F8344/$F835E and CheckPowerDown storing FlexEthanol there, this supports StoredFlexEthanol as the descriptive name. Indirect accesses and actual value scaling not exhaustively verified; identifier is now canonical in A/B.

## Retained ethanol and VSS canonical names

Stock [2d52496](https://github.com/DDex89/neon-sbec3-firmware/commit/2d5249633efdaaa3e843d75ab7d9ae53595d49a6), ReCore [ae9007d](https://github.com/DDex89/recore-sbec3/commit/ae9007d377e5468faa0415a003d5d7e8b92f3078). A/B hand and four port RAM maps now name StoredFlexEthanol at F8344/F835E (one byte), VssQualifiedEventCounter at F8032/F8034 (big-endian word), and VssQualifiedEventCounterLow at F8033/F8035 (alias used by MainLoop). Direct Z-relative scan included adjacent offsets; no other named or numeric direct overlapping word access identified in the reviewed banks. EEPROM readback table maps 00C to the retained ethanol byte. CheckPowerDown compares the live ethanol byte against this copy, writes at difference >=18 hex, and stores successful returned readback; RunModeSwitch and B MonTaskB request zeroing. VSS four direct word operations and one byte load per ROM retain original operand widths. Seven ethanol operands and ten VSS operands changed in total; exact inverse substitution recovered original bank text, equates validated with unchanged offsets. ReCore source fixture updated for symbolic operands; execution and full regeneration pending. Indirect aliases not exhaustively excluded; physical VSS and ethanol scaling unresolved. No global rename outside A/B.

Canonical context word names and Reset phase semantics: [reset/exception context](reset-128k-context.md).

## KnockNoiseCalc: A/B lookup semantics (2026-11-26)

Exact source: [A bank1](https://github.com/DDex89/neon-sbec3-firmware/blob/d5bb4eb74e91c56257d3bd33578cd8dd3ba91a4d/src/04887050/bank1.asm#L19738), [B bank1](https://github.com/DDex89/neon-sbec3-firmware/blob/d5bb4eb74e91c56257d3bd33578cd8dd3ba91a4d/src/05293013AC/bank1.asm#L8017). Entry 1D42A/1558C. All five Lookup2D calls use EngineRpm; instruction sequence identical.

| Legacy table | Proposed alias | A ROM / RAM | B ROM / RAM |
|---|---|---|---|
| KnockNoiseMax | KnockNoiseMax | 1C97 / F8370 | 1CAF / F838A |
| KnockNoiseLearnWeight | KnockNoiseMin | 1C8B / F8371 | 1CA3 / F838B |
| KnockSensorCheckRpm | KnockMapThresholdRpm | 1C63 / F836E | 1C7B / F8388 |
| KnockWindowRpm | KnockNoiseFilterWeightRpm | 1C7F / F836F | 1C97 / F8389 |
| KnockRetardMaxRpm | KnockSensorSignalMinRpm | 3DAD / F837D | 3DD8 / F8397 |

RAM names in table order: KnockNoiseDA6, KnockNoiseDA7, KnockMapThreshold, KnockWindowFactor, KnockSensorCheck. Identical stock raw decimal (x,y) pairs: max (48,58),(80,58),(112,68),(144,76),(176,76); min (48,22),(80,22),(112,22),(144,27),(176,27); MAP (255,146); weight (83,224),(94,245); diagnostic min (255,0).

KnockCylinderRetard L1D70E/L15872 multiplies old learned noise by the weight and KnockSignal by complementary weight (256-weight, saturated to 255 if overflow); adds high product bytes with carry handling and saturates overflow to 255. The result is bounded to min/max (upper check first); exact CPU16 rounding pending fixtures. KnockWindowRpm is an old-sample retention coefficient, not a direct timer window length. KnockSample L1D4D2/L15634 filters channel 1 by ADD/ROR; filtered signal >= KnockSignalMax OR below KnockSensorCheck qualifies HwErrorFlags.6 unless FaultSet06.3 already set. Channel 2 is analogous (HwErrorFlags.5, FaultSet0B.3), gated by ROM 031F.6. Stock lower threshold zero makes the unsigned lower failure branch impossible. This is not a final DTC lifecycle proof.

MAP equality differs by consumer: KnockLearn/KnockLearnUpdate reject below threshold; KnockSample reloads countdown at MAP >= threshold and rejects retard below threshold; KnockCylinderRetard background-noise learning rejects MAP >= threshold (L1D68E/L157F2).

Existing table descriptions and y units mult256 (lower noise bound) and spark (diagnostic minimum) are misleading. Correct A/B hand overlays, port copies, then generated catalogues and XDF as a coordinated migration; independently audit sibling images before claiming equivalent use. No changes to symbols, units, binary or source instructions in this documentation-only pass. Z-relative contextual address review, remaining monitor conditions, regeneration, exact-ROM fixtures and CI pending.
