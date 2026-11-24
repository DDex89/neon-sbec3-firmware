#!/usr/bin/env python3
"""Experimental DinoFuel absolute 16-bit table port for the stock 04887050/05293013AC.

Adapted from Dino Yancey's DinoFuel, corrected in DDex89/dinofuel at ff9521d.
This does NOT change the stock sources or enable a real vehicle flash.
Run after tools/build.py:
    python3 patches/dinofuel/dinofuel128.py build/04887050.bin
    python3 patches/dinofuel/dinofuel128.py build/05293013AC.bin --full
Optional --output writes an experimental ROM only after full simulator checks.
"""
import argparse
import hashlib
import json
import sys
from fractions import Fraction
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from asm16 import assemble
from cpu16 import decode
from cpu16sim import CPU
SIZE = 0x20000
CODE = 0x0FC04
CODE_LIMIT = 0x10000
PT_BASE = 0x04401
WT_BASE = 0x04669
DATA_LIMIT = 0x047C0

# All addresses are independently mapped in the stock disassembly.
CONFIG = {
    "04887050": dict(cfp=0x07D62, hook=0x07DEA, tail=0x07E0E,
        lookup2d=0x0E400, lookup3d=0x0E54E, pt_scale=0x048F,
        wt_scale=0x0483, pt_table=0x07C2, wt_table=0x0715,
        pt_offset=0x0657, pt_k=0x0656, wt_offset=0x0655, wt_k=0x0654,
        accel=0x0693, hold=0x0491, map=0x032B, rpm=0x0306, flags=0x055B,
        wte=0x05B3, baro=0x0596, fuel=0x05BA, calc=0x03BF,
        tip=0x0567, scratch=0x03B0),
    "05293013AC": dict(cfp=0x07D82, hook=0x07E0A, tail=0x07E2E,
        lookup2d=0x0E500, lookup3d=0x0E64E, pt_scale=0x04A1,
        wt_scale=0x0495, pt_table=0x07D5, wt_table=0x0728,
        pt_offset=0x066A, pt_k=0x0669, wt_offset=0x0668, wt_k=0x0667,
        accel=0x06A6, hold=0x04A3, map=0x0345, rpm=0x031D, flags=0x056A,
        wte=0x05C3, baro=0x05A6, fuel=0x05CA, calc=0x03D7,
        tip=0x0576, scratch=0x02FE),
}

# The stock routine has already computed effective MAP, handled MAP hold
# and the below-offset cutoff, selected the table, and prescaled the row.
# At the original Lookup3D call: A=row position, B=rpm, E=stock linear base.
# Replace that JSR with a same-size JMP. Outside the scale, use stock code.
# Inside the scale, compute the absolute base pulse then rejoin the stock
# tail (CalcFuel432, WOT enrichment, BARO, FuelPulse, Temp4F6 and RTS).
HOOK_ASM = """
DF_Hook:
        PSHM    D
        LDAA    >Temp4F0,Z
        BRSET   >FuelModeFlags,Z,#$20,DF_WOT
        CMPA    >PTMin
        BCS     DF_Stock
        CMPA    >PTMax
        BHI     DF_Stock
        LDX     #PTTABLE
        BRA     DF_New
DF_WOT:
        CMPA    >WTMin
        BCS     DF_Stock
        CMPA    >WTMax
        BHI     DF_Stock
        LDX     #WOTTABLE
DF_New:
        PULM    D
        JSR     Table_3D_word
        STE     >LookupResult,Z
        TDE
        LSRE
        BRCLR   >AccelFuelOptions,#$80,DF_Done
        LDAB    >Temp4F0,Z
        STAB    >TipIn802,Z
DF_Done:
        JMP     StockTail
DF_Stock:
        PULM    D
        JSR     StockLookup3D
        JMP     StockAfterLookup
"""

# Derived from the corrected DinoFuel word lookup. Both XK assignments
# select bank zero for the 128 KB layout. INTERP additionally returns
# without reading the next word when the interpolation fraction is zero.
LOOKUP_ASM = """
Table_3D_word:
        PSHM    E,Y,K
        PSHM    D
        CLRB
        LDAB    #$00
        TBXK
        PULM    D
        PSHM    D
        TXY
        AIY    #$03
        CLRA
        TDE
        CPE    $0000,Y
        BLS    loc_E672
        LDAA    $01,X
        DECA
loc_E666:
        BEQ    loc_E672
        CPE    $0002,Y
        BCS    loc_E676
        AIY    #$02
        DECA
        BRA    loc_E666
loc_E672:
        CLRD
        BRA    loc_E698
loc_E676:
        PSHM    X
        LDX    #$0000
        LDD    $02,Y
        SUBD    $00,Y
        BNE    loc_E68A
        LDD    #$FFFF
        BRA    loc_E696
loc_E68A:
        ADX
        SUBE    $0000,Y
        TED
        FDIV
        XGDX
loc_E696:
        PULM    X
loc_E698:
        PSHM    D
        LDAB    $01,X
        ABY
        ABY
        PSHM    X,Y
        PULM    E,D
        SDE
        SUBE    #$0003
        LDAB    $01,X
        CLRA
        SDE
        SDE
        ASLE
        ASLE
        ASLE
        ASLE
        PSHM    X
        TSX
        AIX    #$04
        LDD    $00,X
        PULM    X
        LDAB    #$00
        TBXK
        LDAB    $00,X
        DECB
        MUL
        TAB
        ADE
        LDAB    $01,X
        MUL
        ABY
        ABY
        PULM    E
        PSHM    E
        BSR    INTERP
        STE    >LookupResult,Z
        LDAB    $01,X
        ABY
        ABY
        PULM    E
        BSR    INTERP
        PULM    D
        XGEY
        PSHM    Y
        LDE    >LookupResult,Z
        PSHM    E
        TSY
        LDAB    $00,X
        DECB
        MUL
        TBA
        CLRB
        TDE
        BSR    INTERP
        PULM    Y
        PULM    D
        TED
        PULM    K,Y,E
        RTS
INTERP:
        CPE     #$0000
        BNE     DF_InterpNonzero
        LDE     $0000,Y
        RTS
DF_InterpNonzero:
        LDD    $02,Y
        SUBD    $00,Y
        BCS    loc_282
        EMUL
        ADCE    #$0000
        ADDE    $0000,Y
        BRA    locret_290
loc_282:
        NEGD
        EMUL
        ADCE    #$0000
        XGDE
        LDE    $0000,Y
        SDE
locret_290:
        RTS
"""


def require(condition, message):
    if not condition:
        raise ValueError(message)


def scale_points(rom, addr):
    n = rom[addr]
    require(n == 3, "Expected three-point MAP scale")
    p = [(rom[addr + 2 + 2*i], rom[addr + 3 + 2*i]) for i in range(n)]
    require(all(x1 > x0 and y1 > y0
                for (x0, y0), (x1, y1) in zip(p, p[1:])), "Nonmonotonic MAP scale")
    require(p[0][1] == 0 and p[-1][1] == 255, "Unexpected MAP scale endpoints")
    return p


def inverse_scale(points, pos):
    if pos <= points[0][1]:
        return Fraction(points[0][0])
    if pos >= points[-1][1]:
        return Fraction(points[-1][0])
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if y0 <= pos <= y1:
            return x0 + Fraction(pos - y0, y1 - y0) * (x1 - x0)
    raise ValueError("Invalid row position")


def word_table(rom, p, wot):
    prefix = "wt" if wot else "pt"
    addr = p[prefix + "_table"]
    rows, cols, flag = rom[addr:addr+3]
    require((rows, cols, flag) == (9 if wot else 17, 17, 255),
            "Unexpected stock fuel table shape or signedness")
    axis = list(rom[addr+3:addr+3+cols])
    require(all(b > a for a, b in zip(axis, axis[1:])), "Nonmonotonic RPM axis")
    points = scale_points(rom, p[prefix + "_scale"])
    offset, k = rom[p[prefix + "_offset"]], rom[p[prefix + "_k"]]
    values = []
    # Stock-derived absolute base-pulse table (times two, as in DinoFuel).
    # The last row corresponds to the upper scale endpoint, position 255.
    for j in range(rows):
        pos = min(Fraction(255), Fraction(256*j, rows-1))
        mp = inverse_scale(points, pos)
        base = max(0, mp - offset) * (256 + k) / 16
        row = []
        for i in range(cols):
            f = rom[addr+3+cols+j*cols+i]
            f = f - 256 if f >= 128 else f
            word = round(2 * base * (256 + f) / 256)
            require(0 <= word <= 65535, "Absolute pulse table overflows")
            row.append(word)
        values.append(row)
    data = bytes([rows, cols, 0]) + b"".join(v.to_bytes(2, "big") for v in axis)
    data += b"".join(v.to_bytes(2, "big") for row in values for v in row)
    return data, axis, values


def patch_code(p, rom):
    h = decode(rom, p["hook"])
    require(h and h.mn == "JSR" and h.size == 4 and h.target() == p["lookup3d"],
            "Hook is not the expected stock Lookup3D call")
    after = decode(rom, p["hook"]+4)
    require(after and after.mn == "BRCLR" and after.mode == "EXT"
            and dict(after.vals)["hhll"] == p["accel"]
            and dict(after.vals)["mm"] == 0x80, "Unexpected stock TipIn branch")
    tail = decode(rom, p["tail"])
    require(tail and tail.mn == "TED", "Unexpected stock tail")
    symbols = dict(Temp4F0=0x00F0, FuelModeFlags=p["flags"],
                   PTMin=p["pt_scale"]+2, PTMax=p["pt_scale"]+6,
                   WTMin=p["wt_scale"]+2, WTMax=p["wt_scale"]+6,
                   PTTABLE=PT_BASE, WOTTABLE=WT_BASE,
                   LookupResult=p["scratch"], TipIn802=p["tip"],
                   AccelFuelOptions=p["accel"], StockTail=p["tail"],
                   StockLookup3D=p["lookup3d"], StockAfterLookup=p["hook"]+4)
    text = "\n".join(f"{k} equ ${v:04X}" for k, v in symbols.items())
    text += f"\norg ${CODE:05X}\n" + HOOK_ASM + LOOKUP_ASM
    text += f"\norg ${p['hook']:05X}\n        JMP DF_Hook\n"
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "dinofuel128.asm"
        path.write_text(text)
        a = assemble([str(path)], SIZE)
    h = decode(a, p["hook"])
    require(h and h.mn == "JMP" and h.size == 4 and h.target() == CODE,
            "Incorrect assembled hook")
    code = a[CODE:CODE_LIMIT].rstrip(b"\xFF")
    require(code and len(code) <= CODE_LIMIT-CODE, "Code does not fit")
    return a[p["hook"]:p["hook"]+4], code


def put_erased(dst, address, data, limit):
    end = address + len(data)
    require(end <= limit and end <= len(dst), "Patch does not fit")
    require(all(b == 0xFF for b in dst[address:end]), "Destination is not erased")
    dst[address:end] = data


def create_patch(rom, p):
    pt, pax, pv = word_table(rom, p, False)
    wt, wax, wv = word_table(rom, p, True)
    require(PT_BASE % 2 == 1 and WT_BASE % 2 == 1, "Word alignment")
    hook, code = patch_code(p, rom)
    dst = bytearray(rom)
    put_erased(dst, PT_BASE, pt, WT_BASE)
    put_erased(dst, WT_BASE, wt, DATA_LIMIT)
    put_erased(dst, CODE, code, CODE_LIMIT)
    dst[p["hook"]:p["hook"]+4] = hook
    hdr = int.from_bytes(dst[0x202:0x204], "big")
    require(0 <= hdr <= SIZE-14, "Invalid checksum header")
    target = dst[hdr+3]
    dst[hdr+13] = (dst[hdr+13] + target - sum(dst)) & 0xFF
    require(sum(dst) & 0xFF == target, "Checksum failed")
    allowed = [(PT_BASE, PT_BASE+len(pt)), (WT_BASE, WT_BASE+len(wt)),
               (CODE, CODE+len(code)), (p["hook"], p["hook"]+4), (hdr+13, hdr+14)]
    require(all(x == y or any(lo <= i < hi for lo, hi in allowed)
                for i, (x, y) in enumerate(zip(rom, dst))), "Unexpected ROM modification")
    print(f"Code: {len(code)} bytes at ${CODE:05X}; PT: {len(pt)} at ${PT_BASE:05X}; "
          f"WOT: {len(wt)} at ${WT_BASE:05X}; hook: ${p['hook']:05X}")
    return bytes(dst), (pax, pv), (wax, wv)


def run_cfp(rom, p, mp, rpm, flags, wte, baro):
    c = CPU(rom, 0x800)
    for name, value in (("map", mp), ("rpm", rpm), ("flags", flags), ("wte", wte),
                        ("tip", 0xA5)):
        c.ram_byte(p[name], value)
    c.ram_word(p["baro"], baro)
    c.ram_word(p["calc"], 0xA55A)
    sp = c.sp
    c.call(p["cfp"])
    require(c.sp == sp, "Unbalanced stack")
    return c, (c.ram_word(p["fuel"]), c.ram_word(p["calc"]),
               c.ram_word(0x00F6), c.ram_byte(p["tip"]), c.ram_byte(0x00F0))


def lookup_position(rom, p, scale, mp):
    c = CPU(rom, 0x800)
    c.ix, c.a = scale, mp
    c.call(p["lookup2d"])
    return c.a


def reference(table, pos, rpm):
    axis, v = table
    i = 0
    while i < len(axis)-1 and rpm >= axis[i+1]:
        i += 1
    fc = 0 if rpm <= axis[0] or i == len(axis)-1 else Fraction(rpm-axis[i], axis[i+1]-axis[i])
    j, fr = divmod(pos * (len(v)-1), 256)
    ii = min(i+1, len(axis)-1)
    jj = min(j+1, len(v)-1)
    a = v[j][i] + (v[j][ii]-v[j][i])*fc
    b = v[jj][i] + (v[jj][ii]-v[jj][i])*fc
    return (a+(b-a)*Fraction(fr,256))/2


def validate(stock, new, p, pt, wt, full):
    # Both original and patched entry points run in the existing CPU16 simulator.
    mps = list(range(0,256,4 if full else 17)) + [12,13,19,20,31,32,127,128,239,240,241,254,255]
    rpms = list(range(0,256,3 if full else 19)) + pt[0] + wt[0] + [0,15,16,224,225,226,255]
    mps, rpms = sorted(set(mps)), sorted(set(rpms))
    scales = [scale_points(stock,p[k]) for k in ("pt_scale","wt_scale")]
    positions = [[lookup_position(stock,p,p[k],mp) for mp in range(256)]
                 for k in ("pt_scale","wt_scale")]
    worst = [0.0,0.0]
    rel = [[],[]]
    counts = [0,0]
    fallback = 0
    max_steps = 0
    max_stock_steps = 0
    for mp in mps:
        for rpm in rpms:
            for flags in ((0,1,0x20,0x21) if full else (0,0x21)):
                mode = int(bool(flags & 0x20))
                # Include correction and saturation cases while retaining a base-pulse comparison.
                wte = 40 if (mp+rpm)%2 else 0
                baro = 65535 if (mp+rpm)%31 == 0 else (100 if (mp+rpm)%3 else 0)
                oc, ov = run_cfp(stock,p,mp,rpm,flags,wte,baro)
                nc, nv = run_cfp(new,p,mp,rpm,flags,wte,baro)
                max_steps = max(max_steps,nc.steps)
                max_stock_steps = max(max_stock_steps,oc.steps)
                points = scales[mode]
                effective = max(mp,stock[p["hold"]]) if not mode and stock[0x0323]&1 else mp
                offset = stock[p["wt_offset" if mode else "pt_offset"]]
                active = effective >= offset and points[0][0] <= effective <= points[-1][0]
                where = f"MAP={mp} RPMbyte={rpm} flags={flags:02X}"
                require(nv[2] == nv[0], "FuelPulse mirror mismatch "+where)
                require(nv[3:] == ov[3:], "TipIn or effective MAP mismatch "+where)
                if not active:
                    require(nv == ov, "Stock fallback or cutoff mismatch "+where)
                    fallback += 1
                    continue
                counts[mode] += 1
                base = float(reference(wt if mode else pt, positions[mode][effective],rpm))
                expected = min(65535, base*(1+wte/256 if mode and flags & 1 else 1)+baro)
                err = abs(nv[0]-expected)
                worst[mode] = max(worst[mode],err)
                require(err <= 2.5, "Interpolation/output mismatch "+where+f": {nv[0]} vs {expected}")
                require(abs(nv[1]-base/2) <= 1.5, "CalcFuel432 mismatch "+where)
                lo = WT_BASE if mode else PT_BASE
                hi = lo + (343 if mode else 615)
                require(all(not 0x04374 <= a < 0x04800 or lo <= a < hi
                            for a in nc.reads), "Cross-table read "+where)
                # CalcFuel432 is half of the base before enrichment and baro.
                if ov[1]:
                    rel[mode].append(abs(nv[1]-ov[1])/ov[1]*100)
    for i, name in enumerate(("PT","WOT")):
        avg = sum(rel[i])/len(rel[i]) if rel[i] else 0
        mx = max(rel[i],default=0)
        print(f"{name}: {counts[i]} patched cases; max reference error {worst[i]:.2f} counts; "
              f"stock CalcFuel432 difference mean {avg:.3f}%, max {mx:.3f}%")
    print(f"Total cases: {sum(counts)+fallback}; {fallback} stock fallback/cutoff cases; maximum instructions stock={max_stock_steps}, "
          f"patched={max_steps} (not CPU cycles).")
    # Exercise option combinations independently of the stock ROM settings.
    # The patch is created only from a verified original ROM; these copies
    # are for simulation only and are never exported.
    edge_n = 0
    for hold in (0,1):
        for tip in (0,1):
            old, patched = bytearray(stock), bytearray(new)
            for image in (old, patched):
                image[0x0323] = (image[0x0323] & 0xFE) | hold
                image[p["accel"]] = (image[p["accel"]] & 0x7F) | (tip << 7)
            for mp in (0,12,13,19,20,31,32,33,127,128,239,240,241,255):
                for rpm in (0,16,17,224,225,226,255):
                    for flags in (0,1,0x20,0x21):
                        oc, ov = run_cfp(old,p,mp,rpm,flags,255,100)
                        nc, nv = run_cfp(patched,p,mp,rpm,flags,255,100)
                        require(nv[3:] == ov[3:], "Option edge: TipIn or MAP hold mismatch")
                        require(nv[0] == nv[2], "Option edge: FuelPulse mirror mismatch")
                        mode = int(bool(flags & 0x20))
                        effective = max(mp,old[p["hold"]]) if hold and not mode else mp
                        points = scales[mode]
                        offset = old[p["wt_offset" if mode else "pt_offset"]]
                        if effective < offset or not points[0][0] <= effective <= points[-1][0]:
                            require(nv == ov, "Option edge: stock fallback mismatch")
                        else:
                            base = float(reference(wt if mode else pt, positions[mode][effective],rpm))
                            expected = min(65535,base*(1+255/256 if mode and flags & 1 else 1)+100)
                            require(abs(nv[0]-expected) <= 3.5, "Option edge: interpolation mismatch")
                            require(abs(nv[1]-base/2) <= 1.5, "Option edge: CalcFuel432 mismatch")
                        edge_n += 1
    print(f"Additional MAP hold / TipIn / WOT flag edge tests: {edge_n} passed.")
    print("Simulator validation passed; no hardware validation implied.")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("rom", type=Path)
    ap.add_argument("--full", action="store_true", help="Denser MAP/RPM simulator grid")
    ap.add_argument("--output", type=Path, help="Experimental image (requires --full)")
    a = ap.parse_args()
    stock = a.rom.read_bytes()
    variants = json.loads((ROOT/"tools"/"variants.json").read_text())
    digest = hashlib.sha256(stock).hexdigest()
    pn = next((n for n in CONFIG if variants[n]["sha256"] == digest), None)
    require(len(stock)==SIZE and pn, "Unsupported or modified stock ROM; exact SHA-256 required")
    require(not a.output or a.full, "--output requires --full")
    require(not a.output or a.output.resolve() != a.rom.resolve(), "Will not overwrite stock ROM")
    print(f"{pn}: exact stock ROM verified")
    patched, pt, wt = create_patch(stock,CONFIG[pn])
    validate(stock,patched,CONFIG[pn],pt,wt,a.full)
    if a.output:
        with a.output.open("xb") as f:
            f.write(patched)
        print("Experimental ROM written; NOT hardware-qualified:", a.output)


if __name__ == "__main__":
    main()
