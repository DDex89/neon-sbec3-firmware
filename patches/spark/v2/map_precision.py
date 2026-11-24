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

def check(pn):
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
        worst=None
        for mp,pos in enumerate(positions):
            for rpm in range(256):
                raw,_=invoke(cpu,p,entry,mp,rpm,mode)
                old=(raw-256 if raw>=128 else raw)*8
                exact,outputs=evaluate(t,pos,rpm)
                for k,q in [("stock",old),*outputs.items()]:
                    e=abs(q-exact)/16
                    maxima[k]=max(maxima[k],e);sums[k]+=e
                # Conservative integration study, no firmware policy change.
                delta=outputs[11]-old
                if abs(delta)>residual: residual=abs(delta);worst=(mp,rpm,old,outputs[11])
                outside+=not(-4<=delta<=3)
                above+=delta>0;below+=delta<0
        # Quantized interpolation must stay within the original map cell range.
        require(maxima[11]<=0.05,"Unexpected interpolation precision loss")
        print(f"{pn} {'WOT' if mode else 'PT'}: 65536 cases; max error deg {maxima}; mean error deg { {k:v/65536 for k,v in sums.items()} }")
        print(f"  Q11-vs-stock residual max {residual}/16 degree; outside [-4,+3] {outside}; positive {above}; negative {below}; worst {worst}")
    print(f"{pn}: 131072 stock machine + host interpolation cases passed; no production patch",flush=True)

if __name__=="__main__":
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pn",choices=CONFIG)
    check(ap.parse_args().pn)
