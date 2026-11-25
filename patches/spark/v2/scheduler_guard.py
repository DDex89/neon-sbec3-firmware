#!/usr/bin/env python3
"""Spark V2 guarded angle-to-timer linkage; isolated research only.

The legacy byte remains the sole scheduling/diagnostic input. This
fixture starts *after* a stock path was selected. It neither changes nor
emulates the scheduler, coil dwell, compare registers or real IRQ timing.
Synthetic Q4/legacy pairs include unreachable extremes. No ROM patch.
"""
from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/"patches/spark"))
from timercheck import model,signed
from precision import ASM,ENTRY,STRIDE,CPU,assemble,require,nearest

CONSTANTS=(138,98,58)
SLOPES=(182,410,410)

def guard(path,raw,q,forced=False):
    """Return (reason, positive Q4 delta or None).

    Retain signed legacy branch predicate for paths 2/3. Fall back at
    the local zero/wrap boundary or if either coefficient cannot be
    represented without wrap. Forced paths must keep *stock timer math*,
    not just the integer angle. No policy yet for actual ISR reachability.
    """
    require(0<=raw<=255 and -1024<=q<=1016,"Angle domain")
    residual=q-signed(raw)*8
    if path==0:
        delta=(138-raw)&255
    else:
        delta=CONSTANTS[path]-signed(raw)
        if delta<=0:
            return "skip",None
    if forced:
        return "forced",None
    if abs(residual)>8:
        return "residual",None
    d8=delta*8-residual
    if (path==0 and not 0<=d8<2048) or (path and d8<=0):
        return "boundary",None
    if path and (nearest(delta*410,256)*256>65535 or
                 nearest(d8*410,8)>65535):
        return "coefficient",None
    return "fine",d8

def effective_period(path,period,anchor,prev):
    if path==0:
        return period
    if path==1:
        return ((period*0x1C71)>>16)*4&65535
    return ((anchor-prev)&65535)*4&65535

def candidate(cpu,path,raw,q,period,anchor,prev,forced=False):
    old,tmp=model(path,raw,period,anchor,prev)
    reason,d8=guard(path,raw,q,forced)
    if reason!="fine":
        return old,tmp,reason,0.0
    require(old is not None,"Fine arithmetic activated skipped path")
    e=effective_period(path,period,anchor,prev)
    coef=nearest(d8*SLOPES[path],8)
    require(0<=coef<=65535 and 0<=e<=65535,"Fine coefficient domain")
    cpu.reset_regs()
    cpu.d=d8
    cpu.e=e
    sp=cpu.sp
    cpu.call(ENTRY+(STRIDE if path else 0))
    counts=nearest(coef*e,65536)
    require(cpu.e==counts and cpu.sp==sp,"Joined timer machine mismatch")
    require(all(0xF8700<=a<0xF8800 for a in cpu.writes),"Timer scratch write")
    ideal=d8*SLOPES[path]*e/(8*65536)
    err=abs(counts-ideal)
    require(err<=0.5+e/(2*65536)+1e-10,"Timer rounding bound")
    out=(counts+anchor-60)&65535
    if path==0 and q==signed(raw)*8:
        require(out==old,"Integer path 1 changed")
    return out,tmp,reason,err

def audit_source(pn):
    """Classify direct named uses, including non-timer consumers."""
    lines=[]
    for bank in ("bank0","bank1"):
        lines.extend(l.split(";")[0].strip().split() for l in
                     (ROOT/"src"/pn/(bank+".asm")).read_text().splitlines())
    refs=[i for i,l in enumerate(lines) if any("SparkAdvanceD11" in x for x in l)]
    require(len(refs)==16,"Named angle consumers changed")
    refs_by_op=Counter(lines[i][0] for i in refs)
    require(refs_by_op=={"LDAA":9,"SUBA":5,"LDAB":1,"STAA":1},
            "Named angle use signature changed")
    checks=Counter()
    for i in refs:
        m=lines[i][0]
        prev=lines[i-1]
        nxt=lines[i+1]
        if m=="SUBA" and prev[:1]==["LDAA"] and len(prev)>1 and prev[1] in ("#$8A","#$62","#$3A"):
            checks[prev[1]]+=1
        if m=="LDAA" and nxt[:1]==["CMPA"] and len(nxt)>1:
            if nxt[1]=="#$30":
                require(lines[i+2][0] in ("BLT","BGE"),"Signed 30 threshold")
                checks["signed30"]+=1
            if nxt[1]=="#$62":
                require(lines[i+2][0]=="BCC","Unsigned 62 threshold")
                checks["unsigned62"]+=1
    require(checks=={"#$8A":1,"#$62":1,"#$3A":1,"signed30":2,"unsigned62":2},
            "Scheduler direct angle signatures changed")
    print(pn+": direct named reads/writer and signed/unsigned threshold signatures verified")

def main():
    for pn in ("04887050","05293013AC"):
        audit_source(pn)
    with TemporaryDirectory() as tmp:
        src=Path(tmp)/"timer_guard.asm"
        src.write_text(ASM)
        cpu=CPU(assemble([str(src)],0x20000),0x800)
    expected=(
        {"fine":4327,"boundary":9},
        {"fine":2700,"skip":502,"boundary":1,"coefficient":1133},
        {"fine":2700,"skip":1182,"boundary":1,"coefficient":453},
    )
    for path in range(3):
        pairs=Counter()
        actual=Counter()
        changed=0
        maxerr=0.0
        for raw in range(256):
            for residual in range(-8,9):
                q=signed(raw)*8+residual
                if not -1024<=q<=1016:
                    continue
                reason,_=guard(path,raw,q)
                pairs[reason]+=1
                for period,anchor,prev in ((0,0,0),(1000,100,65500),
                                            (30000,32768,20000),(65535,65535,0)):
                    old,tmp=model(path,raw,period,anchor,prev)
                    out,t,why,err=candidate(cpu,path,raw,q,period,anchor,prev)
                    require(why==reason and t==tmp,"Joined timer state mismatch")
                    if why!="fine":
                        require(out==old,"Fallback changed timer result")
                    forced,ft,fr,_=candidate(cpu,path,raw,q,period,anchor,prev,True)
                    require((forced,ft)==(old,tmp) and fr in ("skip","forced"),
                            "Forced path changed timer result")
                    require((out is None)==(old is None),"Legacy skip changed")
                    actual[why]+=1
                    changed+=out!=old
                    maxerr=max(maxerr,err)
        require(pairs==expected[path],"Guard stress grid changed")
        print(f"Path {path+1}: {sum(pairs.values())} angle pairs {dict(pairs)}; "
              f"{sum(actual.values())} timer cases, {actual['fine']} CPU16 fine executions, "
              f"{sum(actual.values())} forced controls, {changed} changed outputs; "
              f"max fine rounding {maxerr:.8f} counts",flush=True)
    print("No ISR, hardware timing, RAM reservation or production patch.",flush=True)

if __name__=="__main__":
    main()
