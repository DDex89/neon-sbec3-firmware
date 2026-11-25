#!/usr/bin/env python3
"""Isolated CPU16 Q4 publication transaction, synthetic RAM only.

E = candidate signed Q4 (caller certifies range), B = actual stock angle.
Synthetic gate bit 0 is caller certification; bit 1 is running state.
No stock hook or allocation. The base writer always publishes the actual
stock byte; cancelled/forced publication clears readiness. An event is
independently qualified and is not rewritten by a base update.
Maskable IPL model only; no actual interrupt delivery or hardware timing.
"""
from itertools import product
from pathlib import Path
from tempfile import TemporaryDirectory
import sys
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/"patches/dinofuel"))
from dinofuel128 import CPU,assemble,decode
import timing

ASM="""
org $01000
Begin:
        PSHM CCR
        ORP #$00E0
        BCLR >$0104,Z,#$04
        PULM CCR
        RTS
org $01040
Invalidate:
        PSHM CCR
        ORP #$00E0
        BCLR >$0104,Z,#$01
        BSET >$0104,Z,#$04
        PULM CCR
        RTS
org $01080
DebugMode:
        PSHM CCR
        ORP #$00E0
        BCLR >$0104,Z,#$03
        BSET >$0104,Z,#$0C
        PULM CCR
        RTS
org $01100
PublishBase:
        PSHM CCR
        ORP #$00E0
        STAB >$0105,Z
        BRSET >$0107,Z,#$03,BaseGate
        BRA BaseReject
BaseGate:
        BRCLR >$0104,Z,#$0C,BaseAccept
BaseReject:
        BCLR >$0104,Z,#$01
        BRA BaseDone
BaseAccept:
        STE >$0100,Z
        BSET >$0104,Z,#$01
BaseDone:
        PULM CCR
        RTS
org $01180
PublishEvent:
        PSHM CCR
        ORP #$00E0
        STAB >$0106,Z
        BRSET >$0107,Z,#$03,EventGate
        BRA EventReject
EventGate:
        BRCLR >$0104,Z,#$01,EventReject
        BRCLR >$0104,Z,#$0C,EventAccept
EventReject:
        BCLR >$0104,Z,#$02
        BRA EventDone
EventAccept:
        STE >$0102,Z
        BSET >$0104,Z,#$02
EventDone:
        PULM CCR
        RTS
"""
class Fixture(CPU):
    def reset_regs(self):
        super().reset_regs()
        self.ipl=0
        self.extra=0
        self.trace=[]
        self.low_sp=self.sp
    def ccr(self):
        return self.extra|(self.h<<13)|(self.n<<11)|(self.z<<10)|(self.v<<9)|(self.c<<8)|(self.ipl<<5)|self.pk
    def set_ccr(self,v,pk=True):
        self.h,self.n,self.z,self.v,self.c=((v>>b)&1 for b in (13,11,10,9,8))
        self.extra=v&0xD010
        self.ipl=(v>>5)&7
        if pk:self.pk=v&15
    def op_ORP(self,ins,f,nxt):
        assert f["jjkk"]==0x00E0
        self.ipl=7
    def push(self,v):
        super().push(v)
        self.low_sp=min(self.low_sp,self.sp)
    def state(self):
        return tuple(self.ram_byte(i) for i in range(0x100,0x107))
    def step(self,pc):
        ins=decode(self.mem,pc)
        super().step(pc)
        taken=((self.pk<<16)|self.pc)!=pc+ins.size
        self.trace.append((ins,taken,self.ipl,self.state()))

def expected(old,entry,gate):
    out=list(old);f=old[4]
    if entry==0x1000:out[4]=f&~4
    elif entry==0x1040:out[4]=(f&~1)|4
    elif entry==0x1080:out[4]=(f&~3)|12
    else:
        event=entry==0x1180
        bit=2 if event else 1
        eligible=gate==3 and not f&12 and (not event or bool(f&1))
        out[6 if event else 5]=0x01
        if eligible:
            i=2 if event else 0
            out[i:i+2]=[0,9]
            out[4]=f|bit
        else:out[4]=f&~bit
    return tuple(out)

def main():
    with TemporaryDirectory() as tmp:
        src=Path(tmp)/"publish.asm"
        src.write_text(ASM)
        image=assemble([str(src)],0x20000)
    cpu=Fixture(image,0x800)
    n=observations=0;stats={}
    for entry,flags,ipl,gate in product((0x1000,0x1040,0x1080,0x1100,0x1180),
                                        range(256),range(8),range(4)):
        cpu.reset_regs();cpu.ipl=ipl;cpu.extra=0x5010
        cpu.n,cpu.z,cpu.v,cpu.c,cpu.h=1,0,1,1,1
        cpu.e=9;cpu.d=0xA501
        cpu.ix,cpu.iy=0x1234,0x5678
        for i,v in enumerate((255,248,255,240,flags,255,254,gate)):
            cpu.ram_byte(0x100+i,v)
        old=cpu.state();want=expected(old,entry,gate)
        regs=(cpu.d,cpu.e,cpu.ix,cpu.iy,cpu.iz,cpu.k(),cpu.sp,cpu.ccr()&0xFFF0)
        cpu.call(entry,max_steps=32)
        assert cpu.state()==want,(entry,flags,ipl,gate,cpu.state(),want)
        assert regs==(cpu.d,cpu.e,cpu.ix,cpu.iy,cpu.iz,cpu.k(),cpu.sp,cpu.ccr()&0xFFF0)
        assert all(0xF8100<=a<=0xF8106 or 0xF8700<=a<0xF8800 for a in cpu.writes)
        for _,_,mask,state in cpu.trace:
            for priority in range(1,7):
                if priority>mask:
                    assert state in (old,want),"Torn visible transaction"
                    observations+=1
        # Count actual executed instructions within the masked span.
        # Existing timing model lacks BCLR/BSET, so do not guess cycles.
        critical=len(cpu.trace)-2 # excludes initial PSHM and final RTS
        prev=stats.get(entry,(0,0,0))
        stats[entry]=tuple(max(a,b) for a,b in zip(prev,(cpu.steps,critical,regs[-2]-cpu.low_sp)))
        n+=1
    assert n==40960
    for entry,(steps,critical,stack) in stats.items():
        print(f"${entry:05X}: max {steps} instructions, {critical} mask-span instructions, {stack} stack bytes")
    print(f"{n} CPU16 cases, {observations} modeled observable boundaries; no torn state")
    print("No measured clocks: bit RMW timings require separate reference validation.")
if __name__=="__main__":main()
