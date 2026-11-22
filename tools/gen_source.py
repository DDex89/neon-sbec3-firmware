#!/usr/bin/env python3
"""Generate annotated assembly source for an SBEC3 flash image.

    python3 tools/gen_source.py roms/05293190AC.bin src/05293190AC

Writes 00_equates.asm (register and RAM symbols) and one file per 64 KB bank (bank0.asm ...).
Code found by tools/analyse.py is written as instructions, everything else as dc.b. Names and
notes come from annotations/:

  labels.json             code labels                 vectors.json   exception vector names
  ram.json                RAM offsets from Z          hc16z_registers.json   module registers
  routines.md             routine notes               analysis.json  where Z is not the RAM base

The source assembles back into the identical image with tools/build.py.
"""
import collections, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from analyse import Analysis
from syntax16 import format_insn

BANK = 0x10000
ANN = os.path.join(ROOT, "annotations")
Z_BASE = 0xF8000


def load(name, default=None):
    p = os.path.join(ANN, name)
    if not os.path.exists(p):
        return default if default is not None else {}
    d = json.load(open(p, encoding="utf-8"))
    if isinstance(d, dict):
        d.pop("_comment", None)
    return d


def load_routines():
    """annotations/routines.md: '## XXXXX Name' headings followed by note lines."""
    p = os.path.join(ANN, "routines.md")
    out = {}
    if not os.path.exists(p):
        return out
    cur = None
    for line in open(p, encoding="utf-8"):
        m = re.match(r"^## ([0-9A-F]{5}) (\S+)", line)
        if m:
            cur = int(m.group(1), 16)
            out[cur] = {"name": m.group(2), "text": []}
        elif cur is not None and not line.startswith("# "):
            out[cur]["text"].append(line.rstrip("\n"))
    for v in out.values():
        while v["text"] and not v["text"][-1].strip():
            v["text"].pop()
        while v["text"] and not v["text"][0].strip():
            v["text"].pop(0)
    return out


class Names:
    def __init__(self, an, data):
        self.an = an
        self.labels_ann = {int(k, 16): v for k, v in load("labels.json").items()}
        self.vectors = {int(k, 16): v for k, v in load("vectors.json").items()}
        self.ram = {int(k, 16): v for k, v in load("ram.json").items()}
        self.regs = {int(k, 16): v["name"] for k, v in load("hc16z_registers.json").items()}
        self.routines = load_routines()
        self.z_not_base = [(int(a, 16), int(b, 16)) for a, b, *_ in load("analysis.json").get("z_not_base", [])]
        self.callers = collections.defaultdict(list)
        for a, i in an.insn.items():
            if i.mn in ("JSR", "LBSR", "BSR") and i.target() is not None:
                self.callers[i.target()].append(a)
        self.vec_of = collections.defaultdict(list)
        for n in range(4, 256):
            t = (data[2 * n] << 8) | data[2 * n + 1]
            self.vec_of[t].append(n)
        self.labels = {}
        for a in an.labels:
            if a < len(data):
                self.labels[a] = self.name(a)
        for a, r in self.routines.items():
            self.labels.setdefault(a, r["name"])
        self.used = {}

    def name(self, a):
        if a in self.labels_ann:
            return self.labels_ann[a]
        if a in self.routines:
            return self.routines[a]["name"]
        vs = [n for n in self.vec_of.get(a, []) if n in self.vectors]
        if a != self.an.vectors()[0][0] and len(self.vec_of.get(a, [])) < 8 and vs:
            return self.vectors[vs[0]]
        if a in self.an.tables:
            return "JumpTable_%05X" % a
        if a in self.callers:
            return "Sub_%05X" % a
        return "L%05X" % a

    def zsym_for(self, addr):
        if any(lo <= addr < hi for lo, hi in self.z_not_base):
            return None

        def z(off):
            if off in self.ram:
                s = self.ram[off]
            elif 0x7000 <= off < 0x8000 and (Z_BASE + off) & 0xFFFFF in self.regs:
                s = self.regs[(Z_BASE + off) & 0xFFFFF].replace("/", "")
            elif 0x7000 <= off < 0x8000 and off & 1 and (Z_BASE + off - 1) & 0xFFFFF in self.regs:
                # byte access to the low half of a 16-bit register
                s = self.regs[(Z_BASE + off - 1) & 0xFFFFF].replace("/", "") + "_L"
            else:
                return None
            self.used[s] = off
            return s
        return z


def header(names, a):
    nm = names.labels.get(a, "L%05X" % a)
    out = [";" + "-" * 99, "; %s ($%05X)" % (nm, a)]
    vecs = names.vec_of.get(a, [])
    if vecs and len(vecs) < 8:
        out.append("; Vector%s %s" % ("s" if len(vecs) > 1 else "", ", ".join("$%02X" % v for v in vecs)))
    cl = sorted(names.callers.get(a, []))
    if cl:
        own = []
        for c in cl:
            o = names.labels.get(names.owner(c), "$%05X" % c)
            if o not in own:
                own.append(o)
        out.append("; Called from: " + ", ".join(own[:8]) +
                   (" and %d more routines" % (len(own) - 8) if len(own) > 8 else "") +
                   (" (%d calls)" % len(cl) if len(cl) > len(own) else ""))
    r = names.routines.get(a)
    if r:
        out.append(";")
        out += ["; " + t if t else ";" for t in r["text"]]
    out.append(";" + "-" * 99)
    return out


def generate(image_path, outdir):
    data = open(image_path, "rb").read()
    an = Analysis(data).run()
    names = Names(an, data)
    lab = names.labels.get
    vec_names = names.vectors

    # routine starts: call targets, vector handlers, annotated routines
    starts = set(names.callers) | set(names.routines) | \
        {a for a, v in names.vec_of.items() if len(v) < 8} | {an.vectors()[0][0]}
    # owner of an address = nearest preceding routine start (for "Called from")
    sorted_starts = sorted(starts)
    import bisect

    def owner(a):
        i = bisect.bisect_right(sorted_starts, a) - 1
        return sorted_starts[i] if i >= 0 else a
    names.owner = owner

    os.makedirs(outdir, exist_ok=True)
    files = []
    for bank in range(0, len(data), BANK):
        end = min(bank + BANK, len(data))
        lines = ["; %s, bank %X ($%05X-$%05X)" % (os.path.basename(image_path), bank >> 16, bank, end - 1),
                 "; Generated by tools/gen_source.py from the annotations in annotations/.", "",
                 "        org     $%05X" % bank, ""]
        a = bank
        while a < end:
            if a in starts and a in an.insn:
                lines.append("")
                lines += header(names, a)
            if a in names.labels:
                lines.append("%s:" % names.labels[a])
            if a < 0x200 and a not in an.insn:
                w = (data[a] << 8) | data[a + 1]
                n = a // 2
                if a in (0, 4, 6):
                    what = {0: "reset: ZK, SK, PK", 4: "reset: initial SP", 6: "reset: initial IZ"}[a]
                    lines.append("        dc.w    $%04X                ; %s" % (w, what))
                else:
                    tgt = names.labels.get(w, "$%04X" % w)
                    lines.append("        dc.w    %-20s ; vector $%02X%s" % (
                        tgt, n, " " + vec_names[n] if n in vec_names and n >= 4 else (" reset: initial PC" if a == 2 else "")))
                a += 2
                continue
            ins = an.insn.get(a)
            if ins is not None:
                mn, ops = format_insn(ins, lab, names.zsym_for(a))
                lines.append("        %-7s %s" % (mn, ops) if ops else "        %s" % mn)
                a += ins.size
                continue
            run = []
            while a < end and a not in an.insn and len(run) < 16 and not (run and a in names.labels):
                run.append(data[a]); a += 1
            lines.append("        dc.b    " + ",".join("$%02X" % b for b in run))
        name = "bank%X.asm" % (bank >> 16)
        open(os.path.join(outdir, name), "w").write("\n".join(lines) + "\n")
        files.append(name)
    eq = ["; Symbols used in the source: module registers and RAM variables, as offsets from Z.",
          "; Z holds $F8000 (ZK = $F, IZ = $8000) everywhere except where annotations/analysis.json",
          "; says otherwise, so `SYM,Z` addresses $F8000 + SYM. Generated by tools/gen_source.py.", ""]
    for s, off in sorted(names.used.items(), key=lambda x: x[1]):
        eq.append("%-16s equ $%04X        ; $%05X" % (s, off, (Z_BASE + off) & 0xFFFFF))
    open(os.path.join(outdir, "00_equates.asm"), "w").write("\n".join(eq) + "\n")
    return an, files


def main():
    an, files = generate(sys.argv[1], sys.argv[2])
    cov = sum(i.size for i in an.insn.values())
    print("%d instructions (%d bytes), %d labels, %d jump tables, %d unresolved indirect jumps, "
          "%d jumps into RAM, %d problems" % (len(an.insn), cov, len(an.labels), len(an.tables), len(an.indirect), len(an.ram_jumps),
                           len(an.problems)))


if __name__ == "__main__":
    main()
