#!/usr/bin/env python3
"""Isolated CPU16 SparkEvent arithmetic: selected signed bytes -> Q4 result.

D = fine base, Y/YK points to four signed legacy correction bytes (AC,
pair, event, knock), followed by two signed Q4 words (minimum, ramp).
D returns final Q4. E, X, Y, Z, K and stack preserved; CCR clobbered.
Caller selects stock mode and performs stock ramp update BEFORE this call.
Forced/crank/hold paths stay outside this candidate, with legacy output.
No production RAM, scheduler, or ROM modification.
"""
from itertools import product
from pathlib import Path
from tempfile import TemporaryDirectory
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "patches/spark"))
from simulate_v11 import CPU, assemble, require
from spark_event_q4_contract import stock, shadow

ENTRY = 0x1000
ASM = """
org $01000
SparkEventQ4:
        PSHM E
        PSHM D
        LDAB $00,Y
        SXT
        TDE
        LDAB $01,Y
        SXT
        ADE
        LDAB $02,Y
        SXT
        SDE
        LDAB $03,Y
        SXT
        SDE
        ASLE
        ASLE
        ASLE
        PULM D
        ADE
        TED
        CPD >$04,Y
        BGE Upper
        LDD >$04,Y
Upper:
        CPD #$03F8
        BLE Ramp
        LDD #$03F8
Ramp:
        CPD >$06,Y
        BLE Done
        LDD >$06,Y
Done:
        PULM E
        RTS
"""

class TraceCPU(CPU):
    def push(self, v):
        super().push(v)
        self.low_sp = min(self.low_sp, self.sp)

def signed16(v):
    return v - 65536 if v & 32768 else v

def invoke(cpu, q, corrections, lo, hi):
    cpu.reset_regs()
    cpu.low_sp = cpu.sp
    cpu.iy, cpu.yk = 0x8100, 15
    cpu.ix, cpu.xk = 0x4567, 3
    cpu.e = 0xA55A
    cpu.d = q
    for i, value in enumerate(corrections):
        cpu.ram_byte(0x100+i, value)
    cpu.ram_word(0x104, lo*8)
    cpu.ram_word(0x106, hi*8)
    before = (cpu.e,cpu.ix,cpu.iy,cpu.iz,cpu.k(),cpu.sp,cpu.sk)
    cpu.call(ENTRY, max_steps=64)
    after = (cpu.e,cpu.ix,cpu.iy,cpu.iz,cpu.k(),cpu.sp,cpu.sk)
    require(before == after, "Register/stack contract")
    require(all(0xF8700 <= a < 0xF8800 for a in cpu.writes),
            "Unexpected non-stack write")
    return signed16(cpu.d), cpu.steps, before[-2]-cpu.low_sp

def main():
    with TemporaryDirectory() as tmp:
        src = Path(tmp)/"event_q4.asm"
        src.write_text(ASM)
        cpu = TraceCPU(assemble([str(src)],0x20000),0x800)
    edge = (-128,-1,0,1,127)
    limits = ((-128,127),(-12,42),(0,0),(127,-128),(-1,0),(0,-1))
    count = max_steps = max_stack = 0
    for base in (-128,-65,-1,0,1,48,58,98,126,127):
        for c in product(edge,repeat=4):
            for lo,hi in limits:
                q = base*8
                got,steps,sp = invoke(cpu,q,c,lo,hi)
                require(got==8*stock(base,c,lo,hi),"Integer equivalence")
                max_steps=max(max_steps,steps); max_stack=max(max_stack,sp)
                count+=1
    fractional=0
    for base in range(-128,128):
        for residual in range(-8,9):
            q=base*8+residual
            if not -1024<=q<=1016:
                continue
            for c in ((0,0,0,0),(3,-5,2,8),(-128,-128,127,127),
                      (127,127,-128,-128)):
                for lo,hi in limits:
                    got,steps,sp=invoke(cpu,q,c,lo,hi)
                    require(got==shadow(base,q,c,lo,hi),"Fractional equivalence")
                    max_steps=max(max_steps,steps); max_stack=max(max_stack,sp)
                    fractional+=1
    require((count,fractional)==(37500,104064),"Coverage changed")
    print(f"{count} integer + {fractional} fractional CPU16 cases; "
          f"max {max_steps} instructions, {max_stack} stack bytes including return frame")
    print("Synthetic selected corrections; no ISR, production RAM, or hardware proof.")

if __name__=="__main__":
    main()
