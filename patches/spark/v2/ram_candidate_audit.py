#!/usr/bin/env python3
"""Conservative source audit of the unallocated 05F2..05FF RAM candidate.

No allocator or ownership proof. Checks direct Z-relative operands including
the preceding three bytes, to catch a potential multi-byte access spanning
the candidate. Reports unresolved indirect accesses separately: static absence
of named/direct references is NOT proof of free RAM.
"""
import re
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
LO, HI = 0x5F2, 0x5FF
VARIANTS = {
    "04887050": (0x3D9E, "BatteryTempInputs"),
    "05293013AC": (0x3DC9, "Sub_11EFC"),
}

def audit(pn):
    base = ROOT / "src" / pn
    eq = dict((name, int(val, 16)) for name, val in re.findall(
        r"^(\w+)\s+equ\s+\$([0-9a-fA-F]+)[^\n]*?\$F8",
        (base/"00_equates.asm").read_text(), re.M))
    named = {n: a for n, a in eq.items() if LO <= a <= HI}
    assert not named, (pn, named)
    direct, nearby, battery = [], [], []
    addr, routine = VARIANTS[pn]
    for bank in ("bank0", "bank1"):
        label = ""
        for i, line in enumerate((base/(bank+".asm")).read_text().splitlines(), 1):
            line = line.split(";")[0].strip()
            if re.fullmatch(r"\w+:", line) and not re.fullmatch(r"L[0-9A-Fa-f]+:",line):
                label = line[:-1]
            m = re.match(r"^(\w+)\s+[<>]?(\$[0-9A-Fa-f]+|\w+),Z(?:,|$)", line)
            if m:
                operand = m[2]
                a = int(operand[1:],16) if operand.startswith("$") else eq.get(operand)
                if a is not None and LO <= a <= HI:
                    direct.append((bank,i,label,line))
                elif a is not None and LO-3 <= a < LO:
                    nearby.append((bank,i,label,line))
            if bank=="bank1" and label==routine:
                for b in (addr,addr+1):
                    if re.fullmatch(r"CMPA\s+\$%04X"%b,line):
                        battery.append(b)
    assert not direct, (pn,direct)
    # The two 1997 neighboring accesses are proven one-byte opcodes at
    # 05EF. Keep all other near-start accesses blocked, including unknown
    # widths. Verify the exact signatures, not just the number of hits.
    expected = [] if pn == "04887050" else [
        ("bank0","AccelEnrichFactors","STAA", "AccelTpsBaroFactor"),
        ("bank0","FinishFuelPulse","LDAB", "AccelTpsBaroFactor"),
    ]
    observed = []
    for bank,i,label,line in nearby:
        m = re.fullmatch(r"(STAA|LDAB)\s+>(AccelTpsBaroFactor),Z",line)
        assert m and eq[m[2]] == 0x5EF, (pn,bank,i,line)
        observed.append((bank,label,m[1],m[2]))
    assert sorted(observed)==sorted(expected), (pn,observed)
    assert sorted(battery)==[addr,addr+1], (pn,battery)
    print(f"{pn}: no named/direct candidate operands; {len(nearby)} reviewed nonoverlapping byte accesses")
    print(f"{pn}: ROM ${addr:04X}/${addr+1:04X} are separate CMPA operands in {routine}")
    print("Still open: computed pointers, implicit accesses, diagnostic aliases, reset lifecycle, "
          "1997 05FB ROM pattern; no RAM reservation.")


def audit_page_pointers(pn):
    """Inventory literal X/Y loads and comparisons in page 85.
    This freezes known source signatures, not computed-pointer reachability.
    """
    base = ROOT / "src" / pn
    first, second, learn1, learn2 = (
        (0x8500,0x8521,0x85A1,0x85A8) if pn=="04887050" else
        (0x850F,0x8530,0x85B1,0x85B8))
    expected = [
        ("O2UpdateUpstream","LDX",first),("O2UpdateUpstream","LDX",second),
        ("O2UpdateDownstream","LDX",first),("O2UpdateDownstream","LDX",second),
        ("O2DownTrim","CPX",first),
        ("ClosedLoopManager","LDX",first),("ClosedLoopManager","LDY",second),
        ("O2UpTrim","CPX",first),
        ("O2CellSelect","LDY",learn1),("O2CellSelect","LDY",learn2),
        ("O2LearnEnable","CPY",learn1),("O2LearnEnable","CPY",learn2),
    ]
    actual=[]
    for bank in ("bank0","bank1"):
        label=""
        for line in (base/(bank+".asm")).read_text().splitlines():
            line=line.split(";")[0].strip()
            if re.fullmatch(r"\w+:",line) and not re.fullmatch(r"L[0-9A-Fa-f]+:",line):
                label=line[:-1]
            m=re.fullmatch(r"(LDX|LDY|CPX|CPY)\s+#\$(85[0-9A-Fa-f]{2})",line)
            if m:
                assert bank=="bank0",(pn,bank,label,line)
                actual.append((label,m[1],int(m[2],16)))
    assert sorted(actual)==sorted(expected),(pn,actual)
    # The spacing of O2 banks is 0x21; last word in O2DownTrim
    # is at offset 0x1F and occupies bytes 0x1F..0x20.
    assert second-first==0x21
    assert second+0x20 < 0x8000+LO
    print(f"{pn}: {len(actual)} literal page-85 X/Y signatures; "
          f"O2 bank extents ${first:04X}-${first+0x20:04X}, "
          f"${second:04X}-${second+0x20:04X}; no overlap by these fixed extents")
    print("Computed aliases, alternate bases, cal tables and reset remain unproven.")


if __name__=="__main__":
    for pn in VARIANTS:
        audit(pn)
        audit_page_pointers(pn)
