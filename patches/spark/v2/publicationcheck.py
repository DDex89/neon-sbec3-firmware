#!/usr/bin/env python3
"""Isolated CalcSpark sum/publication contract and fractional-angle model.

Runs the original sum/fault/override tail, not correction producers or the
whole ECU. Fractional publication is a separate host model, not a ROM patch.
"""
import argparse
import hashlib
import json
import random
import re
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/"patches/spark"))
from simulate_v11 import CONFIG,CPU,decode,patch,require

START={"04887050":0x1BE80,"05293013AC":0x14000}
EXTRA={"04887050":(0x0606,0x060F,0x0696,0x060C),
       "05293013AC":(None,0x061D,0x06A4,0x061A)}
NAMES=("FlexSparkValue","CalcSparkD05","CalcSparkD06","CalcSparkD08",
       "CalcSparkD07","CalcSparkD0A","CalcSparkD09","CalcSparkD0C",
       "AcClutchSparkTime","AcSparkWork","KnockRetard","CalcSparkD0E",
       "CalcSparkD0B","IacStepSum")

def sx(v):
    return (v&255)-256 if v&128 else v&255

def clip(x,lo,hi):
    return max(lo,min(hi,x))

def find_tail(rom,pn,first,eq):
    a=START[pn]
    while a<START[pn]+0x180:
        i=decode(rom,a)
        require(i is not None,"Invalid CalcSpark instruction")
        if i.mn=="LDAB" and dict(i.vals).get("gggg")==first:
            j=decode(rom,a+i.size)
            k=decode(rom,a+i.size+j.size)
            if j.mn=="SXT" and k.mn=="TDE":
                b=a
                sums=[]
                while True:
                    load=decode(rom,b)
                    if load.mn=="TED": break
                    require(load.mn=="LDAB","Unexpected correction load")
                    extend=decode(rom,b+load.size)
                    op=decode(rom,b+load.size+extend.size)
                    require(extend.mn=="SXT" and op.mn in ("TDE","ADE","SDE"),"Correction arithmetic signature")
                    sums.append((dict(load.vals)["gggg"],-1 if op.mn=="SDE" else 1))
                    b+=load.size+extend.size+op.size
                return a,sums
        a+=i.size
    raise ValueError("CalcSpark sum tail not found")

def check(pn):
    stock=(ROOT/"build"/(pn+".bin")).read_bytes()
    v=json.loads((ROOT/"tools/variants.json").read_text())[pn]
    require(hashlib.sha256(stock).hexdigest()==v["sha256"],"Original SHA")
    eq={k:int(v,16) for k,v in re.findall(r"^(\w+)\s+equ\s+\$([0-9A-Fa-f]+)",(ROOT/"src"/pn/"00_equates.asm").read_text(),re.M)}
    trim,speed,other,high=EXTRA[pn]
    offsets=[(eq[n],-1 if n in ("AcClutchSparkTime","AcSparkWork") else 1) for n in NAMES]+[(speed,1),(other,1),(high,1)]
    if trim is not None: offsets.append((trim,1))
    entry,observed=find_tail(stock,pn,trim if trim is not None else eq["FlexSparkValue"],eq)
    require(sorted(observed)==sorted(offsets),"Correction list differs from source contract")
    _,combined,_,_=patch(stock,pn)
    cpus=[CPU(x,0x800) for x in (stock,combined)]
    allowed={0xF8000+eq[x] for x in ("CalcSpark6D3","SparkValueD0F")}
    rng=random.Random(0x53424543)
    vectors=[]
    for a in (-128,-127,-64,-1,0,1,64,126,127):
        vectors.append([a]*len(offsets))
        vectors.append([a*s for _,s in offsets])
        for i in range(len(offsets)):
            x=[0]*len(offsets);x[i]=a;vectors.append(x)
    for _ in range(256):
        vectors.append([rng.randrange(-128,128) for _ in offsets])
    flags=[(o,t,d,f,h) for o in (0,2) for t in (0,1) for d in (0,1) for f in (0,0x40,0x80,0xc0) for h in (0,0x20)]
    n=0
    branches={"normal":0,"fault":0,"override":0}
    fractional_cases=0
    for vals in vectors:
        state={addr:value&255 for (addr,_),value in zip(offsets,vals)}
        total=sum(s*sx(state[addr]) for addr,s in offsets)
        sat=clip(total,-128,127)
        for opt,th,dash,fault,hold in flags:
            state2=dict(state)
            override=(vals[0]^0x55)&255
            for k,value in (("FuelPulseOptFlags",opt),("ThrottleState",th),("DashpotTimer",dash),("FaultSet02",fault),("SparkFaultFlags",hold),("CalcSparkC51",override)):
                state2[eq[k]]=value
            forced=(bool(hold) if th or dash else bool(fault&0xc0))
            if opt&2:
                expected=sx(override);branch="override"
            elif forced:
                expected=clip(24+(sx(state[trim]) if trim is not None else 0),-128,127);branch="fault"
            else:
                expected=sat;branch="normal"
            for cpu in cpus:
                cpu.reset_regs()
                cpu.mem[0xF8000:0xF8800]=bytes(0x800)
                for addr,value in state2.items(): cpu.ram_byte(addr,value)
                sp=cpu.sp
                cpu.call(entry)
                got=(sx(cpu.ram_byte(eq["CalcSpark6D3"])),sx(cpu.ram_byte(eq["SparkValueD0F"])))
                require(got==(sat,expected),f"CalcSpark tail mismatch {pn} {branch}: {got} vs {(sat,expected)}")
                require(cpu.sp==sp and all(a in allowed or 0xF8700<=a<0xF8800 for a in cpu.writes),"Unexpected tail state write")
            branches[branch]+=1;n+=1
            # Hypothetical publication: old integer corrections times eight,
            # add signed fractional residual only in the ordinary branch.
            for residual in range(-8,9):
                fine=clip(total*8+residual,-1024,1016) if branch=="normal" else expected*8
                require(-1024<=fine<=1016,"Fine publication bounds")
                if residual==0 or branch!="normal":
                    require(fine==expected*8,"Integer or forced path compatibility")
                if branch=="normal":
                    require(abs(fine-expected*8)<=8,"Unexpected fractional change")
                fractional_cases+=1
    print(f"{pn}: CalcSpark tail at ${entry:05X}; {len(offsets)} signed terms; {n} exact stock/composed cases; branches {branches}")
    print(f"{pn}: {fractional_cases} host-only fractional publication cases passed; no new RAM or production ABI")

if __name__=="__main__":
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pn",choices=CONFIG)
    check(ap.parse_args().pn)
