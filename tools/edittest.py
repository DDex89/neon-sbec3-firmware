#!/usr/bin/env python3
"""Edit test: change calibration in the source, rebuild, and check that only the intended bytes
change, that the XDF points at the same bytes, and that tools/fixsum.py repairs the checksum.

    python3 tools/edittest.py

Edits made in a copy of src/05293190AC/: one cell of the 3D table PartThrottleFuelMain, the
constant RevLimit and bit 5 of the option byte Options0337. No ROM image is needed.
"""
import os, re, shutil, sys, tempfile
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from asm16 import assemble
import json

PN = "05293190AC"


def build(src):
    files = sorted(os.path.join(src, f) for f in os.listdir(src) if f.endswith(".asm"))
    return assemble(files, json.load(open(os.path.join(ROOT, "tools", "variants.json")))[PN]["size"])


def edit(lines, label, fn):
    i = lines.index(label + ":\n")
    return fn(lines, i)


def main():
    src = os.path.join(ROOT, "src", PN)
    base = build(src)
    tmp = tempfile.mkdtemp()
    work = os.path.join(tmp, PN)
    shutil.copytree(src, work)
    path = os.path.join(work, "bank0.asm")
    L = open(path).readlines()
    want = {}

    def table_cell(L, i):  # 3D table: header line, column axis, rows; change row 5, column 3
        j = next(k for k in range(i, i + 40) if L[k].rstrip().endswith("; row 5"))
        vals = L[j].split("dc.b", 1)[1].split(";")[0].split(",")
        old = int(vals[3])
        vals[3] = " %d" % (old + 10 if old < 200 else old - 10)
        L[j] = "        dc.b    " + ",".join(v.strip() for v in vals) + " ; row 5\n"
        return old

    def first_byte(new):
        def f(L, i):
            m = re.match(r"(\s+dc\.b\s+)\$([0-9A-F]{2})(.*)", L[i + 1], re.S)
            old = int(m.group(2), 16)
            L[i + 1] = "%s$%02X%s" % (m.group(1), new(old), m.group(3))
            return old
        return f
    edit(L, "PartThrottleFuelMain", table_cell)
    edit(L, "RevLimit", first_byte(lambda v: v - 2))
    edit(L, "Options0337", first_byte(lambda v: v ^ 0x20))
    open(path, "w").writelines(L)
    img = bytearray(build(work))
    diff = [a for a in range(len(base)) if base[a] != img[a]]
    # where the XDF says these items are
    root = ET.parse(os.path.join(ROOT, "xdf", PN + ".xdf")).getroot()
    xdf = {}
    for e in root:
        t = e.findtext("title") or ""
        if t == "PartThrottleFuelMain":
            z = [a for a in e.findall("XDFAXIS") if a.get("id") == "z"][0].find("EMBEDDEDDATA")
            cols = int(z.get("mmedcolcount"))
            xdf["table"] = int(z.get("mmedaddress"), 0) + 5 * cols + 3
        elif t == "RevLimit":
            xdf["const"] = int(e.find("EMBEDDEDDATA").get("mmedaddress"), 0)
        elif t.startswith("Options0337 bit $20"):
            xdf["flag"] = int(e.find("EMBEDDEDDATA").get("mmedaddress"), 0)
    ok = sorted(diff) == sorted(xdf.values())
    print("changed bytes: %s" % ", ".join("$%05X" % a for a in diff))
    print("XDF cells:     %s" % ", ".join("%s $%05X" % (k, v) for k, v in sorted(xdf.items(), key=lambda x: x[1])))
    # checksum repair with tools/fixsum.py itself
    import subprocess
    hdr = (img[0x202] << 8) | img[0x203]
    target = img[hdr + 3]
    before = sum(img) & 0xFF
    edited = os.path.join(tmp, "edited.bin")
    open(edited, "wb").write(img)
    subprocess.run([sys.executable, os.path.join(ROOT, "tools", "fixsum.py"), edited, "--fix"], check=True,
                   stdout=subprocess.DEVNULL)
    img = bytearray(open(edited, "rb").read())
    after = sum(img) & 0xFF
    diff2 = [a for a in range(len(base)) if base[a] != img[a]]
    ok2 = after == target and set(diff2) - set(diff) <= {hdr + 13}
    print("checksum: sum $%02X before fix, $%02X after, target $%02X; correction byte $%05X" % (before, after, target, hdr + 13))
    shutil.rmtree(tmp)
    print("edit test %s" % ("passed" if ok and ok2 else "FAILED"))
    sys.exit(0 if ok and ok2 else 1)


if __name__ == "__main__":
    main()
