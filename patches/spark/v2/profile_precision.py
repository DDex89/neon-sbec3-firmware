#!/usr/bin/env python3
"""Instruction/stack profile of isolated precision candidate, not ISR WCET."""
from precision import ASM,ENTRY,STRIDE,assemble,TemporaryDirectory,Path,require
import timing

def main():
    timing.ALU.add("ADDD") # immediate word addition, same timing class as ADDE
    timing.REG2.add("RORD") # rotate D, inherent; 2-clock register operation
    with TemporaryDirectory() as tmp:
        p=Path(tmp)/"isolated.asm"
        p.write_text(ASM)
        rom=assemble([str(p)],0x20000)
    for addr in (ENTRY,ENTRY+STRIDE):
        cpu=timing.ProfileCPU(rom)
        cpu.d=1024
        cpu.e=10000
        cpu.call(addr)
        require(cpu.sp==cpu.initial_sp,"Profile stack balance")
        print(f"${addr:05X}: {cpu.steps} instructions; {cpu.initial_sp-cpu.low_sp} stack bytes including sentinel; model clocks 2/3/4 flash: {[cpu.clocks(x) for x in (2,3,4)]}")
if __name__=="__main__":
    main()
