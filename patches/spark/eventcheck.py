#!/usr/bin/env python3
"""Independent signed-angle model for selected real SparkEventCalc paths.

No CPU hooks/stubs. A/C correction inactive; RPM-rate state initially zero.
Synthetic state fixture, not a running engine/ISR model. Includes original
cranking branch, fault/hold bypass, cylinder corrections and knock where
enabled by original option bytes, lower/upper startup limits and ramp.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

from simulate_v11 import ROOT, CONFIG, CPU, decode, patch, require

ENTRIES={"04887050":0x1D006,"05293013AC":0x15168}
CYL={"04887050":(0x06B8,0x0376,(0xCFF8,0xD000,0xCFFC)),
     "05293013AC":(0x06C6,0x0390,(0x515A,0x5162,0x515E))}

def signed(v):
    return (v&255)-256 if v&128 else v&255

def check(pn):
    stock=(ROOT/"build"/(pn+".bin")).read_bytes()
    v=json.loads((ROOT/"tools/variants.json").read_text())[pn]
    require(hashlib.sha256(stock).hexdigest()==v["sha256"],"Original SHA")
    p=CONFIG[pn]
    _,composed,_,_=patch(stock,pn)
    eq={k:int(v,16) for k,v in re.findall(r"^(\w+)\s+equ\s+\$([0-9A-Fa-f]+)",(ROOT/"src"/pn/"00_equates.asm").read_text(),re.M)}
    entry=ENTRIES[pn]
    cylbase,knockbase,ptrs=CYL[pn]
    a=entry
    scale=None
    while a<entry+0x110:
        ins=decode(stock,a)
        if ins.mn=="LDX" and ins.mode=="IMM16":
            # The last immediate LDX before the sole Lookup2D call is the startup minimum table.
            nxt=decode(stock,a+ins.size)
            if nxt and nxt.mn=="LDAA":
                following=decode(stock,a+ins.size+nxt.size)
                if following and following.mn=="JSR" and following.target()==p["lookup2d"]:
                    scale=dict(ins.vals)["jjkk"]
        a+=ins.size
        if ins.mn=="RTS": break
    require(scale is not None,"Startup minimum table not found")
    # Isolate the original Lookup2D output; angle sum model is independent of that routine.
    c=CPU(stock,0x800)
    minima={}
    for t in (0,20,21,30,40,50,59,60,255):
        c.reset_regs();c.ix=scale;c.a=t;c.call(p["lookup2d"])
        minima[t]=signed(c.a)
    cpus=[CPU(x,0x800) for x in (stock,composed)]
    def invoke(c,state,cylinder,corr,evt,retard):
        c.reset_regs()
        c.mem[0xF8000:0xF8800]=bytes(0x800)
        for k,val in state.items(): c.ram_byte(eq[k],val)
        c.ram_byte(cylbase,corr);c.ram_byte(cylbase+1,corr)
        c.ram_byte(eq["CylinderIndex"],cylinder)
        c.ram_byte(eq["EventSpark"],evt)
        for i in range(6): c.ram_byte(knockbase+i,retard)
        sp=c.sp
        c.call(entry)
        require(c.sp==sp and c.sk==15,"Event stack imbalance")
        require(all(0xF8000<=x<0xF8800 for x in c.writes),"Event write outside RAM")
        return (signed(c.ram_byte(eq["SparkAdvanceD11"])),c.ram_byte(eq["SparkStartRamp"]),c.ram_byte(eq["SparkStartRampValue"]),
                tuple(sorted((x,c.mem[x]) for x in c.writes if x<0xF8700)))
    n=0
    paths={}
    # Ramp updates are covered with the actual option setting and a frozen branch.
    for running,bypass in ((0,0),(1,1),(1,2),(1,0)):
        for base in (-128,-65,-32,-1,0,18,48,58,98,126,127):
            for t,minimum in minima.items():
                for ramp in (-20,0,40,125,127):
                    for freeze in (0,1):
                        for cylinder in (0,1):
                            for corr,evt,retard in ((0,0,0),(12,8,6),(-20,35,24),(127,-100,0)):
                                state={"SparkFlags":32 if running else 0,
                                       "FuelPulseOptFlags":2 if bypass==1 else 0,
                                       "SparkFaultFlags":32 if bypass==2 else 0,
                                       "SparkValueD0F":base,"SparkStartTime":t,
                                       "SparkStartRamp":ramp,"SparkStartRampValue":16,
                                       "FuelModeFlags2":128 if freeze else 0}
                                nr,nv=ramp,16
                                if not running:
                                    expected=18
                                else:
                                    total=base
                                    if not bypass:
                                        total+=corr-evt
                                        if stock[0x31F]&0xC0:
                                            selector=stock[0x31D]
                                            ptr=ptrs[0] if selector&0x83 else ptrs[1] if selector&0x78 else ptrs[2]
                                            offset=stock[0x10000+ptr+cylinder]
                                            require(offset<6,"Unsupported knock index in fixture")
                                            total-=retard
                                    if not freeze:  # ThrottleState=0: both option paths reach the ramp update.
                                        nv=8
                                        r=(ramp+4)&255
                                        nr=127 if r&128 else r
                                    expected=min(nr,max(minimum,min(127,total)))
                                a,b=[invoke(c,state,cylinder,corr,evt,retard) for c in cpus]
                                require(a==b,f"Composed event regression {state}")
                                require(a[:3]==(expected,nr&255,nv),f"Event model mismatch {state} {(corr,evt,retard)}: {a[:3]} vs {(expected,nr&255,nv)}")
                                n+=1
                                paths[bypass if running else "crank"]=paths.get(bypass if running else "crank",0)+1
    print(f"{pn}: {n} SparkEventCalc fixture cases, exact stock/composed and signed-angle model; paths {paths}; startup minima {minima}",flush=True)

if __name__=="__main__":
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pn",choices=CONFIG)
    check(ap.parse_args().pn)
