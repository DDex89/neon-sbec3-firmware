#!/usr/bin/env python3
"""Execute original angle-to-timer arithmetic slices, not the complete ISR.

CrankPeriodSum is a synthetic register value in the simulator. No actual
timer, peripheral, coil, interrupt scheduling or ROM export is involved.
"""
import argparse
import hashlib
import json
import re
from simulate_v11 import ROOT, CONFIG, CPU, decode, patch, require

P1="LDAA SUBA LDAB MUL LDE EMUL ADCE SUBE STE".split()
P2="LDD LDE EMUL ASLE ASLE LDAA SUBA LBLE LDAB MUL ASLD ASLB ADCA CLRB EMUL ADCE SUBE STE".split()
P3="LDE SUBE STE ASLE ASLE LDAA SUBA LBLE LDAB MUL ASLD ASLB ADCA CLRB EMUL ADCE SUBE STE".split()

def signed(x):
    return x-256 if x&128 else x

def round16(x):
    return (x+32768)//65536

def find(rom,pattern,constant,eq):
    matches=[]
    for start in range(0x4800,0x5100,2):
        a=start
        ins=[]
        for mn in pattern:
            i=decode(rom,a)
            if i is None or i.mn!=mn: break
            ins.append(i)
            a+=i.size
        if len(ins)!=len(pattern): continue
        aa=ins[pattern.index("LDAA")]
        sub=ins[pattern.index("SUBA")]
        if dict(aa.vals).get("ii")!=constant: continue
        if dict(sub.vals).get("gggg")!=eq["SparkAdvanceD11"]: continue
        require(dict(ins[-1].vals).get("gggg")==eq["Temp4F4"],"Unexpected timer store")
        branch=next((i.target() for i in ins if i.mn=="LBLE"),None)
        matches.append((start,a,branch))
    require(len(matches)==1,f"Expected one timer arithmetic path for {constant:02X}: {matches}")
    return matches[0]

def model(path,raw,period,anchor,prev):
    if path==0:
        k=((138-raw)&255)*182
        return (round16(k*period)+anchor-60)&65535,None
    delta=(98 if path==1 else 58)-signed(raw)
    diff=(anchor-prev)&65535
    tmp=diff if path==2 else None
    if delta<=0:
        return None,tmp
    e=(((period*0x1C71)>>16)*4 if path==1 else diff*4)&65535
    k=((2*delta*205+128)//256 &255)*256
    return (round16(k*e)+anchor-60)&65535,tmp

def run(c,loc,eq,raw,period,anchor,prev):
    start,end,branch=loc
    c.reset_regs()
    c.reads.clear();c.writes.clear()
    for n,v in (("RefPeriodLow",period),("CrankAC0",anchor),("CrankPeriodSum",anchor),("CrankPeriodPrev",prev),("Temp4F4",0xA55A),("Temp4F6",0x5AA5)):
        c.ram_word(eq[n],v)
    c.ram_byte(eq["SparkAdvanceD11"],raw)
    c.jump(start)
    for _ in range(30):
        pc=(c.pk<<16)|c.pc
        if pc==end or pc==branch: break
        c.step(pc)
    else:
        raise ValueError("Timer arithmetic did not terminate")
    require(c.writes<={0xF8000+eq[k]+i for k in ("Temp4F4","Temp4F6") for i in (0,1)},"Unexpected arithmetic write")
    return (None if pc==branch else c.ram_word(eq["Temp4F4"]),c.ram_word(eq["Temp4F6"]))

def check(pn):
    stock=(ROOT/"build"/(pn+".bin")).read_bytes()
    sha=json.loads((ROOT/"tools/variants.json").read_text())[pn]["sha256"]
    require(hashlib.sha256(stock).hexdigest()==sha,"Original SHA")
    eq={k:int(v,16) for k,v in re.findall(r"^(\w+)\s+equ\s+\$([0-9A-Fa-f]+)",(ROOT/"src"/pn/"00_equates.asm").read_text(),re.M)}
    _,combined,_,_=patch(stock,pn)
    cpus=[CPU(rom,0x800) for rom in (stock,combined)]
    n=0
    for path,(pattern,constant) in enumerate(zip((P1,P2,P3),(138,98,58))):
        loc=find(stock,pattern,constant,eq)
        require(stock[loc[0]:loc[1]]==combined[loc[0]:loc[1]],"Timer bytes changed")
        count=skip=0
        for raw in range(256):
            for period in (0,1,127,255,256,1000,5000,10000,30000,60000,65535):
                for anchor,prev in ((0,0),(100,65500),(32768,20000),(65535,0),(12345,12344),(60000,1000)):
                    v,tmp=model(path,raw,period,anchor,prev)
                    expected=(v,0x5AA5 if tmp is None else tmp)
                    a,b=[run(c,loc,eq,raw,period,anchor,prev) for c in cpus]
                    require(a==b==expected,f"Timer model path {path} angle {signed(raw)} period {period} anchor {anchor} prev {prev}: {a}/{b} vs {expected}")
                    count+=1
                    skip+=v is None
        print(f"{pn}: path {path+1} at ${loc[0]:05X}, {count} exact original/composed/model cases, {skip} conditional skips",flush=True)
        n+=count
    print(f"{pn}: {n} arithmetic slice cases passed (not complete ISR)",flush=True)

if __name__=="__main__":
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pn",choices=CONFIG)
    check(ap.parse_args().pn)
