# Tools and build

The SBEC3 firmware is rebuilt from source with the project's own CPU16 tools: no free assembler
supports the 68HC16. The disassembler and the assembler use the same opcode table, so a
byte-identical rebuild checks both at once.

## Building

```sh
python3 tools/build.py              # assemble src/<part number>/ and check the SHA-256
```

This needs only Python 3 and the sources; no ROM image. The result goes to `build/`. CI runs the same
command on every push.

Regenerating a source from an image (needed only when the generator changes or for another image):

```sh
python3 tools/gen_source.py roms/05293190AC.bin src/05293190AC
python3 tools/survey.py roms/*.bin  # header, checksum and families of all images
```

## Files

| File | Purpose |
|---|---|
| `tools/cpu16_isa.json` | All 842 CPU16 opcodes: mnemonic, addressing mode, operand fields, size |
| `tools/cpu16.py` | Instruction decoder |
| `tools/syntax16.py` | Assembly syntax, shared by the generator and the assembler |
| `tools/asm16.py` | Two-pass assembler |
| `tools/analyse.py` | Code-flow analysis: what is code and what is data |
| `tools/gen_source.py` | Writes one source file per 64 KB bank |
| `tools/build.py` | Assembles and verifies against `tools/variants.json` |
| `tools/survey.py` | Survey of images (stage 1) |

## Opcode table

The table was extracted from the CPU16 Reference Manual (CPU16RM/AD): Table 6-36 "Instruction Set
Summary" gives mnemonic, addressing mode, opcode and operand format, and Tables 7-2 to 7-5 list the
four opcode pages in order. Both agree on all 842 opcodes (246 on page 0, 186 on page 1 behind
prebyte $17, 202 on page 2 behind $27, 208 on page 3 behind $37). Every instruction is a whole
number of 16-bit words (2, 4 or 6 bytes), as the CPU16 requires.

Two CPU16 details matter for the tools:

- Branch offsets are relative to the address of the instruction **plus 6**, because of the
  three-word prefetch pipeline (CPU16RM 7.3). Offsets are added on 20 bits (PK : PC).
- `JMP` and `JSR` take a 20-bit address (EXT20) or a 20-bit offset from an index register (IND20).

## Syntax

Close to Motorola's, with every width explicit so that the assembler reproduces the original
encoding:

| Mode | Example | Note |
|---|---|---|
| Immediate | `LDAA #$12`, `LDD #$1234` | 2 hex digits = 8 bit, 4 = 16 bit |
| Indexed | `LDAA $12,Z`, `STD $7A04,Z`, `JMP $2CE5E,X` | 2 digits = IND8, 4 = IND16 (written unsigned), 5 = IND20 |
| Extended | `CMPA $19DC`, `JSR L0C440` | 4 digits = EXT (bank from EK), 5 digits or a label = EXT20 |
| Accumulator offset | `LDAA E,X` | |
| Branch | `BRA L080B4`, `LBNE L08B52` | Bcc = 8-bit offset, LBcc = 16-bit |
| Bit operations | `BSET $0A,Z,#$02`, `BRSET $0332,#$08,L2CE6C` | address, mask, target |
| Move | `MOVB $05,X+,$1234`, `MOVW $1234,$5678` | |
| Register mask | `PSHM #$2F`, `PULM #$20` | raw mask for now |

## Code-flow analysis

`tools/analyse.py` starts at the reset entry and at the exception vectors, follows branches, calls
and EXT20 jumps, and resolves **jump tables**: an index scaled by 4 in X followed by
`JMP $base,X`, where the base holds a run of 4-byte `JMP $xxxxx` entries (a preceding `CMPB #n`
limits the count). Tables may start at any even address. In 05293190AC this finds 40,760
instructions (135,104 bytes) and 16 jump tables. Four indirect jumps are not resolved yet: they go
through pointers loaded from data (stage 3). Code reached only through them is still emitted as
`dc.b`, which does not affect the rebuild.

## Results

All eleven images rebuild byte for byte from generated sources. Only the reference image,
05293190AC, has its source in the repository; the others will follow once the annotations are
ported to their families.

| Image | Instructions | Code bytes | Jump tables |
|---|---|---|---|
| 05293190AC (reference) | 40,760 | 135,104 | 16 |
| 05269833AI, 05269834AJ | 39,878 | 132,032 | 16 |
| 05269833AH | 38,744 | 127,960 | 16 |
| 05032017AA | 41,375 | 137,048 | 16 |
| 05293013AC, 05293014AC | 29,487 | 96,882 | 13 |
| 04887050, 04887051 | 28,336 | 92,770 | 12 |
| 05007038, 05293148AA | 30,646 | 98,734 | 14 |

Images of one family have the same instruction count, which supports the family grouping of
stage 1: same program, different calibration.

## Check against the 2GNT reference addresses

The calibration addresses that 2GNT lists for 05293190AC were checked against the analysis. All of
them lie outside the code, and most are loaded by code as table pointers:

| Address | 2GNT name | Referenced by |
|---|---|---|
| $1BFA | part-throttle spark | `LDX #$1BFA` at $1D2A6 |
| $1FAF | WOT spark | `LDX #$1FAF` at $1D2C4 |
| $08F8 | part-throttle Y scale | `LDX #$08F8` at $10F46, $1DA42 and others |
| $0904 | WOT Y scale | `LDX #$0904` at $1D2B4 |
| $24AB | knock sensor threshold | `LDX #$24AB` at $1F360 |
| $0B9E | returnless fuel scale | `LDX #$0B9E` at $1090A, $10AFC |
| $0B76 | injector dead time | `LDX #$0B76` at $10020 |
| $19DC | MTX / PN rev limit | `CMPA $19DC` at $101F8, `LDAB $19DC` at $20C86 |
| $4052 | fault attribute array | `ADDD #$4052` at $20A8C, `LDX #$4052` at $326BE and others |
| $2684 | target idle RPM | `LDX #$2684` at $1B344 |

The fuel tables ($0BF6, $0F6C) and their MAP offset and K constants ($0B92-$0B95) are not loaded
directly: their addresses appear as data words around $11F4E-$11FC2, so they are reached through a
descriptor table. That is a stage 4 topic.

## Memory model seen in the code

The reset routine sets SK = ZK = $F, SP = $8FFE and IZ = $8000, and EK = 0. So:

- **Z points at $F8000, the start of RAM.** `$xx,Z` and `$0xxx,Z` address RAM ($F8000-$F8FFF on
  the 4 KB parts); `$7xxx,Z` reaches the module registers at $FFxxx, for example `$7A00,Z` = $FFA00
  (SIM) and `$791F,Z` = $FF91F (general-purpose timer). RAM variables will be named by their offset
  from Z.
- **Extended addresses (`$xxxx`, EK = 0) point into bank 0**, that is into the calibration. Code in
  banks 1-3 reads calibration with plain `LDAA $19DC` style instructions.
- XK and YK are set often (`TBXK` 92 times, `TBYK` 117 times), so indexed table access across banks
  needs register tracking in the next stages.
