#!/usr/bin/env python3
"""Conservative resource survey for the existing 128 KB composition.

Candidates only, NOT a RAM allocator or proof of interrupt safety. Uses the
repository's existing decoded-code/table inventory, then subtracts module
reservations. Never edits an image or profile.
"""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/"patches/spark"))
from simulate_v11 import CONFIG,patch,require
from resource_check import resources
from revision import inventory

def parse_run(s):
    m=re.fullmatch(r"\$([0-9A-Fa-f]+) \((\d+)\)",s)
    require(m is not None,"Unexpected inventory format: "+s)
    lo=int(m[1],16)
    return lo,lo+int(m[2])

def subtract(lo,hi,blocked):
    ranges=[(lo,hi)]
    for a,b in blocked:
        ranges=[part for x,y in ranges for part in
                ([(x,y)] if b<=x or y<=a else
                 [(x,min(a,y)),(max(b,x),y)]) if part[0]<part[1]]
    return ranges

def fmt(r):
    return f"${r[0]:05X}..${r[1]-1:05X} ({r[1]-r[0]} B)"

def check(pn):
    file=ROOT/"build"/(pn+".bin")
    stock=file.read_bytes()
    sha=json.loads((ROOT/"tools/variants.json").read_text())[pn]["sha256"]
    require(hashlib.sha256(stock).hexdigest()==sha,"Original SHA")
    _,composed,_,_=patch(stock,pn)
    inv=inventory(str(file))
    blocked=[(a,b) for _,space,a,b in resources("fuel_q11_spark") if space=="flash"]
    print(pn,"reserved flash:",sum(b-a for a,b in blocked),"bytes",flush=True)
    candidates=[]
    for bank in inv["flash"]:
        for raw in bank["largest"]:
            lo,hi=parse_run(raw)
            for a,b in subtract(lo,hi,blocked):
                if b-a<16: continue
                require(all(x==255 for x in stock[a:b]),"Stock candidate not erased")
                require(all(x==255 for x in composed[a:b]),"Composed candidate not erased")
                candidates.append((a,b))
    candidates.sort(key=lambda r:r[1]-r[0],reverse=True)
    print("Remaining flash candidates (from top four inventoried runs per bank):",
          [fmt(r) for r in candidates],flush=True)
    ram=inv["ram"]
    print("Heuristic RAM inventory:",ram,flush=True)
    # Reject annotated offsets as possible candidate storage even when inventory
    # has not observed direct access. Width of a symbol is not fully known.
    eq={int(v,16):k for k,v in re.findall(r"^(\w+)\s+equ\s+\$([0-9A-Fa-f]+)",(ROOT/"src"/pn/"00_equates.asm").read_text(),re.M) if int(v,16)<0x800}
    rams=[]
    for raw in ram["largest"]:
        lo,hi=parse_run(raw)
        excluded=[(a,min(a+2,0x800)) for a in eq if a<hi and a+2>lo]
        for a,b in subtract(lo,hi,excluded):
            if b-a<8: continue
            a=(a+1)&~1
            if b-a>=8:rams.append((a,b))
    rams.sort(key=lambda r:r[1]-r[0],reverse=True)
    print("RAM candidates after annotated-offset exclusions (NOT allocated):",
          [fmt(r) for r in rams],flush=True)
    print("Gate: computed pointers, reset initialization, diagnostic access, ISR nesting and actual stack high-water remain unverified.",flush=True)

if __name__=="__main__":
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pn",choices=CONFIG)
    check(ap.parse_args().pn)
