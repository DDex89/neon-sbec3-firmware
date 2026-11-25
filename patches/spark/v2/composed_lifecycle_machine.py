#!/usr/bin/env python3
"""Composed CPU16 Spark Q4 lifecycle, using the exact tested subroutines.

Synthetic RAM/ROM; no production hooks. Host selects stock correction inputs,
stock mode and publication eligibility. Calls share one persistent CPU/RAM
image. No ISR entry/exit or production timing assertion.
"""
from itertools import product
from pathlib import Path
from tempfile import TemporaryDirectory
from publication_transaction_machine import Fixture, ASM as PUBLISH, assemble
from publication_snapshot_machine import ASM as READ, signed, BASE, EVENT
from spark_event_q4_machine import ASM as ARITH
from spark_event_q4_contract import stock,shadow

# Relocate the arithmetic fixture only; its operands are Y-relative.
ARITH=ARITH.replace("org $01000","org $01300")
# Reader and publisher originally assembled separately and share local labels.
READ=READ.replace("BaseDone","ReadBaseDone").replace("EventDone","ReadEventDone")
BEGIN,INVALIDATE,DEBUG,PB,PE,CALC=0x1000,0x1040,0x1080,0x1100,0x1180,0x1300
BVALID,EVALID,CANCEL,DBG=1,2,4,8

def call(cpu,entry):
    sp=cpu.sp
    cpu.call(entry,max_steps=512)
    assert cpu.sp==sp
    # Only synthetic fixture state, host-selected correction block or stack
    # are permitted; instructions must never modify the correction block.
    assert all(0xF8100<=a<=0xF8106 or 0xF8700<=a<0xF8800 for a in cpu.writes)

def pub(cpu,entry,q,legacy,gate):
    cpu.e=q&65535
    cpu.d=0xA500|(legacy&255)
    cpu.ram_byte(0x107,gate)
    call(cpu,entry)

def read(cpu,entry):
    call(cpu,entry)
    return signed(cpu.d,16)

def flags(cpu): return cpu.ram_byte(0x104)

def main():
    with TemporaryDirectory() as tmp:
        src=Path(tmp)/"combined.asm"
        src.write_text(PUBLISH+"\n"+READ+"\n"+ARITH)
        image=assemble([str(src)],0x20000)
    cpu=Fixture(image,0x800)
    count=accepted=fallback=0
    for base,residual,c,limits,mode,cut,initial in product(
            (-128,-1,0,1,48,127),(-7,0,7),
            ((0,0,0,0),(3,-5,2,8),(-128,-128,127,127),(127,127,-128,-128)),
            ((-128,127),(-12,42),(0,-1),(127,-128)),
            (0,1,2,3),("none","before_begin","before_base","after_base","debug_before_base","debug_after_base"),
            (0,1,3,7)):
        q=base*8+residual
        if not -1024<=q<=1016: continue
        lo,hi=limits
        cpu.reset_regs();cpu.ipl=initial
        cpu.iy,cpu.yk=0x8120,15
        # Deliberately stale words and historical event from prior cycle.
        cpu.ram_word(0x100,0x7777)
        cpu.ram_word(0x102,-17)
        cpu.ram_byte(0x104,EVALID)
        cpu.ram_byte(0x105,99)
        cpu.ram_byte(0x106,-2)
        for i,v in enumerate(c): cpu.ram_byte(0x120+i,v)
        cpu.ram_word(0x124,lo*8)
        cpu.ram_word(0x126,hi*8)
        if cut=="before_begin":call(cpu,INVALIDATE)
        call(cpu,BEGIN)
        if cut=="before_base":call(cpu,INVALIDATE)
        if cut=="debug_before_base":call(cpu,DEBUG)
        pub(cpu,PB,q,base,3)
        if cut=="after_base":call(cpu,INVALIDATE)
        if cut=="debug_after_base":call(cpu,DEBUG)
        base_ok=cut in ("none","before_begin")
        dbg=cut.startswith("debug")
        assert bool(flags(cpu)&BVALID)==base_ok
        assert bool(flags(cpu)&DBG)==dbg
        # Invalidation does not retroactively change an existing event.
        assert read(cpu,EVENT)==(-16 if dbg else -17)
        got_base=read(cpu,BASE)
        assert got_base==(q if base_ok else base*8)
        # Use same stock-selected correction inputs for both paths.
        cpu.d=got_base&65535
        call(cpu,CALC)
        got=signed(cpu.d,16)
        legacy=stock(base,c,lo,hi)
        want=shadow(base,got_base,c,lo,hi)
        assert got==want
        # Mode 3: ordinary+running; other modes force legacy fallback.
        pub(cpu,PE,got,legacy,mode)
        ok=base_ok and mode==3
        assert bool(flags(cpu)&EVALID)==ok
        assert read(cpu,EVENT)==(want if ok else legacy*8)
        assert cpu.ram_byte(0x105)==base&255
        assert cpu.ram_byte(0x106)==legacy&255
        assert cpu.ipl==initial
        # A subsequent background cancellation must not rewrite this event.
        call(cpu,INVALIDATE)
        assert read(cpu,EVENT)==(want if ok else legacy*8)
        assert read(cpu,BASE)==base*8
        count+=1;accepted+=ok;fallback+=not ok
    assert count==24576,(count,accepted,fallback)
    print(f"{count} composed CPU16 lifecycle scenarios; {accepted} accepted Q4 events, {fallback} legacy fallbacks")
    print("One assembled image and persistent synthetic RAM; host-selected inputs, no real ISR/ROM integration.")
if __name__=="__main__":main()
