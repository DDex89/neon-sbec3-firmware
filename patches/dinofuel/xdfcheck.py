#!/usr/bin/env python3
"""Verify the committed experimental XDFs against real patched ROMs.

Tests XML, axis labels, unsigned big-endian 16-bit cell layout, non-overlap,
and an emulated edit of a table cell followed by actual CPU16 execution.
No edited ROM is written. Does not validate the TunerPro GUI.
"""
import hashlib
import json
import sys
import xml.etree.ElementTree as ET
from fractions import Fraction
from pathlib import Path

from dinofuel128 import (
    ROOT, CONFIG, PT_BASE, WT_BASE, CODE, SIZE, create_patch,
    inverse_scale, scale_points, run_cfp, require,
)


def check(pn):
    stock = (ROOT / "build" / (pn + ".bin")).read_bytes()
    v = json.loads((ROOT / "tools" / "variants.json").read_text())[pn]
    require(hashlib.sha256(stock).hexdigest() == v["sha256"], "Wrong stock ROM")
    p = CONFIG[pn]
    rom, pt, wt = create_patch(stock, p)
    root = ET.parse(Path(__file__).parent / "xdf" / (pn + "-dinofuel.xdf")).getroot()
    require(root.tag == "XDFFORMAT" and root.get("version") == "1.60", "XDF format")
    require(pn in root.findtext("XDFHEADER/deftitle"), "Wrong XDF title")
    require(int(root.find("XDFHEADER/REGION").get("size"), 0) == SIZE, "Wrong region")
    require(root.find("XDFHEADER/DEFAULTS").get("lsbfirst") == "0", "Wrong endian")
    tables = root.findall("XDFTABLE")
    require(len(tables) == 2 and len({t.get("uniqueid") for t in tables}) == 2, "Table count/IDs")
    require(not root.findall("XDFCONSTANT") and not root.findall("XDFFLAG"), "Unexpected items")
    used = set()
    for mode, (t, base, table) in enumerate(zip(tables, (PT_BASE, WT_BASE), (pt, wt))):
        axis, values = table
        rows, cols = len(values), len(axis)
        require(t.findtext("title") == ("DinoFuel WOT" if mode else "DinoFuel Part Throttle"), "Wrong table")
        axes = {a.get("id"): a for a in t.findall("XDFAXIS")}
        require(set(axes) == {"x","y","z"}, "Missing axis")
        for key, count in (("x",cols), ("y",rows)):
            a = axes[key]
            require(a.find("EMBEDDEDDATA") is None and a.findtext("outputtype") == "4", "Axis not fixed")
            require(int(a.findtext("indexcount")) == count, "Axis size")
            require([int(x.get("index")) for x in a.findall("LABEL")] == list(range(count)), "Axis indices")
        require([int(x.get("value")) for x in axes["x"].findall("LABEL")] == [i*32 for i in axis], "RPM labels")
        points = scale_points(stock, p["wt_scale" if mode else "pt_scale"])
        labels = [f"{float(inverse_scale(points,min(Fraction(255),Fraction(256*j,rows-1))))/2.428:.1f}" for j in range(rows)]
        require([x.get("value") for x in axes["y"].findall("LABEL")] == labels, "MAP labels")
        z = axes["z"]
        e = z.find("EMBEDDEDDATA")
        g = lambda key: int(e.get(key),0)
        addr = g("mmedaddress")
        require(addr == base+3+2*cols and addr%2 == 0, "Cell start")
        require(g("mmedtypeflags") == 0 and g("mmedelementsizebits") == 16, "Unsigned word format")
        require(g("mmedrowcount") == rows and g("mmedcolcount") == cols, "Dimensions")
        require(g("mmedmajorstridebits") == cols*16 and g("mmedminorstridebits") == 16, "Strides")
        require(z.find("MATH").get("equation") == "X/2", "Scaling")
        require(rom[base:base+3] == bytes((rows,cols,0)), "ROM header")
        require([int.from_bytes(rom[base+3+2*i:base+5+2*i],"big") for i in range(cols)] == axis, "ROM RPM axis")
        for j in range(rows):
            for i in range(cols):
                a = addr + j*g("mmedmajorstridebits")//8 + i*g("mmedminorstridebits")//8
                require(a not in used and a+1 not in used and a+2 <= CODE, "Overlap")
                used.update((a,a+1))
                require(int.from_bytes(rom[a:a+2],"big") == values[j][i], "Cell mapping")
        # Emulate a TunerPro write to an exact node of the first row.
        # All other bytes stay unchanged; CPU16 must consume the new word.
        a = addr
        edited = bytearray(rom)
        old = int.from_bytes(edited[a:a+2],"big")
        word = old+32
        require(word < 65536, "Test word overflow")
        edited[a:a+2] = word.to_bytes(2,"big")
        mp, rpm, flags = points[0][0], axis[0], 0x20 if mode else 0
        _, before = run_cfp(rom,p,mp,rpm,flags,0,0)
        _, after = run_cfp(edited,p,mp,rpm,flags,0,0)
        require(before[0] == old//2 and after[0] == word//2, "Edited cell not used by CPU16")
        require(after[0]-before[0] == 16 and after[2] == after[0], "Edit scaling")
        require(after[1] == after[0]//2, "CalcFuel432 after edit")
        print(f"{pn}: {t.findtext('title')} {rows}x{cols}, {rows*cols} cells at ${addr:05X}; edit +16 counts verified")
    require(len(used) == 884, "Wrong total cell bytes")
    print(f"{pn}: XDF validation passed (442 cells, 2 simulated edits)")


if __name__ == "__main__":
    for pn in sys.argv[1:] or CONFIG:
        check(pn)
