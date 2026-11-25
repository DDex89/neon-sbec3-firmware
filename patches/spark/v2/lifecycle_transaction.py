#!/usr/bin/env python3
"""Host-only Spark Q4 lifecycle transaction model and source anchors.

The proposal uses a sticky cancellation bit in the existing candidate status
byte, not a generation counter. One non-reentrant background CalcSpark writer.
All state transitions below are atomic abstract operations. Event publication
is separate and only certified at the actual stock SparkEventCalc exit.
Do not alter already programmed GPT compares or retroactively reinterpret
an event on background publication. No real ISR, ROM hook or allocation.
"""
from itertools import product
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
BASE,EVENT,CANCEL,DEBUG=1,2,4,8
VARIANTS=("04887050","05293013AC")

def audit(pn):
    def lines(bank):
        return [x.split(";")[0].strip() for x in
                (ROOT/"src"/pn/(bank+".asm")).read_text().splitlines()]
    b0,b1=lines("bank0"),lines("bank1")
    def exact(seq,op):
        return [i for i,l in enumerate(seq) if l.split()==op.split()]
    ic=exact(b0,"BCLR >EngineStateFlags,Z,#$80")
    stall=exact(b1,"BCLR >EngineStateFlags,Z,#$8E")
    assert len(ic)==len(stall)==1
    assert b0.index("Isr_GPT_IC1:")<ic[0]
    assert b1.index("CalcEngineRpm:")<stall[0]
    assert b1[stall[0]+1].split()==["BCLR",">SparkFlags,Z,#$20"]
    assert len(exact(b0,"BSET >EngineStateFlags,Z,#$80"))==1
    event=exact(b0,"JSR SparkEventCalc")
    assert len(event)==1
    assert b0[event[0]+2].split()==["SUBA",">SparkAdvanceD11,Z"]
    for op in ("STAA >SparkValueD0F,Z","STAA >SparkAdvanceD11,Z",
               "BSET >SparkFaultFlags,Z,#$20","JMP $F8700"):
        assert len(exact(b1,op))==1,(pn,op)
    print(f"{pn}: IC1 run-state clear, background stall, angle writers, "
          "diagnostic hold and RAM execution anchors found")

def begin(flags):
    # Only one background transaction may exist. Clear cancellation at begin
    # under the mask, not at commit. DEBUG is a sticky no-Q4 mode until reset.
    return flags & ~CANCEL

def invalidate(flags):
    # Invalidate the background angle and cancel an in-flight computation.
    # EVENT is historical and remains paired with its own published stock byte.
    # Do not touch already scheduled compares; new event mode uses stock policy.
    return (flags & ~BASE) | CANCEL

def enter_debug(flags):
    # Arbitrary uploaded code is outside the trusted-state model; flag is
    # only an entry policy, not protection against writes by such code.
    return invalidate(flags) & ~EVENT | DEBUG

def commit_base(flags, ordinary, running):
    accepted=ordinary and running and not flags&(CANCEL|DEBUG)
    flags=(flags | BASE) if accepted else (flags & ~BASE)
    return flags, bool(accepted)

def commit_event(flags, certified, running):
    accepted=certified and running and bool(flags&BASE) and not flags&DEBUG
    flags=(flags | EVENT) if accepted else (flags & ~EVENT)
    return flags, bool(accepted)

def model():
    count=0
    # All binary choices and all invalidation/debug placements across the
    # modeled begin -> compute -> commit sequence, including stop/restart.
    for initial,ordinary,running,cut1,cut2,debug in product(
            range(16),(False,True),(False,True),range(3),range(3),range(3)):
        f=initial
        if cut1==0: f=invalidate(f)
        if cut2==0: f=invalidate(f)
        if debug==0: f=enter_debug(f)
        f=begin(f)
        if cut1==1: f=invalidate(f)
        if cut2==1: f=invalidate(f)
        if debug==1: f=enter_debug(f)
        f,accepted=commit_base(f,ordinary,running)
        expected=ordinary and running and not (initial&DEBUG or debug<2 or cut1==1 or cut2==1)
        assert accepted==bool(expected)
        if cut1==2: f=invalidate(f)
        if cut2==2: f=invalidate(f)
        if debug==2: f=enter_debug(f)
        assert not f&BASE
        assert f&DEBUG
        for certified,event_running in product((False,True),repeat=2):
            _,ok=commit_event(f,certified,event_running)
            assert not ok
        count+=1
    # Explicit clean and interrupted control cases without forced debug.
    for initial,ordinary,running,interrupted in product(range(16),(False,True),
            (False,True),(False,True)):
        f=begin(initial)
        if interrupted: f=invalidate(f)
        f,accepted=commit_base(f,ordinary,running)
        assert accepted==bool(ordinary and running and not interrupted and not initial&DEBUG)
        for certified,event_running in product((False,True),repeat=2):
            ef,ok=commit_event(f,certified,event_running)
            assert ok==bool(accepted and certified and event_running)
            assert bool(ef&EVENT)==ok
            assert bool(ef&BASE)==accepted
        count+=1
    print(f"{count} abstract transaction scenarios; no stale base commit after modeled invalidation")
    print("Actual mask duration, hook positions, diagnostic exit policy, aliases and event ownership remain open")

if __name__=="__main__":
    for pn in VARIANTS: audit(pn)
    model()
