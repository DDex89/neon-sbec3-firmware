# Diagnostic symbol canonicalization, phase 1

The six names below are implemented in reference 05293190AC only in this phase. Addresses and firmware instruction operands are unchanged; exact word-boundary substitution was used on the five generated ASM/equate files, and the inverse substitution reproduced each original text exactly. This is a textual equivalence check, not a binary rebuild.

| Old | Canonical | Reference offset/address |
|---|---|---|
| MonFlags09D | ObdPriorFailSwitch | Z+$009D |
| MonFlags09E | ObdPriorFailO2 | Z+$009E |
| MonFlags09F | ObdPriorFailMisc | Z+$009F |
| MonFlags65A | ObdResultMisc | Z+$065A |
| MilFaultIncrement | ClearFaultHistoryAndCurrentState | $241E4 |
| MilRequest | ClearMilRequestState | $24210 |

Cross-family evidence: MilFaultIncrement clears the fault history/current state and MilFaultCount in all seven representative families. A/B perform some additional clears inline; C and the four 256 KB families call MilRequest, which clears MIL-associated flags. A/B do not have a separate MilRequest label. The four 256 KB families use the three prior-failure flag groups and current misc result group; 05032017AA relocates the prior flags to Z+$009E/$009F/$00A0. Family C has the first two names at $00B5/$00B6 and result groups at $02CE/$02CF, but its full qualification mechanism has not been verified. A/B do not expose those same RAM symbols. No blind substitution was made in any ported image.

Shared legacy bit definitions remain available to ported images. The reference-specific alias map adapts bit keys and descriptions during reference ASM generation. Other families and historical documentation still retain old names until their independent synchronization. Full regeneration, binary build and CI have not been executed. Previous DTC helper tests are not independently verified in this phase.


## Phase 2 — stock port synchronization, 2026-11-27

Audited baselines are Original main at 7e23f987994b657d962ab1299e9139b1a55e0eb1 and ReCore dinofuel-128k at 6d01ef2bfc84566ffaeb5d87ae9fa84439242061.

| Stock image | ClearFaultHistoryAndCurrentState | ClearMilRequestState | Prior failure groups (Z-relative) | Misc result (Z-relative) |
|---|---|---|---|---|
| 04887050 / 04887051 | $1BB34 | — | — | — |
| 05293013AC / 05293014AC | $1E450 | — | — | — |
| 05007038 / 05293148AA | $19C5A | $19CA4 | — | — |
| 05293190AC (phase 1) | $241E4 | $24210 | $009D/$009E/$009F | $065A |
| 05269833AH / 05269833AI / 05269834AJ | $241E4 | $24210 | $009D/$009E/$009F | $065A |
| 05032017AA | $241E6 | $24212 | $009E/$009F/$00A0 | $065A |

The history routine clears history, current fault state and MilFaultCount. The A/B variants clear MIL-related flags inline and have no separate ClearMilRequestState entry. The earlier RAM names remain as before pending independent qualification evidence.

For the four 256 KB families in the original audit, the 22 two-trip rows read by ObdFaultReport pair the three prior-failure groups with result groups $0658/$0659/$065A. The audit checked the prior offsets in each row at +2 and result offsets at +6, and traced the path that sets a prior-failure bit on a first failure, reports a repeated failure and clears the pair on a pass. The row block starts at $75FA in 05293190AC, 05269833AH and 05269833AI, and at $7629 in 05032017AA. The 05269834AJ row block and the relevant diagnostic routines match 05269833AI byte for byte.

| Variant without tracked ASM | Local result |
|---|---|
| 04887051 | ROM hash matched. Compared the clear routine and nearby MIL flag clearing with 04887050. Generated ASM reassembled to the supplied ROM byte for byte. |
| 05293014AC | ROM hash matched. Compared the clear routine and nearby MIL flag clearing with 05293013AC. Generated ASM reassembled to the supplied ROM byte for byte. |
| 05269834AJ | ROM hash matched, including the duplicate supplied as 05269834AI.bin. Generated ASM reassembled to the supplied ROM byte for byte. |
| 05293148AA | Both 128 KB halves of the supplied 05293063AC.bin matched the expected ROM hash. The diagnostic code matched 05007038 and generated ASM reassembled to the supplied ROM byte for byte. |

tools/gen_source.py uses the scoped aliases for bit keys and descriptions. tools/port.py applies the same hash-pinned list to carried labels and RAM names, then applies local hand annotations. For A/B, the generator describes MIL flag clearing in prose where the shared bit text used a function name from another family.

In each repository, inverse substitutions recovered the original text on all 37 renamed ASM and annotation files. All seven tracked ASM sets assembled byte for byte against the hash-verified supplied ROMs. Generating ASM with python -X utf8 tools/gen_source.py and reassembling it with tools/asm16.py also reproduced all eleven available ROMs byte for byte. The two supplied 05293013AC files each contain two identical copies of the expected 128 KB ROM. Local port regeneration checked the early RAM naming boundary on 05007038 and the canonical 256 KB names on 05269834AJ. Generated ASM for the four additional variants was kept in local verification folders. CI was not launched.

## Exact ROM follow-up for 05293148AA

The supplied file was named 05293063AC.bin. Its header at $00302 identifies 05293148AA. Each identical 131,072-byte half has SHA-256 1c39aaef1f4702d2c4aeb1c35612083495a25a243705c62e99df11ba4ecb3951. The first half was used as the local input roms/05293148AA.bin.

The two ROMs differ at 2,214 offsets. All 107,124 bytes identified as instructions in either ROM by tools/analyse.py match, including the entire interval $19C5A–$19CB5. The instruction at $19C5C calls $19CA4. The first routine clears the history and current state at Z+$014D–$0173 and Z+$021C–$023B, and clears MilFaultCount. The called routine clears MIL-related state. The early RAM labels MonFlags09D and MonFlags09E are still at Z+$00B5 and Z+$00B6.

Both checked-in and freshly generated port annotations were tested locally. After running tools/port.py on the extracted ROM in a copy of the annotations, tools/gen_source.py preserved the two canonical routine labels and tools/asm16.py reproduced all 131,072 input bytes. The same assembly check passed using the checked-in annotations. The ROM and generated ASM stayed local.

## Family C monitor latches

05007038 and 05293148AA use inline monitor logic. The prior failure bytes at Z+$00B5/$00B6 pair with result bytes SwitchMonFlags and O2MonFlags at Z+$02CE/$02CF. The two bytes of each pair can be set together on the first failure. A matching prior bit can lead to ReportFault only after the monitor passes its current-cycle guards. MonitorFlagsClear at $19C92 clears all four bytes. The family C bit descriptions override the 256 KB descriptions. The RAM labels are retained because the groups mix monitor classes.

| Prior / result mask | Family C stock evidence |
|---|---|
| $00B5 / $02CE, $10 | VssMonitor uses P0500 descriptor $039BD. The first qualifying failure sets both bits and requests freeze-frame capture. A prior failure with a clear result bit reaches ReportFault. The pass path clears both bits. |
| $00B5 / $02CE, $02 and $01 | O2HighVoltMonitor uses the two Bank 1 descriptors at $14FF2 and $15008. Their mask bytes at +$0F/+$11 select P0138 and P0158, respectively. O2 activity logic tests the prior bits, and the monitor can clear both bits for the matching sensor. |
| $00B6 / $02CF, $08 and $04 | O2LowVoltMonitor reads the paired masks at +$0E/+$0F of $1526C and $15280 for P0137 and P0157. Its first qualifying failure requests freeze-frame capture, a repeat with the result bit clear reaches ReportFault, and an already-set result bit skips that path. |
| $00B6 / $02CF, $01 and $02 | CatMonSwitchRatio reads result/prior masks at +$36/+$37 of $170DE and $17128 and fault descriptors for P0133 and P0153. It clears the prior bit after reporting and on the pass path. |

Local CPU16 traces on each hash-verified ROM exercised nine isolated branch slices for P0500, P0137 and P0157, stopping at the capture/report call boundary or the no-call exit. A separate call to MonitorFlagsClear zeroed all four seeded bytes on both ROMs. Both images reassembled byte for byte with the verified comments. Bits 7–4 of the O2 pair and the full drive-cycle liveness of these latches remain open.

The exact-ROM fixed-destination store scan found the same ten instructions touching Z+$00B6/$02CF in both family C images. Eight update the pair in O2LowVoltMonitor or CatMonSwitchRatio. The O2 masks from $1526C/$15280 are $08/$04 and the catalyst masks from $170DE/$17128 are $01/$02. These operations preserve bits 7–4. The other two instructions in MonitorFlagsClear zero the entire bytes. The general byte tests in MonTaskD/MonTaskE would still observe a nonzero upper nibble. No upper-nibble setter was found among these direct instructions. Indirect destinations and a complete drive-cycle trace remain open.

The 13 primary and 16 distinct secondary OBD descriptor offsets from $1EE60 onward exclude both bytes on each family C ROM. In isolated reset checks, NvChecksum read $F80B6 and excluded $F82CF. The warm clear loop starts at $8174 and preserves the seeded value at $F80B6 while zeroing $F82CF. The cold loop starts at $8055 and zeroes both bytes. These checks establish reset behavior for seeded values, including upper bits. The test leaves normal producers and complete reset-to-monitor timing open.

The 88 EepromReadInit destinations in each family C ROM exclude Z+$00B6 and Z+$02CF. The exact stock loops at $1EC78 copied 88 simulated successful byte responses into their descriptor destinations on both images. Both tested latches were preserved. The test stops before QSPI initialization and does not simulate the EEPROM peripheral or a drive cycle.

The table-derived address envelopes for family C were checked separately. The reviewed high-O2 fields are +2/+8/+$0C in the two rows at $14FF2/$15008. The low-O2 fields are +0/+2/+6/+8 in four rows at $15244/$15258/$1526C/$15280. The catalyst check conservatively includes all aligned words through +$28 in the rows at $170DE/$17128. Both exact family C ROMs have the same sets for these fields. Neither Z+$00B6 nor Z+$02CF is in the resulting ranges, including a second byte for possible word accesses. This bounds the selected descriptor values. It does not characterize every other source of an indirect address or the upper bits' complete drive-cycle lifetime.

For family C, the MonTaskD and MonTaskE whole-byte tests were executed with an empty fault list and Z+$00B5 clear. For each of the two watched bytes, all 256 values were supplied separately on both exact ROMs. The $00B6 value alone determined the tested MonData646.2 and MilRequestFlags.1 results. Upper bits in $00B6 therefore matter if set. Varying $02CF did not change these two outputs. Both clear controls zeroed the four latch bytes. These observations identify consumers and leave the source of a nonzero upper nibble in a stock drive cycle open.

Isolated captures, frame clears, and the ID-gated FreezeFrameStore on 05007038 and 05293148AA preserved Z+$00B6/$02CF. MisfireFaultRecord ($1F2DC) reaches MonitorFlagsClear after clearing fault history on the seeded aging threshold path, so it zeroes both whole bytes. This confirms an additional caller of the known clear routine. [Exact-ROM freeze-frame and misfire checks](sci-obd-128k.md#freeze-frame-capture-and-misfire-aging)
