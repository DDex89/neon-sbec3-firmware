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
    # Conservatively fail on ANY operand starting in the three bytes before
    # the candidate, rather than presuming its access width.
    assert not nearby, (pn,nearby)
    assert sorted(battery)==[addr,addr+1], (pn,battery)
    print(f"{pn}: no named/direct Z-relative candidate or preceding-three-byte operands")
    print(f"{pn}: ROM ${addr:04X}/${addr+1:04X} are separate CMPA operands in {routine}")
    print("Still open: computed pointers, implicit accesses, diagnostic aliases, reset lifecycle, "
          "1997 05FB ROM pattern; no RAM reservation.")

if __name__=="__main__":
    for pn in VARIANTS:
        audit(pn)
