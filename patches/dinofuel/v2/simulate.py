#!/usr/bin/env python3
"""Simulation-only DinoFuel V2: Q2.14 correction tables, optional packed RPM LUT.

The V1 absolute-table patch is unchanged. No ROM is written by this program.
The Q2.14 table contains (256 + stock signed correction) * 64.
Use the original MAP scale and linear base; no MAP-boundary fallback.
Two machine-code implementations: original corrected word lookup (Q16 RPM
fraction), and packed 512-byte RPM index/fraction LUT (Q11 RPM fraction).
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dinofuel128 import (ROOT, SIZE, CODE, CODE_LIMIT, PT_BASE, WT_BASE,
    DATA_LIMIT, CONFIG, LOOKUP_ASM, assemble, decode, put_erased, require,
    lookup_position, scale_points, CPU, create_patch as create_v1)
import timing

# Reserve a common erased 512-byte area at the top of bank 0.
LUT = 0x0FE00

HOOK = """
DF2_Hook:
        BRSET   >FuelModeFlags,Z,#$20,DF2_Wot
        LDX     #PTTABLE
        BRA     DF2_New
DF2_Wot:
        LDX     #WOTTABLE
DF2_New:
        JSR     Table_3D_word
        EMUL
        ASLD
        ROLE
        ASLD
        ROLE
        ASLD
        ADCE    #$0000
        STE     >LookupResult,Z
        BRCLR   >AccelFuelOptions,#$80,DF2_Done
        LDAB    >Temp4F0,Z
        STAB    >TipIn802,Z
DF2_Done:
        JMP     StockTail
"""

# A single table is valid for both fuel modes only when RPM axes match.
# Each entry packs column index in bits 15:11 and a fractional position
# in bits 10:0. Convert to column byte offset and Q0.16 for the existing
# interpolation kernel. This removes the linear scan and FDIV.
FAST_PREFIX = """
Table_3D_word:
        PSHM    E,Y,K
        PSHM    D
        CLRA
        ASLD
        TDE
        CLRB
        TBXK
        TXY
        LDY     #RPMIndex
        LDD     E,Y
        TDE
        TAB
        ANDB    #$F8
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
"""


def factor_table(stock,p,mode):
    a=p["wt_table" if mode else "pt_table"]
    rows,cols,flag=stock[a:a+3]
    require((rows,cols,flag)==(9 if mode else 17,17,255),"Stock table shape")
    axis=list(stock[a+3:a+3+cols])
    require(all(x<y for x,y in zip(axis,axis[1:])),"RPM axis order")
    v=[]
    for j in range(rows):
        row=[]
        for i in range(cols):
            f=stock[a+3+cols+j*cols+i]
            if f>=128:
                f-=256
            row.append((256+f)*64)
        v.append(row)
    data=bytes((rows,cols,0))+b"".join(x.to_bytes(2,"big") for x in axis)
    data+=b"".join(x.to_bytes(2,"big") for row in v for x in row)
    return data,(axis,v)


def index_fraction(axis,rpm,bits):
    i=0
    while i<len(axis)-1 and rpm>=axis[i+1]:
        i+=1
    f=0 if rpm<=axis[0] or i==len(axis)-1 else ((rpm-axis[i])<<bits)//(axis[i+1]-axis[i])
    return i,f


def make_v2(stock,p,fast):
    pt,ptv=factor_table(stock,p,0)
    wt,wtv=factor_table(stock,p,1)
    require(ptv[0]==wtv[0],"Different RPM axes: one LUT cannot serve both")
    h=decode(stock,p["hook"])
    require(h and h.mn=="JSR" and h.target()==p["lookup3d"] and h.size==4,"Stock hook signature")
    require(decode(stock,p["tail"]).mn=="TED","Stock tail signature")
    sym=dict(FuelModeFlags=p["flags"],PTTABLE=PT_BASE,WOTTABLE=WT_BASE,
             LookupResult=p["scratch"],AccelFuelOptions=p["accel"],
             Temp4F0=0x00F0,TipIn802=p["tip"],StockTail=p["tail"],RPMIndex=LUT)
    source="\n".join(f"{k} equ ${v:04X}" for k,v in sym.items())
    lookup=(FAST_PREFIX+LOOKUP_ASM[LOOKUP_ASM.index("loc_E698:"):]) if fast else LOOKUP_ASM
    source+=f"\norg ${CODE:05X}\n"+HOOK+lookup
    source+=f"\norg ${p['hook']:05X}\n        JMP DF2_Hook\n"
    with TemporaryDirectory() as tmp:
        f=Path(tmp)/"v2.asm"
        f.write_text(source)
        asm=assemble([str(f)],SIZE)
    hook=decode(asm,p["hook"])
    require(hook.mn=="JMP" and hook.target()==CODE and hook.size==4,"Assembled hook")
    code=asm[CODE:CODE_LIMIT].rstrip(b"\xff")
    require(CODE+len(code)<=LUT if fast else CODE+len(code)<=CODE_LIMIT,"Code does not fit")
    dst=bytearray(stock)
    put_erased(dst,PT_BASE,pt,WT_BASE)
    put_erased(dst,WT_BASE,wt,DATA_LIMIT)
    put_erased(dst,CODE,code,LUT if fast else CODE_LIMIT)
    if fast:
        packed=[]
        for rpm in range(256):
            col,frac=index_fraction(ptv[0],rpm,11)
            packed.append((col<<11)|frac)
        raw=b"".join(x.to_bytes(2,"big") for x in packed)
        require(len(raw)==512,"LUT length")
        put_erased(dst,LUT,raw,CODE_LIMIT)
    dst[p["hook"]:p["hook"]+4]=asm[p["hook"]:p["hook"]+4]
    hdr=int.from_bytes(dst[0x202:0x204],"big")
    require(0<=hdr<=SIZE-14,"Checksum header")
    dst[hdr+13]=(dst[hdr+13]+dst[hdr+3]-sum(dst))&255
    require(sum(dst)&255==dst[hdr+3],"Checksum")
    allowed=[(PT_BASE,PT_BASE+len(pt)),(WT_BASE,WT_BASE+len(wt)),(CODE,CODE+len(code)),
             (p["hook"],p["hook"]+4),(hdr+13,hdr+14)]
    if fast:
        allowed.append((LUT,LUT+512))
    require(all(a==b or any(lo<=i<hi for lo,hi in allowed)
                for i,(a,b) in enumerate(zip(stock,dst))),"Unexpected ROM change")
    print(f"V2 {'packed LUT' if fast else 'Q16 search'}: {len(code)} code bytes, {len(pt)+len(wt)} table bytes, {512 if fast else 0} LUT bytes",flush=True)
    return bytes(dst),(ptv,wtv)


def interp(a,b,f):
    delta=b-a
    return a+(1 if delta>=0 else -1)*((abs(delta)*f+32768)>>16)


def expected(stock,p,tables,positions,mp,rpm,flags,wte,baro,fast,hold):
    mode=int(bool(flags&32))
    effective=max(mp,stock[p["hold"]]) if hold and not mode else mp
    prefix="wt" if mode else "pt"
    offset,k=stock[p[prefix+"_offset"]],stock[p[prefix+"_k"]]
    if effective<offset:
        return 0,0xA55A
    axis,v=tables[mode]
    i,f=index_fraction(axis,rpm,11 if fast else 16)
    if fast:
        f <<= 5
    j,y=divmod(positions[mode][effective]*(len(v)-1),256)
    ii=min(i+1,len(axis)-1)
    jj=min(j+1,len(v)-1)
    word=interp(interp(v[j][i],v[j][ii],f),interp(v[jj][i],v[jj][ii],f),y<<8)
    base=(effective-offset)*(256+k)//16
    pulse=(base*word+8192)//16384
    calc=pulse//2
    if mode and flags&1:
        pulse=min(65535,pulse+(pulse*wte)//256)
    return min(65535,pulse+baro),calc


class Runner:
    """Reuse CPU allocation; reset all RAM and registers before each call."""
    def __init__(self,rom,p):
        self.c=CPU(rom,0x800)
        self.p=p
    def run(self,mp,rpm,flags,wte=0,baro=0):
        c,p=self.c,self.p
        c.mem[0xF8000:0xF8800]=bytes(0x800)
        c.reset_regs()
        for n,v in (("map",mp),("rpm",rpm),("flags",flags),("wte",wte),("tip",0xA5)):
            c.ram_byte(p[n],v)
        c.ram_word(p["baro"],baro)
        c.ram_word(p["calc"],0xA55A)
        sp=c.sp
        c.call(p["cfp"])
        require(c.sp==sp and c.sk==15,"Stack imbalance")
        require(all(0xF8000<=x<0xF8800 for x in c.writes),"Write outside RAM")
        pulse=c.ram_word(p["fuel"])
        require(pulse==c.ram_word(0x00F6),"Pulse mirror")
        return pulse,c.ram_word(p["calc"]),c.ram_byte(p["tip"]),c.ram_byte(0x00F0)


def measure():
    return dict(n=0,sum=0.0,maxpct=0.0,maxcount=0,atleast1=0,
                maxpct100=0.0,atleast1_100=0,small_maxcount=0,case=None,zero_mismatch=0)


def add(s,a,b,case):
    delta=abs(a-b)
    s["maxcount"]=max(s["maxcount"],delta)
    if b==0:
        s["zero_mismatch"]+=int(delta!=0)
        return
    pct=100*delta/b
    s["n"]+=1
    s["sum"]+=pct
    s["atleast1"]+=int(pct>=1)
    if b>=100:
        s["maxpct100"]=max(s["maxpct100"],pct)
        s["atleast1_100"]+=int(pct>=1)
    else:
        s["small_maxcount"]=max(s["small_maxcount"],delta)
    if pct>s["maxpct"]:
        s["maxpct"],s["case"]=pct,(case,a,b)


def summarize(s):
    return {**s,"mean_pct":s["sum"]/max(1,s["n"])}


def profile(p,roms,mps,rpms):
    # These additional opcodes are register shifts or ordinary immediate LDY.
    timing.REG2.update(("ASLD","LSRB"))
    timing.ALU.add("LDY")
    best={name:{"cycles4":0,"stack":0,"instructions":0} for name in roms}
    for mp in mps:
        for rpm in rpms:
            for flags in (0,0x21):
                for name,rom in roms.items():
                    c=timing.run(timing.ProfileCPU(rom),p,mp,rpm,flags,255 if flags else 0,100)
                    m=best[name]
                    m["cycles4"]=max(m["cycles4"],c.clocks(4))
                    m["stack"]=max(m["stack"],c.initial_sp-c.low_sp)
                    m["instructions"]=max(m["instructions"],c.steps)
    print("PROFILE",json.dumps(best),flush=True)


def check(pn,full):
    p=CONFIG[pn]
    stock=(ROOT/"build"/(pn+".bin")).read_bytes()
    variant=json.loads((ROOT/"tools"/"variants.json").read_text())[pn]
    require(hashlib.sha256(stock).hexdigest()==variant["sha256"],"Wrong stock ROM")
    v1,*_=create_v1(stock,p)
    q16,tables=make_v2(stock,p,False)
    q11,_=make_v2(stock,p,True)
    roms=dict(stock=stock,v1=v1,q16=q16,q11=q11)
    positions=[[lookup_position(stock,p,p[k],mp) for mp in range(256)]
               for k in ("pt_scale","wt_scale")]
    hold=bool(stock[0x323]&1)
    mps=list(range(256)) if full else sorted(set(range(0,256,17))|{12,13,14,19,20,21,31,32,33,34,35,111,112,113,127,128,129,239,240,241,254,255})
    rpms=list(range(256)) if full else sorted(set(range(0,256,13))|{0,20,42,59,83,159,225,255}|set(tables[0][0]))
    n=0
    for mode in (0,1):
        stats={k:{n:measure() for n in ("pulse","calc","active_pulse","active_calc")} for k in ("v1","q16","q11")}
        jumps={k:{"absolute":0,"excess":0,"case":None} for k in stats}
        runners={k:Runner(v,p) for k,v in roms.items()}
        # Preserve previous MAP sample per RPM for adjacent-point continuity.
        previous={}
        for mp in mps:
            for rpm in rpms:
                flags=0x20 if mode else 0
                case=(mp,rpm,flags)
                values={k:r.run(*case) for k,r in runners.items()}
                ov=values["stock"]
                effective=max(mp,stock[p["hold"]]) if hold and not mode else mp
                prefix="wt" if mode else "pt"
                pts=scale_points(stock,p[prefix+"_scale"])
                active=pts[0][0]<=effective<=pts[-1][0]
                for name in stats:
                    nv=values[name]
                    require(nv[2:]==ov[2:],f"TipIn/MAP contract {name} {case}")
                    if name!="v1":
                        ref=expected(stock,p,tables,positions,*case,0,0,name=="q11",hold)
                        require(nv[:2]==ref,f"Machine/reference {name} {case}: {nv[:2]} vs {ref}")
                    for i,field in enumerate(("pulse","calc")):
                        if i==1 and ov[1]==0xA55A:
                            require(nv[1]==ov[1],"Cutoff changed CalcFuel432")
                            continue
                        add(stats[name][field],nv[i],ov[i],case)
                        if active:
                            add(stats[name]["active_"+field],nv[i],ov[i],case)
                    if rpm in previous and previous[rpm][0]==mp-1:
                        prev=previous[rpm][1]
                        dj=nv[0]-prev[name][0]
                        excess=dj-(ov[0]-prev["stock"][0])
                        j=jumps[name]
                        j["absolute"]=max(j["absolute"],abs(dj))
                        if abs(excess)>j["excess"]:
                            j["excess"],j["case"]=abs(excess),(case,prev["stock"][0],ov[0],prev[name][0],nv[0])
                previous[rpm]=(mp,values)
                n+=1
        print(pn,"PT" if not mode else "WOT","STATS",json.dumps({k:{f:summarize(s) for f,s in v.items()} for k,v in stats.items()}),flush=True)
        print(pn,"PT" if not mode else "WOT","JUMPS",json.dumps(jumps),flush=True)
    # Exercise both MAP hold and TipIn option states and WOT enrichment/BARO.
    edges=0
    for h in (0,1):
        for tip in (0,1):
            testroms={}
            for name,rom in roms.items():
                b=bytearray(rom)
                b[0x323]=(b[0x323]&0xFE)|h
                b[p["accel"]]=(b[p["accel"]]&0x7F)|(tip<<7)
                testroms[name]=Runner(b,p)
            for mp in (0,13,14,20,21,31,32,33,112,113,127,128,239,240,241,255):
                for rpm in (0,20,59,83,159,225,255):
                    for flags in (0,1,0x20,0x21):
                        wte=255
                        baro=65535 if (mp+rpm)%2 else 100
                        ov=testroms["stock"].run(mp,rpm,flags,wte,baro)
                        for name in ("q16","q11"):
                            nv=testroms[name].run(mp,rpm,flags,wte,baro)
                            require(nv[2:]==ov[2:],f"Option contract {name}")
                            ref=expected(stock,p,tables,positions,mp,rpm,flags,wte,baro,name=="q11",bool(h))
                            require(nv[:2]==ref,f"Option reference {name} {(h,tip,mp,rpm,flags)}: {nv[:2]} vs {ref}")
                        edges+=1
    print(f"{pn}: {n} stock/V1/V2 input cases and {edges} option edge cases; machine reference checks passed",flush=True)
    if not full:
        profile(p,roms,(13,32,35,80,112,128,200,240,241,255),(0,20,42,59,62,83,159,194,195,224,225,255))


if __name__=="__main__":
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pn",choices=CONFIG)
    ap.add_argument("--full",action="store_true")
    a=ap.parse_args()
    check(a.pn,a.full)
