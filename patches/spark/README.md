# Spark V1 — exact-behaviour optimization

Atmospheric engines only. The first experiment preserves the original 8-bit maps, 0.5 degree angle representation, and the original interpolation arithmetic. No new angle calibration is introduced; stock XDF spark addresses remain valid on the composed image. No widening of the downstream ABI yet.

| ROM | CalcBaseSpark | Lookup3D continuation | PT / WOT table |
|---|---|---|---|
| 04887050 | $1C082 | $0E598 | $1544 / $1497 |
| 05293013AC | $141E4 | $0E698 | $155C / $14AF |

The two original JSRs are replaced with same-size JSRs to a small bank-0 stub. It reuses the existing fuel Q11 RPM index at $0FE00, truncating the 11-bit fraction to the original 8-bit fraction. WOT uses it for all RPM bytes; PT reuses it except 48..62 inclusive, because the PT spark axis contains 54 instead of 55. The fallback calls the original Lookup3D unchanged. The stub prepares the original stack/register contract and jumps to the stock lookup continuation. Both original MAP scales remain unchanged. The original interpolation kernel and all post-base corrections remain unchanged. This version requires the fuel Q11 profile.

`simulate.py` checks original SHA, two hook signatures, shared index compatibility across every relevant RPM byte, memory overlap, checksum, stack balance and exact base-spark output plus non-stack RAM writes against stock and fuel-only images. A separate mathematical bilinear reference is also compared. Full mode tests all 256 MAP x 256 RPM x 2 modes. A sampled timing profile is separate from full ISR timing.

```sh
python3 tools/build.py 04887050 05293013AC
python3 patches/spark/simulate.py 04887050
python3 patches/spark/simulate.py 05293013AC --full
```

Do not infer accuracy of the physical ignition event from this isolated test. Next: trace CalcSpark/SparkEventCalc/angle-to-timer, audit shared scratch and interrupt interleaving, then consider a higher-resolution angle path without removing knock, temperature, startup, dwell or fault corrections. No modified ROM is exported.
