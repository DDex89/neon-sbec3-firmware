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
   A callee is taken over from a call site only if the two callees also look alike (35 % alike,
   or the same first instructions): a run of calls shifts when a call is added or removed, and
   such a shift would pair the wrong routines. The lookups inside two matched routines are paired
   in call order when the table kinds agree.
6. **Fuzzy pass**: each routine still open gets its best candidate by mnemonic similarity and by
   how many of its matched callers and callees agree; the pair is accepted only when it is the
   best in both directions by a clear margin. These pairs are aligned on longer runs only, and
   their operands name RAM and calibration only where the other pairs say nothing.
7. **Chain** (128 KB families): B also takes names from the port of C, and A from the port of B,
   for whatever the reference left open. A and B are closer to each other and to C than to F.

The aligned instructions give the address map for code labels. Their operands give the maps for
RAM offsets (`$xxxx,Z`) and calibration addresses (`LDX #table`, `$xxxx`); a name is carried over
only when at least 80 % of the aligned instructions agree on the new address. When two reference
names land on the same new address, the one with more votes keeps it; on a tie neither does.
Option bytes are named by their address (`Options0331`); the same option byte can sit elsewhere
in another image, so a carried-over option takes the name of its new address, with the bit texts
of the reference byte (in 05007038 the byte the reference calls `Options033A` is `Options0331`).
`stats.json` lists these renames. Structures taken over with the row count of the reference (bit maps, word lists, fault rows) are
cut where the next named item or code starts, so a shorter list in an older program does not run
into the code after it.

**Hand names.** For the images whose code differs most from the reference, the routines the port
leaves open are named by reading the code: `annotations/hand/05007038/` (also used for
05293148AA) and `annotations/hand/04887050/` (also 04887051) hold labels, RAM names, bit texts and
routine notes. `tools/port.py` lays them over the carried-over names (a hand name wins and the
same name elsewhere is dropped), and the chain takes the names of C on to B. In C and A every
routine now has a name; B still has 56 `Sub_` routines.

The result is written to `annotations/ports/<part number>/` (labels, RAM, tables, analysis) with
`stats.json`, which also holds the SHA-256 of the image so that the set is never applied to the
wrong file. These files are generated: change the reference annotations and re-run the port
(05007038 before 05293013AC/14AC, those before 04887050/51).

## Results

| Image | Family | Size | Routines matched | Instructions mapped | Labels | RAM names | Tables | Constants |
|---|---|---|---|---|---|---|---|---|
| 05269833AI, 05269834AJ | E | 256 KB | 654 of 657 | 42,460 of 43,370 | 651 of 680 | 1,800 of 1,871 | 402 of 410 | 1,404 of 1,451 |
| 05269833AH | D | 256 KB | 642 | 40,076 | 639 | 1,735 | 391 | 1,351 |
| 05032017AA | G | 256 KB | 647 | 42,145 | 644 | 1,802 | 385 | 1,399 |
| 05007038, 05293148AA | C | 128 KB | 409 + 60 by hand | 23,699 | 457 | 1,168 | 295 | 861 |
| 05293013AC, 05293014AC | B | 128 KB | 320 | 16,963 | 355 | 955 | 241 | 701 |
| 04887050, 04887051 | A | 128 KB | 297 + 59 by hand | 15,417 | 397 | 877 | 240 | 695 |

The 256 KB families are close relatives of the reference: almost everything carries over, and
the RAM layout is nearly the same. The 128 KB families are an older, smaller program (30,000 to
33,000 instructions) with a 2 KB RAM laid out differently. There the port now covers about half
of the code of family C and a third of A and B: the skeleton (reset, interrupts, scheduler,
lookups, CCD/SCI), the fuel and spark paths (`CalcFuelPulse`, `CalcBaseSpark` and the tables they
read), idle, fan, purge, the sensor processing and most of the OBD monitors. The lookup routines
and table formats are the same in all families, so every table is found and laid out in every
image, named or not.

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

- In family B 56 routines have no name yet (most of them the OBD monitors that A also has: the
  names of A could be chained to B the same way).
- Bit texts in the 128 KB images come from the reference by RAM name; where a byte is used
  differently in the older program the text can be wrong. The option bytes are the worst case:
  their bit layout changed between the generations, so carrying the reference text by byte gives
  the wrong meaning. For families A, B and C every tested option bit and EquipmentFlags have hand
  texts read from the routines that test them (`annotations/hand/04887050/bits.json`,
  `annotations/hand/05293013AC/bits.json`; in B the bytes from $0328 on sit two bytes higher than
  in A). Family C has them too (`annotations/hand/05007038/bits.json`, with the development port
  bit, Options0331 bit 4).
- Vehicle and engine of most images are still unknown; the fault tables (cylinder count) and the
  calibration differences are the next clues.
