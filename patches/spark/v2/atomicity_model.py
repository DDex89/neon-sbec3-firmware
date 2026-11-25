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


def reader_protocol():
    """Reader-side preemption: writer commit can occur between byte reads.

    Abstract single CPU, one writer update, priorities 1..6 only.
    The writer is already atomic; its own masking cannot prevent a
    higher-priority writer from interrupting a lower-priority reader.
    The three-byte test patterns cover all nonempty byte-change subsets;
    they are not required to be physically reachable angle pairs.
    """
    old=(0xFF,0xFF,0xF8)
    protected=0
    unsafe=0
    for changed in range(1,8):
        new=tuple((0x01,0x00,0x08)[i] if changed&(1<<i) else old[i]
                  for i in range(3))
        for initial in range(8):
            for priority in range(1,7):
                for cut in range(4):
                    for masked in (False,True):
                        mask=7 if masked and 0<cut<3 else initial
                        if priority<=mask:
                            continue
                        observed=old[:cut]+new[cut:]
                        if masked:
                            require(observed in (old,new),"Torn masked reader")
                            protected+=1
                        elif observed not in (old,new):
                            unsafe+=1
    require(protected>0 and unsafe>0,"Reader model negative control missing")
    print(f"Abstract reader preemptions: {protected} protected observations; "
          f"{unsafe} torn unprotected observations; not machine validation")


def machine_protocol():
    """Assembled CPU16 fixture, with explicit *modeled* IPL semantics.

    The base simulator has no interrupt delivery and hard-codes IPL=7.
    Extend only this fixture. Synthetic RAM offsets are NOT ECU reservations.
    Only ORP #$00E0 is implemented here, not general CCR semantics.
    """
    import sys
    from tempfile import TemporaryDirectory
    sys.path.insert(0,str(ROOT/"patches/dinofuel"))
    from dinofuel128 import assemble, CPU, decode
    import timing

    asm="""
org $01000
Publish:
        PSHM CCR
        ORP #$00E0
        STE >$0100,Z
        STAB >$0102,Z
        PULM CCR
        RTS
org $01040
Snapshot:
        PSHM CCR
        ORP #$00E0
        LDE >$0100,Z
        LDAB >$0102,Z
        PULM CCR
        RTS
org $01080
UnprotectedSnapshot:
        LDE >$0100,Z
        LDAB >$0102,Z
        RTS
"""
    with TemporaryDirectory() as tmp:
        src=Path(tmp)/"publication_fixture.asm"
        src.write_text(asm)
        image=assemble([str(src)],0x20000)

    class FixtureCPU(CPU):
        def reset_regs(self):
            super().reset_regs()
            self.ipl=0
            self.extra_ccr=0
            self.defer_irq=False
            self.boundaries=[]
            self.inject=None

        def ccr(self):
            return (self.extra_ccr|(self.h<<13)|(self.n<<11)|(self.z<<10)|
                    (self.v<<9)|(self.c<<8)|(self.ipl<<5)|self.pk)

        def set_ccr(self,v,pk=True):
            self.h,self.n,self.z,self.v,self.c=((v>>b)&1 for b in (13,11,10,9,8))
            self.extra_ccr=v&0xD010 # S, MV, EV, SM; retained, not executed
            self.ipl=(v>>5)&7
            if pk:
                self.pk=v&15

        def op_ORP(self,ins,f,nxt):
            require(f["jjkk"]==0x00E0,"Unexpected fixture ORP")
            self.ipl=7
            self.defer_irq=True # CPU16RM 5.9: through following instruction

        def state(self):
            return (self.ram_byte(0x102),self.ram_word(0x100))

        def step(self,pc):
            if self.inject is not None:
                cut,priority,new=self.inject
                if self.steps==cut and priority>self.ipl and not self.defer_irq:
                    # Atomic higher-priority publisher; not hardware ISR delivery.
                    self.ram_byte(0x102,new[0])
                    self.ram_word(0x100,new[1])
            self.defer_irq=False
            super().step(pc)
            self.boundaries.append((self.ipl,self.state()))

    cpu=FixtureCPU(image,0x800)
    allowed={0xF8100,0xF8101,0xF8102}
    old=(0xFF,0xFFF8)
    new=(0x01,0x0008)
    observations=publish_cases=read_cases=unsafe=0

    def prepare(ipl):
        cpu.reset_regs()
        cpu.ipl=ipl
        cpu.extra_ccr=0x5010 # inert MV/EV/SM bits in fixture
        cpu.n,cpu.z,cpu.v,cpu.c,cpu.h=1,0,1,1,1
        cpu.ix,cpu.iy=0x1234,0x5678
        cpu.d=0xA500|new[0]
        cpu.e=new[1]
        cpu.ram_byte(0x102,old[0])
        cpu.ram_word(0x100,old[1])

    def flags():
        return cpu.ccr()&0xFFF0

    def check_restore(sp,ccr):
        require(cpu.sp==sp and flags()==ccr,"Fixture stack/CCR restoration")
        require(cpu.ix==0x1234 and cpu.iy==0x5678 and
                cpu.iz==0x8000 and cpu.zk==15,"Fixture register corruption")

    for initial in range(8):
        prepare(initial)
        sp,ccr=cpu.sp,flags()
        cpu.call(0x1000)
        check_restore(sp,ccr)
        require(cpu.state()==new and cpu.e==new[1] and
                cpu.d==0xA500|new[0],"Fixture publication result")
        require((cpu.writes&allowed)==allowed and
                all(a in allowed or 0xF8700<=a<0xF8800 for a in cpu.writes),
                "Unexpected fixture publication write")
        for mask,pair in cpu.boundaries:
            for priority in range(1,7):
                if priority>mask:
                    require(pair in (old,new),"Torn assembled publication")
                    observations+=1
        publish_cases+=1
        for entry,nsteps in ((0x1040,6),(0x1080,3)):
            for cut in range(nsteps):
                for priority in range(1,7):
                    prepare(initial)
                    sp,ccr=cpu.sp,flags()
                    cpu.inject=(cut,priority,new)
                    cpu.call(entry)
                    require(cpu.sp==sp,"Snapshot stack restoration")
                    require(cpu.a==0xA5 and cpu.ix==0x1234 and
                            cpu.iy==0x5678,"Snapshot register corruption")
                    require(not(cpu.writes&allowed),"Snapshot wrote angle")
                    pair=(cpu.b,cpu.e)
                    if entry==0x1040:
                        check_restore(sp,ccr)
                        require(pair in (old,new),"Torn assembled snapshot")
                        read_cases+=1
                    elif pair not in (old,new):
                        unsafe+=1
    # Decode the actual assembled fixture and use the existing timing model.
    # CPU16RM ORP IMM16: 4 clocks, two program words. The original timing
    # module intentionally does not support this instruction.
    for entry,mn_pair in ((0x1000,("STE","STAB")),(0x1040,("LDE","LDAB"))):
        pc=entry
        seq=[]
        for _ in range(6):
            ins=decode(image,pc)
            require(ins is not None,"Fixture timing decode")
            if ins.mn=="ORP":
                require(ins.mode=="IMM16" and ins.size==4 and
                        dict(ins.vals)["jjkk"]==0x00E0,"ORP timing signature")
                clocks,words=4,2
            else:
                clocks,words=timing.timing(ins,False)
            seq.append((ins.mn,clocks,words))
            pc+=ins.size
        require(tuple(x[0] for x in seq)==("PSHM","ORP",*mn_pair,"PULM","RTS"),
                "Fixture timing sequence")
        # Conservative span includes the entire mask-setting and restoring
        # instructions; excludes call, PSHM, RTS and interrupt entry latency.
        critical=seq[1:5]
        def model(rows,flash,ram,operands):
            return (sum(x[1] for x in rows)+(flash-2)*sum(x[2] for x in rows)
                    +(ram-2)*operands)
        # Two data operations + two PULM stack accesses; full routine adds
        # one PSHM and two RTS stack accesses. Aligned 16-bit buses assumed.
        span=[model(critical,f,2,4) for f in (2,3,4)]
        full=[model(seq,f,2,7) for f in (2,3,4)]
        require(span==[24,31,38] and full==[42,53,64],"Unexpected timing totals")
        print(f"Fixture ${entry:05X}: {pc-entry} bytes; critical clocks "
              f"2/3/4-clock flash: {span}; complete routine: {full}; "
              "2-clock aligned RAM; no hardware WCET")

    require(unsafe>0,"Assembled reader negative control missing")
    print(f"CPU16 assembled fixture: {publish_cases} publications, "
          f"{observations} observable writer boundaries, {read_cases} snapshots; "
          f"{unsafe} torn unprotected snapshots. Modeled IPL, no real ISR timing.")


def check(pn):
    audit(pn)
    protocol()
    reader_protocol()
    machine_protocol()


if __name__=="__main__":
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pn",choices=VARIANTS)
    check(ap.parse_args().pn)
