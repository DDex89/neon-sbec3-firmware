#!/usr/bin/env python3
"""Check O2 descriptor and adaptive-cell computed RAM aliases against Q4.

Exact factory ROM and source anchors; NOT a global RAM ownership proof.
Descriptor offsets are read from the built ROM, not guessed from labels.
Cell index is conservatively allowed every byte, including corrupt values.
Only the identified O2CellUpdate caller bases and purge path are covered.
"""
import hashlib
import json
from pathlib import Path
import re
from itertools import product

ROOT=Path(__file__).resolve().parents[3]
CANDIDATE=set(range(0x85F2,0x8600))
CONFIG={
    "04887050": (0x86DC, (0x803F,0x804D,0x8050,0x805E)),
    "05293013AC": (0x87CA, (0x8040,0x804E,0x8051,0x805F)),
}

def audit(pn):
    rom=(ROOT/"build"/(pn+".bin")).read_bytes()
    spec=json.loads((ROOT/"tools/variants.json").read_text())[pn]
    assert hashlib.sha256(rom).hexdigest()==spec["sha256"]
    desc,bases=CONFIG[pn]
    lines=[" ".join(l.split(";")[0].split()) for l in
           (ROOT/"src"/pn/"bank0.asm").read_text().splitlines()]
    start=lines.index("ClosedLoopManager:")
    i=lines.index(f"LDY #${desc:04X}",start)
    assert i-start<200
    assert lines[i-2].startswith("LBHI ")
    assert lines[i-3]=="CPE #$0003" and lines[i-1]=="PSHM E"
    assert lines[i+1:i+7]==["LDD #$000E","EMUL","ADY","TPD","TBYK","CLRB"]
    block=lines[i:i+60]
    for op in ("LDE $0000,Y","LDE $0002,Y","LDAA E,Z","STAA E,Z",
               "LDX $06,Y","LDX $08,Y","CMPA $00,X","TBXK"):
        assert op in block,(pn,op)
    def word(addr):
        return int.from_bytes(rom[addr:addr+2],"big")
    for index in range(4):
        p=desc+14*index
        raw,timer=word(p),word(p+2)
        thresholds=(word(p+6),word(p+8))
        assert raw<0x800 and timer<0x800,(pn,index,raw,timer)
        assert not CANDIDATE.intersection((0x8000+raw,0x8000+timer)),(pn,index,raw,timer)
        # X bank is zero here, so both thresholds are ROM reads.
        assert lines[i+6:i+8]==["CLRB","TBXK"]
        assert all(v<len(rom) for v in thresholds)
        print(f"{pn} O2 descriptor {index}: raw RAM ${0x8000+raw:04X}, "
              f"timer RAM ${0x8000+timer:04X}, ROM thresholds "
              f"${thresholds[0]:04X}/${thresholds[1]:04X}")
    # Both direct callers establish RAM X/Y bases. Verify their signatures.
    start=lines.index("O2LearnEnable:")
    end=lines.index("O2CellUpdate:")
    body=lines[start:end]
    for x,y in zip(bases[::2],bases[1::2]):
        i=body.index(f"LDX #${x:04X}")
        assert body[i-1:i+5]==["TZX",f"LDX #${x:04X}","STX >Scratch6,Z",
                               "TZY",f"LDY #${y:04X}","STY >Scratch4,Z"]
        assert body[i+5:i+10]==[
            f"LDAA >ShortTermTrim{1 if x==bases[0] else 2},Z","STAA >Scratch2,Z",
            f"LDAA >ClosedLoop{'704' if x==bases[0] else '72C'},Z","STAA >Scratch3,Z",
            "JSR O2CellUpdate"]
    assert sum(l=="JSR O2CellUpdate" for l in lines)==2
    block=lines[end:end+35]
    assert block[1:3]==["LDAB >O2MemCell,Z","ABX"]
    assert block.count("AIY #$01")==2
    assert "XGDY" in block and "XGDX" in block
    # Include a two-byte access conservatively even though the indexed
    # adaptive cells are bytes. No bound on the cell index is assumed.
    touched=set()
    for x,b in product(bases[::2],range(256)):
        touched.update((x+b,x+b+1))
    for y,offset in product(bases[1::2],range(3)):
        touched.update((y+offset,y+offset+1))
    assert not touched&CANDIDATE
    print(f"{pn}: {len(touched)} possible bytes in selected cell/purge address ranges "
          f"${min(touched):04X}..${max(touched):04X}; candidate disjoint")
    print("Does not prove other X/Y/E indexed paths, diagnostic aliases or global allocation.")

if __name__=="__main__":
    import argparse
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pn",choices=CONFIG)
    audit(ap.parse_args().pn)
