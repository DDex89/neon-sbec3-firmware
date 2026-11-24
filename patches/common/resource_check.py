#!/usr/bin/env python3
"""Validate module reservations and composed ROM byte ranges; no ROM export."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
MANIFEST=json.loads((ROOT/"profiles/modules.json").read_text())

def require(ok,msg):
    if not ok:
        raise ValueError(msg)

def ranges(spec):
    return [(int(a,0),int(b,0)) for a,b in spec]

def resources(profile):
    chosen=MANIFEST["profiles"][profile]
    mods=MANIFEST["modules"]
    require(len(set(chosen))==len(chosen),"Duplicate module")
    result=[]
    for name in chosen:
        m=mods[name]
        require(set(m["depends"])<=set(chosen),"Missing dependency: "+name)
        require(not set(m["conflicts"])&set(chosen),"Conflicting module: "+name)
        for space,limit in (("flash",0x20000),("persistent_ram",0x800)):
            for lo,hi in ranges(m[space]):
                require(0<=lo<hi<=limit,"Invalid range")
                for owner,s,a,b in result:
                    require(s!=space or hi<=a or b<=lo,f"Resource overlap {owner}/{name}")
                result.append((name,space,lo,hi))
    return result

def verify_delta(before,after,profile,hooks,checksum):
    require(len(before)==len(after)==0x20000,"ROM length")
    allowed=[(a,b) for _,s,a,b in resources(profile) if s=="flash"]
    for lo,hi in allowed:
        require(all(x==255 for x in before[lo:hi]),f"Reservation not erased: {lo:05X}")
    for lo,hi in hooks:
        require(0<=lo<hi<=len(before),"Invalid hook")
        require(all(hi<=a or b<=lo for a,b in allowed),"Hook overlaps reservation")
        allowed.append((lo,hi))
    require(0<=checksum<len(before) and all(not a<=checksum<b for a,b in allowed),"Checksum overlaps reservation")
    allowed.append((checksum,checksum+1))
    require(all(x==y or any(a<=i<b for a,b in allowed) for i,(x,y) in enumerate(zip(before,after))),"Unexpected ROM byte changed")
    return sum(x!=y for x,y in zip(before,after))

if __name__=="__main__":
    for p in MANIFEST["profiles"]:
        print(p,resources(p))
