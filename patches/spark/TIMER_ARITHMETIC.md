# Angle-to-timer arithmetic audit

Atmospheric SBEC3 04887050 and 05293013AC. No timer code is changed. `timercheck.py` locates three exact instruction sequences in the original ROM, verifies their bytes are unchanged in the fuel+spark V1.1 composition, executes them instruction by instruction and compares with an independent integer model. The test includes all 256 raw angle bytes, multiple period values, anchors and wrap-around cases. The peripheral register CrankPeriodSum is a synthetic input, not an emulated timer. No claim is made about reachability of arbitrary combinations.

## Path 1
The stock instruction sequence computes an unsigned byte difference (138 - raw angle) modulo 256, multiplies by 182, multiplies by RefPeriodLow, rounds the high product word, adds CrankAC0 and subtracts 60, modulo 65536. An eighth of a stock angle count (0.0625 degree) corresponds to an *ideal local* delta of period * 182 / (8 * 65536) timer counts before rounding. This is not yet a proposed firmware change.

| RefPeriodLow (raw) | Ideal counts per 0.0625 degree |
|---:|---:|
| 1000 | 0.347 |
| 5000 | 1.736 |
| 10000 | 3.471 |
| 30000 | 10.414 |
| 60000 | 20.828 |

Thus the benefit depends on period and actual timer tick. No physical RPM conversion is asserted. At very negative synthetic angles (raw signed -118 or lower) the byte difference wraps; normal reachability must be audited rather than treating this as a proven stock defect.

## Paths 2 and 3
The constants are 98 and 58 raw angle counts; the signed conditional branch skips the arithmetic if the difference is nonpositive. A second quantization rounds the product by 205 after doubling and clears its low byte. The intermediate period is scaled differently in each path, including modulo-16-bit operations. The third path also stores the period difference. A wider angle must preserve the separate branch conditions and timer wrap semantics, not merely substitute a larger multiplication.

## Gates
Verify the isolated arithmetic tests, then audit the full reference ISR path selection, period formation, signed angle ranges, timer prescaler and physical tick on hardware. Verify coil dwell and output compare timing separately. V2 high-resolution maps and publication ABI are not implemented by this audit.
