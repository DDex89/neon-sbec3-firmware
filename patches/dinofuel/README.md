# DinoFuel — experimental 128 KB SBEC3 port

[Русский](README.ru.md)

## Versions

This directory describes V1 (absolute pulse maps). The selected naturally aspirated Q11 candidate is isolated in [v2/](v2/README.md). The formats are incompatible.

## Scope

This port adapts the corrected [DinoFuel](https://github.com/DDex89/dinofuel) by Dino Yancey (dino2gnt) to the stock 04887050 (family A) and 05293013AC (family B) images. It is kept outside the original source tree. The stock sources, stock XDF definitions and byte-identical build remain unchanged.

The new hook replaces only the stock fuel lookup and base-pulse calculation, retaining MAP hold, the original cutoff path, TipIn802, CalcFuel432, WOT enrichment, barometric compensation and subsequent stock fuel corrections. Outside the calibrated MAP range the original algorithm is used. The boost-specific adaptive-memory modification is not included.

## Memory layout

| Block | Address | Bytes |
|---|---|---:|
| Part throttle (17 × 17) | $04401 | 615 |
| WOT (9 × 17) | $04669 | 343 |
| Code | $0FC04 | 342 |
| Hook (replaces one JSR) | $07DEA / $07E0A | 4 |

The ROM remains 128 KB. The tables store twice the base pulse in unsigned 16-bit words, generated from each original ROM's own calibration. Words are aligned to even addresses. No new persistent RAM is reserved. The bank-zero lookup avoids an extra read at zero interpolation fraction.

## Build and test

From the repository root:

```sh
python3 tools/build.py 04887050 05293013AC
python3 patches/dinofuel/dinofuel128.py build/04887050.bin --full
python3 patches/dinofuel/dinofuel128.py build/05293013AC.bin --full
```

The script requires an exact stock SHA-256, checks erased regions, hook instructions and ROM checksum, and compares the patched and stock routines in the CPU16 simulator. The dense grid includes both WOT enrichment flag states, RPM axis nodes, MAP endpoints and saturation cases, plus separate option-edge tests. It does not test every possible combination.

## Verified baseline (2026-11-24)

[CI run 45490806429](https://github.com/DDex89/neon-sbec3-firmware/actions/runs/45490806429), before folder relocation and expanded tests:

| Metric | 04887050 | 05293013AC |
|---|---:|---:|
| Cases | 1,848 | 1,848 |
| Stock fallback/cutoff | 594 | 594 |
| Max reference error, PT / WOT (counts) | 0.90 / 1.65 | 0.90 / 1.65 |
| Mean CalcFuel432 difference from stock, PT / WOT | 0.542% / 0.107% | 0.542% / 0.107% |
| Max CalcFuel432 difference from stock, PT / WOT | 3.608% / 0.617% | 3.608% / 0.617% |
| Peak instructions, stock / patched | 337 / 343 | 337 / 343 |

The reported stock difference is a calibration/model difference in the half-base-pulse variable, not interpolation error. Instruction count is not timing. Expanded tests run in CI on this branch.

## Experimental TunerPro definitions

Use only the matching file in [xdf/](xdf/) with the corresponding patched ROM. The stock XDF does not edit the new tables. Both RPM and MAP axis labels are fixed to the original calibration; do not change the underlying axes or MAP scale. The cells are unsigned big-endian words, displayed as base pulse counts (X/2), not milliseconds; physical time conversion has not been independently verified. The 17x17 PT cells begin at $04426; the 9x17 WOT cells begin at $0468E. After editing, checksum repair is required for any bench image. No on-vehicle use.

`python3 patches/dinofuel/xdfcheck.py` verifies all 442 cells per ROM and simulates a single cell edit per table through actual CPU16 instructions. TunerPro GUI compatibility remains untested.

## Remaining work

- Check CPU16 worst-case cycle time, total interrupt/stack budget, actual RAM and flash access on hardware.
- Validate the experimental XDFs in the actual TunerPro GUI; the separate definitions and automated checks are now in this folder.
- Compare final fuel delivery on a bench, including transition at the MAP fallback boundary.
- Extend to other exact ROM variants only after verifying their signatures and free areas.

**Experimental only. No hardware or on-vehicle validation. Do not flash a vehicle with this prototype.** The script's optional output is for development and bench analysis.
