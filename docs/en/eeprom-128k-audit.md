# EEPROM service and readback audit (128 KB A/B)

The source review started from 9487c2b6824d02828ec1d43fd88ece8300a50ef1 on
2026-11-26. The service-mileage section adds stock CPU16 execution with
supplied QSPI replies.

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

Write service accepts byte addresses 0..511. The CPU16 BRSET instruction branches only if every selected bit is set (CPU16RM, p. 6-67, https://www.nxp.com/docs/en/reference-manual/CPU16RM.pdf). Thus BRSET EepromAddrLow,#03 selects split transaction only at address mod 4 = 3, not every nonzero low pair. Host enumeration of 512 valid addresses gives 128 split and 384 combined word-request branches; SRI slots 0,2,4,6 all take the combined branch. The split path sets bit 4 and clears bit 6. On a successful first-byte check, bit 4 skips the first explicit request clear but reaches common cleanup BCLR EepromFlags,#A0, which clears both bit 7 and bit 5, then invalidates EepromAddr to FFFF. Bit 4 remains set, and bit 1 schedules readback-table work. The next EepromWriteService call returns immediately unless another caller reasserts bit 7; there is no automatic next-byte continuation proved. Investigate queue/caller interleaving and hardware write boundaries for split addresses. This corrects earlier descriptions of misalignment and retained bit 7; no field defect is demonstrated. Error path reinitializes QSPI and reports fault when not already set, then clears request and in-progress flags; no bounded retry count proved. Invalid-address branch also clears bits 7/5 and sets address FFFF. Check residual bit 4/6 on errors.

Readback table: paired source words and destination offsets, A at $13F84/$13FEA (51 entries), B at $171A6/$17246 (80 entries). Host parsed all 131 pairs, checked unique EEPROM addresses and bounds. Cursor initialized to FE; increments by two, terminates at 66/A0. No blanket claim that all EEPROM writes are represented by this table; SRI ring 0..7 is separate. Queue reads EEPROM and copies returned byte into RAM only on carry clear; it is not a direct rewrite of failed payload. EepromStatusRead returns carry on failed read, but service compares A (and for word B) without an explicit carry check: test false-match failure cases.

## Power-down path

CheckPowerDown calls EepromPowerDownWrite separately, after stopping QSPI. This routine clears all EEPROM flags, submits a single byte, performs watchdog service and DelayLoop($1388), reads back and compares; success/failure both invalidate address. It is not a generic pending-word flush. In both variants one caller conditionally stores FlexEthanol to EEPROM $00C if absolute difference from RAM PowerDownCount is >= $18, option enabled and EEPROM fault clear; the RAM byte is now named StoredFlexEthanol. Direct zero-test consumers are traced below. Sudden power loss is not equivalent to this controlled path. No atomicity or data-retention guarantee established.

### CheckPowerDown gates and stored ethanol

The low bit of Options0324 is clear on all four archived family A/B
images. On 04887050 and 05293013AC the stock key-off tests entered from
the actual MainLoop call site, checked the key and reference-period
guards, and reached Reset with the checksum for marker $4AB5 on the
completed paths. The stock option kept the StoredFlexEthanol write path
inactive.

Ten stock entry checks included four completed key-off traces. With
the key held off, the supplied A and B cases executed 81,366 and 179,299
PowerInputHold iterations including the terminal heater-monitor hold.
The early key-on controls completed after one hold iteration. Those
are instruction-loop counts. The model supplies key and ADC states.
In these stock traces the already queued EEPROM address, data and flags
were preserved at the reset boundary.

Forty conditional checks entered the existing instruction stream after
the option gate with unchanged ROMs. Differences $17, $18 and $19 were
tested in both directions. With the EEPROM fault gate clear, an absolute
difference of at least $18 requested a single-byte write to $00C. A
matching readback updated StoredFlexEthanol. Enable, program and verify
timeouts and a readback mismatch preserved the previous RAM value. The
conditional paths continued through the stock NvChecksum publication
and Reset check. Real power hold, device timing and persistence on loss
of power remain open.
[Exact-ROM power-down audit](https://github.com/DDex89/recore-sbec3/blob/dinofuel-128k/patches/spark/v2/stock_power_down_audit.py)

Run `python patches/spark/v2/stock_power_down_audit.py` from ReCore with
both primary 128 KiB ROMs in `roms/`.

## Follow-up regression gates

- Extend non-ring checks to callers and readback table entries beyond the tested limits.
- Check the device behavior of interrupted SRI writes, stale QSPI words and scratch-index PIT interference.
- Check controlled shutdown caller sequencing, actual EEPROM device/page program semantics, power hold-up and brownout; no modifications to stock before exact-ROM verification.
- Sync symbol semantics and RAM dependencies to engineering docs, original SBEC3 and TurboNeon wiki when evidence complete. CI held.

## Exact-ROM service-mileage transactions

On 04887050 and 05293013AC the stock startup refreshed the four receive
words, SriMileageStore queued one word and EepromWriteService programmed
both bytes together at $00, $02, $04 or $06. A new mileage event stayed
latched while a request was active. With matching device status and
readback, the service cleared the request, activity and word flags and
invalidated the address. The readback table missed the SRI slot. The
subsequent ring refresh used the updated contents from the modeled device.

At $FFFF to $0000, the refreshed ring still contained a valid pair with
$FFFF as its numerically greatest word. The next event queued $0000 to
the same slot again. This was reproduced with both images, from each of
the four slot positions. Normal progression and the $FFFE boundary also
ran through complete write and readback.

Each image passed 12 two-write sequences, six isolated failures, three
successes at the 255th QSPI poll and a sequence of ten failed requests.
The failed paths included a busy status, sequence timeouts and mismatches
in both verified bytes. They cleared the request and activity flags
without rolling back the already published SriMileage. EepromFlags.6
remained set on the checked failures except the low-byte mismatch.
The ninth consecutive failed request recorded P1696 and the tenth
skipped another ReportFault call. A new request was required to attempt
another write. Neighboring RAM, the candidate RAM range and modeled device
bytes outside $00–$07 were preserved in the checked cases.

Run `python patches/spark/v2/stock_vss_eeprom_audit.py` from ReCore with
the four archived A/B ROMs in `roms/`. The device model supplies QSPI
replies and a byte store. [Exact-ROM mileage audit](https://github.com/DDex89/recore-sbec3/blob/dinofuel-128k/patches/spark/v2/stock_vss_eeprom_audit.py)

### SRI restart at a write boundary

04887050, 04887051, 05293013AC and 05293014AC passed 256 paired cold/warm
checks. Per ROM the fixture crossed the four write positions, starting
values $02FF and $FFFF, and eight supplied persistence states from request
through refresh. The two mixed-byte states retain either the old high
or the old low byte. The reported stage describes where the software ran
before the snapshot. The byte outcomes are inputs to the device model.

The cold reset sequence at $0CA90/$0CB90 calls QspiStartupConfig, then
copies the first QSPI word at $FFD18 into SriMileage at $F801E/$F8020.
This path reads offset $00 of the refreshed EEPROM ring directly. In
192 of 256 cases this value differed from the newest eligible ring word.
The matching-marker branch for $4AB5 skips this copy. The fixture seeds
retained RAM to check that branch.

At the next service-mileage event, SriMileageStore selects the greatest
unsigned word with a predecessor exactly one less modulo 65536. In these
fixtures, unchanged and mixed words repeated the intended write to the same
slot. A completed $0300 advanced the next request to $0301 in the next slot.
A completed $0000 after $FFFF still caused another write of $0000 to the
same slot. Physical persistence and concurrent Scratch0/1 use remain open.
[Reset context](reset-128k-context.md)

## Exact-ROM address limits and controlled power-down write

On the two 128 KiB ROMs, word requests at $1FC, $1FD and $1FE programmed
both bytes. At $1FF the split branch programmed and checked the high byte.
The low byte was outside that verification. Cleanup set EepromAddr to
$FFFF and left flags $12. The next EepromWriteService made no further
program request. EepromWriteQueue still refreshed the ring on a readback
table miss, leaving flags $10. At $200 the service sent write enable,
skipped programming and readback and left flags $40 with address $FFFF.

For the tested word request at $1E0, the service pointed the readback
cursor one word before the match. Successive EepromWriteQueue calls
published $1E0 and $1E1 into Z+$0339/$033A on 04887050 and
Z+$0353/$0354 on 05293013AC. Supplied busy and verification-timeout
controls left those RAM bytes unchanged.

EepromPowerDownWrite submitted the high byte at $00C and $1FF through
the actual watchdog/delay path, cleared the pending flags and invalidated
the address. A successful readback returned carry clear. A timeout,
high-byte mismatch or invalid address returned carry set. The new
regression covered 34 cases across both ROMs. The cases supply QSPI
responses and do not model power hold-up or actual write durability.
[Exact-ROM boundary audit](https://github.com/DDex89/recore-sbec3/blob/dinofuel-128k/patches/spark/v2/stock_vss_eeprom_audit.py)

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

PowerDownCount follow-up: all direct named zero-test consumers reviewed. RunModeSwitch $15200/$124E0 and B-only MonTaskB $1894E test nonzero RAM, defer while EepromFlags.7 is set, otherwise queue zero to EEPROM $00C. Together with EepromReadInit mapping $00C -> $F8344/$F835E and CheckPowerDown storing FlexEthanol there, this supports StoredFlexEthanol as the descriptive name. Indirect accesses and actual value scaling not exhaustively verified; the descriptive identifier is now canonical in A/B.
