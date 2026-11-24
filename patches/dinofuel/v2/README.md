# DinoFuel V2 — simulation-only comparison

The V1 absolute pulse maps remain unchanged. V2 is a separate experiment: store unsigned Q2.14 fuel multipliers instead of absolute pulse widths, interpolate, then multiply by the original MAP-dependent linear term. The original MAP scale clamps the coefficient outside its range, while MAP itself continues to affect pulse width. No switch to a different fuel model is needed. Edited V2 coefficients therefore also affect out-of-range MAP where the original scale clamps.

The comparison includes two machine-code versions: Q16 RPM fractional position with the existing lookup and an optimized packed RPM table (512 bytes, 5-bit column index and 11-bit fraction). The latter uses a fixed common RPM axis and cannot be reused after an axis edit without regenerating the table. The V1 XDF is **not** applicable to V2. No output binary or hardware flash action is supported.

Run from repository root:
```sh
python3 tools/build.py 04887050 05293013AC
python3 patches/dinofuel/v2/simulate.py 04887050
python3 patches/dinofuel/v2/simulate.py 05293013AC --full
```

The fast job checks CPU16 execution against a separate integer reference, option edges, and sampled instruction/bus/stack profiles. Full jobs compare all 256 MAP x 256 RPM x 2 mode input tuples against stock/V1, plus option tests; the same inputs are reused for the candidates. Results report absolute counts and relative error separately, including pulses below 100 counts, since one count can exceed 1% there. A completed simulation does not imply that the 1% target is met: inspect the statistics. No physical timing, full ISR or vehicle validation is implied.
