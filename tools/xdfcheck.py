#!/usr/bin/env python3
"""Check a generated XDF against the disassembled image.

    python3 tools/xdfcheck.py roms/05293190AC.bin xdf/05293190AC.xdf [-v]

For every XDFTABLE, XDFCONSTANT and XDFFLAG the script checks that
  - its data lies inside the image and inside the one calibration item or constant of the same
    name (the layout comes from tools/gen_source.py, as for the source);
  - table sizes match the table header in the image (points, rows, columns);
  - a flag's mask is a bit the code tests;
  - no two elements share data bytes;
  - the unit formula gives values in a plausible range for the unit text (rpm, deg C, kPa, volts,
    degrees, ms, percent) when applied to the values stored in the image.
It prints one line per problem and a summary; the exit code is 1 when there are errors.
"""
import os, re, sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from analyse import Analysis
from gen_source import Calibration, Names, annotation_set, load
from stock_xdf_options import hand_options, verify

RANGES = [  # unit text pattern -> (low, high) of plausible physical values
    (r"^rpm", (0, 12000)), (r"deg C", (-60, 260)), (r"kPa", (0, 310)), (r"^V$|volt", (0, 30)),
    (r"BTDC|deg(rees)? spark|crank deg", (-90, 90)), (r"^ms$", (0, 600)), (r"%", (-200, 400)),
    (r"km/h", (0, 300)), (r"mph", (0, 200)),
]


def evaluate(eq, x):
    expr = eq.replace("X", "(%r)" % x)
    if not re.match(r"^[0-9eE+\-*/(). ]+$", expr):
        return None
    try:
        return eval(expr, {"__builtins__": {}})
    except ZeroDivisionError:
        return None


def embedded(e):
    d = e.find("EMBEDDEDDATA")
    if d is None:
        return None
    g = lambda k, dflt=0: int(d.get(k, str(dflt)), 0)
    size = g("mmedelementsizebits", 8) // 8
    rows, cols = g("mmedrowcount", 1) or 1, g("mmedcolcount", 1) or 1
    major = g("mmedmajorstridebits", 0) // 8 or size * cols
    minor = g("mmedminorstridebits", 0) // 8 or size
    addr = g("mmedaddress")
    cells = []
    for r in range(rows):
        for c in range(cols):
            a = addr + r * major + c * minor if rows > 1 else addr + c * (g("mmedmajorstridebits", 0) // 8 or size)
            cells.append(a)
    return addr, size, rows, cols, cells, int(d.get("mmedtypeflags", "0"), 0)


def main():
    rom, xdf = sys.argv[1], sys.argv[2]
    verbose = "-v" in sys.argv
    data = open(rom, "rb").read()
    an = Analysis(data).run(extra=[(int(x, 16), "unreached") for x in load("analysis.json").get("unreached_code", [])]
                            if os.path.basename(rom).startswith("05293190AC") else ())
    own, ref = annotation_set(data, os.path.splitext(os.path.basename(rom))[0])
    names = Names(an, data, own, ref)
    cal = Calibration(data, an, names, own)
    spans = {}
    for a, t in cal.items.items():
        spans[t["name"]] = (a, a + t["size"], t)
    for a, v in cal.scalars.items():
        spans[v["name"]] = (a, a + v.get("size", 1), dict(v, kind="scalar"))
    root = ET.parse(xdf).getroot()
    pn = os.path.splitext(os.path.basename(rom))[0]
    reviewed = hand_options(pn)
    if reviewed:
        verify(root, pn)
    errors, warnings, owner = [], [], {}
    ids = set()
    n = 0
    for e in root:
        if e.tag not in ("XDFTABLE", "XDFCONSTANT", "XDFFLAG"):
            continue
        n += 1
        title = e.findtext("title")
        uid = e.get("uniqueid")
        if uid in ids:
            errors.append("%s: unique id %s used twice" % (title, uid))
        ids.add(uid)
        base = title.split(" bit $")[0]
        span = spans.get(base)
        parts = []
        if e.tag == "XDFTABLE":
            for ax in e.findall("XDFAXIS"):
                em = embedded(ax)
                if em:
                    parts.append((ax.get("id"), em, ax.findtext("units") or "", ax.find("MATH").get("equation") if ax.find("MATH") is not None else "X"))
        else:
            em = embedded(e)
            if em:
                parts.append(("v", em, e.findtext("units") or "", e.find("MATH").get("equation") if e.find("MATH") is not None else "X"))
        if span is None:
            errors.append("%s: no calibration item or constant of this name" % title)
            continue
        lo, hi, item = span
        for pid, (addr, size, rows, cols, cells, tf), units, eq in parts:
            for c in cells:
                if not (0 <= c and c + size <= len(data)):
                    errors.append("%s %s: address $%05X outside the image" % (title, pid, c))
                    break
                if not (lo <= c and c + size <= hi):
                    errors.append("%s %s: cell $%05X outside %s ($%04X-$%04X)" % (title, pid, c, base, lo, hi - 1))
                    break
                if e.tag != "XDFFLAG":
                    for b in range(c, c + size):
                        o = owner.get(b)
                        if o and o != title:
                            errors.append("%s %s: byte $%05X also belongs to %s" % (title, pid, b, o))
                            break
                        owner[b] = title
            # value range check
            for pat, (vlo, vhi) in RANGES:
                if re.search(pat, units):
                    signed = tf & 1
                    bad = []
                    for c in cells:
                        raw = int.from_bytes(data[c:c + size], "big")
                        if signed and raw >= 1 << (8 * size - 1):
                            raw -= 1 << (8 * size)
                        v = evaluate(eq, raw)
                        if v is not None and not (vlo <= v <= vhi):
                            bad.append(round(v, 1))
                    if bad:
                        warnings.append("%s %s: %d value(s) outside %s..%s %s, e.g. %s" % (title, pid, len(bad), vlo, vhi, units, bad[:3]))
                    break
        # sizes against the header
        k = item.get("kind")
        if e.tag == "XDFTABLE" and k in ("2D", "2Dr", "3D", "3Dn"):
            z = [p for p in parts if p[0] == "z"]
            if z:
                _, (addr, size, rows, cols, cells, tf), _, _ = z[0]
                if k in ("2D", "2Dr") and rows * cols != data[lo]:
                    errors.append("%s: %d cells, header says %d points" % (title, rows * cols, data[lo]))
                if k in ("3D", "3Dn") and (rows, cols) != (data[lo], data[lo + 1]):
                    errors.append("%s: %dx%d cells, header says %dx%d" % (title, rows, cols, data[lo], data[lo + 1]))
        if e.tag == "XDFFLAG":
            m = e.findtext("mask")
            if m is None or (("%02X" % int(m, 0)) not in item.get("bits", [])
                             and int(m, 0) not in reviewed.get(base, {})):
                errors.append("%s: mask %s is not a bit the code tests" % (title, m))
    # every laid-out table and constant should be in the XDF; 2D axes must be ordered for Lookup2D
    titles = {e.findtext("title").split(" bit $")[0] for e in root if e.tag in ("XDFTABLE", "XDFCONSTANT", "XDFFLAG")}
    in_xdf = {"2D", "2Dr", "3D", "3Dn", "grid", "fault", "cond"}
    missing = sorted(nm for nm, (lo, hi, it) in spans.items() if nm not in titles and it.get("kind", "scalar") in in_xdf | {"scalar"}
                     and not (it.get("kind") == "cond" and data[lo] == 0))
    if missing:
        warnings.append("%d items not in the XDF, e.g. %s" % (len(missing), ", ".join(missing[:5])))
    for a, t in cal.items.items():
        if t["kind"] == "2D" and data[a] > 1:
            xs = [data[a + 2 + 2 * j] for j in range(data[a])]
            if xs != sorted(xs) and xs != sorted(xs, reverse=True):
                warnings.append("%s: x axis not ordered: %s" % (t["name"], xs))
    for x in errors:
        print("ERROR " + x)
    for x in warnings if verbose else warnings[:40]:
        print("WARN  " + x)
    print("%s: %d elements, %d errors, %d warnings" % (os.path.basename(xdf), n, len(errors), len(warnings)))
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
