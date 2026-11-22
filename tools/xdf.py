#!/usr/bin/env python3
"""Write a TunerPro XDF definition for an SBEC3 image.

    python3 tools/xdf.py roms/05293190AC.bin xdf/05293190AC.xdf

Every calibration table found by tools/caltables.py goes in, named ones in their category and the
rest under "Unidentified" (grouped by the routine that reads them), plus the named constants and
the fault table. Units come from annotations/tables.json and, for unnamed tables, from the input
variable (EngineRpm -> rpm, CoolantTemp -> deg C, Map -> kPa ...). Rows of a 3D table that are
selected through a MAP scale table are labelled with the MAP value of each row, computed from the
scale table in this image: if you change the scale table, the labels are only refreshed by
generating the XDF again.

The image checksum is not handled by TunerPro here: run tools/fixsum.py on the edited file.
"""
import os, re, sys
from xml.etree.ElementTree import Element, SubElement, ElementTree, indent

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from analyse import Analysis
from gen_source import Calibration, Names, annotation_set
from xref import Xref

# unit -> (equation, unit text, decimals)
UNITS = {
    "rpm32": ("X*32", "rpm", 0),
    "rpm8": ("X*8", "rpm", 0),
    "rpmw": ("X/8", "rpm", 0),
    "kpa": ("X/2.428", "kPa", 1),
    "spark": ("X/2", "deg BTDC", 1),
    "tempc": ("X-128", "deg C", 0),
    "volt16": ("X/16.19", "V", 2),
    "volt51": ("X/51", "V", 2),
    "pwus32": ("X*32", "us", 0),
    "mult256": ("X/256", "factor", 3),
    "pos256": ("X", "position 0-255", 0),
    "fuelcorr": ("X*100/256", "% change", 1),
    "raw": ("X", "", 0),
}
INPUT_UNITS = {"EngineRpm": "rpm32", "CoolantTemp": "tempc", "AirTemp": "tempc", "Map": "kpa", "Baro": "kpa",
               "ManifoldVacuum": "kpa", "MapLast": "kpa", "BatteryVolts": "volt16", "BatteryVolts2": "volt16"}
CATEGORY_WORDS = [("Fuel", "Fuel"), ("Injector", "Fuel"), ("Spark", "Spark"), ("Knock", "Spark"),
                  ("Idle", "Idle"), ("Thermistor", "Sensors"), ("Throttle", "Sensors"),
                  ("RevLimit", "Limits"), ("SpeedLimit", "Limits"), ("Fault", "Faults")]
FAULT_FIELDS = ["row", "count", "blink", "attr", "mask", "byte", "P hi", "P lo", "spare", "spare"]


class Xdf:
    def __init__(self, title, size, desc):
        self.root = Element("XDFFORMAT", version="1.60")
        h = SubElement(self.root, "XDFHEADER")
        SubElement(h, "flags").text = "0x1"
        SubElement(h, "deftitle").text = title
        SubElement(h, "description").text = desc
        SubElement(h, "BASEOFFSET", offset="0", subtract="0")
        SubElement(h, "DEFAULTS", datasizeinbits="8", sigdigits="4", outputtype="1", signed="0",
                   lsbfirst="0", float="0")
        SubElement(h, "REGION", type="0xFFFFFFFF", startaddress="0x0", size="0x%X" % size, regionflags="0x0",
                   name="Binary", desc="SBEC3 flash image")
        self.header = h
        self.cats = []
        self.uid = 0x100

    def category(self, name):
        if name not in self.cats:
            SubElement(self.header, "CATEGORY", index="0x%X" % len(self.cats), name=name)
            self.cats.append(name)
        return self.cats.index(name) + 1

    def next_id(self):
        self.uid += 1
        return "0x%X" % self.uid

    def item(self, tag, title, desc, cats):
        e = SubElement(self.root, tag, uniqueid=self.next_id(), flags="0x0")
        SubElement(e, "title").text = title
        SubElement(e, "description").text = desc
        for i, c in enumerate(cats):
            SubElement(e, "CATEGORYMEM", index=str(i), category=str(self.category(c)))
        return e

    @staticmethod
    def math(e, eq):
        m = SubElement(e, "MATH", equation=eq)
        SubElement(m, "VAR", id="X")

    def embedded_axis(self, t, axis, addr, count, unit, stride=8):
        eq, text, dec = UNITS[unit]
        a = SubElement(t, "XDFAXIS", id=axis, uniqueid="0x0")
        SubElement(a, "EMBEDDEDDATA", mmedtypeflags="0x00", mmedaddress="0x%X" % addr, mmedelementsizebits="8",
                   mmedcolcount=str(count), mmedmajorstridebits=str(stride), mmedminorstridebits="0")
        SubElement(a, "units").text = text
        SubElement(a, "indexcount").text = str(count)
        SubElement(a, "decimalpl").text = str(dec)
        SubElement(a, "embedinfo", type="1")
        SubElement(a, "outputtype").text = "1"
        SubElement(a, "DALINK", index="0")
        self.math(a, eq)

    def label_axis(self, t, axis, labels, text=""):
        a = SubElement(t, "XDFAXIS", id=axis, uniqueid="0x0")
        SubElement(a, "units").text = text
        SubElement(a, "indexcount").text = str(len(labels))
        SubElement(a, "outputtype").text = "4"
        SubElement(a, "DALINK", index="0")
        self.math(a, "X")
        for i, v in enumerate(labels):
            SubElement(a, "LABEL", index=str(i), value=v)

    def zdata(self, t, addr, rows, cols, unit, signed, major=0, output="1"):
        eq, text, dec = UNITS[unit]
        a = SubElement(t, "XDFAXIS", id="z")
        SubElement(a, "EMBEDDEDDATA", mmedtypeflags="0x01" if signed else "0x00", mmedaddress="0x%X" % addr,
                   mmedelementsizebits="8", mmedrowcount=str(rows), mmedcolcount=str(cols),
                   mmedmajorstridebits=str(major), mmedminorstridebits="0")
        SubElement(a, "units").text = text
        SubElement(a, "decimalpl").text = str(dec)
        SubElement(a, "outputtype").text = output
        self.math(a, eq)

    def write(self, path):
        indent(self.root, space=" ")
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        ElementTree(self.root).write(path, encoding="utf-8", xml_declaration=True)


def fmt(v, dec):
    return ("%%.%df" % dec) % v


def scale_positions(d, sa, nrows):
    """MAP (raw) at the row positions of a 3D table, by inverting the 2D scale table at sa."""
    n = d[sa]
    pts = [(d[sa + 2 + 2 * i], d[sa + 3 + 2 * i]) for i in range(n)]
    out = []
    for r in range(nrows):
        pos = min(255, r * 256 / max(1, nrows - 1))
        x = pts[-1][0]
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            if y0 <= pos <= y1 and y1 != y0:
                x = x0 + (pos - y0) * (x1 - x0) / (y1 - y0)
                break
        else:
            if pos <= pts[0][1]:
                x = pts[0][0]
        out.append(x)
    return out


def main():
    path, out = sys.argv[1], sys.argv[2]
    d = open(path, "rb").read()
    pn = os.path.splitext(os.path.basename(path))[0]
    an = Analysis(d).run()
    own, ref = annotation_set(d, pn)
    names = Names(an, d, own, ref)
    cal = Calibration(d, an, names, own)
    x = Xref(d, an)

    def var(s):
        m = re.match(r"^\$([0-9A-F]{2,4}),Z$", s or "")
        return names.ram.get(int(m.group(1), 16)) if m else None

    def input_unit(s):
        return INPUT_UNITS.get(var(s), "raw")

    def category(t):
        nm = t["name"]
        if t.get("cur", {}).get("category"):
            return [t["cur"]["category"]]
        for w, c in CATEGORY_WORDS:
            if w in nm:
                return [c]
        o = {names.labels.get(x.owner(c)) for c in t.get("calls", [])} - {None}
        o = sorted(n for n in o if not re.match(r"^(Sub_|L)[0-9A-F]{5}$", n))
        return ["Unidentified"] + (["Unidentified: " + o[0]] if o else [])

    title = "SBEC3 %s" % pn
    X = Xdf(title, len(d), "Generated by tools/xdf.py from github.com/DDex89/neon-sbec3-firmware. Unnamed tables "
            "are under Unidentified. Fix the checksum with tools/fixsum.py before flashing.")
    n_named = n_tables = 0
    for a in sorted(cal.items):
        t = cal.items[a]
        c = t.get("cur", {})
        kind = t["kind"]
        named = not re.match(r"^Tab", t["name"])
        n_named += named
        n_tables += 1
        inputs = list(t.get("inputs", {}))
        desc = (c.get("desc", "") + " " if c.get("desc") else "") + "$%04X, %s; inputs: %s" % (
            a, kind, cal.input_text(t) or "?")
        cats = category(t)
        if kind in ("2D", "2Dr"):
            n = d[a]
            if n == 0 or n > 64:
                continue
            xu = c.get("x") or (input_unit(inputs[0][0]) if inputs else "raw")
            if inputs and inputs[0][0].startswith("result of"):
                xu = c.get("x", "pos256")
            yu = c.get("y", "raw")
            signed = kind == "2D" and d[a + 1] == 0x20
            e = X.item("XDFTABLE", t["name"], desc, cats)
            X.label_axis(e, "x", ["value"])
            xa, ya = (a + 2, a + 3) if kind == "2D" else (a + 3, a + 2)
            X.embedded_axis(e, "y", xa, n, xu, stride=16)
            X.zdata(e, ya, n, 1, yu, signed, major=16)
        elif kind in ("3D", "3Dn"):
            ny, nx, sg = d[a], d[a + 1], d[a + 2]
            zu = c.get("z", "raw")
            e = X.item("XDFTABLE", t["name"], desc, cats)
            p = a + 3
            if kind == "3D":
                xu = c.get("x") or (input_unit(inputs[0][1]) if inputs and len(inputs[0]) > 1 else "raw")
                X.embedded_axis(e, "x", p, nx, xu)
                p += nx
            else:
                X.label_axis(e, "x", [str(round(i * 255 / max(1, nx - 1))) for i in range(nx)], "position 0-255")
            rf = list(t.get("row_from", {}))
            if rf and rf[0] in cal.items:
                sa = rf[0]
                st = cal.items[sa]
                su = st.get("cur", {}).get("x") or (input_unit(list(st.get("inputs", {}))[0][0])
                                                    if st.get("inputs") else "raw")
                eq, text, dec = UNITS[su]
                vals = scale_positions(d, sa, ny)
                conv = {"kpa": lambda v: v / 2.428, "rpm32": lambda v: v * 32, "tempc": lambda v: v - 128}.get(su, lambda v: v)
                X.label_axis(e, "y", [fmt(conv(v), dec) for v in vals], "%s (rows set by %s)" % (text, st["name"]))
            else:
                X.label_axis(e, "y", [str(round(r * 255 / max(1, ny - 1))) for r in range(ny)], "row position 0-255")
            X.zdata(e, p, ny, nx, zu, sg != 0)
        elif kind == "grid":
            e = X.item("XDFTABLE", t["name"], (c.get("desc") or "") + " $%04X" % a, [c.get("category", "Other")])
            X.label_axis(e, "x", [str(i + 1) for i in range(t["cols"])])
            X.label_axis(e, "y", [str(i + 1) for i in range(t["rows"])])
            X.zdata(e, a, t["rows"], t["cols"], "raw", False)
        elif kind == "fault":
            rows = t["rows"]
            e = X.item("XDFTABLE", t["name"], (c.get("desc") or "") + " $%04X" % a, ["Faults"])
            X.label_axis(e, "x", FAULT_FIELDS)
            labels = []
            for r in range(rows):
                b = d[a + 10 * r:a + 10 * r + 10]
                labels.append("%d P%02X%02X" % (r, b[6], b[7]) if b[6] or b[7] else str(r))
            X.label_axis(e, "y", labels)
            X.zdata(e, a, rows, 10, "raw", False, output="3")
    n_flags = 0
    for a in sorted(cal.scalars):
        v = cal.scalars[a]
        cat = [v["category"]] if v.get("category") else next(([c] for w, c in CATEGORY_WORDS if w in v["name"]),
                                                              ["Constants"])
        if v.get("bits"):
            bn = v.get("bitnames", {})
            for m in v["bits"]:
                e = X.item("XDFFLAG", "%s bit $%s%s" % (v["name"], m, " " + bn[m] if m in bn else ""),
                           v.get("desc", "") + " $%04X mask $%s" % (a, m), cat)
                SubElement(e, "EMBEDDEDDATA", mmedaddress="0x%X" % a, mmedelementsizebits="8")
                SubElement(e, "mask").text = "0x%s" % m
                n_flags += 1
            continue
        u = v.get("unit", "raw")
        eq, text, dec = UNITS.get(u, UNITS["raw"])
        e = X.item("XDFCONSTANT", v["name"], v.get("desc", "") + " $%04X" % a, cat)
        SubElement(e, "EMBEDDEDDATA", mmedaddress="0x%X" % a, mmedelementsizebits=str(8 * v.get("size", 1)),
                   mmedtypeflags="0x00")
        SubElement(e, "units").text = text
        SubElement(e, "decimalpl").text = str(dec)
        SubElement(e, "outputtype").text = "1"
        Xdf.math(e, eq)
    X.write(out)
    print("%s: %d tables (%d named), %d constants, %d flags, %d categories" % (
        out, n_tables, n_named, len(cal.scalars), n_flags, len(X.cats)))


if __name__ == "__main__":
    main()
