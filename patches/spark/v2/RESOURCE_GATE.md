# Spark V2 resource and publication gate

## Resource survey

`resource_survey.py` starts from the exact original hashes, composes the validated DinoFuel Q11 + Spark V1.1 test image, uses `tools/revision.py` to find the largest classified erased ranges, and subtracts all manifest reservations. Checks remaining candidate bytes in both images. It reports heuristic RAM candidates after excluding annotated offsets. It does NOT allocate memory or claim all candidates are safe: computed pointers, array spans, reset clearing, diagnostics, interrupt nesting and stack high-water require separate evidence. Flash candidates are from the largest four runs per bank, not an exhaustive allocator.

## Proposed interface (not implemented)

- Signed 16-bit angle in units of 1/16 degree; retain the original published byte for legacy diagnostics and scheduling until every consumer is audited.
- Keep intermediate results on the current call stack where practical. Do not reuse LookupResult or other shared scratch as persistent angle storage.
- Initial budget study: one aligned word for background corrected angle, one aligned word for final event angle if persistent storage is required; optional validity/generation state only if necessary. No RAM addresses reserved.
- A single aligned word store may be sufficient for an individual value if the hardware guarantees atomicity, but two separate publications of legacy and fine angle are not inherently coherent. Before selecting a protocol, inspect the actual interrupt mask policy, nesting, reset/fault handling, writer and reader sites. Do not assume that a seqlock retry in an interrupt can complete while its background writer is preempted.
- Keep current 8-bit angle, startup/diagnostic/knock decisions, output compare and dwell unchanged until branch-boundary and atomicity tests pass. No on-engine changes at this stage.

## Outstanding

Resource survey CI and byte-interpolation CI must complete; RAM ownership is a separate gate. No modification to production firmware or allocation manifest.
