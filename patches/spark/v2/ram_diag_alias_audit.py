#!/usr/bin/env python3
"""Audit stock diagnostic indexed stores near the Q4 allocation candidate.

Source signatures and conservative address ranges only. Arbitrary uploaded
RAM code, hardware faults, other indirect accesses remain out of scope.
DiagRamAddrAllowed gates EEPROM writes, not a general RAM-write sandbox.
"""
from pathlib import Path
import re
ROOT=Path(__file__).resolve().parents[3]
CAND=set(range(0x85F2,0x85F7))
CONFIG={"04887050":(0x8395,0x803F,0x8062),
        "05293013AC":(0x83AF,0x8040,0x8063)}

def audit(pn):
    lines=[" ".join(l.split(";")[0].split()) for l in
           (ROOT/"src"/pn/"bank1.asm").read_text().splitlines()]
    start=lines.index("SciRequestReceive:")
    end=lines.index("DiagCommandMain:")
    body=lines[start:end]
    stores=[i for i,l in enumerate(body) if re.match(
        r"^(ST[A-Z]+|CLR|INC|DEC|BSET|BCLR|COM) [^,]+,[XY](,|$)",l)]
    assert [body[i] for i in stores]==["STAA $00,X","STAA $00,X",
        "STAA $00,X","CLR $00,X","STD $00,X","STE $0000,X"],(pn,stores)
    sci,lo,hi=CONFIG[pn]
    a,b,c,d,e,f=stores
    assert body[a-6:a]==["ANDB #$07","CMPB #$04",body[a-4],"TZX",f"LDX #${sci:04X}","ABX"]
    assert body[a-4].startswith("BEQ ")
    assert body[b-6:b]==["ABX","CPX #$87FF",body[b-4],"NEGB","LDAA #$FF","ADX"]
    assert body[b-4].startswith("BCS ")
    assert body[c-5:c]==["LDX #$8700","CLR >DiagCommand,Z",
        "LDAB >DiagParam2,Z","LDAA >DiagParam1,Z","ABX"]
    assert body[d-3:d-1]==["TZX",f"LDX #${lo:04X}"]
    assert body[d+1:d+3]==["AIX #$01",f"CPX #${hi:04X}"]
    assert body[d+3].startswith("BCS ")
    output=body.index("OutputTestOcFire:")
    oc=body[output:e]
    io=body[e:f]
    def bases(block):
        return [int(l.split("#$")[1],16) for l in block if l.startswith("LDX #$")]
    assert sorted(bases(oc))==[0xF916,0xF918,0xF91A]
    assert sorted(bases(io))==[0x8824,0x8828,0x882C,0x8830,0x8834,0x8838]
    for block in (oc,io):
        for i,l in enumerate(block):
            if l.startswith("LDX #$"):assert block[i-1]=="TZX"
    # The special DiagWriteRamByte branch only reaches ADX at X=87FF:
    # B=FF -> NEGB=01, A=FF => 16-bit D=FF01 => X=8700.
    assert (0x87FF+0xFF01)&65535==0x8700
    groups={"SCI override":set(range(sci,sci+8)),
            "RAM upload":set(range(0x8700,0x8800)),
            "adaptation clear":set(range(lo,hi)),
            "output compares":{x+j for x in bases(oc) for j in (0,1)},
            "output controls":{x+j for x in bases(io) for j in (0,1)}}
    for name,addresses in groups.items():
        assert not addresses&CAND,(pn,name,addresses&CAND)
        print(f"{pn}: {name}: {len(addresses)} bytes; no Q4 overlap")
    calls=[i for i,l in enumerate(lines) if l=="JSR DiagRamAddrAllowed"]
    assert len(calls)==1
    i=calls[0]
    assert lines[i+2:i+5]==["STE >EepromAddr,Z","LDAA >DiagParam1,Z","STAA >EepromData,Z"]
    assert lines[i+1].startswith("BNE ")
    assert lines.count("JMP $F8700")==1
    print("EEPROM permission caller verified; RAM code execution is unrestricted by this audit.")
    print("Six reviewed diagnostic indexed store signatures; no global allocation proof.")
if __name__=="__main__":
    for pn in CONFIG:audit(pn)
