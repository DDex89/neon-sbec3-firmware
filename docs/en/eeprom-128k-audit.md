# EEPROM service and readback audit (128 KB A/B)

2026-11-26. Source baseline 9487c2b6824d02828ec1d43fd88ece8300a50ef1. Static source review; no CPU16 ROM execution, QSPI device simulation, hardware power interruption or CI. Stock code/calibration unchanged.

## Address and state contracts

| Routine / RAM | 04887050 | 05293013AC |
|---|---|---|
| EepromWriteService | $14188 | $1741E |
| EepromWriteQueue | $14050 | $172E6 |
| EepromReadInit | $140EA | $17380 |
| EepromPowerDownWrite | $13ED4 | $170F6 |
| EepromReadByte | $13F4C | $1716E |
| EepromStatusRead | $14144 | $173DA |
| EepromAddr word | $F8486 | $F84A2 |
| EepromData word | $F8488 | $F84A4 |
| EepromFlags byte | $F848A | $F84A6 |
| table cursor | $F848B | $F84A7 |

EepromWrite947 aliases the low byte of EepromAddr (address alignment test), EepromWrite949 aliases the low byte of EepromData (second data byte), and EepromWrite94B is a byte offset into the readback table, not a demonstrated retry counter. Flag bit 1 schedules rereading the matching table entry; both successful and error write completions can enter that path. The three identifiers have since been migrated in the reviewed A/B sources; see the migration note below. Flag bit 0 not established by this service.

Write service accepts byte addresses 0..511. For an aligned word request (address low two bits zero) it submits both data bytes in one QSPI sequence; otherwise it clears bit 6, sets bit 4 and uses two byte transactions. The second transaction increments address, copies the low data byte to the first data byte and clears bit 4. Successful first-byte verification can retain bit 7 while clearing bit 5 and invalidating address to FFFF; **critical review item:** next pass increments FFFF to 0000 unless another caller restores address. Verify the intervening queue/foreground state and exact ROM trace before classifying this as a stock defect. Error path reinitializes QSPI and reports fault when not already set, then clears request and in-progress flags; no bounded retry count proved. Invalid-address branch also clears bits 7/5 and sets address FFFF. Check residual bit 4/6 on errors.

Readback table: paired source words and destination offsets, A at $13F84/$13FEA (51 entries), B at $171A6/$17246 (80 entries). Host parsed all 131 pairs, checked unique EEPROM addresses and bounds. Cursor initialized to FE; increments by two, terminates at 66/A0. No blanket claim that all EEPROM writes are represented by this table; SRI ring 0..7 is separate. Queue reads EEPROM and copies returned byte into RAM only on carry clear; it is not a direct rewrite of failed payload. EepromStatusRead returns carry on failed read, but service compares A (and for word B) without an explicit carry check: test false-match failure cases.

## Power-down path

CheckPowerDown calls EepromPowerDownWrite separately, after stopping QSPI. This routine clears all EEPROM flags, submits a single byte, performs watchdog service and DelayLoop($1388), reads back and compares; success/failure both invalidate address. It is not a generic pending-word flush. In both variants one caller conditionally stores FlexEthanol to EEPROM $00C if absolute difference from RAM PowerDownCount is >= $18, option enabled and EEPROM fault clear; the RAM name PowerDownCount is misleading in this use. Direct zero-test consumers now traced; see the migration note below. Sudden power loss is not equivalent to this controlled path. No atomicity or data-retention guarantee established.

## Follow-up regression gates

- Model/trace actual two-byte write for addresses 0,2,4,6, boundary 0x1FF and invalid 0x200; aligned/unaligned branches, address after first verification and intervening queue calls.
- Inject failed QSPI wait/status/readback, mismatched first/second byte, residual flags; verify carry propagation and table cursor scan. Test table miss (SRI).
- SRI ring: interrupted first/second-byte updates, stale QSPI receive words and wrap through FFFF->0000; cold reset behavior and scratch-index PIT interference remain open.
- Check controlled shutdown caller sequencing, actual EEPROM device/page program semantics, power hold-up and brownout; no modifications to stock before exact-ROM verification.
- Sync symbol semantics and RAM dependencies to engineering docs, original SBEC3 and TurboNeon wiki when evidence complete. CI held.

## Initialization/readback map

### 04887050: 51 entries

EEPROM byte address → RAM offset from Z ($F8000); table order preserved. Not a complete EEPROM allocation map.

| EEPROM | RAM offset |
|---|---|
| $00A | $062 |
| $00B | $063 |
| $008 | $48C |
| $009 | $48D |
| $097 | $38D |
| $098 | $38E |
| $00C | $344 |
| $00D | $48E |
| $00F | $490 |
| $062 | $491 |
| $063 | $492 |
| $064 | $493 |
| $065 | $494 |
| $066 | $495 |
| $067 | $496 |
| $068 | $497 |
| $069 | $498 |
| $06A | $499 |
| $06B | $49A |
| $06C | $49B |
| $06D | $49C |
| $06E | $49D |
| $06F | $49E |
| $070 | $49F |
| $071 | $4A0 |
| $072 | $4A1 |
| $050 | $4A2 |
| $051 | $4A3 |
| $052 | $4A4 |
| $053 | $4A5 |
| $054 | $4A6 |
| $055 | $4A7 |
| $056 | $4A8 |
| $057 | $4A9 |
| $058 | $4AA |
| $059 | $4AB |
| $05A | $4AC |
| $05B | $4AD |
| $05C | $4AE |
| $05D | $4AF |
| $05E | $4B0 |
| $05F | $4B1 |
| $060 | $4B2 |
| $061 | $4B3 |
| $090 | $4B5 |
| $091 | $4B6 |
| $092 | $4B7 |
| $093 | $4B8 |
| $1E0 | $339 |
| $1E1 | $33A |
| $1EF | $4B4 |

### 05293013AC: 80 entries

EEPROM byte address → RAM offset from Z ($F8000); table order preserved. Not a complete EEPROM allocation map.

| EEPROM | RAM offset |
|---|---|
| $008 | $4A8 |
| $009 | $4A9 |
| $097 | $3A7 |
| $098 | $3A8 |
| $00C | $35E |
| $00D | $4AA |
| $00F | $4AC |
| $062 | $4AD |
| $063 | $4AE |
| $064 | $4AF |
| $065 | $4B0 |
| $066 | $4B1 |
| $067 | $4B2 |
| $068 | $4B3 |
| $069 | $4B4 |
| $06A | $4B5 |
| $06B | $4B6 |
| $06C | $4B7 |
| $06D | $4B8 |
| $06E | $4B9 |
| $06F | $4BA |
| $070 | $4BB |
| $071 | $4BC |
| $072 | $4BD |
| $050 | $4BE |
| $051 | $4BF |
| $052 | $4C0 |
| $053 | $4C1 |
| $054 | $4C2 |
| $055 | $4C3 |
| $056 | $4C4 |
| $057 | $4C5 |
| $058 | $4C6 |
| $059 | $4C7 |
| $05A | $4C8 |
| $05B | $4C9 |
| $05C | $4CA |
| $05D | $4CB |
| $05E | $4CC |
| $05F | $4CD |
| $060 | $4CE |
| $061 | $4CF |
| $090 | $4D1 |
| $091 | $4D2 |
| $092 | $4D3 |
| $093 | $4D4 |
| $1E0 | $353 |
| $1E1 | $354 |
| $1EF | $4D0 |
| $0CC | $50A |
| $0CD | $50B |
| $0CE | $50C |
| $0CF | $50D |
| $0D0 | $50E |
| $0D1 | $70F |
| $0D2 | $710 |
| $0D3 | $711 |
| $0D4 | $712 |
| $0D5 | $713 |
| $0D6 | $714 |
| $0D7 | $715 |
| $0D8 | $716 |
| $0D9 | $717 |
| $0DA | $718 |
| $0DB | $719 |
| $0DC | $71A |
| $0DD | $71B |
| $080 | $4E1 |
| $081 | $4E7 |
| $082 | $4E6 |
| $083 | $4E8 |
| $084 | $4E9 |
| $085 | $4EA |
| $08A | $4E0 |
| $08B | $720 |
| $08C | $71C |
| $08F | $723 |
| $0DE | $71D |
| $0DF | $71E |
| $0E0 | $71F |

## Canonical A/B symbol migration

Stock [4e9cfff](https://github.com/DDex89/neon-sbec3-firmware/commit/4e9cfff96a3018d99b125c0ed9bff58f129408b8) and ReCore [9359bc6](https://github.com/DDex89/recore-sbec3/commit/9359bc64a21efbc3de45fe4bc227277b33c38f82) migrate EepromWrite947 -> EepromAddrLow, EepromWrite949 -> EepromDataLow, EepromWrite94B -> EepromReadbackTableOffset in the A/B hand overlays, four port RAM/bit maps, and both checked-in bank1/equates sources. Addresses remain fixed; all 16 changed file blobs match between repositories. Nine instruction references and three stale inline bit comments per ROM updated. Inverse-name normalized source comparison and JSON parsing passed; no ROM/XDF changes. Full generator/build and exact-ROM regression remain pending. Other families retain legacy identifiers until independently audited.

PowerDownCount follow-up: all direct named zero-test consumers reviewed. RunModeSwitch $15200/$124E0 and B-only MonTaskB $1894E test nonzero RAM, defer while EepromFlags.7 is set, otherwise queue zero to EEPROM $00C. Together with EepromReadInit mapping $00C -> $F8344/$F835E and CheckPowerDown storing FlexEthanol there, this supports StoredFlexEthanol as the descriptive name. Indirect accesses and actual value scaling not exhaustively verified; identifier retained for a separate migration.
