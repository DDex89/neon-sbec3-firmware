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
| `tools/gen_source.py` | Writes `00_equates.asm` and one source file per 64 KB bank, with names and notes from `annotations/` |
| `tools/caltables.py` | Finds the calibration tables from the calls to the lookup routines |
| `tools/catalogue.py` | Writes the calibration catalogue (`docs/catalogue/`) |
| `tools/xref.py` | Cross-reference of RAM variables and calibration addresses: who reads and writes them |
| `tools/port.py` | Carries the reference annotations over to another image (`annotations/ports/`) |
| `tools/caldiff.py` | Compares two images of one family table by table (`docs/diffs/`) |
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
| Register list | `PSHM D,E,X,Y,K`, `PULM K,X,D` | the order of the list does not matter |
| Symbol | `INC >PitTickCounter,Z`, `STD >SYNCR,Z` | `>` forces 16-bit, `<` 8-bit encoding, as in the original |

## Code-flow analysis

`tools/analyse.py` starts at the reset entry and at the exception vectors, follows branches, calls
and EXT20 jumps, and resolves **jump tables** reached by an indexed `JMP`:

- `JMP $base,X` or `JMP $base,Y` over a run of 4-byte `JMP $xxxxx` entries, a run of 4-byte
  `JSR $xxxxx` entries, or 6-byte `JSR` / `BRA` pairs. A preceding `CMPB #n` limits the count. An
  entry may be a short inline stub ending in `RTS`; if entry 0 is not a jump but entry 1 is, the
  caller never uses index 0 and the table starts at entry 1.
- `LDX #base` ... `CPX #limit` ... `JMP $00000,X`: entries between the two bounds.

In 05293190AC this finds 43,370 instructions (144,074 bytes) and 21 jump tables, with no unresolved
indirect jump. One jump goes into RAM ($F8700): a diagnostic service that runs code downloaded
through the SCI line (see [architecture.md](architecture.md)); it is listed separately, not as a
problem.

## Names and notes

`tools/gen_source.py` takes names from `annotations/`:

| File | Content |
|---|---|
| `labels.json` | code labels of the reference image |
| `vectors.json` | names of the exception vectors |
| `ram.json` | RAM variables, as offsets from Z |
| `hc16z_registers.json` | the 68HC16Z module registers (from the Z-series user's manual) |
| `routines.md` | notes printed above routines |
| `analysis.json` | where Z is not the RAM base; jumps into RAM |

Other labels are generated: `Sub_xxxxx` for call targets, `JumpTable_xxxxx`, `Lxxxxx` for the rest.
`$xxxx,Z` operands become `NAME,Z` when the offset is a known RAM variable or register; a byte access
to the low half of a 16-bit register gets the suffix `_L` (`SCDR_L` = low byte of SCDR). The symbols
used are written to `00_equates.asm`. Each routine has a header with its vectors, its callers and the
notes.

## Results

All eleven images rebuild byte for byte from generated sources. The repository holds the source of
one image per family (see [porting.md](porting.md)); the second image of a family differs only in
calibration bytes.

| Image | Instructions | Code bytes | Jump tables | Jump into RAM at |
|---|---|---|---|---|
| 05293190AC (reference) | 43,370 | 144,074 | 21 | $35AE2 |
| 05269833AI, 05269834AJ | 42,473 | 140,922 | 21 | $35ACE |
| 05269833AH | 41,340 | 136,844 | 21 | $35AA4 |
| 05032017AA | 43,970 | 145,938 | 21 | $35AC4 |
| 05293013AC, 05293014AC | 31,833 | 104,764 | 18 | $162F6 |
| 04887050, 04887051 | 30,371 | 99,534 | 17 | $130D6 |
| 05007038, 05293148AA | 33,139 | 107,118 | 19 | $1B158 |

Images of one family have the same instruction count, which supports the family grouping of
stage 1: same program, different calibration. No image has an unresolved indirect jump.

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
  (SIM) and `$791F,Z` = $FF91F (general-purpose timer). RAM variables are named by their offset
  from Z.
- **Extended addresses (`$xxxx`, EK = 0) point into bank 0**, that is into the calibration. Code in
  banks 1-3 reads calibration with plain `LDAA $19DC` style instructions.
- XK and YK are set often (`TBXK` 92 times, `TBYK` 117 times), so indexed table access across banks
  needs register tracking in the next stages.
