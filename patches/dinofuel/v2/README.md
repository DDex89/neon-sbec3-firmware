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

## Selected candidate and confirmed results

Q11 is the selected naturally aspirated candidate. The exhaustive [1996](https://github.com/DDex89/neon-sbec3-firmware/actions/runs/45495253939/job/138803901847) and [1997](https://github.com/DDex89/neon-sbec3-firmware/actions/runs/45495253939/job/138803902119) jobs both passed 131,072 input cases and 1,792 option cases. PT/WOT maximum base-pulse difference within the map range is 0.692%/0.468%; mean 0.11349%/0.08923%. The separate sampled timing profile estimates 2,000 clocks (119.21 us at assumed 16.777216 MHz, four-clock Flash) vs stock 2,652; stack 22 vs 24 bytes. This is not a full-ISR timing proof. Extremely short WOT pulses outside the map range can differ by one count and exceed 1% relative. No hardware validation.

## V2-specific TunerPro definitions

Use only the matching Q11 file in [xdf/](xdf/). The V1 files use X/2 and are incompatible. V2 displays the multiplier X/16384, neutral 1.0; axes are fixed. `check_calibration.py` validates the 442 cells, 256 packed RPM entries, simulated cell edits and rejection of unexpected changes, including wrong LUT and code. Only the two Q11 calibration value regions and the checksum correction byte may differ from the generated baseline. It rejects an edited axis; changing axes is a separate engineering task. An image can pass this structural check and still contain unsafe calibration values; real TunerPro and hardware remain untested.

```sh
python3 patches/dinofuel/v2/check_calibration.py 04887050
python3 patches/dinofuel/v2/check_calibration.py 05293013AC
```

Use [TURBO_CHECKLIST.md](TURBO_CHECKLIST.md) only in the deferred boost phase. Current scope is naturally aspirated only.
