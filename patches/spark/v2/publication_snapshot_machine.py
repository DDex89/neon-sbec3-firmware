#!/usr/bin/env python3
"""CPU16 snapshot of legacy byte, Q4 word and readiness in one critical section.

Synthetic addresses only. D returns signed Q4 (legacy byte * 8 on fallback).
E, X, Y, Z, K, SP and incoming IPL preserved; arithmetic CCR flags clobbered.
The reader copies all three fields under the mask, then computes outside it.
An event snapshot is historical: CANCEL applies only to the base snapshot.
This is an instruction-level fixture with modeled maskable preemption, not
hardware interrupt delivery, production RAM ownership or hardware WCET.
"""
from itertools import product
from pathlib import Path
from tempfile import TemporaryDirectory
import sys
from publication_transaction_machine import Fixture,assemble,decode,timing

ASM="""
org $01200
ReadBase:
        PSHM E,CCR
        ORP #$00E0
        LDAA >$0104,Z
        LDAB >$0105,Z
        LDE >$0100,Z
        PULM CCR
        ANDA #$0D
        CMPA #$01
        BNE BaseFallback
        CPE #$FC00
        BLT BaseFallback
        CPE #$03F8
        BGT BaseFallback
        TED
        BRA BaseDone
BaseFallback:
        SXT
        ASLD
        ASLD
        ASLD
BaseDone:
        PULM E
        RTS
org $01280
ReadEvent:
        PSHM E,CCR
        ORP #$00E0
        LDAA >$0104,Z
        LDAB >$0106,Z
        LDE >$0102,Z
        PULM CCR
        ANDA #$0A
        CMPA #$02
        BNE EventFallback
        CPE #$FC00
        BLT EventFallback
        CPE #$03F8
        BGT EventFallback
        TED
        BRA EventDone
EventFallback:
        SXT
        ASLD
        ASLD
        ASLD
EventDone:
        PULM E
        RTS
"""
BASE,EVENT=0x1200,0x1280

def signed(v,bits):
    return v-(1<<bits) if v&(1<<(bits-1)) else v

def expected(state,entry):
    q,legacy,flags=state
    mask,required=(13,1) if entry==BASE else (10,2)
    return q if flags&mask==required and -1024<=q<=1016 else legacy*8

class Reader(Fixture):
    def reset_regs(self):
        super().reset_regs()
        self.inject=None
        self.delayed=False
        self.delivered=False
    def install(self,entry,state):
        q,legacy,flags=state
        self.ram_word(0x100 if entry==BASE else 0x102,q)
        self.ram_byte(0x105 if entry==BASE else 0x106,legacy)
        self.ram_byte(0x104,flags)
    def step(self,pc):
        if self.inject is not None:
            cut,priority,entry,new=self.inject
            if self.steps==cut and priority>self.ipl and not self.delayed:
                self.install(entry,new)
                self.delivered=True
        self.delayed=False
        ins=decode(self.mem,pc)
        super().step(pc)
        if ins.mn=="ORP": self.delayed=True

def run(cpu,entry,state,ipl,inject=None):
    cpu.reset_regs()
    cpu.ipl=ipl
    cpu.extra=0x5010
    cpu.e=0xA55A
    cpu.ix,cpu.iy=0x1234,0x5678
    cpu.xk,cpu.yk=3,4
    cpu.install(entry,state)
    before=(cpu.e,cpu.ix,cpu.iy,cpu.iz,cpu.k(),cpu.sp,cpu.sk,cpu.ipl,cpu.extra)
    cpu.inject=inject
    cpu.call(entry,max_steps=32)
    after=(cpu.e,cpu.ix,cpu.iy,cpu.iz,cpu.k(),cpu.sp,cpu.sk,cpu.ipl,cpu.extra)
    assert before==after,(before,after)
    assert all(0xF8700<=a<0xF8800 for a in cpu.writes),"Snapshot writes outside stack"
    return signed(cpu.d,16)

def main():
    with TemporaryDirectory() as tmp:
        path=Path(tmp)/"snapshot.asm"
        path.write_text(ASM)
        image=assemble([str(path)],0x20000)
    cpu=Reader(image,0x800)
    n=0
    for entry,flags,q,legacy in product((BASE,EVENT),range(256),
            (-32768,-1025,-1024,-1,0,1,1016,1017,32767),(-128,-1,0,127)):
        state=q,legacy,flags
        assert run(cpu,entry,state,flags&7)==expected(state,entry)
        n+=1
    for entry,q in product((BASE,EVENT),range(-1024,1017)):
        state=q,-128,1 if entry==BASE else 2
        assert run(cpu,entry,state,q&7)==q
        n+=1
    assert n==22514,n
    # All boundary cuts of a valid and invalid snapshot, across every
    # mask and priority. A higher-priority writer updates the complete
    # tuple at once if allowed. This is modeled injection, not an ISR.
    pairs=(((9,-1,3),(-17,2,0)),((-17,2,0),(9,-1,3)),
           ((0,-128,3),(1016,127,3)),((1017,-4,3),(-1024,7,3)))
    injections=delivered=0
    for entry,(old,new),ipl,priority,cut in product((BASE,EVENT),pairs,
            range(8),range(1,7),range(22)):
        got=run(cpu,entry,old,ipl,(cut,priority,entry,new))
        assert got in (expected(old,entry),expected(new,entry))
        if not cpu.delivered:
            assert got==expected(old,entry)
        # The first field read is instruction index 2; the last is 4.
        # If a writer is delivered before masking, take its new tuple.
        if cpu.delivered and cut<2:
            assert got==expected(new,entry)
        if cpu.delivered and cut>=6:
            assert got==expected(old,entry)
        assert not (cpu.delivered and 2<=cut<=5)
        delivered+=cpu.delivered
        injections+=1
    # Decode the exact masked sequence. ORP timing already used by
    # atomicity_model.py; other instructions use the existing timing model.
    for entry in (BASE,EVENT):
        pc=entry;seq=[]
        for _ in range(6):
            ins=decode(image,pc);pc+=ins.size
            seq.append(ins)
        assert [i.mn for i in seq]==["PSHM","ORP","LDAA","LDAB","LDE","PULM"]
        rows=[(4,2) if i.mn=="ORP" else timing.timing(i,False) for i in seq[1:]]
        clocks=[sum(c+(f-2)*w for c,w in rows) for f in (2,3,4)]
        assert clocks==[30,39,48],clocks
        print(f"${entry:05X}: modeled masked span {clocks} clocks at 2/3/4-clock flash, aligned 2-clock RAM")
    print(f"{n} CPU16 value cases, {injections} modeled injection attempts, {delivered} delivered")
    print("No production hook, real interrupt or hardware timing proof.")
if __name__=="__main__":main()
