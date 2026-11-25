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

# Research-only adapters; no production code or new scheduling policy.
# D = unsigned projection of Q4 for OC2; E returns the legacy class 1..3.
# History uses signed Q4 operands in D/E, returns absolute difference in D.
CONSUMER_ASM="""
org $02000
OcClass:
        LDE #$0001
        CPD #$0310
        BCC OcDone
        ADDE #$0001
        CPD #$01D0
        BCC OcDone
        ADDE #$0001
OcDone:
        RTS
org $02040
HistoryDelta:
        SDE
        TED
        CPD #$0000
        BGE HistoryDone
        NEGD
HistoryDone:
        RTS
org $02080
LegacyAngle:
        ADDD #$0004
        ASRD
        ASRD
        ASRD
        TBA
        RTS
org $020A0
ObdAngle:
        JSR LegacyAngle
        ADDA #$80
        RTS
"""

def oc_class(raw):
    return 1 if raw>=98 else 2 if raw>=58 else 3

def fine_oc_class(q):
    # The original OC2 compares raw *unsigned* bytes. A signed compare
    # is not equivalent even at zero fractional residual.
    u=q&2047
    return 1 if u>=784 else 2 if u>=464 else 3

def diagnostic_adapter(cpu):
    """Q4 is already clamped to [-1024,1016]; no extra saturation needed.
    Input D = signed Q4, output A = legacy raw or OBD encoded angle.
    Ties toward positive infinity. E, X and Y preserved; D/CCR clobbered.
    The caller supplies a coherent snapshot; no actual RAM ABI is assigned.
    """
    cases=exact=0
    last=-129
    for q in range(-1024,1017):
        # Independent nearest-integer selection with positive tie break.
        lo,frac=divmod(q,8)
        expected=lo+(frac>=4)
        require(-128<=expected<=127 and expected>=last,"Diagnostic range/monotonicity")
        require(abs(q-8*expected)<=4,"Diagnostic quantization")
        last=expected
        if q%8==0:
            require(expected==q//8,"Integer diagnostic compatibility")
            exact+=1
        for entry,want in ((0x2080,expected&255),(0x20A0,expected+128)):
            cpu.reset_regs()
            cpu.d=q&65535
            cpu.e=0xA55A
            cpu.ix,cpu.iy=0x1234,0x5678
            sp=cpu.sp
            cpu.call(entry)
            require(cpu.a==want and cpu.sp==sp,"Diagnostic adapter mismatch")
            require((cpu.e,cpu.ix,cpu.iy)==(0xA55A,0x1234,0x5678),
                    "Diagnostic adapter register corruption")
            require(all(0xF8700<=x<0xF8800 for x in cpu.writes),
                    "Diagnostic adapter non-stack write")
            cases+=1
    require(cases==4082 and exact==256,"Diagnostic grid changed")
    print(f"Diagnostic adapters: {cases} CPU16 conversions; {exact} exact legacy "
          "integer angles per encoding; max error 0.25 degree; no external ABI change",
          flush=True)

def consumer_precision():
    with TemporaryDirectory() as tmp:
        src=Path(tmp)/"consumers.asm"
        src.write_text(CONSUMER_ASM)
        cpu=CPU(assemble([str(src)],0x20000),0x800)
    diagnostic_adapter(cpu)
    n=oc_diff=wrong_signed=ic_diff=0
    for raw in range(256):
        for residual in range(-8,9):
            q=signed(raw)*8+residual
            if not -1024<=q<=1016:
                continue
            cpu.reset_regs()
            cpu.d=q&2047
            sp=cpu.sp
            cpu.call(0x2000)
            new=fine_oc_class(q)
            require(cpu.e==new and cpu.sp==sp,"OC2 adapter mismatch")
            require(all(0xF8700<=a<0xF8800 for a in cpu.writes),"OC2 scratch write")
            old=oc_class(raw)
            oc_diff+=old!=new
            ic_diff+=(signed(raw)>=48)!=(q>=384)
            if not residual:
                require(old==new,"Integer OC2 compatibility")
                wrong_signed+=old!=(1 if q>=784 else 2 if q>=464 else 3)
            n+=1
    hcount=hdiff=hmachine=0
    for prev in range(256):
        for raw in range(256):
            p,c=signed(prev),signed(raw)
            # Stock SUBA + signed BGE + optional NEGA + unsigned CMPA.
            # The resulting byte represents the magnitude even for 128..255.
            v=(prev-raw)&255
            old_mag=v if p>=c else (-v)&255
            require(old_mag==abs(p-c),"Stock history magnitude")
            old=old_mag<10
            for dp in (-8,0,8):
                for dc in (-8,0,8):
                    a,b=p*8+dp,c*8+dc
                    if not(-1024<=a<=1016 and -1024<=b<=1016):
                        continue
                    new=abs(a-b)<80
                    hdiff+=old!=new
                    hcount+=1
                    if dp==dc==0:
                        require(old==new,"Integer history compatibility")
                    # Exercise the assembled adapter on all boundary pairs
                    # and a deterministic sample of the remaining domain.
                    if abs(p-c) in (0,9,10,11,127,128,255) or (prev%31==0 and raw%31==0):
                        cpu.reset_regs()
                        cpu.d=a&65535
                        cpu.e=b&65535
                        sp=cpu.sp
                        cpu.call(0x2040)
                        require(cpu.d==abs(a-b) and cpu.sp==sp,"History adapter mismatch")
                        require(all(0xF8700<=x<0xF8800 for x in cpu.writes),"History scratch write")
                        hmachine+=1
    require((n,oc_diff,wrong_signed,ic_diff,hcount,hdiff)==
            (4336,27,128,9,586756,3932),"Consumer stress grid changed")
    print(f"Consumer research: {n} OC2 CPU16 cases; {oc_diff} OC2 class changes; "
          f"{wrong_signed} integer mismatches with naive signed OC2; "
          f"{ic_diff} signed IC1 threshold differences",flush=True)
    print(f"History research: {hcount} host cases, {hdiff} threshold differences; "
          f"{hmachine} CPU16 magnitude cases",flush=True)
    # Do not promote either adapter to scheduler/monitor code. Changes
    # in classification must be validated together with dwell and protection.

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
    consumer_precision()
    print("No ISR, hardware timing, RAM reservation or production patch.",flush=True)

if __name__=="__main__":
    main()
