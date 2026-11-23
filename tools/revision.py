#!/usr/bin/env python3
"""Memory and code inventory of an image: what an improvement can use.

    python3 tools/revision.py roms/05007038.bin            # report as text (or build/05007038.bin)
    python3 tools/revision.py roms/05007038.bin --json     # the same as JSON

Flash: every byte is classed as code (decoded instructions), table (calibration items), constant,
vector or other; runs of at least 16 erased bytes ($FF) that are none of these count as free.
RAM: the offsets read or written by Z-relative instructions, the RAM areas that code points X/Y at
(16 bytes counted from each such pointer), and RAM offsets held in calibration lists; the rest is
unreferenced. The top of RAM is the stack (SP starts at the last word and grows down), so the
unreferenced run that touches it is not free.
Routines: one-instruction stubs (RTS), and routines whose first instruction skips almost the whole
body on an option bit that this calibration leaves off ("off here").
"""
import collections, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import gen_source as g
from port import ops

WORD = {"LDD", "STD", "CPD", "ADDD", "SUBD", "LDE", "STE", "CPE", "ADDE", "SUBE", "ADCD", "ADCE",
        "SBCD", "SBCE", "ANDD", "ANDE", "ORD", "ORE", "EORD", "EORE", "LDX", "STX", "CPX", "LDY",
        "STY", "CPY", "LDZ", "STZ", "LDS", "STS", "CPS"}
LISTS = ("bitmaps", "words", "monitors", "optbits", "cond", "faultmap")


def inventory(path):
    d = open(path, "rb").read()
    pn = os.path.splitext(os.path.basename(path))[0]
    own, ref = g.annotation_set(d, pn)
    extra = [(int(x, 16), "unreached") for x in own("analysis.json").get("unreached_code", [])]
    an = g.Analysis(d).run(extra=extra)
    names = g.Names(an, d, own, ref)
    cal = g.Calibration(d, an, names, own)
    out = {"image": pn, "size": len(d), "instructions": len(an.insn)}

    cls = bytearray(len(d))     # 0 other, 1 code, 2 tables, 3 constants, 4 vectors
    for a, i in an.insn.items():
        cls[a:a + i.size] = bytes([1]) * i.size
    for a, it in cal.items.items():
        n = min(it["size"], len(d) - a)
        cls[a:a + n] = bytes([2]) * n
    for a in cal.scalars:
        cls[a] = 3
    cls[0:0x200] = bytes([4]) * 0x200
    banks = []
    for b in range((len(d) + 0xFFFF) // 0x10000):
        lo, hi = b * 0x10000, min(len(d), (b + 1) * 0x10000)
        c, runs, i = collections.Counter(), [], lo
        while i < hi:
            if cls[i] == 0 and d[i] == 0xFF:
                j = i
                while j < hi and cls[j] == 0 and d[j] == 0xFF:
                    j += 1
                if j - i >= 16:
                    runs.append((i, j - i))
                    c["free"] += j - i
                else:
                    c["other"] += j - i
                i = j
            else:
                c[("other", "code", "tables", "constants", "vectors")[cls[i]]] += 1
                i += 1
        runs.sort(key=lambda r: -r[1])
        banks.append(dict(bank=b, **{k: c.get(k, 0) for k in ("code", "tables", "constants", "vectors", "other", "free")},
                          largest=["$%05X (%d)" % r for r in runs[:4]]))
    out["flash"] = banks

    size = 0x800 if len(d) <= 0x20000 else 0x1000
    used, ptrs = collections.Counter(), set()
    for a, i in an.insn.items():
        v = ops(i)
        if i.mode.endswith(", Z"):
            for f in ("ff", "gggg"):
                if f in v and v[f] < size:
                    used[v[f]] += 1
                    if i.mn in WORD or i.mn.endswith("W"):
                        used[v[f] + 1] += 1
        if i.mode.startswith("IMM16") and 0x8000 <= v.get("jjkk", 0) < 0x8000 + size and i.mn in ("LDX", "LDY", "LDZ", "CPX", "CPY", "LDD", "LDE", "ADDD"):
            ptrs.add(v["jjkk"] - 0x8000)
    for a, it in cal.items.items():
        if it.get("kind") in LISTS:
            for p in range(a, a + it["size"] - 1, 2):
                w = (d[p] << 8) | d[p + 1]
                if 0 < w < size:
                    used[w] += 1
    for p in ptrs:
        if p >= size - 0x40:        # loop bounds of the RAM test and stack checks, not data
            continue
        for k in range(16):
            used[p + k] += 1
    runs, i = [], 0
    while i < size:
        if not used[i]:
            j = i
            while j < size and not used[j]:
                j += 1
            runs.append((i, j - i))
            i = j
        else:
            i += 1
    stack = [r for r in runs if r[0] + r[1] >= size - 0x10]
    free = [r for r in runs if r not in stack]
    out["ram"] = dict(size=size, referenced=sum(1 for k in range(size) if used[k]),
                      stack_gap="$%04X-$%04X" % (stack[0][0], size - 1) if stack else None,
                      unreferenced=sum(n for a, n in free), in_runs_of_8=sum(n for a, n in free if n >= 8),
                      largest=["$%04X (%d)" % r for r in sorted(free, key=lambda r: -r[1])[:6]])

    # routines, from the analysis: starts are call targets, vectors and named routines
    starts = sorted(set(names.callers) | set(names.routines) | {a for a, v in names.vec_of.items() if len(v) < 8} |
                    {a for a, _ in extra})
    starts = [a for a in starts if a in an.insn]
    optval = {v["name"]: d[a] for a, v in cal.scalars.items() if v["name"].startswith("Options")}
    stubs, off = [], []
    for k, a in enumerate(starts):
        end = starts[k + 1] if k + 1 < len(starts) else len(d)
        body = [an.insn[x] for x in sorted(an.insn) if a <= x < end]
        nbytes = sum(x.size for x in body)
        name = names.labels.get(a, "$%05X" % a)
        if len(body) == 1 and body[0].mn == "RTS" or (body and body[0].mn == "RTS"):
            stubs.append(name)
            continue
        x = body[0] if body else None
        if x is not None and x.mn in ("BRCLR", "BRSET") and x.mode == "EXT" and x.target() is not None:
            v = ops(x)
            opt = cal.labels.get(v["hhll"])
            if opt in optval and x.target() >= a + 0.8 * nbytes:
                bit = optval[opt] & v["mm"]
                if (x.mn == "BRCLR" and not bit) or (x.mn == "BRSET" and bit):
                    off.append(dict(name=name, bytes=nbytes, test="%s %s #$%02X" % (x.mn, opt, v["mm"])))
    out["routines"] = len(starts)
    out["stubs"] = stubs
    out["off_here"] = off
    out["unreached"] = [names.labels.get(int(x, 16), x) for x in own("analysis.json").get("unreached_code", [])]
    return out


def main():
    r = inventory(sys.argv[1])
    if "--json" in sys.argv:
        print(json.dumps(r, indent=1))
        return
    print("%s: %d KB, %d routines, %d instructions" % (r["image"], r["size"] // 1024, r["routines"], r["instructions"]))
    for b in r["flash"]:
        print("  bank %d: code %d, tables %d, constants %d, vectors %d, other %d, free %d; largest free: %s" % (
            b["bank"], b["code"], b["tables"], b["constants"], b["vectors"], b["other"], b["free"], ", ".join(b["largest"])))
    m = r["ram"]
    print("  RAM %d bytes: %d referenced, %d unreferenced (%d in runs of 8 or more), stack area from %s; largest: %s" % (
        m["size"], m["referenced"], m["unreferenced"], m["in_runs_of_8"], m["stack_gap"], ", ".join(m["largest"])))
    print("  stubs: %s" % (", ".join(r["stubs"]) or "none"))
    print("  off here: %s" % (", ".join("%s (%d bytes, %s)" % (o["name"], o["bytes"], o["test"]) for o in r["off_here"]) or "none"))
    print("  unreached: %s" % (", ".join(r["unreached"]) or "none"))


if __name__ == "__main__":
    main()
