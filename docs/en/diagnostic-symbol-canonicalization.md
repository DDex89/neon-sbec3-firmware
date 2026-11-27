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
| 05007038 | $19C5A | $19CA4 | — | — |
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
| 05293148AA | Only XDF was available locally. The existing comparison with 05007038 reports zero changed code bytes. Exact-ROM generation and validation remain pending until a dump matches SHA-256 1c39aaef1f4702d2c4aeb1c35612083495a25a243705c62e99df11ba4ecb3951. |

tools/gen_source.py uses the scoped aliases for bit keys and descriptions. tools/port.py applies the same hash-pinned list to carried labels and RAM names, then applies local hand annotations. For A/B, the generator describes MIL flag clearing in prose where the shared bit text used a function name from another family.

In each repository, inverse substitutions recovered the original text on all 36 renamed ASM and annotation files. All seven tracked ASM sets assembled byte for byte against the hash-verified supplied ROMs. Generating ASM with python -X utf8 tools/gen_source.py and reassembling it with tools/asm16.py also reproduced all ten available ROMs byte for byte. The two supplied 05293013AC files each contain two identical copies of the expected 128 KB ROM. Local port regeneration checked the early RAM naming boundary on 05007038 and the canonical 256 KB names on 05269834AJ. Generated ASM for the three additional variants was kept in local verification folders. CI was not launched.
