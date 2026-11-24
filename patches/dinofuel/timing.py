#!/usr/bin/env python3
"""CPU16 fuel-routine timing/stack profile, not a hardware WCET proof.

Nominal cycles: CPU16RM, table 6-36, pp 6-270..6-286.
Bus adjustment: Motorola EB251, tables 1-3. Assumed aligned 16-bit
2-clock program/operand bus for the reference; odd word accesses are
charged an additional bus cycle. Report slower flash-bus scenarios.
The simulator excludes the rest of the ISR and actual hardware events.
"""
import argparse
import hashlib
import json
from collections import Counter
from functools import lru_cache

from dinofuel128 import ROOT, CONFIG, create_patch, require, CPU, decode

REG2 = set("ABA ABX ABY ADE ADX AEX ASLB ASLE CLRA CLRB CLRD CLRE DECA DECB INCB LSRE LSRD NEGA NEGB NEGD ROLE RORB RORE SDE TAB TBA TBXK TDE TED TSTA TSX TSY TXY XGAB XGDE XGDX XGDY XGEX XGEY".split())
ALU = set("ADCA ADDA ADDB ADDE ADCE ANDB ANDE CMPA CMPB CPE EORB LDAA LDAB LDD LDE LDX SUBA SUBB SUBD SUBE TST".split())
STORE = set("STAA STAB STD STE STX".split())
BR = set("BCC BCS BEQ BNE BHI BLS BMI BPL BLT BLE BGE BGT BVC BVS".split())

def timing(ins, taken):
    """Return nominal system clocks and number of program word accesses."""
    m, mode = ins.mn, ins.mode
    words = ins.size // 2
    if m in ("BRCLR","BRSET"):
        short = mode.startswith("IND8")
        # EB251 table 2: taken costs more accesses. Table 6-36 prints
        # the bit-test branch pair in ascending order, unlike Bcc.
        return (12 if short else 14, 4 if short else 5) if taken else (10,3)
    if m in BR or (m.startswith("L") and m[1:] in BR):
        return (6,3) if taken else (words*2,words)
    if m in ("BRA","LBRA","JMP"):
        require(m != "JMP" or mode == "EXT20","Unsupported JMP mode")
        return 6,3
    if m in ("BSR","LBSR","JSR"):
        require(m != "JSR" or mode == "EXT20","Unsupported JSR mode")
        return 10,3
    if m == "RTS":
        return 12,3
    if m in ("PSHM","PULM"):
        n = dict(ins.vals)["ii"].bit_count()
        return 4+2*(n+(m=="PULM")),1
    if m in ("PSHA","PSHB"):
        return 4,1
    if m in ("PULA","PULB"):
        return 6,1
    if m in ("MUL","EMUL"):
        return 10,1
    if m in ("IDIV","FDIV"):
        return 22,1
    if m in REG2 and mode=="INH":
        return 2,1
    if m in ("AIX","AIY") and mode in ("IMM8","IMM16"):
        return words*2,words
    if m in ALU:
        if mode in ("IMM8","IMM16"):
            return words*2,words
        if mode.startswith(("IND8","IND16","E, ")) or mode=="EXT":
            return 6,words
    if m in STORE:
        if mode.startswith(("IND8","E, ")):
            return 4,words
        if mode.startswith("IND16") or mode=="EXT":
            return 6,words
    raise ValueError(f"Unverified timing: {ins.key} {m} {mode} at ${ins.addr:05X}")

class ProfileCPU(CPU):
    def __init__(self,image):
        super().__init__(image,0x800)
        self.initial_sp=self.sp
        self.low_sp=self.sp
        self.nominal=0
        self.program_words=0
        self.flash_accesses=0
        self.ram_accesses=0
        self.flash_odd=0
        self.ram_odd=0
        self._inside=False
        self._word=False
        self.mix=Counter()

    def access(self,a,width):
        if not self._inside:
            return
        a &= 0xFFFFF
        odd = int(width==2 and a&1)
        if a < self.rom_size:
            self.flash_accesses+=1+odd
            self.flash_odd+=odd
        elif 0xF8000 <= a < 0xF8800:
            self.ram_accesses+=1+odd
            self.ram_odd+=odd
        else:
            raise ValueError(f"Unexpected operand address ${a:05X}")

    def rb(self,a):
        if not self._word:
            self.access(a,1)
        return super().rb(a)

    def wb(self,a,v):
        if not self._word:
            self.access(a,1)
        return super().wb(a,v)

    def rw(self,a):
        self.access(a,2)
        self._word=True
        try:
            return super().rw(a)
        finally:
            self._word=False

    def ww(self,a,v):
        self.access(a,2)
        self._word=True
        try:
            return super().ww(a,v)
        finally:
            self._word=False

    def step(self,pc):
        self._inside=True
        super().step(pc)
        self._inside=False
        ins=self.ins
        next_pc=(self.pk<<16)|self.pc
        taken=next_pc != ((pc+ins.size)&0xFFFFF)
        if ins.mn in BR or ins.mn in ("BRCLR","BRSET") or (ins.mn.startswith("L") and ins.mn[1:] in BR):
            require(ins.target()!=((pc+ins.size)&0xFFFFF),"Ambiguous conditional branch target")
        cycles,words=timing(ins,taken)
        self.nominal+=cycles
        self.program_words+=words
        if ins.mn=="PULM":
            # EB251 counts one additional stack operand access for PULM.
            self.ram_accesses+=1
        self.low_sp=min(self.low_sp,self.sp)
        self.mix[ins.mn]+=1

    def clocks(self,flash_periods=2,ram_periods=2):
        # Base timings assume aligned operands, 16-bit data and 2-clock buses.
        return (self.nominal+2*(self.flash_odd+self.ram_odd)
                +(flash_periods-2)*(self.program_words+self.flash_accesses)
                +(ram_periods-2)*self.ram_accesses)

def run(cpu,p,mp,rpm,flags,wte,baro):
    for name,value in (("map",mp),("rpm",rpm),("flags",flags),("wte",wte)):
        cpu.ram_byte(p[name],value)
    cpu.ram_word(p["baro"],baro)
    cpu.call(p["cfp"])
    require(cpu.sp==cpu.initial_sp,"Stack imbalance")
    return cpu

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pn",choices=CONFIG)
    ap.add_argument("--dense",action="store_true")
    ap.add_argument("--mhz",type=float,default=16.777216,help="Assumed oscillator frequency in MHz")
    a=ap.parse_args()
    require(a.mhz>0,"Invalid frequency")
    stock=(ROOT/"build"/(a.pn+".bin")).read_bytes()
    variant=json.loads((ROOT/"tools"/"variants.json").read_text())[a.pn]
    require(hashlib.sha256(stock).hexdigest()==variant["sha256"],"Not exact stock")
    p=CONFIG[a.pn]
    patched,pt,wt=create_patch(stock,p)
    # Every RPM knot and each adjacent byte, and MAP cutoffs/scale transitions.
    mp_set=set(range(0,256,4 if a.dense else 16))
    mp_set.update((0,12,13,19,20,31,32,33,111,112,113,127,128,129,239,240,241,254,255))
    rp_set=set(range(0,256,3 if a.dense else 19))
    for v in pt[0]+wt[0]:
        rp_set.update((v-1,v,v+1))
    rp_set.update((0,255))
    best={k:{} for k in ("stock","patched")}
    worst_delta={}
    n=0
    for mp in sorted(mp_set):
        for rpm in sorted(rp_set):
            for flags in (0,0x20,0x21):
                wte=255 if flags==0x21 else 0
                baro=65535 if (mp+rpm)%31==0 else 100
                case=(mp,rpm,flags,wte,baro)
                metrics=[]
                for name,rom in (("stock",stock),("patched",patched)):
                    c=run(ProfileCPU(rom),p,*case)
                    vals={"instructions":c.steps,"stack_bytes":c.initial_sp-c.low_sp,
                          "cycles_2":c.clocks(2),"cycles_3":c.clocks(3),"cycles_4":c.clocks(4)}
                    for key,val in vals.items():
                        if key not in best[name] or val>best[name][key][0]:
                            best[name][key]=(val,case)
                    metrics.append(vals)
                for key in ("cycles_2","cycles_3","cycles_4","stack_bytes"):
                    delta=metrics[1][key]-metrics[0][key]
                    if key not in worst_delta or delta>worst_delta[key][0]:
                        worst_delta[key]=(delta,case)
                n+=1
    print(f"{a.pn}: {n} paired profiles (MAP, RPM byte, flags, WOT enrichment, BARO)")
    for name,vals in best.items():
        for key,(v,case) in vals.items():
            us=f" = {v/a.mhz:.2f} us at assumed {a.mhz:.6f} MHz" if key.startswith("cycles_") else ""
            print(f"{name} {key}: {v}{us}; case {case}")
    for key,(v,case) in worst_delta.items():
        print(f"largest paired delta {key}: {v:+d}; case {case}")
    print("No full-ISR, hardware, or hard-real-time WCET certification.")

if __name__=="__main__":
    main()
