# Spark V2 — bottleneck research (simulation only)

The stock timer slice checks passed on both ROMs in [CI 45504787696](https://github.com/DDex89/neon-sbec3-firmware/actions/runs/45504787696): 101,376 cases. This study asks which quantization is worth changing first. It is NOT a patch and is not included in any composed image.

## Isolated candidate

Use a signed high-resolution angle concept with 1/16 degree units (eight units per legacy 0.5 degree count). On an already selected positive-delta branch, let d8 be eight times the raw legacy angular difference. Preserve the existing coefficients: path 1 uses round(182*d8/8), paths 2/3 use round(410*d8/8), avoiding rounding the latter to a multiple of 256. The isolated CPU16 experiment uses a 32-bit EMUL intermediate, rounds and shifts, restores effective period, multiplies and rounds the final timer offset. Inputs are synthetic and bounded; no production memory, timer, safety or branch logic is changed.

## Numerical experiment

Angle domain -16..42 degrees, seven synthetic periods per path, only branches whose old and proposed angle classifications agree; four angle values close to the path 3 threshold are excluded and reported. The reference is the continuous arithmetic using the existing constants and effective integer period, NOT the actual crank angle. Separate the error from rounding the angle, rounding the coefficient and rounding the final timer count. For path 2 report period quantization separately. Path 3 avoids the synthetic period-wrap region. The grid is not a reachable-state distribution or an ISR safety proof.

| Path | Samples | Max stock error, counts | Max candidate error, counts | Mean stock / candidate |
|---|---:|---:|---:|---:|
| 1 | 6503 | 83.812 | 0.952 | 12.763 / 0.266 |
| 2 | 6503 | 134.869 | 0.702 | 14.552 / 0.253 |
| 3 | 5012 | 303.290 | 0.954 | 32.813 / 0.266 |

These numbers come from a separate mathematical evaluation; the CPU16 regression must pass before the candidate is accepted even as an isolated arithmetic implementation. The worst errors across the artificial grid are not physical crank-angle error, because the raw periods differ between paths. Removing the legacy coefficient rounding in paths 2/3 also changes timing for existing integer angles: it must NOT be silently incorporated into the stock-compatible profile.

## Next gates

1. Verify isolated machine arithmetic and quantify instruction cost with confirmed CPU16 timing.
2. Establish period and angle reachability, actual GPT clock and timer paths; preserve branch selection and wrap semantics. Four excluded path-3 angle values make this especially important.
3. Audit the complete CalcSpark correction ABI, atomic publication and RAM allocation; retain the proven V1.1 profile. A more precise timer calculation alone cannot recover fractional angles lost earlier.
4. Validate protection, dwell, ISR budget and physical timing before any on-engine use.

No turbo changes, ROM export or hardware validation.

## Confirmed isolated arithmetic

[CI 45506783465, job 138843937377](https://github.com/DDex89/neon-sbec3-firmware/actions/runs/45506783465/job/138843937377): all 18,018 isolated CPU16 cases passed, confirming the numerical table. `profile_precision.py` measures the isolated arithmetic routine under the existing CPU16 timing model; this excludes caller setup, branch selection, hardware and the rest of the ISR.

## CalcSpark publication contract

`publicationcheck.py` independently checks the actual stock correction-sum and publication tail in both original and fuel+spark V1.1 images. The 1996 implementation has 18 terms including a separate checked trim and adds that trim to the fault angle with saturation; the 1997 implementation has 17 terms and uses the fault angle directly. Override, fault, hold, idle/dashpot branches and signed saturation must stay unchanged. Correction generators are not executed in this fixture. A separate host-only fractional experiment uses 1/16-degree units, preserving integer corrections and forcing exactly the original angle in override/fault paths. No claim of atomic publication, downstream compatibility, or available RAM is made.

## Confirmed correction and arithmetic profile

[Publication CI 45507213567](https://github.com/DDex89/neon-sbec3-firmware/actions/runs/45507213567): 27,904 (1996) and 27,328 (1997) stock/composed tail cases passed; 441,856 separate host fractional cases passed. [Precision profile CI 45507266759](https://github.com/DDex89/neon-sbec3-firmware/actions/runs/45507266759/job/138845575237): 13 instructions, 6 bytes stack including test return frame, modeled 70/89/108 clocks for 2/3/4-clock flash. Not a complete ISR cost.

## Stock byte-map interpolation experiment

`map_precision.py` retains the original angle cells, MAP scale and row coordinate; evaluates all MAP/RPM bytes in PT/WOT for each supported ROM. Compares actual stock machine results against a rational reference and Q8/Q11/Q16 host interpolation with final rounding to 1/16 degree. No increase in stored map size is required for this experiment. It also reports residuals relative to actual stock outputs, particularly cases outside the previously studied [-4,+3] fine-unit publication envelope. These must be measured before choosing a representation; the host-only publication test does not demonstrate that all real interpolation residuals fit. No production map, firmware, or ABI is modified.

## Byte-cell CPU16 candidate

A separate exhaustive host calculation over all 256 row positions and 256 RPM inputs per map (not MAP input bytes) found Q11 single-round maximum errors 0.033482 degrees (PT), 0.034539 degrees (WOT), versus Q16 0.03125 degrees. The 8-bit cells are retained. A practical staged implementation using 1/256-degree intermediates before final Q4 rounding had maximum host-calculated errors 0.036184 degrees (PT) and 0.035362 degrees (WOT). That is a different rounding rule, with some one-fine-count differences from the single-round Q11 model.

`byte_interp.py` assembles a separate CPU16 test image; evaluates four byte cells with packed Q11-derived RPM fractions and Q8-derived row fractions; verifies staged integer arithmetic against an independent model and exact rational bilinear reference. Signed cells are biased in the synthetic caller; production conversion, indexing, calling convention, interrupt ownership and RAM allocation remain to be designed. The program checks stack/Y restoration, writes, extrema, and reports actual instruction counts. It does not patch or export firmware. Full CI covers 262,144 row-position/RPM machine cases across both ROMs plus synthetic cases. The existing Spark V1.1 remains the selected stock-compatible baseline.
