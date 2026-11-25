#!/usr/bin/env python3
"""Audit diagnostic override aliases and fine-angle qualification.

Source signatures and host policy only. Not a ROM hook or an interrupt proof.
The existing SCI interface remains unchanged. Invalidate base readiness on
override/hold writes, including indexed SCI writes to the parameter block.
At event entry independently honor the actual stock bypass decisions.
Already published event history stays paired with its own legacy angle.
"""
from itertools import product
from pathlib import Path
import re
ROOT=Path(__file__).resolve().parents[3]
CONFIG={"04887050":0x8395,"05293013AC":0x83AF}

def audit(pn):
    root=ROOT/"src"/pn
    eq={n:int(v,16) for n,v in re.findall(r"^(\w+)\s+equ\s+\$([0-9A-Fa-f]+)",
        (root/"00_equates.asm").read_text(),re.M)}
    base=CONFIG[pn]
    assert eq["FuelPulseOptFlags"]==base-0x8000
    assert eq["CalcSparkC51"]==base-0x8000+1
    lines=[l.split(";")[0].strip() for l in (root/"bank1.asm").read_text().splitlines()]
    i=lines.index("SciRequestReceive:")
    hits=[j for j,l in enumerate(lines) if l.split()==["LDX",f"#${base:04X}"]]
    assert len(hits)==1 and hits[0]>i
    j=hits[0]
    assert [l.split() for l in lines[j-4:j+3]]==[
        ["ANDB","#$07"],["CMPB","#$04"],["BEQ",lines[j-2].split()[1]],
        ["TZX"],["LDX",f"#${base:04X}"],["ABX"],["STAA","$00,X"]]
    # Index 4 branches away; 5..7 are not proven unreachable by this
    # local signature. Conservatively include all remaining possibilities.
    destinations={base+i for i in range(8) if i!=4}
    assert base in destinations and base+1 in destinations
    # The directly named hold-bit writes appear in these exact source groups.
    labels=[]; label=""
    for l in lines:
        if re.fullmatch(r"\w+:",l) and not re.fullmatch(r"L[0-9A-Fa-f]+:",l):
            label=l[:-1]
        if l.split() in (["BSET",">SparkFaultFlags,Z,#$20"],
                         ["BCLR",">SparkFaultFlags,Z,#$20"]):
            labels.append((label,l.split()[0]))
    assert sorted(labels)==sorted([
        ("GearStateUpdate","BCLR"),("ThrottleInputs","BCLR"),
        ("DiagRunRamCode","BCLR"),("DiagRunRamCode","BSET")]),(pn,labels)
    print(f"{pn}: SCI indexed override aliases ${base:04X}/${base+1:04X}; "
          "four named hold-bit writes verified")
    print("Index reachability and diagnostic dispatch timing are not established.")

def ordinary(override,throttle,dashpot,fault,hold):
    # Exactly the CalcSpark tail condition, separate from event bypass.
    return not override and not (hold if throttle or dashpot else fault)

def event_eligible(base_valid,running,override,hold,debug,cancelled):
    return base_valid and running and not (override or hold or debug or cancelled)

def model():
    cases=0
    for override,throttle,dashpot,fault,hold in product((False,True),repeat=5):
        normal=ordinary(override,throttle,dashpot,fault,hold)
        for valid,running,debug,cancelled in product((False,True),repeat=4):
            allowed=event_eligible(valid and normal,running,override,hold,debug,cancelled)
            if allowed:
                assert not override and not hold and normal and valid and running
            if override or hold or not normal or debug or cancelled or not running or not valid:
                assert not allowed
            cases+=1
    assert cases==512
    print(f"{cases} host branch combinations; no fine event in a modeled forced/bypass state.")

if __name__=="__main__":
    for pn in CONFIG: audit(pn)
    model()
