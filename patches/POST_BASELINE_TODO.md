# Post-baseline engineering backlog

Status: DEFERRED. This is a separate roadmap, not a requirement for the first
integrated improved firmware. Do not implement these items or change factory
control policy in the baseline profile. Keep the original ROMs and proven
stock-compatible profile available as references.

## Release gate before starting this backlog

- [ ] Complete and integrate the initial DinoFuel and Spark improvements and
  any required compatibility adapters (including OBD).
- [ ] Regress both 128 KiB target images (04887050, 05293013AC) against the
  original firmware and the stock-compatible profile.
- [ ] Verify actual CPU16 machine execution, memory ownership, interrupt
  coherence, worst-case timing, stack, reset, fault and diagnostic behavior.
- [ ] Validate engine-control timing and behavior on a suitable bench, then
  controlled engine testing; document limitations and establish a stable
  versioned baseline with a rollback procedure.

## P1 — Knock V2 (independent module)

- [ ] Establish measured benefit, sensor/noise repeatability and a baseline
  of the factory knock response before changing any algorithm.
- [ ] Evaluate independently calibratable attack and recovery behavior,
  including conditions for recovery and repeated-knock response.
- [ ] Evaluate response magnitude against measured knock intensity and
  recurrence; preserve conservative fallback and fault handling.
- [ ] Review individual-cylinder control, shared-versus-individual learning
  and whether separate cylinder calibrations are justified.
- [ ] Evaluate load/RPM-dependent limits, temperature effects and validation
  of the existing sensing windows; do not weaken protection.
- [ ] Assess whether fractional correction/accumulation provides measurable
  benefit over the stock 0.5-degree steps. Do not widen merely for consistency
  with Spark Q4.
- [ ] Review XDF/diagnostic visibility and any RAM/CPU cost of the selected
  implementation. Require independent protection and hardware validation.

## P2 — Further ignition and fuel refinements (candidate studies)

- [ ] Assess finer calibration cell resolution separately from higher
  interpolation precision; quantify flash, runtime and tuning benefit.
- [ ] Review EventTimingLimit and timer-path quantization as separate policy
  changes, only after actual ISR reachability and output timing are verified.
- [ ] Evaluate whether dwell, transient corrections, startup, idle and
  temperature corrections have measurable bottlenecks. Keep these functions
  stock until evidence warrants independent modules.
- [ ] Review fuel transients and closed-loop/adaptive fuel correction for
  remaining precision losses and measurable improvements.

## P3 — Diagnostics, tooling and maintainability (candidate studies)

- [ ] Add optional high-resolution internal telemetry while retaining
  standard OBD representations and diagnostic semantics.
- [ ] Extend XDF definitions, per-module resource budgets and automated
  regression coverage for approved changes.
- [ ] Evaluate porting individually to additional SBEC3 variants after the
  initial two-variant implementation is established.

## P4 — Firmware cleanup, refactoring and defragmentation (feasibility study)

Status: OPTIONAL / DEFERRED; decision pending. Consider only after the
replacement modules are integrated, validated and a stable rollback baseline
exists. This is not approval to remove or relocate production code.

- [ ] Quantify reachable code, flash savings, RAM savings, timing effects and
  maintenance benefits versus relocation and regression risk. Decide whether
  the work is justified at all.
- [ ] Evaluate removing the unused factory FlexFuel implementation in a
  gasoline-only profile or after a validated ReFlex replacement; preserve
  required interfaces and fallback behavior.
- [ ] Evaluate eliminating unused second cylinder-bank logic on the target
  four-cylinder Neon configurations. Do not confuse bank 2 with the downstream
  oxygen sensor on bank 1; retain both required sensor paths.
- [ ] Identify diagnostics and tables exclusively tied to absent equipment;
  prove unreachability before removal and retain required OBD-II, readiness,
  fault reporting, protective functions and service compatibility.
- [ ] Evaluate dead code elimination, ROM layout consolidation and relocation
  (defragmentation), including bank boundaries, absolute and relative
  references, computed dispatch, pointer tables, vectors, calibration/XDF
  addresses, checksums and bootloader compatibility.
- [ ] Require byte-level reference tracking, reproducible builds, complete
  regression on both target variants, timing/stack/IRQ checks and bench
  validation after each relocation stage. Preserve original and stable
  pre-cleanup images for rollback. Reject cleanup if benefits do not justify risk.

## ReFlex / ReLoop — fault-path research (deferred integration gate)

- [ ] Investigate the potential stack-growing control-flow cycle from
  O2LearnEnable ($09C88 / $09D84) back into O2CellSelect
  ($09C04 / $09D00) in 04887050 / 05293013AC, respectively, when
  FaultSet0B & $30 or BusModuleFlags & $10 is set. Confirm machine-code
  targets, actual reachability, stack growth and watchdog/fault behavior.
  Do not label a runtime overflow as proven yet.
- [ ] DTC table entries associate FaultSet0B bits 4/5 with P0179/P0178
  (fuel composition sensor high/low). Factory Options0324 bit 0 is clear
  in both targets ($72/$32). ReportFault uses descriptor bytes 4/5 to
  update indexed fault RAM (group base $0133/$0163). Group $0D mask $10
  corresponds to P0176 (BusModuleFlags bit 4), descriptor $38ED/$3918.
  P0179/P0178 descriptors are $384D/$3857 and $3878/$3882 respectively.
  The factory sensor-check entries $11212/$11112 gate all three reporting
  paths on Options0324 bit 0. Trace restore, diagnostic and other indirect
  writers; prove baseline reachability or exclusion.
- [ ] All reviewed O2LearnEnable learning-condition branches converge on
  the fault check ($09DB0/$09EB2), before the local closed-loop-disable
  check. The backward reset path does not explicitly clear the triggering
  flags and can issue another JSR O2LearnEnable. Verify instruction encoding,
  persistent-fault execution and interrupt/watchdog effects; distinguish a
  conditional stack-growth proof from observed hardware failure.
- [ ] Validate the observed STFT-based ethanol fallback, LTFT learning
  inhibition and actual closed/open-loop state under sensor faults.
  Compare the 1999 reference implementation. Resolve any confirmed
  stack/control-flow defect before enabling ReFlex; regress ReLoop,
  fuel and spark interactions. Keep FlexFuel disabled in the baseline.

### ReFlex fault-path audit — reset and restore evidence

- Both target calibrations disable FlexFuel (Options0324 bit 0) and
  P0176/P0178/P0179 reporting (descriptor byte 3 = $03; ReportFault
  requires bit 7). These are separate gates.
- Reset clears active fault bytes: 1996 offsets $013E/$0140 within
  $010A..$06FF; 1997 offsets $016E/$0170 within $013A..$0725.
  The retained RAM checksum ends before these bytes. Stored DTC history
  is distinct from active fault flags.
- Original ROM table inspection: EepromReadInit destinations at
  $13FEA (51 big-endian words) and $17246 (80 words) contain neither
  active fault-byte offset. The 13 primary ObdResetInit destinations
  at $1F000/$1F006 (20-byte records, word at offset 2) also contain
  neither. This excludes these direct table-driven restoration paths,
  not all indirect writes or service modes.
- Remaining gate: review secondary OBD descriptor destinations, other
  indirect writers and interrupt paths; do not claim unconditional
  unreachability. Preserve the HardwareCheck stack-anchor mechanism
  in any future relocation/refactoring.

## Interrupt mask restoration — conditional calibration hazard

- [ ] Review IacSetTarget ($0B486/$0B580): ORP #$00E0 followed by
  unconditional ANDP #$FF1F clears IPL rather than restoring its entry
  value. A static path exists from Isr_PIT via ChargeControl and
  IacChargeStepCalc. In both original target ROMs this specific call
  is excluded by stock calibration: IacChargeStep ($1FBB/$1FE1)
  and IacStepBaroFactor ($21E8/$220F) each contain 01 80 FF 00
  (one unsigned point, y=0). Lookup2D returns the sole y regardless
  of input; the subsequent multiply and TSTA/BEQ skip IacSetTarget.
  Do not claim an observed stock ISR re-entry. If these calibrations
  or calling contexts change, require saved/restored IPL/CCR semantics,
  preserved register/flag contracts, IRQ re-entry analysis and timing
  regression before activation. Check other callers and IRQ7 separately.
- [ ] MapTpsFilters ($07E60/$07E80) also clears IPL in its A=0 branch,
  but the reviewed GPT IC1 call explicitly passes A=$55, bypassing
  those sections. Retain this invariant or review mask restoration
  if refactoring. Do not globally replace ANDP instructions without
  checking caller/return contracts.

### IRQ nesting and provisional stack envelope

- Reset/HardwareCheck set PFPAR=$14; IRQ7 pin not selected as IRQ.
  IRQ7 handler $0C658/$0C758 saves D,X,K and clears PFPAR.7.
  CPU16 exception frame is four bytes (PC/CCR); single IRQ7 adds ten.
  IRQ7 is non-maskable at CPU level; abnormal assertion is separate.
- Existing stack_direct_cfg_audit.py expands all four ConditionTable
  selector entries at $1F938/$1FA06; source assertions: IC1 52 bytes,
  PIT 38/34 bytes, excluding exception frame. Not a new regression run.
- Conditional envelope for closed main-loop roots only:
  56/58 + (52+4) + (22+4) = 138/140 bytes, SP $F8774/$F8772.
  Single abnormal IRQ7: 148/150 bytes, SP $F876A/$F8768.
  Not a global maximum; unresolved roots, dynamic masks, actual RAM
  writes, timing and ownership remain open.
- $F85F2..$F85FF remains a candidate, not an allocation. Diagnostic
  page $F8700..$F87FF is excluded from persistent reservations.

## Change-control rule

Each item starts with a measurable problem and an independent module proposal:
baseline, expected benefit, ROM/RAM/CPU budget, failure modes, compatibility,
regression criteria and rollback. No automatic activation or bundling of
unvalidated experiments. Priorities are provisional; P2/P3 are suggestions,
not approved implementation scope.

For the initial Spark V2, the stock knock detector, learning, per-cylinder
bytes, accumulation, recovery, limits and diagnostics stay unchanged.
Signed correction bytes are converted to Q4 at the arithmetic consumer only.
