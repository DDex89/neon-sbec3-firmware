#!/usr/bin/env python3
"""Isolated byte-cell interpolation in CPU16, final result in 1/16 degrees.

Input: four contiguous unsigned (or caller-biased signed) byte cells at Y,
E = Q0.16 RPM fraction, D = Q0.16 row fraction.
Output: D = unsigned Q4 degrees, subtract 1024 in the caller for signed cells.
The two horizontal and one vertical lerps use 1/256-degree intermediates.
No production lookup, ROM patch, scratch allocation, or timer change.
"""
import argparse
import hashlib
import itertools
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/"patches/spark"))
from simulate_v11 import CONFIG,MANIFEST,CPU,assemble,table,require
from map_precision import interval,bilinear

ENTRY=0x1000
ASM="""
org $01000
ByteMap:
        PSHM    D,E,Y
        JSR     ByteLerp
        PSHM    D
        AIY     #$02
        TSX
        LDE     $04,X
        JSR     ByteLerp
        TDE
        PULM    D
        PSHM    D
        SDE
        TED
        PULM    X
        PULM    Y
        AIS     #$02
        PULM    E
        JSR     DeltaLerp
        ADDD    #$0008
        LSRD
        LSRD
        LSRD
        LSRD
        RTS

ByteLerp:
        PSHM    E
        LDAA    $01,Y
        CLRB
        LSRD
        TDE
        LDAA    $00,Y
        CLRB
        LSRD
        PSHM    D
        SDE
        TED
        PULM    X
        PULM    E
DeltaLerp:
        CPD     #$0000
        BMI     Descending
        EMUL
        ADCE    #$0000
        BRA     AddFirst
Descending:
        NEGD
        EMUL
        ADCE    #$0000
        NEGE
AddFirst:
        XGDX
        ADE
        TED
        RTS
"""

class TraceCPU(CPU):
    def push(self,v):
        super().push(v)
        self.low_sp=min(self.low_sp,self.sp)

def run(cpu,cells,fx,fy):
    cpu.reset_regs()
    cpu.low_sp=cpu.sp
    initial=cpu.sp
    for i,value in enumerate(cells):
        require(0<=value<=255,"Byte cell range")
        cpu.ram_byte(0x100+i,value)
    cpu.iy=0x8100;cpu.yk=15
    cpu.e=fx;cpu.d=fy
    cpu.call(ENTRY,max_steps=250)
    require(cpu.sp==initial and cpu.iy==0x8100 and cpu.yk==15,"Stack or Y contract")
    require(all(0xF8700<=a<0xF8800 for a in cpu.writes),"Unexpected non-stack write")
    return cpu.d,cpu.steps,initial-cpu.low_sp

def lerp(a,b,f):
    delta=b-a
    return a+(1 if delta>=0 else -1)*((abs(delta)*f+32768)//65536)

def staged(cells,fx,fy):
    a,b,c,d=(x*128 for x in cells)
    return (lerp(lerp(a,b,fx),lerp(c,d,fx),fy)+8)//16

def exact_q4(cells,fx,fy):
    a,b,c,d=cells
    t=(a*(65536-fx)+b*fx)*(65536-fy)+(c*(65536-fx)+d*fx)*fy
    return t*8/65536**2

def check(pn,full):
    rom=(ROOT/"build"/(pn+".bin")).read_bytes()
    sha=json.loads((ROOT/"tools/variants.json").read_text())[pn]["sha256"]
    require(hashlib.sha256(rom).hexdigest()==sha,"Original SHA")
    with TemporaryDirectory() as tmp:
        src=Path(tmp)/"byte_interp.asm"
        src.write_text(ASM)
        image=assemble([str(src)],0x20000)
    cpu=TraceCPU(image,0x800)
    m=MANIFEST["variants"][pn]
    steps=stack=synthetic=0
    # Every ascending/descending/equal corner combination over signed-biased
    # extrema; fractions immediately before/at/after rounding boundaries.
    for cells in itertools.product((0,1,127,128,254,255),repeat=4):
        for fx,fy in ((0,0),(65535,65535),(32768,32768),(32767,32769),(2048,63488),(63488,2048)):
            got,ins,sp=run(cpu,cells,fx,fy)
            require(got==staged(cells,fx,fy),"Synthetic stage mismatch")
            require(abs(got-exact_q4(cells,fx,fy))<=0.6,"Synthetic final rounding error")
            require(min(cells)*8<=got<=max(cells)*8,"Interpolation outside cell envelope")
            steps=max(steps,ins);stack=max(stack,sp);synthetic+=1
    print(f"{pn}: {synthetic} synthetic machine corner/fraction cases passed",flush=True)
    for mode in (0,1):
        axis,v=table(rom,int(m["spark_tables"][mode],0))
        bias=128 if mode else 0
        positions=range(256) if full else sorted(set(range(0,256,7))|{0,1,15,16,17,31,32,33,127,128,129,254,255})
        rpms=range(256) if full else sorted(set(range(0,256,7))|{max(0,min(255,x+k)) for x in axis for k in (-1,0,1)}|set(range(48,63))|{255})
        n=0;maxerr=0.0;mean=0.0;single_diff=0
        for pos in positions:
            j,y=divmod(pos*(len(v)-1),256)
            jj=min(j+1,len(v)-1)
            for rpm in rpms:
                i,fn,fd=interval(axis,rpm)
                ii=min(i+1,len(axis)-1)
                fx=(fn*2048//fd)*32
                fy=y*256
                cells=tuple(x+bias for x in (v[j][i],v[j][ii],v[jj][i],v[jj][ii]))
                got,ins,sp=run(cpu,cells,fx,fy)
                require(got==staged(cells,fx,fy),"Machine stage mismatch")
                require(min(cells)*8<=got<=max(cells)*8,"Outside map envelope")
                exact_num,exact_den=bilinear(v,i,j,fn,fd,y)
                exact=exact_num/exact_den
                q=got-bias*8
                error=abs(q-exact)/16
                require(error<=0.05,"Factory map precision bound")
                maxerr=max(maxerr,error);mean+=error
                single_diff+=got!=(int(exact_q4(cells,fx,fy)+0.5))
                steps=max(steps,ins);stack=max(stack,sp);n+=1
        print(f"{pn} {'WOT' if mode else 'PT'}: {n} machine cases; max error {maxerr:.8f} deg; mean {mean/n:.8f} deg; staged vs single-round count {single_diff}",flush=True)
    print(f"{pn}: max {steps} instructions, {stack} stack bytes including test frame; isolated only",flush=True)

if __name__=="__main__":
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pn",choices=CONFIG)
    ap.add_argument("--full",action="store_true")
    a=ap.parse_args()
    check(a.pn,a.full)
