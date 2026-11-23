# SBEC3 flash images: survey

First look at the images collected so far: what each file is, how the flash is laid out, the
checksum, and which images share code. Everything here can be reproduced with
`python3 tools/survey.py roms/*.bin`. Tags: **[code]** read from the images, **[source]** from a
named outside source, **[inferred]** a conclusion that still needs confirming.

## Images

| File | Flash | RAM (stack top) | Header | Reset entry | Family | Build stamp | Vehicle |
|---|---|---|---|---|---|---|---|
| `04887050` | 128 KB | 2 KB ($F87FE) | $03DDD | $0C760 | A | | unknown; copyright 1995, so 1996 model year [inferred] |
| `04887051` | 128 KB | 2 KB | $03DDD | $0C760 | A | | unknown, as above |
| `05293013AC` | 128 KB | 2 KB | $03E08 | $0C860 | B | 960716 | 1997 Eagle Talon, manual [source: 2GNT forum] |
| `05293014AC` | 128 KB | 2 KB | $03E08 | $0C860 | B | 961211 | 1997 Mitsubishi Eclipse (VIN 4A3AK44Y0VE097567 in the SBECBootLoader README) [source] |
| `05007038` | 128 KB | 2 KB | $00302 | $06A00 | C | | unknown; probably a Mopar Performance calibration [inferred] |
| `05293148AA` | 128 KB | 2 KB | $00302 | $06A00 | C | | unknown; probably the factory counterpart of 05007038 [inferred] |
| `05269833AH` | 256 KB | 4 KB ($F8FFE) | $00302 | $0D132 | D | 970804 | unknown; probably Neon [inferred] |
| `05269833AI` | 256 KB | 4 KB | $00302 | $0D08C | E | | unknown; probably Neon [inferred] |
| `05269834AJ` | 256 KB | 4 KB | $00302 | $0D08C | E | | unknown; probably Neon [inferred] |
| `05293190AC` | 256 KB | 4 KB | $00302 | $0D08C | F | 980929 | 1999 Mitsubishi Eclipse, manual [source: 2GNT forum and calibration page] |
| `05032017AA` | 256 KB | 4 KB | $00302 | $0D08C | G | | unknown; copyright 1998 |

- **Families.** Images with an identical exception vector table ($00000-$001FF) are put in one
  family; inside a family the vector tables, and so most likely the code, are the same. Families E,
  F and G share the reset entry and the padded block layout, so they are probably revisions of one
  program. How far the families differ will be measured once the disassembler exists (stage 2). [code]
- **Two generations of hardware.** 128 KB flash with 2 KB RAM (stack top $F87FE) and 256 KB flash
  with 4 KB RAM ($F8FFE). That matches the 68HC16Z2 (2 KB) and 68HC16Z3 (4 KB) named on the 2GNT
  forum. The build stamps of the 128 KB images are from 1996 and those of the 256 KB images from 1997
  and 1998. [code] [source]
- **Build stamp.** Four images contain a 12-digit string whose last six digits read as a date
  (960716 = 16 July 1996 and so on). [inferred]
- **Vehicle hints.** Part numbers 05269xxx are in the block of the 1995 Neon revisions (5269646,
  5269709, 5269712, 5269718, 5269738), and 5007xxx in the Mopar Performance block (P5007033 and
  P5007034 are the Mopar 1995 Neon calibrations). 05007038 also has $98 where the other headers
  have the first revision letter. These are hints only. [inferred]

### Notes on the files received

- `05293013AC` and `05293063AC` arrived as 256 KB files that hold the same 128 KB image twice
  (read from a 128 KB chip as if it were 256 KB). Only the first half is used.
- The file named `05293063AC` carries part number **05293148AA** in its header, so it is listed
  under that number.
- The files named `05269834AI` and `05269834aj` are identical and their header says **AJ**.
- `05293190AC_99_eclipse` and `05293013AC_97_taloon` were duplicates of `05293190AC` and
  `05293013AC`.

## Memory layout (first look)

| Range | Content |
|---|---|
| $00000-$00007 | CPU16 reset vector: word 0 holds ZK, SK and PK ($0FF0: ZK = 0, SK = F, PK = 0), then the initial PC, SP and IZ. The PC is the reset entry above; SP is $87FE or $8FFE in bank F, so RAM sits at $F8000 [code] |
| $00008-$001FF | Exception vectors, 16-bit addresses in bank 0. About 27 distinct targets; all unused vectors point to the reset entry [code] |
| $00200-$00203 | $0000 and the address of the header block [code] |
| $00204-$002FF | $FF filler (in families B, D and F only up to $00283 or $0028F, followed by data) [code] |
| Header block | Part number (4 bytes BCD), revision (2 ASCII letters), one byte ($A0 or $B0), six spaces, checksum correction byte (+13), then further bytes. Family A uses a different form: part number, $0A, part number again, $0A, one byte [code] |
| Calibration | Families A and B: header at the **end** of the calibration ($03DDD / $03E08), $FF up to $03FFF, code from about $04000. Families C-G: header at the **start**, $00302. In the 256 KB images the data ends around $04A1A-$04AE4 ($05839 in 05032017AA), followed by $FF up to $06FFF [code] |
| Code | 256 KB images: modules padded to 2 KB or 4 KB boundaries up to $3FFDB. Family C is packed without padding [code] |
| End | "COPYRIGHT 199x CHRYSLER CORPORATION" just before the end ($1FFDC or $3FFDC). Family C has no copyright string [code] |

Peripheral registers: the SBECBootLoader kernels reach the serial interface as `$7C0C,Z` with Z
set to $F8000, that is $FFC0C, the SCI status register of the 68HC16Z queued serial module
(registers at $FFxxx). [source: SBECBootLoader]

In bootstrap mode (voltage on SCI RX at power-on) RAM is mapped at $00000 and an 8 KB mask ROM
appears at $E0000; the flash is then reached at $40000 by the reflash kernels. [source: 2GNT forum,
SBECBootLoader]

## Checksum

The 8-bit sum of every byte of the image equals the last byte of the part number (header + 3);
header + 13 is the correction byte that is adjusted to make it so. This is the scheme of
`checksum.py` in SBECBootLoader, and it holds for all eleven images. It is the same idea as in the
1995 FCC firmware, where the sum must equal the last byte of the part number at $B805. [code]

In the code the check is `ChecksumCheck` ($2191E), called from `CheckPowerDown` (the power-down path)
once input bit $1000.3 has read set 32 times in a row, not at start-up. `SumBanks` ($2195E) adds the bytes of two banks at a time
(0 and 1, then 2 and 3) in 16 KB steps; the result is compared with `ChecksumTarget` ($0305 in
05293190AC) and a mismatch reports P0601. It is a plain 8-bit sum, not a CRC. TunerPro does not
correct it; run `tools/fixsum.py --fix` on an edited image. [code]

In family A, header + 13 is $FF; the byte after the repeated part number ($D3 / $06) is probably the
correction byte there. [inferred]

## Next steps

Stage 2 is done, see [tools.md](tools.md): disassembler, assembler and source generator, with all
eleven images rebuilt byte for byte. It also confirmed that Z points at RAM ($F8000) and that
extended addresses read the calibration in bank 0. The reference image is **05293190AC**, because
outside reference addresses exist for it. The project owner's 1996 Neon controller is expected to be
a 128 KB, 2 KB RAM unit; its family will be reached by porting the annotations.
