# Other families

The annotations are made on the reference image 05293190AC (family F). `tools/port.py` carries
them over to every other image; `tools/gen_source.py` then uses the carried-over set, so each
image gets names, table layouts and symbols without being annotated by hand.

## How the port works

The two programs are matched routine by routine:

1. **Anchors**: the reset entry and the handler of each exception vector.
2. **Unique routines**: a routine whose sequence of opcodes and addressing modes (operands left
   out) occurs exactly once in each image.
3. **Table shapes**: a routine that reads the same sequence of 3D table shapes (rows, columns,
   signed) as exactly one routine in the other image. This finds the fuel and spark routines even
   where their code changed.
4. **Mnemonics only**: a routine whose sequence of mnemonics is unique, for code whose
   addressing modes changed between program versions.
5. **Propagation**: two matched routines are aligned instruction by instruction (or on their
   common runs when they are at least 60 % alike); the routines they call are matched in turn.
   The lookups inside two matched routines are paired in call order when the table kinds agree.

The aligned instructions give the address map for code labels. Their operands give the maps for
RAM offsets (`$xxxx,Z`) and calibration addresses (`LDX #table`, `$xxxx`); a name is carried over
only when at least 80 % of the aligned instructions agree on the new address.

The result is written to `annotations/ports/<part number>/` (labels, RAM, tables, analysis) with
`stats.json`, which also holds the SHA-256 of the image so that the set is never applied to the
wrong file. These files are generated: change the reference annotations and re-run the port.

## Results

| Image | Family | Size | Routines matched | Instructions mapped | Labels | RAM names | Tables | Constants |
|---|---|---|---|---|---|---|---|---|
| 05269833AI, 05269834AJ | E | 256 KB | 654 of 657 | 42,461 of 43,370 | 35 of 35 | 55 of 55 | 402 of 410 | 8 of 8 |
| 05269833AH | D | 256 KB | 618 | 37,929 | 35 | 55 | 361 | 8 |
| 05032017AA | G | 256 KB | 623 | 39,434 | 34 | 55 | 351 | 6 |
| 05007038, 05293148AA | C | 128 KB | 301 | 15,809 | 19 | 39 | 167 | 6 |
| 05293013AC, 05293014AC | B | 128 KB | 194 | 8,103 | 17 | 39 | 134 | 6 |
| 04887050, 04887051 | A | 128 KB | 170 | 7,042 | 17 | 37 | 131 | 6 |

The 256 KB families are close relatives of the reference: almost everything carries over, and
the RAM layout is nearly the same. The 128 KB families are an older, smaller program (30,000 to
33,000 instructions) with a 2 KB RAM laid out differently; there the port covers the skeleton
(reset, interrupts, scheduler counters, lookup routines) and the main fuel and spark paths:
`CalcFuelPulse`, `CalcBaseSpark`, both fuel and spark tables, the MAP scales, the fuel constants,
dead time, knock threshold, the thermistor curves, `EngineRpm`, `Map`, `CoolantTemp`, `Throttle`
and others. The lookup routines and table formats are the same in all families, so every table is
found and laid out in every image, named or not.

## Sources in the repository

One image per family has its source in `src/` and is checked by the build:

| Family | Image | Note |
|---|---|---|
| A | 04887050 | copyright 1995, probably 1996 model year |
| B | 05293013AC | 1997 Eagle Talon, manual |
| C | 05007038 | probably a Mopar Performance calibration |
| D | 05269833AH | probably Neon |
| E | 05269833AI | probably Neon |
| F | 05293190AC | reference, 1999 Mitsubishi Eclipse, manual |
| G | 05032017AA | copyright 1998 |

Each has its catalogue in [docs/catalogue/](../catalogue/). The second image of a family differs
from the first only in calibration bytes (no code byte differs); `tools/caldiff.py` lists those
differences table by table:

| Comparison | Differing bytes | In tables | Directly read constants |
|---|---|---|---|
| [05293148AA and 05007038](../diffs/05293148AA_05007038.md) (C) | 2,214 | 1,743 in 63 tables | 105 |
| [04887050 and 04887051](../diffs/04887050_04887051.md) (A) | 939 | 620 in 58 tables | 118 |
| [05293013AC and 05293014AC](../diffs/05293013AC_05293014AC.md) (B) | 955 | 633 in 58 tables | 121 |
| [05269833AI and 05269834AJ](../diffs/05269833AI_05269834AJ.md) (E) | 1,021 | 683 in 69 tables | 122 |

In family C, 05007038 rewrites both fuel tables and both spark tables almost completely compared
with 05293148AA, plus about 60 smaller tables; that fits a performance calibration for the same
program.

## Open points

- The 128 KB port covers about a quarter of the program. More anchors (named routines in the
  reference) raise it, since every new match propagates to the routines it calls.
- Vehicle and engine of most images are still unknown; the fault tables (cylinder count) and the
  calibration differences are the next clues.
