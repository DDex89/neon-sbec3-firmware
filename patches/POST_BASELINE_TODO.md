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

## Change-control rule

Each item starts with a measurable problem and an independent module proposal:
baseline, expected benefit, ROM/RAM/CPU budget, failure modes, compatibility,
regression criteria and rollback. No automatic activation or bundling of
unvalidated experiments. Priorities are provisional; P2/P3 are suggestions,
not approved implementation scope.

For the initial Spark V2, the stock knock detector, learning, per-cylinder
bytes, accumulation, recovery, limits and diagnostics stay unchanged.
Signed correction bytes are converted to Q4 at the arithmetic consumer only.
