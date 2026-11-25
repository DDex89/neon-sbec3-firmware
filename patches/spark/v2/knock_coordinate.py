#!/usr/bin/env python3
"""Knock window coordinate study, NOT a knock protection patch.

Execute the original quantization slice of KnockCylinderRetard in each
verified ROM, then compare a synthetic Q4 coordinate. Do not change the
ADC sampling window, learnt retard, clamps, timer registers or ISR.
Factory calibration only. The two variants differ downstream: 1997
clears A before the second multiply, 1996 does not. Full timer semantics
(including signed multiply and EDIV overflow) remain separate gates.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/"patches/spark"))
from simulate_v11 import CONFIG,CPU,assemble,decode,require
from timercheck import signed

# End of the stock coordinate slice (before STAB Temp4F2).
END={"04887050":0x1D62E,"05293013AC":0x15790}
PATTERN="LDAB LSRB SUBB CMPB BLE LDAB".split()
ASM="""
org $01000
KnockCoordinateQ4:
        SUBD #$0010
        CPD #$0090
        BLE CoordinateDone
        LDD #$0090
CoordinateDone:
        RTS
"""

def find(rom,end):
    matches=[]
    for start in range(end-40,end,2):
        pc=start
        ins=[]
        for op in PATTERN:
            i=decode(rom,pc)
            if i is None or i.mn!=op:
                break
            ins.append(i)
            pc+=i.size
        if len(ins)==len(PATTERN) and pc==end and ins[4].target()==end:
            matches.append((start,ins))
    require(len(matches)==1,"Original knock coordinate signature")
    return matches[0]

def stock_coordinate(cpu,start,end,off,raw):
    cpu.reset_regs()
    cpu.ram_byte(off,raw)
    cpu.reads.clear()
    cpu.writes.clear()
    cpu.jump(start)
    for _ in range(8):
        pc=(cpu.pk<<16)|cpu.pc
        if pc==end:
            break
        cpu.step(pc)
    else:
        raise ValueError("Knock coordinate slice did not terminate")
    require(not cpu.writes,"Unexpected stock coordinate write")
    return signed(cpu.b)

def check(pn):
    rom=(ROOT/"build"/(pn+".bin")).read_bytes()
    expected=json.loads((ROOT/"tools/variants.json").read_text())[pn]["sha256"]
    require(hashlib.sha256(rom).hexdigest()==expected,"Original SHA")
    end=END[pn]
    start,ins=find(rom,end)
    off=dict(ins[0].vals)["gggg"]
    require(off==({"04887050":0x612,"05293013AC":0x620}[pn]),
            "Unexpected angle input")
    stock=CPU(rom,0x800)
    legacy=[]
    for raw in range(256):
        got=stock_coordinate(stock,start,end,off,raw)
        require(got==min((raw>>1)-1,9),"Factory offset/max or slice mismatch")
        legacy.append(got*16)
    with TemporaryDirectory() as tmp:
        src=Path(tmp)/"knock_coordinate.asm"
        src.write_text(ASM)
        cpu=CPU(assemble([str(src)],0x20000),0x800)
    fine=[]
    for u in range(2048):
        cpu.reset_regs()
        cpu.d=u
        sp=cpu.sp
        cpu.call(0x1000)
        q=cpu.d-65536 if cpu.d&32768 else cpu.d
        require(q==min(u-16,144) and cpu.sp==sp,"Q4 coordinate mismatch")
        require(all(0xF8700<=x<0xF8800 for x in cpu.writes),"Coordinate scratch write")
        fine.append(q)
    require(fine==sorted(fine),"Unsigned coordinate monotonicity")
    n=changed=wraps=integer_changes=guard_changes=0
    max_delta=guard_max=integer_max=0
    for raw in range(256):
        for d in range(-8,9):
            q=signed(raw)*8+d
            if not -1024<=q<=1016:
                continue
            old=legacy[raw]
            new=fine[q&2047]
            wrap=(signed(raw)<0)!=(q<0)
            guarded=old if wrap else new
            n+=1
            changed+=old!=new
            wraps+=wrap
            guard_changes+=old!=guarded
            max_delta=max(max_delta,abs(new-old))
            guard_max=max(guard_max,abs(guarded-old))
            if d==0:
                integer_changes+=old!=new
                integer_max=max(integer_max,abs(new-old))
    require((n,changed,wraps,integer_changes,guard_changes,max_delta,guard_max,integer_max)
            ==(4336,329,9,10,320,160,16,8),"Knock coordinate stress grid changed")
    print(f"{pn}: 256 original CPU16 coordinate cases at ${start:05X}, "
          "2048 synthetic Q4 CPU16 cases",flush=True)
    print(f"{pn}: {n} angle pairs, {changed} coordinate changes, {wraps} sign wraps; "
          f"max change {max_delta}/16 degree, guarded {guard_max}/16 degree",flush=True)
    print(f"{pn}: {integer_changes} changes at zero residual, max {integer_max}/16 "
          "degree (legacy LSRB quantization); not a knock window timing proof",flush=True)

if __name__=="__main__":
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pn",choices=CONFIG)
    check(ap.parse_args().pn)
