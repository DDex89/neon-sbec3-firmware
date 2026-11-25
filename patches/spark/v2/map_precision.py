#!/usr/bin/env python3
"""Stock byte map precision study; no ROM modifications.

Compare existing machine output, Q8/Q11 interpolation and an exact rational
bilinear reference with the stock MAP row coordinate. All angle units here
are 1/16 degree (eight units per stock raw count).
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/"patches/spark"))
from simulate_v11 import CONFIG, MANIFEST, CPU, table, invoke, lookup_position, require

def rounddiv(n,d):
    return (n+d//2)//d

def interval(axis,rpm):
    i=max((i for i,x in enumerate(axis) if x<=rpm),default=0)
    return (i,0,1) if rpm<=axis[0] or i==len(axis)-1 else (i,rpm-axis[i],axis[i+1]-axis[i])

def bilinear(v,i,j,fn,fd,y):
    ii=min(i+1,len(v[0])-1)
    jj=min(j+1,len(v)-1)
    a=v[j][i]*(fd-fn)+v[j][ii]*fn
    b=v[jj][i]*(fd-fn)+v[jj][ii]*fn
    return (a*(256-y)+b*y)*8, fd*256

def evaluate(t,pos,rpm):
    ax,v=t
    i,n,d=interval(ax,rpm)
    j,y=divmod(pos*(len(v)-1),256)
    num,den=bilinear(v,i,j,n,d,y)
    exact=num/den
    outputs={}
    for bits in (8,11,16):
        fd=1<<bits
        fn=n*fd//d
        a,b=bilinear(v,i,j,fn,fd,y)
        outputs[bits]=rounddiv(a,b)
    return exact,outputs

# Synthetic fixture only: D = signed *unclamped* stock sum in half degrees,
# E = signed residual in Q4. The input domain (18 signed byte terms) fits
# signed 16-bit even after scaling by eight. No branch policy is implemented
# here: the host fixture selects ordinary vs forced inputs.
FINE_ASM="""
org $02000
FineSum:
        ASLD
        ASLD
        ASLD
        ADE
        TED
        CPD #$03F8
        BGT FineMax
        CPD #$FC00
        BLT FineMin
        RTS
FineMax:
        LDD #$03F8
        RTS
FineMin:
        LDD #$FC00
        RTS
"""

def staged_inputs(t,pos,rpm,mode):
    ax,v=t
    i,n,d=interval(ax,rpm)
    j,y=divmod(pos*(len(v)-1),256)
    ii=min(i+1,len(ax)-1)
    jj=min(j+1,len(v)-1)
    bias=128 if mode else 0
    cells=tuple(x+bias for x in (v[j][i],v[j][ii],v[jj][i],v[jj][ii]))
    require(all(0<=x<=255 for x in cells),"Factory cell bias contract")
    return cells,(n*2048//d)*32,y*256,bias

def joined_sample(pn,stock,p,entry,mode,t,positions):
    """Link machine map and stock correction tail through a synthetic caller.

    The machine fine sum is separate, with host-selected normal/fault paths.
    No full CalcSpark execution, correction generators, event ISR or ROM hook.
    """
    import re
    from tempfile import TemporaryDirectory
    from simulate_v11 import assemble,patch
    from byte_interp import ASM,TraceCPU,run,staged
    from publicationcheck import EXTRA,NAMES,find_tail,sx,clip
    eq={k:int(v,16) for k,v in re.findall(r"^(\w+)\s+equ\s+\$([0-9A-Fa-f]+)",
           (ROOT/"src"/pn/"00_equates.asm").read_text(),re.M)}
    trim,speed,other,high=EXTRA[pn]
    offsets=[(eq[n],-1 if n in ("AcClutchSparkTime","AcSparkWork") else 1)
             for n in NAMES]+[(speed,1),(other,1),(high,1)]
    if trim is not None:
        offsets.append((trim,1))
    tail,observed=find_tail(stock,pn,trim if trim is not None else eq["FlexSparkValue"],eq)
    require(sorted(offsets)==sorted(observed),"Correction tail signature")
    with TemporaryDirectory() as tmp:
        src=Path(tmp)/"joined_fixture.asm"
        src.write_text(ASM+"\n"+FINE_ASM)
        fine_cpu=TraceCPU(assemble([str(src)],0x20000),0x800)
    _,composed,_,_=patch(stock,pn)
    old_cpu,new_cpu=CPU(stock,0x800),CPU(composed,0x800)
    samples=cases=0
    branches={"normal":0,"override":0,"fault":0}
    # Deterministic grid plus the PT exception and its high-RPM alias.
    mps=sorted(set(range(0,256,31))|{0,31,32,127,128,254,255})
    rpms=sorted(set(range(0,256,31))|set(t[0])|{47,48,62,63,175,176,190,191,255})
    scenarios=[
        (0,0,0,0,0,0,0,0),
        (17,-9,0,0,0,0,0,0),
        (127,-128,0,0,0,0,0,0),
        (-128,127,0,0,0,0,0,0),
        (17,-9,2,0,0,0,0,0),
        (17,-9,0,0,0,0x40,0,0),
        (17,-9,0,1,0,0,0x20,0),
        (17,-9,0,0,1,0,0x20,0),
        (17,-9,0,0,0,0x80,0,100),
    ]
    for mp in mps:
        for rpm in rpms:
            raw,_=invoke(old_cpu,p,entry,mp,rpm,mode)
            raw1,_=invoke(new_cpu,p,entry,mp,rpm,mode)
            require(raw==raw1,"Stock/V1.1 base mismatch")
            base=sx(raw)
            cells,fx,fy,bias=staged_inputs(t,positions[mp],rpm,mode)
            fine_base,_,_=run(fine_cpu,cells,fx,fy)
            require(fine_base==staged(cells,fx,fy),"Joined staged CPU16 mismatch")
            fine_base-=bias*8
            residual=fine_base-base*8
            for plus,minus,opt,th,dash,fault,hold,trim_value in scenarios:
                state={a:0 for a,_ in offsets}
                state[eq["FlexSparkValue"]]=raw
                state[eq["CalcSparkD05"]]=plus&255
                state[eq["AcClutchSparkTime"]]=minus&255
                if trim is not None:
                    state[trim]=trim_value&255
                total=sum(sign*sx(state[a]) for a,sign in offsets)
                sat=clip(total,-128,127)
                forced=bool(hold) if th or dash else bool(fault&0xC0)
                override=-33
                for k,value in (("FuelPulseOptFlags",opt),("ThrottleState",th),
                                ("DashpotTimer",dash),("FaultSet02",fault),
                                ("SparkFaultFlags",hold),("CalcSparkC51",override)):
                    state[eq[k]]=value&255
                if opt&2:
                    expected=override
                    branch="override"
                elif forced:
                    expected=clip(24+(trim_value if trim is not None else 0),-128,127)
                    branch="fault"
                else:
                    expected=sat
                    branch="normal"
                new_cpu.reset_regs()
                new_cpu.mem[0xF8000:0xF8800]=bytes(0x800)
                for a,value in state.items():
                    new_cpu.ram_byte(a,value)
                sp=new_cpu.sp
                new_cpu.call(tail)
                require(new_cpu.sp==sp,"Joined tail stack balance")
                require(sx(new_cpu.ram_byte(eq["CalcSpark6D3"]))==sat and
                        sx(new_cpu.ram_byte(eq["SparkValueD0F"]))==expected,
                        "Joined legacy tail result")
                fine_cpu.reset_regs()
                fine_cpu.low_sp=fine_cpu.sp
                sp=fine_cpu.sp
                fine_cpu.d=(total if branch=="normal" else expected)&65535
                fine_cpu.e=(residual if branch=="normal" else 0)&65535
                fine_cpu.call(0x2000)
                fine=fine_cpu.d-65536 if fine_cpu.d&32768 else fine_cpu.d
                reference=(clip(fine_base+8*(total-base),-1024,1016)
                           if branch=="normal" else expected*8)
                require(fine==reference and fine_cpu.sp==sp,"Joined fine sum mismatch")
                require(all(0xF8700<=a<0xF8800 for a in fine_cpu.writes),
                        "Joined fine sum non-stack write")
                require(abs(fine-expected*8)<=abs(residual) if branch=="normal"
                        else fine==expected*8,"Joined correction residual")
                cases+=1
                branches[branch]+=1
            samples+=1
    print(f"{pn} {'WOT' if mode else 'PT'}: joined {samples} map samples, "
          f"{cases} CPU16 correction cases; branches {branches}; synthetic caller only",flush=True)

def check(pn):
    from byte_interp import staged
    p=CONFIG[pn]
    m=MANIFEST["variants"][pn]
    rom=(ROOT/"build"/(pn+".bin")).read_bytes()
    sha=json.loads((ROOT/"tools/variants.json").read_text())[pn]["sha256"]
    require(hashlib.sha256(rom).hexdigest()==sha,"Original SHA")
    entry=int(m["spark_entry"],0)
    cpu=CPU(rom,0x800)
    for mode in (0,1):
        t=table(rom,int(m["spark_tables"][mode],0))
        key="wt_scale" if mode else "pt_scale"
        positions=[lookup_position(rom,p,p[key],mp) for mp in range(256)]
        maxima={k:0.0 for k in ("stock",8,11,16)}
        sums=dict.fromkeys(maxima,0.0)
        residual=0; outside=0; above=0; below=0
        stage_max=0.0; stage_residual=0; stage_outside=0; stage_worst=None
        worst=None
        for mp,pos in enumerate(positions):
            for rpm in range(256):
                raw,_=invoke(cpu,p,entry,mp,rpm,mode)
                old=(raw-256 if raw>=128 else raw)*8
                exact,outputs=evaluate(t,pos,rpm)
                for k,q in [("stock",old),*outputs.items()]:
                    e=abs(q-exact)/16
                    maxima[k]=max(maxima[k],e);sums[k]+=e
                cells,fx,fy,bias=staged_inputs(t,pos,rpm,mode)
                stage=staged(cells,fx,fy)-bias*8
                stage_max=max(stage_max,abs(stage-exact)/16)
                if abs(stage-old)>stage_residual:
                    stage_residual=abs(stage-old)
                    stage_worst=(mp,rpm,old,stage)
                stage_outside+=not(-8<=stage-old<=8)
                # Conservative integration study, no firmware policy change.
                delta=outputs[11]-old
                if abs(delta)>residual: residual=abs(delta);worst=(mp,rpm,old,outputs[11])
                outside+=not(-4<=delta<=3)
                above+=delta>0;below+=delta<0
        # Quantized interpolation must stay within the original map cell range.
        require(maxima[11]<=0.05 and stage_max<=0.05,"Unexpected interpolation precision loss")
        print(f"{pn} {'WOT' if mode else 'PT'}: 65536 cases; max error deg {maxima}; mean error deg { {k:v/65536 for k,v in sums.items()} }")
        print(f"  Q11-vs-stock residual max {residual}/16 degree; outside [-4,+3] {outside}; positive {above}; negative {below}; worst {worst}")
        print(f"  Staged residual max {stage_residual}/16 degree; outside [-8,+8] {stage_outside}; max error {stage_max:.8f} deg; worst {stage_worst}",flush=True)
        joined_sample(pn,rom,p,entry,mode,t,positions)
    print(f"{pn}: 131072 stock machine + host interpolation cases passed; no production patch",flush=True)

if __name__=="__main__":
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pn",choices=CONFIG)
    check(ap.parse_args().pn)
