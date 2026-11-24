#!/usr/bin/env python3
"""Spark V1: exact stock 8-bit result, faster RPM lookup where axes match.

Requires the DinoFuel V2 Q11 profile. Uses its existing RPM LUT but leaves
the stock 8-bit interpolation kernel, angle scaling, correction and event
scheduling untouched. PT uses a compact exception table for the mismatched axis span.
Simulation-only: no binary is written.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"patches/common"))
sys.path.insert(0,str(ROOT/"patches/dinofuel"))
sys.path.insert(0,str(ROOT/"patches/dinofuel/v2"))
from resource_check import MANIFEST,verify_delta
from simulate import CONFIG,make_v2,CPU,decode,assemble,put_erased,require,LUT,lookup_position
import timing

CODE=0x0FD40
LIMIT=0x0FE00
EXCEPT=0x0FDE0

ASM="""
SparkLookup:
        PSHM    E,Y,K
        PSHB
        CLRB
        TBXK
        PULB
        PSHA
        CLRA
        ASLD
        TDE
        LDY     #RPMIndex
        BRSET   >FuelModeFlags,Z,#$20,ReadIndex
        CMPB    #$60
        BCS     ReadIndex
        CMPB    #$7E
        BCC     ReadIndex
        LDY     #PTExceptionBase
ReadIndex:
        LDD     E,Y
        TDE
        TAB
        LSRB
        LSRB
        LSRB
        TXY
        AIY     #$03
        ABY
        TED
        ASLD
        ASLD
        ASLD
        ASLD
        ASLD
        JMP     StockSuffix
"""

def table(rom,a):
    rows,cols,flag=rom[a:a+3]
    require(cols==17 and rows in (9,17) and flag in (0,255),"Table signature")
    axis=list(rom[a+3:a+3+cols])
    vals=[]
    for j in range(rows):
        row=list(rom[a+3+cols+j*cols:a+3+cols+(j+1)*cols])
        vals.append([x-256 if flag and x>=128 else x for x in row])
    return axis,vals

def index(axis,rpm):
    i=max((i for i,x in enumerate(axis) if x<=rpm),default=0)
    f=0 if rpm<=axis[0] or i==len(axis)-1 else ((rpm-axis[i])*256)//(axis[i+1]-axis[i])
    return i,f

def model(t,pos,rpm):
    ax,v=t
    i,f=index(ax,rpm)
    j,y=divmod(pos*(len(v)-1),256)
    ii=min(i+1,len(ax)-1)
    jj=min(j+1,len(v)-1)
    a=v[j][i]+(v[j][ii]-v[j][i])*f/256
    b=v[jj][i]+(v[jj][ii]-v[jj][i])*f/256
    return a+(b-a)*y/256

def patch(stock,pn):
    p=CONFIG[pn]
    m=MANIFEST["variants"][pn]
    entry,suffix=int(m["spark_entry"],0),int(m["spark_tail"],0)
    ts=[table(stock,int(a,0)) for a in m["spark_tables"]]
    fuel,_=make_v2(stock,p,True)
    # Validate the shared LUT against both spark axes for every nonfallback RPM.
    for mode,(axis,_) in enumerate(ts):
        for rpm in range(256):
            if not mode and 48<=rpm<63:
                col,frac=index(axis,rpm)
                word=(col<<11)|(frac<<3)
            else:
                word=int.from_bytes(fuel[LUT+2*rpm:LUT+2*rpm+2],"big")
            require((word>>11,(word&2047)>>3)==index(axis,rpm),"Shared RPM index differs")
    # Verify the exact stock entry and continuation signatures.
    require(decode(stock,entry).mn=="BRSET","Spark entry")
    require(decode(stock,suffix).mn=="LDAB","Lookup continuation")
    calls=[]
    a=entry
    while True:
        i=decode(stock,a)
        require(i is not None and a<entry+80,"Unexpected spark routine")
        if i.mn=="JSR" and i.target()==p["lookup3d"]:
            require(i.size==4,"Unexpected call size")
            calls.append(a)
        if i.mn=="RTS":
            break
        a+=i.size
    require(len(calls)==2,"Expected exactly two spark lookup calls")
    syms=dict(FuelModeFlags=p["flags"],RPMIndex=LUT,StockLookup=p["lookup3d"],StockSuffix=suffix,PTExceptionBase=EXCEPT-96)
    source="\n".join(f"{k} equ ${v:04X}" for k,v in syms.items())+f"\norg ${CODE:05X}\n"+ASM
    for a in calls:
        source+=f"\norg ${a:05X}\n JSR SparkLookup\n"
    with TemporaryDirectory() as tmp:
        file=Path(tmp)/"spark.asm"
        file.write_text(source)
        assembled=assemble([str(file)],0x20000)
    code=assembled[CODE:LIMIT].rstrip(b"\xff")
    require(code and CODE+len(code)<=EXCEPT,"Spark code size")
    dst=bytearray(fuel)
    put_erased(dst,CODE,code,EXCEPT)
    exceptions=b"".join(((col<<11)|(frac<<3)).to_bytes(2,"big") for col,frac in (index(ts[0][0],rpm) for rpm in range(48,63)))
    put_erased(dst,EXCEPT,exceptions,LIMIT)
    for a in calls:
        i=decode(assembled,a)
        require(i.mn=="JSR" and i.target()==CODE,"Wrong assembled call")
        dst[a:a+4]=assembled[a:a+4]
    hdr=int.from_bytes(dst[0x202:0x204],"big")
    dst[hdr+13]=(dst[hdr+13]+dst[hdr+3]-sum(dst))&255
    require(sum(dst)&255==dst[hdr+3],"Checksum")
    changed=verify_delta(stock,dst,"fuel_q11_spark",[(p["hook"],p["hook"]+4)]+[(a,a+4) for a in calls],hdr+13)
    print(f"{pn}: Spark V1.1 code {len(code)} bytes + {len(exceptions)} exception bytes at {CODE:05X}, hooks {[hex(a) for a in calls]}, composed changed bytes {changed}",flush=True)
    return fuel,bytes(dst),entry,ts

def invoke(c,p,entry,mp,rpm,mode):
    c.reset_regs()
    c.mem[0xF8000:0xF8800]=bytes(0x800)
    c.e=0x1234
    c.iy=0x2468
    c.yk=0
    c.ram_byte(p["map"],mp)
    c.ram_byte(p["rpm"],rpm)
    c.ram_byte(p["flags"],32 if mode else 0)
    sp=c.sp
    c.call(entry)
    require(c.sp==sp and c.sk==15,"Stack balance")
    require(c.e==0x1234 and c.iy==0x2468 and c.yk==0,"Register contract")
    require(all(0xF8000<=a<0xF8800 for a in c.writes),"Unexpected write")
    return c.a,tuple(sorted((a,c.mem[a]) for a in c.writes if a<0xF8700))

def check(pn,full):
    p=CONFIG[pn]
    stock=(ROOT/"build"/(pn+".bin")).read_bytes()
    sha=json.loads((ROOT/"tools/variants.json").read_text())[pn]["sha256"]
    require(hashlib.sha256(stock).hexdigest()==sha,"Original SHA")
    fuel,new,entry,ts=patch(stock,pn)
    cpus=[CPU(rom,0x800) for rom in (stock,fuel,new)]
    positions=[[lookup_position(stock,p,p[k],mp) for mp in range(256)] for k in ("pt_scale","wt_scale")]
    mps=list(range(256)) if full else sorted(set(range(0,256,13))|{0,31,32,33,111,112,113,127,128,129,239,240,241,254,255})
    rpms=list(range(256)) if full else sorted(set(range(0,256,11))|set(range(45,65))|set(ts[0][0])|{255})
    n=0
    for mode in (0,1):
        worst=0
        lo,hi=255,-255
        for mp in mps:
            for rpm in rpms:
                a,b,c=[invoke(cpu,p,entry,mp,rpm,mode) for cpu in cpus]
                require(a==b==c,f"Spark regression {pn} {mode} {mp} {rpm}: {a} {b} {c}")
                value=a[0]-256 if a[0]>=128 else a[0]
                ref=model(ts[mode],positions[mode][mp],rpm)
                worst=max(worst,abs(value-ref))
                lo=min(lo,value);hi=max(hi,value)
                require(abs(value-ref)<=1.00001,"Stock model difference exceeds one raw count")
                n+=1
        print(f"{pn} {'WOT' if mode else 'PT'}: exact stock matches, reference max {worst:.4f} counts; output range {lo/2:.1f}..{hi/2:.1f} degrees",flush=True)
    print(f"{pn}: {n} exact comparisons across stock, fuel-only, composed",flush=True)
    if not full:
        timing.REG2.update(("ASLD","LSRB"))
        timing.ALU.add("LDY")
        maxima=[0,0];stacks=[0,0];steps=[0,0];deltas=[]
        for mp in (0,32,80,112,128,200,240,255):
            for rpm in sorted(set(range(0,256,7))|set(range(45,65))|{224,225,255}):
                for mode in (0,1):
                    vals=[]
                    for i,rom in enumerate((stock,new)):
                        c=timing.ProfileCPU(rom)
                        # ProfileCPU must not be reset after capturing initial SP.
                        c.ram_byte(p["map"],mp);c.ram_byte(p["rpm"],rpm);c.ram_byte(p["flags"],32 if mode else 0)
                        c.call(entry)
                        require(c.sp==c.initial_sp,"Profile stack")
                        v=c.clocks(4);vals.append(v)
                        maxima[i]=max(maxima[i],v);stacks[i]=max(stacks[i],c.initial_sp-c.low_sp);steps[i]=max(steps[i],c.steps)
                    deltas.append(vals[1]-vals[0])
        print(f"PROFILE {pn}: stock/composed peak clocks {maxima}; stack {stacks}; instructions {steps}; paired delta min/max {min(deltas)}/{max(deltas)}",flush=True)

if __name__=="__main__":
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pn",choices=CONFIG)
    ap.add_argument("--full",action="store_true")
    a=ap.parse_args()
    check(a.pn,a.full)
