#!/usr/bin/env python3
"""Reset lifecycle and validity-state experiment for Spark V2.

Source signatures plus host model only. Candidate RAM is not reserved.
Two signed Q4 words and one validity byte are proposed. Zero is a valid
angle, so never infer readiness from a zero/nonzero angle. Readers fall
back to the actual stock angle until their corresponding flag is valid.
Publish value, legacy byte and flag in a single bounded masked section.
The event must not become fine-valid solely because its base was valid:
caller must independently certify the event path. No real ISR emulation.
"""
from pathlib import Path
from itertools import product
import re
ROOT=Path(__file__).resolve().parents[3]
CONFIG={
    "04887050": (0x810A,0x8032,0x8700),
    "05293013AC": (0x813A,0x8034,0x8726),
}
CANDIDATE=(0x85F2,0x85F4,0x85F6)
BASE,EVENT=1,2

def source(pn):
    warm,cold,end=CONFIG[pn]
    lines=[x.split(";")[0].strip() for x in
           (ROOT/"src"/pn/"bank0.asm").read_text().splitlines()]
    start=lines.index("Reset:")
    main=lines.index("MainLoop:",start)
    body=lines[start:main]
    assert body[1]=="ORP     #$00E0"
    def locate(op,operand):
        found=[i for i,line in enumerate(body) if line.split()==[op,operand]]
        assert len(found)==1,(pn,op,operand,found)
        return found[0]
    w=locate("LDX",f"#${warm:04X}")
    c=locate("LDX",f"#${cold:04X}")
    e=locate("CPX",f"#${end:04X}")
    unmask=locate("ANDP","#$FF1F")
    assert w<c<e<unmask
    assert [line.split() for line in body[e-2:e]]==[
        ["STE","$0000,X"],["AIX","#$02"]]
    assert body[e+1].startswith("BCS")
    for begin in (warm,cold):
        touched={a for p in range(begin,end,2) for a in (p,p+1)}
        assert all(a in touched for a in
                   (CANDIDATE[0],CANDIDATE[0]+1,CANDIDATE[1],CANDIDATE[1]+1,CANDIDATE[2]))
    nv=lines.index("NvChecksum:")
    block=lines[nv:nv+15]
    assert any(x.split()==["CPX",f"#${warm:04X}"] for x in block)
    assert warm < CANDIDATE[0]
    assert any(x.split()==["JSR","CalcSpark"] for x in lines[main:main+300])
    print(f"{pn}: warm/cold clear coverage, NV checksum boundary, explicit unmask before main CalcSpark verified")
    print("No claim about implicit unmask in callees or actual first interrupt.")

def select(q,legacy,valid,bit):
    assert -128<=legacy<=127
    return q if valid&bit and -1024<=q<=1016 else legacy*8

def model():
    count=0
    # Every legacy angle, validity combination, both consumers, valid and
    # invalid endpoints; zero must be accepted only when explicitly valid.
    for legacy,valid,bit,q in product(range(-128,128),range(4),(BASE,EVENT),
                                      (-32768,-1025,-1024,-1,0,1,1016,1017,32767)):
        got=select(q,legacy,valid,bit)
        expected=q if (valid&bit)!=0 and -1024<=q<=1016 else legacy*8
        assert got==expected
        count+=1
    assert count==18432
    for base,event in product((False,True),repeat=2):
        flags=0
        if base: flags|=BASE
        if event: flags|=EVENT
        assert bool(flags&BASE)==base and bool(flags&EVENT)==event
        flags=0 # both reset-cleared, no retained ready state
        assert select(0,18,flags,BASE)==144
        assert select(0,18,flags,EVENT)==144
    print(f"{count} validity/fallback cases; independent ready flags; no RAM allocation")

if __name__=="__main__":
    for pn in CONFIG: source(pn)
    model()
