#!/usr/bin/env python3
"""Isolated Spark V2 event-clamp research; no production ROM changes.

Host stress grid plus assembled CPU16 signed clamp with synthetic RAM.
Threshold comparisons are research indicators, not a scheduler audit.
Run: python3 patches/spark/v2/fine_event.py
"""
from pathlib import Path
from tempfile import TemporaryDirectory
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/"patches/spark"))
from simulate_v11 import CPU,assemble,require

ASM="""
org $01000
FineEvent:
        CPD >$0100,Z
        BGE FineUpper
        LDD >$0100,Z
FineUpper:
        CPD #$03F8
        BLE FineRamp
        LDD #$03F8
FineRamp:
        CPD >$0102,Z
        BLE FineDone
        LDD >$0102,Z
FineDone:
        RTS
"""

BASES=(-128,-65,-32,-1,0,18,48,58,98,126,127)
RAMPS=(-20,0,40,125,127)
MINIMA=(-128,-32,0,18,48,127)
ADJUSTMENTS=(-255,-59,0,6,227)

def clip(x,lo,hi):
    return max(lo,min(hi,x))

def host():
    count=changed=forced=crossed=0
    for running in (0,1):
        for bypass in (0,1,2):
            for base in BASES:
                for minimum in MINIMA:
                    for ramp in RAMPS:
                        for adjustment in ADJUSTMENTS:
                            for delta in range(-8,9):
                                old=(min(ramp,max(minimum,min(127,base+(0 if bypass else adjustment))))
                                     if running else 18)
                                fine_base=clip(base*8+delta,-1024,1016)
                                fine=(old*8 if not running or bypass else
                                      min(ramp*8,max(minimum*8,min(1016,fine_base+adjustment*8))))
                                require(abs(fine-old*8)<=abs(delta),"Residual grew")
                                require(-1024<=fine<=1016,"Published angle bounds")
                                if not delta or not running or bypass:
                                    require(fine==old*8,"Forced/zero residual mismatch")
                                count+=1
                                changed+=fine!=old*8
                                forced+=not running or bool(bypass)
                                # Signed >= comparison only; actual ISR includes
                                # unsigned arithmetic and strict/equality branches.
                                for threshold in (48,58,98):
                                    crossed+=(old>=threshold)!=(fine>=threshold*8)
    require((count,changed,forced,crossed)==(168300,3664,140250,224),
            "Host stress grid changed")
    print(f"{count} host cases; {changed} changed angles; {forced} forced-path cases; "
          f"{crossed} signed threshold comparison differences",flush=True)

def machine():
    with TemporaryDirectory() as tmp:
        src=Path(tmp)/"fine_event.asm"
        src.write_text(ASM)
        cpu=CPU(assemble([str(src)],0x20000),0x800)
    count=0
    for minimum in MINIMA:
        for ramp in (-128,-20,-1,0,40,125,127):
            lo,hi=minimum*8,ramp*8
            totals={-4096,-1025,-1024,-1,0,1,1016,1017,4096}
            for boundary in (lo,hi,1016):
                totals.update(range(boundary-9,boundary+10))
            for total in sorted(totals):
                cpu.reset_regs()
                cpu.ram_word(0x100,lo&65535)
                cpu.ram_word(0x102,hi&65535)
                cpu.d=total&65535
                sp=cpu.sp
                cpu.call(0x1000)
                expected=min(hi,max(lo,min(1016,total)))
                got=cpu.d-65536 if cpu.d&32768 else cpu.d
                require(got==expected and cpu.sp==sp,"Fine event clamp CPU16 mismatch")
                require(all(0xF8700<=a<0xF8800 for a in cpu.writes),
                        "Fine event clamp non-stack write")
                count+=1
    print(f"{count} isolated CPU16 clamp cases; synthetic RAM, no ISR",flush=True)

if __name__=="__main__":
    host()
    machine()
