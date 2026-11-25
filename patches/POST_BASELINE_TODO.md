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

## Change-control rule

Each item starts with a measurable problem and an independent module proposal:
baseline, expected benefit, ROM/RAM/CPU budget, failure modes, compatibility,
regression criteria and rollback. No automatic activation or bundling of
unvalidated experiments. Priorities are provisional; P2/P3 are suggestions,
not approved implementation scope.

For the initial Spark V2, the stock knock detector, learning, per-cylinder
bytes, accumulation, recovery, limits and diagnostics stay unchanged.
Signed correction bytes are converted to Q4 at the arithmetic consumer only.
