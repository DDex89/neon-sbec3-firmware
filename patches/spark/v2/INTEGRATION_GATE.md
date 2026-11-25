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

## Reader-side preemption and shared candidate follow-up

Source review on 281f0e7: both variants call CalcSpark from the
background task (bank0 L0D276 / L0D3B6), and SparkEventCalc from the
IC1 path at L04988. OC2 and OC4 explicitly raise the mask to 7;
IC1 initially ORs the mask with 3. These are mask operations, not
proof of configured interrupt priorities. The final event angle has
readers in both banks; a future reader requiring both angle formats
must take a coherent snapshot, not merely assume writer-side masking
is sufficient. Legacy-only readers need not acquire the new word.

The additional reader_protocol experiment checks preemption between
three individual byte reads, even when the higher-priority writer
commits atomically. The standalone host function found 126 torn
unprotected observations and 294 protected observations with no torn
snapshot. This is an abstract negative control, not CPU16 execution.
Do not extend interrupt masking to the complete angle calculation.

For offsets 05F2..05FF, both equate inventories contain no named
symbol in that interval. A source scan of the four banks found no
literal matching those offsets or their 85xx addresses in instruction
text; this does not exclude computed offsets, ROM pointer tables,
or multi-byte operations spanning the candidate. The preceding named
fuel fields end at WotDelayTimer (05ED, 1996) and AccelTpsBaroFactor
(05EF, 1997); the next named group begins at 0600 in both variants.
A diagnostic indexed memory read is visible in bank1
(L133F0 / L16610, LDAA $00,X). DiagRamAddrAllowed is called from
the EEPROM-address path, so its name alone cannot establish a
general RAM access whitelist. Debug execution and reset must be
treated separately. No new address is approved by this review.

## Assembled fixture timing and remaining ownership gate

Both resource-survey jobs in run 45559879306 passed the first assembled
fixture: 8 publications, 63 observable writer boundaries, 288 snapshots,
21 torn unprotected snapshots per variant. The timing extension in
a23a4e6 corrects fixture-local CCR bit positions (CPU16RM section 6),
retains the other CCR bits as inert state and models the ORP recognition
delay (section 5.9); the base emulator is unchanged.

The decoded six-instruction fixture has a modeled critical span from ORP
through PULM of 24/31/38 clocks and a complete routine of 42/53/64 clocks
for flash bus periods 2/3/4, assuming aligned two-clock RAM. This follows
the existing timing model plus the documented 4-clock ORP immediate.
The full routine excludes the caller JSR and interrupt entry; neither
number is a real-time hardware bound. Stack growth beyond the call frame
is two bytes. CPU16RM: https://www.nxp.com/docs/en/reference-manual/CPU16RM.pdf
The latest CI must confirm the executable timing assertion.

RAM follow-up: explicit immediate RAM-page-85 pointer loads in the
four source banks identify O2UpdateUpstream/Downstream, ClosedLoopManager
and the O2LearnEnable call sites (85A1/85A8 or 85B1/85B8). The 0510
immediate in the shutdown loop is a PowerInputHold countdown, not an
identified candidate pointer. These observations are not a complete
range analysis of the O2 routines or indirect pointer tables.
No persistent storage has been allocated. Do not promote 05F2..05FF
to a reservation until the remaining alias and lifecycle audit passes.

## Joined interpolation/correction fixture (f109bf6)

Both timing/CCR resource-survey jobs in CI 45560792944 passed, including
the 18-byte publish and snapshot routines and the 24/31/38 modeled
critical-span clock assertions. No measured interrupt deadline yet.

map_precision.py now also evaluates the staged interpolation residual
against actual legacy base-angle output over the complete factory MAP/RPM
grid. Report the observed residual and count outside [-8,+8]; do not
assume this envelope for edited calibrations. The joined sampled fixture
runs the original and V1.1 base lookup, the staged CPU16 interpolator,
the V1.1 CalcSpark tail with injected signed corrections, and a separate
assembled signed fine-sum/saturation routine. The host selects ordinary,
fault and override paths using the known stock fixture policy. This
checks arithmetic linkage but is not a production calling convention,
full correction-generator execution, atomic publication, event scheduling
or ISR integration. CI 45561333798 must confirm the new fixture.

A follow-up scan of contiguous hex dc.b data in both source banks found
05FA in both variants immediately after VssCheckVacuumRpm, 05FB near
O2SwitchMargin in 1997, and three apparent 85FF matches straddling
aligned list entries (0285/0485 followed by FFFF). The latter are not
aligned candidate RAM pointer entries in those lists. The unlabeled
05FA/05FB occurrences still need classification via table consumers;
a byte pattern alone is not proof of a RAM reference or its absence.
The candidate 05F2..05FF remains unallocated.
