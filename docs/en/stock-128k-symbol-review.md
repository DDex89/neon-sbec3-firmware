# Stock A/B engineering symbol and dependency review (2026-11-26)

Scope: 04887050 and 05293013AC only. Stock SBEC3 and ReCore had identical bank0, bank1 and equates blobs at stock 144e67b3f76e6778c25573dfe24e663c129fc501 and ReCore 221e73e1fc4c627cca8dbc5c80eba22840d83419. All eleven stock XDF blobs matched. ReCore-specific XDFs are separate. Preserve calibration, RAM addresses, instructions and assembler identifiers. Descriptive names are documented aliases, not global renames.

| Current symbol | Descriptive name or interpretation | A address | B address | Dependency |
|---|---|---|---|---|
| EepromAddr | EEPROM byte address word | F8486 | F84A2 | Valid below 0200 |
| EepromWrite947 | EepromAddrLow | F8487 | F84A3 | Alignment mask 03 |
| EepromData | Payload word | F8488 | F84A4 | High byte used for byte write |
| EepromWrite949 | EepromDataLow | F8489 | F84A5 | Second payload byte |
| EepromFlags | Service flags | F848A | F84A6 | 7 request, 6 word, 5 in progress, 4 split continuation; 1 readback-table work, not retry count |
| EepromWrite94B | EepromReadbackTableOffset | F848B | F84A7 | FE initial, 66/A0 terminal |
| PowerDownCount | StoredFlexEthanol (candidate) | F8344 | F835E | EEPROM 00C; compared to FlexEthanol at shutdown; additional zero tests require review |
| Unnamed VSS event word | VssQualifiedEventCounter (candidate) | F8032 | F8034 | IC3; low byte feeds ResetCheckWord |
| DistancePulses | CCD distance delta | F8466 | F8480 | Byte modulo 256, cleared before queue admission |
| SriMileage | Service-mileage ring request | F801E | F8020 | Updated before durable commit, not absolute odometer |
| RpmForBus / QSPI RX | Context-dependent receive word | FFD18 | FFD18 | MMIO, also used for SRI at reset |
| Scratch0/1 | Shared temporary / SRI slot indices | F81F0/F81F1 | F81F0/F81F1 | PIT overlap under review |
| UnexpectedIrqStack4 | Path-dependent record | F8002 | F8002 | Original D in IRQ, CCR/PK in exception |
| UnexpectedIrqStack6 | Path-dependent record | F8004 | F8004 | CCR/PK in IRQ, raw low PC in exception |
| ResetCheckWord | Running byte/complement or reset-mode marker | F8006 | F8006 | Not live checksum |
| LookupResult (NvChecksum) | Shared additive 16-bit sum | F83B0 | F82FE | Not CRC |

NvChecksum $0E6BC/$0E7BC sums F8008..F8109/F8139 inclusive (258/306 bytes). Warm clear F810A..F86FF/F813A..F8725; cold clear F8032..F86FF/F8034..F8725. Candidate F85F2..F85FF is cleared on both paths; ownership unproved. Reset 4AB5 selects warm path, mismatch yields 4AB6; exception bypasses checksum, uses 4AB5 or 4AB4 based on complement. Ordinary IRQ returns via RTI; exception resets stack and branches to reset continuation. Raw PC is not necessarily faulting instruction or bus address. OBD/PIT conditional pointer escape envelopes F0DAB..F0DB7 / F0DB3..F0DBF, no demonstrated physical fault. SIM decoding differs from flat simulator.

See [EEPROM](eeprom-128k-audit.md), [architecture](architecture.md), [SCI/PIT](sci-obd-128k.md), [fuel/CCD](fuel-pulse.md), [knock](knock-128k-audit.md) and [pinned audit](https://github.com/DDex89/recore-sbec3/blob/9487c2b6824d02828ec1d43fd88ece8300a50ef1/patches/spark/v2/INTEGRATION_GATE.md). Split-word invalidation and readback carry cases remain hypotheses; later exact-ROM fixtures pending, no new CI. Bit 0 of EepromFlags not established by reviewed A/B write service. Do not propagate names to unreviewed ROMs or convert RAM/MMIO to editable XDF addresses. Generated comments/catalogues and canonical renames require regeneration and ROM reproducibility verification. Turbonator wiki synchronization remains separate.
