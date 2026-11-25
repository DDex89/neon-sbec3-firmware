#!/usr/bin/env python3
"""Source audit and abstract interrupt-publication experiment; no ROM patch.

Only maskable priorities 1..6 are modeled. The result is conditional on actual
CPU16 mask, memory and interrupt semantics, not an emulation of them.
"""
import argparse
import re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
VARIANTS=("04887050","05293013AC")


def require(ok,message):
    if not ok:
        raise ValueError(message)


def source_lines(pn,bank):
    return [line.split(";")[0].strip() for line in
            (ROOT/"src"/pn/(bank+".asm")).read_text().splitlines()]


def audit(pn):
    b0,b1=(source_lines(pn,b) for b in ("bank0","bank1"))
    def first_after(lines,label):
        return lines[lines.index(label+":")+1]
    require(first_after(b0,"Isr_GPT_IC1").split()==["ORP","#$0060"],"IC1 mask changed")
    require(first_after(b0,"Isr_GPT_OC2").split()==["ORP","#$00E0"],"OC2 mask changed")
    # Audit the named direct accesses, not computed/aliased addressing.
    lines=b0+b1
    for symbol,reads in (("SparkValueD0F",1),("SparkAdvanceD11",15)):
        refs=[s for s in lines if re.search(r"\b"+symbol+r"\b",s)]
        writes=[s for s in refs if s.startswith("STAA")]
        require(len(writes)==1 and len(refs)==reads+1,
                "Named angle ABI changed: "+symbol+" "+str(refs))
    start=b1.index("DiagWriteRamByte:")
    block=b1[start:start+35]
    require(any(s.split()==["LDX","#$8700"] for s in block)
            and any(s.split()==["STAA","$00,X"] for s in block),
            "Diagnostic RAM upload signature changed")
    require(any(s.split()==["JMP","$F8700"] for s in b1),
            "Diagnostic RAM execution signature changed")
    start=b1.index("BusTxByte:")
    require(b1[start+1].split()==["PSHM","D,CCR"] and
            b1[start+2].split()==["ORP","#$00E0"],
            "Existing save/mask idiom changed")
    print(pn+": named ABI, IC1/OC2 masks and diagnostic upper-page signatures verified")


def encode(legacy,fine):
    require(-128<=legacy<=127 and -1024<=fine<=1016,"Angle bounds")
    return (legacy&255,(fine>>8)&255,fine&255)


def states(old,new,initial,protected):
    """Yield abstract (mask, published bytes) at every instruction boundary.

    Split the 16-bit store conservatively into byte writes. The mask is
    restored exactly, not unconditionally cleared. No reader waits/spins.
    """
    data=list(old)
    mask=initial
    yield mask,tuple(data)
    if protected:
        yield mask,tuple(data)  # save prior CCR
        mask=7
        yield mask,tuple(data)
    for i in (1,2,0):
        data[i]=new[i]
        yield mask,tuple(data)
    if protected:
        mask=initial
        yield mask,tuple(data)
    require(mask==initial,"Mask restoration")


def protocol():
    values=[encode(a,max(-1024,min(1016,a*8+d)))
            for a in (-128,-127,-65,-1,0,1,48,58,98,126,127)
            for d in (-8,-1,0,1,8)]
    values=sorted(set(values))
    cases=0
    unsafe=0
    for old in values:
        for new in values:
            for initial in range(8):
                for priority in range(1,7):
                    for mask,data in states(old,new,initial,True):
                        if priority>mask:
                            require(data in (old,new),"Torn protected sample")
                            cases+=1
                    for mask,data in states(old,new,initial,False):
                        if priority>mask and data not in (old,new):
                            unsafe+=1
    require(unsafe>0,"Negative control did not expose torn sample")
    print(f"Abstract maskable interrupt observations: {cases}; "
          f"unprotected torn observations: {unsafe}; no machine atomicity claim")


def check(pn):
    audit(pn)
    protocol()


if __name__=="__main__":
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pn",choices=VARIANTS)
    check(ap.parse_args().pn)
