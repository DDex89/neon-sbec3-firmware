# Timing and bench validation

## Status

The 61,312 numerical/edge cases passed in [CI 45491429928](https://github.com/DDex89/neon-sbec3-firmware/actions/runs/45491429928). Both ROMs gave identical numerical results: 0.94/1.91 maximum PT/WOT reference error in pulse counts; mean stock CalcFuel432 difference 0.521%/0.111%; peak executed instructions 337/343 (stock/patched).

## Timing profile

```sh
python3 tools/build.py 04887050 05293013AC
python3 patches/dinofuel/timing.py 04887050
python3 patches/dinofuel/timing.py 05293013AC
```

Optional `--dense` uses a denser input grid. The profiler executes real instruction paths in the existing simulator, sums nominal CPU16 instruction times, records minimum SP (including the synthetic return frame), and adjusts for misaligned word operands. It also reports scenarios with a 2-, 3- and 4-clock 16-bit flash bus and a 2-clock RAM bus. The peak paired delta is reported separately from differences of independent maxima.

References: [Motorola CPU16RM, table 6-36 and chapter 8](https://www.nxp.com/docs/en/reference-manual/CPU16RM.pdf); [Motorola EB251, tables 1-3](https://www.nxp.com/docs/en/engineering-bulletin/EB251.pdf). The bit-test branch timing uses the taken/non-taken ordering implied by EB251, rather than the ambiguous pair order in table 6-36.

Both early ROMs write SYNCR=$7F80, PITR=$0007, CSORBT=$6870, CSOR0=$7070, CSOR2=$7870. The 16.777216 MHz scenario assumes a 32.768 kHz reference as described for the later reference image in docs/en/architecture.md. Verify oscillator, actual flash bus width and termination on the physical early ECU. Do not assume the entire ISR has the same time budget as this single routine. The profile does not include pipeline/bus interactions outside the routine, other interrupts, peripheral latency, or an exhaustive WCET proof.

## Bench acceptance sequence (no engine connected)

1. Preserve and verify the original ROM and EEPROM independently; establish readback/recovery on a spare ECU before any experimental write. Confirm exact ROM identity.
2. Validate the XDF in the actual TunerPro GUI against a copy; change one known cell, inspect the two expected bytes and confirm the checksum on the resulting bench image. Do not use the stock XDF on the new tables.
3. Establish stock baseline on a current-limited bench supply with a suitable harness, simulated crank/cam signals, sensor inputs and rated dummy loads. No fuel system, ignition coils or vehicle connected. Record scope traces and supply current.
4. Repeat the same input matrix with the experimental image. Compare injector pulse widths and event scheduling against the stock baseline and simulator predictions, including MAP boundary transitions, low RPM, high RPM, WOT enrichment, and return to stock paths. Stop on reset, missed event, unexpected output or excessive current.
5. Confirm timing with the actual clock and bus configuration and compare event scheduling at the highest intended test frequency. An isolated routine profile is not proof that total interrupt latency is acceptable.
6. Record part number, SHA-256, calibration revision, hardware version, test conditions and raw scope captures. Keep stock recovery available.

No actual TunerPro session or physical bench test has been performed by the automated tools. This prototype remains experimental; no on-vehicle flashing.
