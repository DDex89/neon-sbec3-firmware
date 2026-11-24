# Spark angle ABI audit — 1996/1997

## Verified source locations

| Item | 04887050 | 05293013AC |
|---|---|---|
| CalcBaseSpark | $1C082 | $141E4 |
| CalcSpark | $1BE80 | $14000 |
| SparkEventCalc | $1D006 | $15168 |
| FlexSparkValue (RAM offset) | $0603 | $0611 |
| SparkValueD0F | $0610 | $061E |
| SparkAdvanceD11 | $0612 | $0620 |
| RefPeriodLow | $0364 | $037E |

CalcBaseSpark returns a byte; CalcSpark stores it in FlexSparkValue, sign extends the correction bytes into a 16-bit accumulator, sums them, saturates to signed [-128,127], and publishes SparkValueD0F after fault/hold handling. SparkEventCalc reads that byte, applies per-event corrections (including per-cylinder knock), applies startup limits, then writes the final byte SparkAdvanceD11. Existing calibration convention is 0.5 degree/count. The storage format is NOT the physical timing resolution.

The bank-0 reference ISR uses at least three angle-to-timer arithmetic paths: subtraction from $8A, $62, $3A, followed by integer multiply/scaling. SparkOutputOc2 and related paths also compare the angle against $62/$3A, and the reference ISR compares against $30 and uses EventTimingLimit. There is a previous-angle history comparison with $0A threshold. Negative angles require particular attention: some consumers use byte arithmetic or unsigned branches while the angle sum itself is signed.

Therefore increasing only map word size cannot provide actual fractional-degree ignition. A new angle ABI would require consistent high-resolution publication, unchanged fault/startup/per-cylinder knock limits, verified scheduling branch boundaries, and atomicity between background and interrupt consumers. Do not allocate new RAM by assuming an erased/unused-looking cell is free; demonstrate lifetime and ISR ownership. Do not modify the timer or coil dwell path yet.

## Next verification gates

1. Finish exact Spark V1 and V1.1 regressions. Compare all 256x256x2 input tuples, stack and timing sample.
2. Build a test fixture for CalcSpark and SparkEventCalc with realistic state and correction inputs; trace every read/write and signed conversion. Test fault, cranking, startup, idle, WOT, knock and correction clamps.
3. Derive a separate model of each angle-to-timer path, then verify against actual CPU16 instructions and actual timer frequency. Quantify representable fractional angle by RPM and timer tick; preserve scheduling thresholds and dwell.
4. Only then choose a 16-bit angle format, allocation and atomic publication contract. Retain stock output ABI for diagnostics and fallback if possible. Do not treat simulation as hardware validation.

## Scope

Naturally aspirated only. No ROM output. No new ignition calibration, changes to protection, or timer modification in V1.1.

See [TIMER_ARITHMETIC.md](TIMER_ARITHMETIC.md) for the separate three-path timer audit and executable arithmetic checks.

See [v2/README.md](v2/README.md) for the separate high-resolution arithmetic experiment. It does not alter any firmware image.
