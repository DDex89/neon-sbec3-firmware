#!/usr/bin/env python3
"""Measure boundary continuity of experimental and stock fuel calculations.

Reports sampled (not hardware) changes across each MAP transition. The
reported excess jump is (patched_high - patched_low) minus the stock jump.
No arbitrary acceptance limit is imposed. Does not produce a flash image.
"""
import hashlib
import json
from dinofuel128 import ROOT, CONFIG, require, create_patch, run_cfp, scale_points


def check(pn):
    stock = (ROOT / "build" / (pn + ".bin")).read_bytes()
    variants = json.loads((ROOT / "tools" / "variants.json").read_text())
    require(hashlib.sha256(stock).hexdigest() == variants[pn]["sha256"], "Wrong stock ROM")
    p = CONFIG[pn]
    patched, _, _ = create_patch(stock, p)
    total = 0
    for mode in (0, 1):
        prefix = "wt" if mode else "pt"
        points = scale_points(stock, p[prefix + "_scale"])
        lo, hi = points[0][0], points[-1][0]
        offset = stock[p[prefix + "_offset"]]
        boundaries = sorted({(x-1,x) for x in (offset,lo,points[1][0]) if x>0}
                            | {(x,x+1) for x in (lo,points[1][0],hi) if x<255})
        for hold in ((0,) if mode else (0,1)):
            old, new = bytearray(stock), bytearray(patched)
            for rom in (old,new):
                rom[0x0323] = (rom[0x0323]&0xFE)|hold
            for a,b in boundaries:
                worst = (-1,None)
                max_jump = 0
                max_stock_jump = 0
                for rpm in range(256):
                    for flags,wte in (((0,0),) if not mode else ((0x20,0),(0x21,40),(0x21,255))):
                        ov = [run_cfp(old,p,x,rpm,flags,wte,0)[1][0] for x in (a,b)]
                        nv = [run_cfp(new,p,x,rpm,flags,wte,0)[1][0] for x in (a,b)]
                        oj,nj = ov[1]-ov[0],nv[1]-nv[0]
                        excess = nj-oj
                        max_jump=max(max_jump,abs(nj))
                        max_stock_jump=max(max_stock_jump,abs(oj))
                        if abs(excess)>worst[0]:
                            worst=(abs(excess),(rpm,flags,wte,ov,nv,excess))
                        total+=1
                print(f"{pn} {prefix.upper()} hold={hold} MAP {a}->{b}: stock max jump {max_stock_jump}; patched max jump {max_jump}; max excess {worst[0]} counts; case {worst[1]}")
    print(f"{pn}: {total} adjacent-MAP comparisons completed; review excess jumps before hardware qualification.")


if __name__=="__main__":
    for pn in CONFIG:
        check(pn)
