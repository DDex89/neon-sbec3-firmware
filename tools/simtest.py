#!/usr/bin/env python3
"""Check tools/cpu16sim.py against independent models of two stock routines of an image.

    python3 tools/simtest.py build/05293190AC.bin      # or roms/<PN>.bin; 1996-1999 families

1. Lookup3D on every 3D fuel and spark map the main fuel and spark code use (part-throttle and
   WOT), over a grid of row positions and rpm, against a bilinear interpolation model of the table
   format (docs/en/calibration.md). Allowed difference: 1 count (rounding).
2. CalcFuelPulse over a grid of MAP, rpm, WOT on/off, WOT enrichment and baro adder, against the
   formula read from its code (docs/en/fuel-pulse.md). Allowed difference: 2 counts (rounding of
   the table value and of the enrichment), or 1 %.

The routines and their calibration are found through the annotations of the image, so this runs on
the reference and on the ported 128 KB images alike. Exit status 1 if a check fails.
"""
import json, os, random, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import gen_source as g
from cpu16 import decode
from cpu16sim import CPU


def table3d(d, a):
    r, c, s = d[a], d[a + 1], d[a + 2]
    ax = list(d[a + 3:a + 3 + c])
    sx = lambda x: x - 256 if s & 0x80 and x > 127 else x
    v = [[sx(x) for x in d[a + 3 + c + j * c:a + 3 + c + (j + 1) * c]] for j in range(r)]
    return r, c, s, ax, v


def model3d(t, pos, col):
    r, c, s, ax, v = t
    if col <= ax[0]:
        i, fc = 0, 0
    else:
        i = 0
        while i < c - 1 and col >= ax[i + 1]:
            i += 1
        fc = 0 if i == c - 1 else ((col - ax[i]) * 256) // (ax[i + 1] - ax[i])
    p = pos * (r - 1)
    j, fr = p >> 8, p & 0xFF
    cell = lambda jj, ii: v[min(jj, r - 1)][min(ii, c - 1)]
    lerp = lambda x, y, f: x + (y - x) * f / 256
    return lerp(lerp(cell(j, i), cell(j, i + 1), fc), lerp(cell(j + 1, i), cell(j + 1, i + 1), fc), fr)


def main():
    path = sys.argv[1]
    d = open(path, "rb").read()
    pn = os.path.splitext(os.path.basename(path))[0]
    own, ref = g.annotation_set(d, pn)
    an = g.Analysis(d).run()
    names = g.Names(an, d, own, ref)
    cal = g.Calibration(d, an, names, own)
    lab = {v: a for a, v in names.labels.items()}
    tab = {v: a for a, v in cal.labels.items()}
    ram_size = 0x800 if len(d) <= 0x20000 else 0x1000
    lookup3d, lookup2d, cfp = lab["Lookup3D"], lab["Lookup2D"], lab["CalcFuelPulse"]
    ok = True

    # 1. Lookup3D
    for name in ("PartThrottleFuel", "WotFuel", "PartThrottleSpark", "WotSpark"):
        a = tab[name]
        t = table3d(d, a)
        worst = 0
        for pos in range(0, 256, 5):
            for col in range(0, 256, 5):
                cpu = CPU(d, ram_size)
                cpu.ix, cpu.xk, cpu.a, cpu.b = a & 0xFFFF, a >> 16, pos, col
                cpu.call(lookup3d)
                got = cpu.a - 256 if t[2] & 0x80 and cpu.a > 127 else cpu.a
                worst = max(worst, abs(got - model3d(t, pos, col)))
        good = worst <= 1
        ok &= good
        print("%-12s Lookup3D on %-18s max difference %.2f  %s" % (pn, name, worst, "OK" if good else "FAIL"))

    # 2. CalcFuelPulse: the calibration addresses are read from its first instructions
    ins, a = [], cfp
    while True:
        i = decode(d, a)
        ins.append(i)
        a += i.size
        if i.mn == "RTS":
            break
    zr = [(i.mn, dict(i.vals).get("ff", dict(i.vals).get("gggg"))) for i in ins if i.mode.endswith(", Z")]
    first = lambda mn, k=0: [o for m, o in zr if m == mn][k]
    zram = {"Map": first("LDAA"), "FuelModeFlags": first("BRCLR"), "EngineRpm": first("LDAB"),
            "WotTimeEnrich": [o for m, o in zr if m == "LDAA"][-1], "BaroFuelAdder": first("ADDE"),
            "FuelPulse": [o for m, o in zr if m == "STE"][-2]}
    ext = [(i.mn, dict(i.vals)) for i in ins if i.mode == "EXT"]
    off, k = ext[0][1]["hhll"], ext[1][1]["hhll"]
    woff, wk = ext[2][1]["hhll"], ext[3][1]["hhll"]
    hold_opt, hold_mask = ext[4][1]["hhll"], ext[4][1]["mm"]
    hold = ext[5][1]["hhll"]
    ptscale, wotscale = tab["PartThrottleMapScale"], tab["WotMapScale"]
    pt, wt = table3d(d, tab["PartThrottleFuel"]), table3d(d, tab["WotFuel"])

    def rowpos(scale, x):
        cpu = CPU(d, ram_size)
        cpu.ix, cpu.a = scale, x
        cpu.call(lookup2d)
        return cpu.a

    def model(mp, rpm, wot, wte, baro):
        t0 = mp
        o, kk = (d[woff], d[wk]) if wot else (d[off], d[k])
        if not wot and d[hold_opt] & hold_mask:
            t0 = max(mp, d[hold])
        if o > t0:
            return 0                          # MAP below the offset: no pulse (and no baro adder)
        base = ((t0 - o) * (256 + kk)) >> 4
        v = round(model3d(wt if wot else pt, rowpos(wotscale if wot else ptscale, t0), rpm))
        e = base * (256 + v) // 256
        if wot and wte:
            e += e * wte // 256
        return min(0xFFFF, e + baro)

    random.seed(1)
    worst, n = 0, 0
    for mp in range(0, 256, 6):
        for rpm in range(0, 256, 9):
            for wot in (0, 1):
                wte, baro = random.choice((0, 40)), random.choice((0, 100))
                cpu = CPU(d, ram_size)
                cpu.ram_byte(zram["Map"], mp)
                cpu.ram_byte(zram["EngineRpm"], rpm)
                cpu.ram_byte(zram["FuelModeFlags"], 0x21 if wot else 0)
                cpu.ram_byte(zram["WotTimeEnrich"], wte)
                cpu.ram_word(zram["BaroFuelAdder"], baro)
                cpu.call(cfp)
                got, m = cpu.ram_word(zram["FuelPulse"]), model(mp, rpm, wot, wte, baro)
                if abs(got - m) > 2 and abs(got - m) / max(1, m) > worst:
                    worst, case = abs(got - m) / max(1, m), (mp, rpm, wot, wte, baro, got, m)
                n += 1
    good = worst <= 0.01
    if not good:
        print("   worst case MAP %d rpm %d WOT %d enrich %d baro %d: simulator %d, model %d" % case)
    ok &= good
    print("%-12s CalcFuelPulse, %d cases: largest difference over 2 counts %.2f %%  %s" % (pn, n, worst * 100, "OK" if good else "FAIL"))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
