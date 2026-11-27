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
