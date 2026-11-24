#!/usr/bin/env python3
"""Validate Q11 XDF, LUT and calibration-only edits. No hardware flashing."""
import argparse
import hashlib
import json
import xml.etree.ElementTree as ET
from fractions import Fraction
from pathlib import Path

from simulate import ROOT, CONFIG, SIZE, PT_BASE, WT_BASE, LUT, make_v2, Runner, expected, lookup_position, scale_points, require
from dinofuel128 import inverse_scale

HERE=Path(__file__).resolve().parent

def original(pn):
    stock=(ROOT/"build"/(pn+".bin")).read_bytes()
    v=json.loads((ROOT/"tools"/"variants.json").read_text())[pn]
    require(len(stock)==SIZE and hashlib.sha256(stock).hexdigest()==v["sha256"],"Wrong original ROM")
    return stock

def repair_sum(rom):
    b=bytearray(rom)
    hdr=int.from_bytes(b[0x202:0x204],"big")
    require(0<=hdr<=SIZE-14,"Invalid header")
    b[hdr+13]=(b[hdr+13]+b[hdr+3]-sum(b))&255
    require(sum(b)&255==b[hdr+3],"Checksum")
    return bytes(b)

def validate(pn,stock,rom,template,tables,check_sum=True):
    require(len(rom)==SIZE,"Image size")
    p=CONFIG[pn]
    root=ET.parse(HERE/"xdf"/(pn+"-dinofuel-v2-q11.xdf")).getroot()
    require(root.tag=="XDFFORMAT" and "V2 Q11" in root.findtext("XDFHEADER/deftitle") and pn in root.findtext("XDFHEADER/deftitle"),"Wrong XDF version")
    require(root.find("XDFHEADER/DEFAULTS").get("lsbfirst")=="0","Endian")
    require(int(root.find("XDFHEADER/REGION").get("size"),0)==SIZE,"Region")
    ts=root.findall("XDFTABLE")
    require(len(ts)==2 and len({t.get("uniqueid") for t in ts})==2,"Table IDs")
    require(not root.findall("XDFCONSTANT") and not root.findall("XDFFLAG"),"Unexpected XDF elements")
    used=set()
    decoded=[]
    axes=[]
    for mode,(t,b,table) in enumerate(zip(ts,(PT_BASE,WT_BASE),tables)):
        axis,v=table
        rows,cols=len(v),len(axis)
        require(t.findtext("title")==("DinoFuel V2 WOT" if mode else "DinoFuel V2 Part Throttle"),"Table identity")
        a={x.get("id"):x for x in t.findall("XDFAXIS")}
        require(set(a)=={"x","y","z"},"Axes")
        for k,count in (("x",cols),("y",rows)):
            require(a[k].find("EMBEDDEDDATA") is None and int(a[k].findtext("indexcount"))==count,"Axis must be fixed")
            require([int(x.get("index")) for x in a[k].findall("LABEL")]==list(range(count)),"Axis indices")
        require([int(x.get("value")) for x in a["x"].findall("LABEL")]==[x*32 for x in axis],"RPM labels")
        points=scale_points(stock,p["wt_scale" if mode else "pt_scale"])
        labels=[f"{float(inverse_scale(points,min(Fraction(255),Fraction(256*j,rows-1))))/2.428:.1f}" for j in range(rows)]
        require([x.get("value") for x in a["y"].findall("LABEL")]==labels,"MAP labels")
        require(rom[b:b+3]==bytes((rows,cols,0)),"Table header")
        actual=[int.from_bytes(rom[b+3+2*i:b+5+2*i],"big") for i in range(cols)]
        require(actual==axis and all(x<y for x,y in zip(actual,actual[1:])),"RPM axis changed")
        axes.append(actual)
        z=a["z"]
        e=z.find("EMBEDDEDDATA")
        g=lambda key:int(e.get(key),0)
        addr=g("mmedaddress")
        require(addr==b+3+2*cols and addr%2==0,"Cell address")
        require(g("mmedtypeflags")==0 and g("mmedelementsizebits")==16,"Word format")
        require(g("mmedrowcount")==rows and g("mmedcolcount")==cols,"Shape")
        require(g("mmedmajorstridebits")==cols*16 and g("mmedminorstridebits")==16,"Strides")
        require(z.find("MATH").get("equation")=="X/16384","Q2.14 scaling")
        values=[]
        for j in range(rows):
            row=[]
            for i in range(cols):
                x=addr+2*(j*cols+i)
                require(x not in used and x+1 not in used and x+2<=LUT,"Cell overlap")
                used.update((x,x+1))
                row.append(int.from_bytes(rom[x:x+2],"big"))
            values.append(row)
        decoded.append((axis,values))
    require(len(used)==884,"Cell bytes")
    require(axes[0]==axes[1],"Axes differ")
    # Independently calculate all packed words, including exact endpoints.
    ax=axes[0]
    for rpm in range(256):
        col=max([i for i,x in enumerate(ax) if x<=rpm],default=0)
        frac=0 if rpm<=ax[0] or col==len(ax)-1 else (2048*(rpm-ax[col]))//(ax[col+1]-ax[col])
        word=int.from_bytes(rom[LUT+2*rpm:LUT+2*rpm+2],"big")
        require(word==(col<<11)|frac,f"RPM LUT mismatch at {rpm}")
    hdr=int.from_bytes(template[0x202:0x204],"big")
    permitted=used|{hdr+13}
    require(all(a==b or i in permitted for i,(a,b) in enumerate(zip(template,rom))),"Non-calibration byte changed (wrong version/code/axes/LUT)")
    if check_sum:
        require(sum(rom)&255==rom[hdr+3],"Checksum mismatch")
    return decoded

def selftest(pn):
    stock=original(pn)
    p=CONFIG[pn]
    rom,tables=make_v2(stock,p,True)
    decoded=validate(pn,stock,rom,rom,tables)
    require(tuple(decoded)==tables,"Initial calibration differs")
    positions=[[lookup_position(stock,p,p[k],m) for m in range(256)] for k in ("pt_scale","wt_scale")]
    hold=bool(stock[0x323]&1)
    for mode,b in enumerate((PT_BASE,WT_BASE)):
        a=b+37
        old=int.from_bytes(rom[a:a+2],"big")
        edited=bytearray(rom)
        edited[a:a+2]=(old+1024).to_bytes(2,"big")
        edited=repair_sum(edited)
        tab=validate(pn,stock,edited,rom,tables)
        mp=scale_points(stock,p["wt_scale" if mode else "pt_scale"])[0][0]
        rpm=tables[mode][0][0]
        flags=32 if mode else 0
        ref=expected(stock,p,tab,positions,mp,rpm,flags,0,0,True,hold)
        before=Runner(rom,p).run(mp,rpm,flags)
        after=Runner(edited,p).run(mp,rpm,flags)
        require(after[:2]==ref and after[0]>before[0],"Q2.14 edit not consumed")
        print(f"{pn}: mode={mode} multiplier +0.0625, pulse {before[0]} -> {after[0]}")
    for a in (LUT,LUT+511,PT_BASE+3,WT_BASE+3,CONFIG[pn]["hook"]):
        bad=bytearray(rom)
        bad[a]^=1
        try:
            validate(pn,stock,repair_sum(bad),rom,tables)
        except ValueError:
            pass
        else:
            raise ValueError(f"Corruption not rejected at {a:05X}")
    print(f"{pn}: 442 XDF cells, 256 RPM LUT entries, 2 simulated edits and 5 corruption tests passed")

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pn",choices=CONFIG)
    ap.add_argument("--image",type=Path,help="Verify an edited V2 Q11 image; never write or flash it")
    a=ap.parse_args()
    if not a.image:
        selftest(a.pn)
        return
    stock=original(a.pn)
    rom,tables=make_v2(stock,CONFIG[a.pn],True)
    validate(a.pn,stock,a.image.read_bytes(),rom,tables)
    print("Calibration-only structural validation passed. Not a safety/engine validation.")

if __name__=="__main__":
    main()
