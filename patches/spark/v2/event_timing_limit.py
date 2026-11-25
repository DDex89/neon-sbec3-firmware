#!/usr/bin/env python3
"""Factory EventTimingLimit two-point Q4 adapter; simulation only.

The real stock Lookup2D is executed for every raw angle in both variants.
The experimental CPU16 routine accepts an unsigned Q4 projection in D
and returns the original output unit in A. It specializes ONLY the
verified factory table, not arbitrary aftermarket calibration.
The host studies a temporary legacy-sign wrap guard and the original
IC1 comparison window; no production scheduler change or RAM allocation.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/"patches/spark"))
from simulate_v11 import CONFIG,CPU,assemble,require
from timercheck import signed

TABLE={"04887050":0x51E1,"05293013AC":0x51ED}
SIGNATURE=bytes((2,128,0,86,127,142))
ENTRY=0x1000
ASM="""
org $01000
EventLimitQ4:
        CPD #$03F8
        BCS Interpolate
        LDAA #$8E
        RTS
Interpolate:
        PSHM E,X
        LDE #$0007
        EMUL
        LDX #$007F
        IDIV
        XGDX
        ADDD #$0056
        TBA
        PULM E,X
        RTS
"""

def reference(u):
    require(0<=u<=2047,"Unsigned Q4 range")
    return 86+7*min(u,1016)//127

def run(cpu,u):
    cpu.reset_regs()
    cpu.d=u
    cpu.e=0xA55A
    cpu.ix,cpu.iy=0x1234,0x5678
    sp=cpu.sp
    cpu.call(ENTRY)
    require(cpu.sp==sp and (cpu.e,cpu.ix,cpu.iy)==(0xA55A,0x1234,0x5678),
            "Event limit register contract")
    require(all(0xF8700<=a<0xF8800 for a in cpu.writes),
            "Event limit non-stack write")
    return cpu.a,cpu.steps

def check(pn):
    rom=(ROOT/"build"/(pn+".bin")).read_bytes()
    expected=json.loads((ROOT/"tools/variants.json").read_text())[pn]["sha256"]
    require(hashlib.sha256(rom).hexdigest()==expected,"Original SHA")
    table=TABLE[pn]
    require(rom[table:table+6]==SIGNATURE,"Factory table signature")
    stock=CPU(rom,0x800)
    old=[]
    old_steps=[]
    for raw in range(256):
        stock.reset_regs()
        stock.ix=table
        stock.a=raw
        sp=stock.sp
        stock.call(CONFIG[pn]["lookup2d"])
        require(stock.sp==sp,"Stock lookup stack")
        require(stock.a==reference(raw*8),"Factory interpolation model")
        old.append(stock.a)
        old_steps.append(stock.steps)
    with TemporaryDirectory() as tmp:
        src=Path(tmp)/"event_timing_limit.asm"
        src.write_text(ASM)
        image=assemble([str(src)],0x20000)
    cpu=CPU(image,0x800)
    out=[]
    steps=[]
    for u in range(2048):
        a,n=run(cpu,u)
        require(a==reference(u),"Fine event limit CPU16 mismatch")
        out.append(a)
        steps.append(n)
    require(all(out[raw*8]==old[raw] for raw in range(256)),
            "Integer angle compatibility")
    require(out==sorted(out),"Unsigned limit monotonicity")
    pairs=changed=wraps=guard_changes=gate=guard_gate=0
    max_delta=guard_max=0
    for raw in range(256):
        base=signed(raw)
        for residual in range(-8,9):
            q=base*8+residual
            if not -1024<=q<=1016:
                continue
            old_limit=old[raw]
            fine=out[q&2047]
            wrap=(base<0)!=(q<0)
            safe=old_limit if wrap else fine
            pairs+=1
            wraps+=wrap
            changed+=fine!=old_limit
            guard_changes+=safe!=old_limit
            max_delta=max(max_delta,abs(fine-old_limit))
            guard_max=max(guard_max,abs(safe-old_limit))
            # In IC1: high RefPeriod byte zero, low byte in [0x4E,0x82).
            # Compare *byte* unsigned, not the 16-bit timer period.
            for period_low in range(0x4E,0x82):
                baseline=old_limit>=period_low
                gate+=baseline!=(fine>=period_low)
                guard_gate+=baseline!=(safe>=period_low)
    require((pairs,changed,wraps,guard_changes,max_delta,guard_max,gate,guard_gate)
            ==(4336,513,9,504,56,1,774,387),"Event limit stress grid changed")
    print(f"{pn}: 256 original CPU16 lookups and 2048 fine CPU16 lookups; "
          f"all integer angles exact; stock instructions {min(old_steps)}..{max(old_steps)}, "
          f"specialized {min(steps)}..{max(steps)}",flush=True)
    print(f"{pn}: {pairs} angle pairs, {changed} threshold value changes, {wraps} "
          f"sign-wrap pairs, max delta {max_delta}; guarded changes {guard_changes}, "
          f"max delta {guard_max}",flush=True)
    print(f"{pn}: {pairs*52} IC1 comparison cases; {gate} unguarded and {guard_gate} "
          "guarded predicate differences. Not ISR reachability or protection proof.",
          flush=True)

if __name__=="__main__":
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pn",choices=CONFIG)
    check(ap.parse_args().pn)
