#!/usr/bin/env python3
"""Spark V2 research: isolate angle/coefficient quantization, no ROM patch.

The continuous reference deliberately retains Chrysler's constants and the
effective integer period (no claim of physical ignition-angle accuracy).
Candidate routines execute only the positive delta -> timer offset math.
No branch selection, hardware timer, protection, scheduling or ROM output.
"""
from pathlib import Path
from tempfile import TemporaryDirectory
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/"patches/dinofuel"))
from dinofuel128 import assemble,CPU,require

# Standalone synthetic image, NOT a modification to either stock ROM.
ENTRY=0x1000
STRIDE=0x80
ASM="""
org $01000
Path1:
        PSHM E
        LDE #$005B
        EMUL
        ADDD #$0002
        ADCE #$0000
        LSRE
        RORD
        LSRE
        RORD
        PULM E
        EMUL
        ADCE #$0000
        RTS

org $01080
Path23:
        PSHM E
        LDE #$00CD
        EMUL
        ADDD #$0002
        ADCE #$0000
        LSRE
        RORD
        LSRE
        RORD
        PULM E
        EMUL
        ADCE #$0000
        RTS
"""

def nearest(n,d):
    return (n+d//2)//d

def main():
    with TemporaryDirectory() as tmp:
        src=Path(tmp)/"isolated.asm"
        src.write_text(ASM)
        image=assemble([str(src)],0x20000)
    cpu=CPU(image,0x800)
    cases=0
    for path,constant in enumerate((138,98,58)):
        slope=182 if path==0 else 410
        addr=ENTRY+(STRIDE if path else 0)
        maxerr={k:0.0 for k in ("angle","coefficient","stock","candidate","period")}
        means={"stock":0.0,"candidate":0.0}
        samples=skips=branch_diff=0
        for q in range(-256,673): # -16..42 degrees, increments of 1/16
            raw=(q+4)//8 # illustrative nearest, ties toward positive
            d8=constant*8-q
            dr=constant-raw
            if path and ((d8>0)!=(dr>0)):
                branch_diff+=1
                continue # deliberately NOT proposing a new branch rule
            if path and d8<=0:
                skips+=1
                continue
            for p in ((250,625,1250,2500,5000,7500,15000) if path==2 else (1000,2500,5000,10000,20000,30000,60000)):
                e=p if path==0 else 4*(p*7281//65536) if path==1 else 4*p
                ci=slope*d8/8
                cr=slope*dr
                cs=cr if path==0 else nearest(cr,256)*256
                cn=nearest(slope*d8,8)
                require(0<=cn<=65535 and 0<=e<=65535,"Candidate domain")
                ideal=ci*e/65536
                old=nearest(cs*e,65536)
                new=nearest(cn*e,65536)
                cpu.reset_regs()
                cpu.d=d8;cpu.e=e
                sp=cpu.sp
                cpu.call(addr)
                require(cpu.e==new and cpu.sp==sp,"Isolated machine arithmetic mismatch")
                require(all(0xF8700<=a<0xF8800 for a in cpu.writes),"Unexpected scratch write")
                if path==0 and q%8==0:
                    require(old==new,"Path1 integer-angle compatibility")
                errors={"angle":abs((cr-ci)*e/65536),
                        "coefficient":abs((cs-cr)*e/65536),
                        "stock":abs(old-ideal),"candidate":abs(new-ideal),
                        "period":abs(ci*(p*7281*4/65536-e)/65536) if path==1 else 0}
                require(errors["candidate"]<=0.5+e/(2*65536)+1e-10,"Rounding error bound")
                for k,x in errors.items(): maxerr[k]=max(maxerr[k],x)
                for k in means: means[k]+=errors[k]
                samples+=1
        cases+=samples
        print(f"Path {path+1}: {samples} isolated CPU16 cases; skipped inactive angle values={skips}, branch ambiguity values={branch_diff}")
        print("  max timer counts:", {k:round(v,6) for k,v in maxerr.items()})
        print("  mean timer counts:", {k:round(v/samples,6) for k,v in means.items()})
    print(f"{cases} isolated arithmetic cases passed; no firmware changes",flush=True)

if __name__=="__main__":
    main()
