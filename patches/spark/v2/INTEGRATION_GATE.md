# Spark V2 integration gate: source findings and publication model

Baseline: 07d91720640be0adadea23cbe64d8e012b1f5168; CI run 45508901204
(all 28 jobs successful). This change is research-only, not an integrated ROM.

## RAM: remove the entire diagnostic/stack page from candidates

Both variants implement DiagWriteRamByte with indexed byte stores based on
$8700 and a diagnostic jump to $F8700 (bank1.asm). Reset sets SP to $87FE.
The entire offset range $0700-$07FF must therefore be excluded from new
persistent reservations. This rejects the previous largest candidates
$0724-$078B (1996) and $0736-$07B9 (1997), regardless of the static inventory.
The revised survey still reports candidates only, not allocations.

Remaining shared candidate $05F2-$05FF (14 bytes) is worth investigating,
but is not assigned: indirect arrays, RAM clear/reset and every diagnostic
mode still require an ownership proof. Reset has a bulk RAM clear loop up
to $8700 (1996) or $8726 (1997); clearing alone does not prove ownership.

## Publication protocol (abstract, not implemented in ROM)

Preserve the stock legacy byte and add a separate fine-angle word only if
RAM ownership is established. The direct named accesses in the stock ASM
show one background writer of SparkValueD0F, one event-reader, one
SparkAdvanceD11 writer and fifteen named final-angle reads per variant.
Final-angle readers include IC1, OC3, SparkOutputOc2, knock, diagnostics
and purge monitoring. This is not an exhaustive alias audit.

IC1 starts with ORP #$0060; OC2 starts with ORP #$00E0. BusTxByte uses
PSHM D,CCR followed by ORP #$00E0. This establishes a stock save/mask
idiom, not a proof that a new critical section meets interrupt deadlines.
Do not use unconditional ANDP #$FF1F to restore a caller's mask.

Candidate: compute outside the critical section, save the incoming CCR,
mask relevant interrupts, publish the fine word and legacy byte, restore
the original CCR. The reader does not retry or spin. The model deliberately
splits the fine-word store into two byte writes and checks maskable
priority observations at every boundary, with an unprotected negative
control. It assumes mask 7 blocks priorities 1..6 and omits level 7,
fault/reset and debug intervention. Actual CPU16 timing, NMI and interrupt
priority behavior must be verified before writing any production hook.

## Integration gates still open

- Prove RAM ownership including computed aliases, diagnostic operations
  and stack high-water for both ROMs; verify initialization/validity.
- Audit all flag transitions and interrupt nesting, and establish bounded
  mask duration against the crank-event deadline.
- Couple staged byte-map interpolation to actual MAP/RPM producers, then
  prove residual bounds for edited maps; preserve integer correction
  generators and force original override/fault/cranking behavior.
- Validate event clamps, branch selection, timing arithmetic and dwell
  end-to-end; keep Spark V1.1 as the selected stock-compatible baseline.
- Hardware-in-loop bench measurements before any vehicle use.

No new RAM address, production hook, module reservation, timer modification
or flashable image is introduced.
