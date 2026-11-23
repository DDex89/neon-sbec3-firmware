#!/usr/bin/env python3
"""Generate annotated assembly source for an SBEC3 flash image.

    python3 tools/gen_source.py roms/05293190AC.bin src/05293190AC

Writes 00_equates.asm (register and RAM symbols) and one file per 64 KB bank (bank0.asm ...).
Code found by tools/analyse.py is written as instructions, everything else as dc.b. Names and
notes come from annotations/:

  labels.json             code labels                 vectors.json   exception vector names
  ram.json                RAM offsets from Z          hc16z_registers.json   module registers
  routines.md             routine notes               analysis.json  where Z is not the RAM base
  tables.json             calibration tables and constants (with tools/caltables.py)

The image-specific files (labels, ram, routines, analysis, tables) belong to the reference image
05293190AC. Other images use the set that tools/port.py carried over into annotations/ports/<PN>/
(routine notes stay with the reference). Vectors, registers and the table layout apply to every image.

The source assembles back into the identical image with tools/build.py.
"""
import collections, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from analyse import Analysis
from syntax16 import format_insn
import caltables

BANK = 0x10000
ANN = os.path.join(ROOT, "annotations")
Z_BASE = 0xF8000
REFERENCE = "05293190AC"


def is_reference(data):
    import hashlib
    v = json.load(open(os.path.join(ROOT, "tools", "variants.json")))[REFERENCE]
    return hashlib.sha256(data).hexdigest() == v["sha256"]


def annotation_set(data, pn):
    """Loader for the image-specific annotations: the reference files, or the set carried over
    by tools/port.py (annotations/ports/<PN>/, checked against the image's SHA-256)."""
    import hashlib
    if is_reference(data):
        return load, True
    d = os.path.join(ANN, "ports", pn)
    st = os.path.join(d, "stats.json")
    if os.path.exists(st) and json.load(open(st)).get("sha256") == hashlib.sha256(data).hexdigest():
        return (lambda name: load(os.path.join("ports", pn, name))), False
    return (lambda name: {}), False


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
    def __init__(self, an, data, own=load, ref=True):
        self.an = an
        self.labels_ann = {int(k, 16): v for k, v in own("labels.json").items()}
        for a, kind in caltables.routines(data).items():
            self.labels_ann.setdefault(a, caltables.NAMES[kind])
        self.vectors = {int(k, 16): v for k, v in load("vectors.json").items()}
        self.ram = {int(k, 16): v for k, v in own("ram.json").items()}
        self.regs = {int(k, 16): v["name"] for k, v in load("hc16z_registers.json").items()}
        self.routines = load_routines() if ref else {}
        self.z_not_base = [(int(a, 16), int(b, 16)) for a, b, *_ in own("analysis.json").get("z_not_base", [])]
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
        self.bits = {k: v for k, v in load("bits.json").items() if isinstance(v, dict)}
        if ref:
            self.bits.update(fault_bits(data))

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

    def bit_note(self, ins, addr, extsym):
        """Meaning of the bits a BSET/BCLR/BRSET/BRCLR touches, from annotations/bits.json."""
        if ins.mn not in BIT_OPS or not self.bits:
            return None
        v = dict(ins.vals)
        wide = ins.mn.endswith("W")
        mask = v.get("mmmm" if wide else "mm")
        if mask is None:
            return None
        if ins.mode.endswith("Z") and ("ff" in v or "gggg" in v):
            z = self.zsym_for(addr)
            off = v.get("ff", v.get("gggg"))
            sym_of = (lambda o: z(o)) if z else (lambda o: None)
        elif ins.mode == "EXT" and not wide:
            off = v["hhll"]
            sym_of = extsym
        else:
            return None
        parts = []
        for b in range(15 if wide else 7, -1, -1):
            if not mask >> b & 1:
                continue
            o, bit = (off + (0 if b >= 8 else 1), b & 7) if wide else (off, b)
            sym = sym_of(o)
            text = self.bits.get(sym, {}).get(str(bit)) if sym else None
            if text:
                parts.append(("%s.%d: %s" % (sym, bit, text)) if wide else ("bit %d: %s" % (bit, text)))
        return "; ".join(parts) or None

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


FAULT_TABLE, FAULT_ROWS = 0x4052, 224


def fault_bits(data):
    """FaultSetNN / FaultMemNN bit -> P-code, from the fault table of the reference image
    (row: index, count, ?, flags, bit mask, byte offset, P-code)."""
    out = collections.defaultdict(dict)
    for r in range(FAULT_ROWS):
        row = data[FAULT_TABLE + 10 * r:FAULT_TABLE + 10 * r + 10]
        if row[0] != r or bin(row[4]).count("1") != 1 or row[5] >= 0x1C:
            continue
        code = "P%02X%02X" % (row[6], row[7])
        text = code if code != "P0000" else "fault row $%02X, no P-code" % r
        for arr in ("FaultSet", "FaultMem"):
            out["%s%02X" % (arr, row[5])][str(row[4].bit_length() - 1)] = text
    return out


BIT_OPS = ("BSET", "BCLR", "BRSET", "BRCLR", "BSETW", "BCLRW")
PREFIX = {"2D": "Tab2D_", "2Dr": "Tab2DR_", "3D": "Tab3D_", "3Dn": "Tab3DN_"}
FLAGS2D = {0x80: "unsigned", 0x40: "unsigned, y = 0 counts as 256", 0x20: "signed", 0x10: "steps, no interpolation",
           0x00: "unsigned"}


class Calibration:
    """Calibration tables and constants in bank 0, laid out as structured dc.b blocks."""

    def __init__(self, data, an, names, own=load):
        self.data = data
        self.names = names
        found = caltables.find(data, an)[1]
        cur = own("tables.json")
        units = cur.get("units", {})
        self.units = units
        curated = {int(k, 16): v for k, v in cur.get("tables", {}).items()}
        self.items = {}
        for a, t in found.items():
            if any(x in an.insn for x in range(a, a + t["size"])):
                continue
            c = curated.get(a, {})
            self.items[a] = dict(t, name=c.get("name", PREFIX[t["kind"]] + "%04X" % a), cur=c)
        for k, v in cur.get("special", {}).items():
            a = int(k, 16)
            v = dict(v)
            if v.get("kind") == "fault":
                # rows are numbered in byte 0; the table ends where the numbering stops
                n = 0
                while n < 256 and a + v["row_size"] * (n + 1) <= len(data) and data[a + v["row_size"] * n] == n:
                    n += 1
                v["rows"] = n
            self.items[a] = dict(v, size=v["rows"] * v["row_size"], cur=v, calls=[])
        self.add_condition_tables(an)
        # a table that overlaps the one before it cannot be laid out; keep the first
        end = -1
        for a in sorted(self.items):
            if a < end:
                del self.items[a]
            else:
                end = a + self.items[a]["size"]
        self.scalars = {}
        for k, v in cur.get("scalars", {}).items():
            a = int(k, 16)
            if not any(lo <= a < lo + t["size"] for lo, t in self.items.items()):
                self.scalars[a] = v
        self.labels = {a: t["name"] for a, t in self.items.items()}
        self.labels.update({a: v["name"] for a, v in self.scalars.items()})

    def add_condition_tables(self, an):
        """Condition lists read by ConditionTable (count, then 4-byte entries: RAM offset, test, mask),
        found from LDY #table before JSR ConditionTable and from the OBD monitor table."""
        d = self.data
        rev = {v: k for k, v in self.names.labels_ann.items()}
        ct = rev.get("ConditionTable")
        found = {}
        if ct is not None:
            order = sorted(an.insn)
            idx = {a: n for n, a in enumerate(order)}
            for a, i in an.insn.items():
                if i.mn == "JSR" and i.target() == ct:
                    for k in range(idx[a] - 1, max(idx[a] - 4, 0), -1):
                        j = an.insn[order[k]]
                        y = dict(j.vals).get("jjkk")
                        if j.mn == "LDY" and y is not None:
                            starts = [x for x in self.names.labels_ann if x <= a]
                            caller = self.names.labels_ann[max(starts)] if starts else None
                            found.setdefault(y, (caller or "Cond", []))[1].append(a)
                            break
        for a, t in list(self.items.items()):
            if t.get("kind") == "monitors":
                for r in range(t["rows"]):
                    row = a + r * t["row_size"]
                    st = self.names.ram.get(int.from_bytes(d[row + 2:row + 4], "big"), "Monitor%d" % r)
                    for n in range(3):
                        y = int.from_bytes(d[row + 8 + 2 * n:row + 10 + 2 * n], "big")
                        found.setdefault(y, ("%sConds%d" % (st.replace("MonStatus", ""), n + 1), []))
        used = {}
        for y, (base, calls) in sorted(found.items()):
            if y >= 0x8000 or y + 1 > len(d) or y in self.items:
                continue
            size = 1 + 4 * d[y]
            if any(x in an.insn for x in range(y, y + size)):
                continue
            name = base if base.endswith(("1", "2", "3")) and "Conds" in base else base + "Conds"
            used[name] = used.get(name, 0) + 1
            if used[name] > 1:
                name += "%d" % used[name]
            self.items[y] = dict(kind="cond", size=size, name=name, cur={}, calls=sorted(calls))

    def cond_text(self, off, op, m):
        """Meaning of one condition entry."""
        sym = self.names.ram.get(off, "$%04X,Z" % off)
        bits = dict(self.names.bits.get(sym, {}))
        names = [bits.get(str(b), "bit %d" % b) for b in range(7, -1, -1) if m >> b & 1]
        what = {0: "needs clear", 2: "needs all set", 4: "needs above"}.get(op, "test %d" % op)
        if op == 4:
            return "%s %s $%02X" % (sym, what, m)
        return "%s %s: %s" % (sym, what, "; ".join(names)) if names else "%s %s $%02X" % (sym, what, m)

    def immsym(self, ins, value):
        if ins.mn in ("LDX", "LDY", "ADDD") and value in self.items:
            return self.items[value]["name"]
        return None

    def extsym(self, addr):
        return self.labels.get(addr)

    def input_text(self, t):
        def nm(x):
            r = re.match(r"^result of \$([0-9A-F]{5})$", x or "")
            if r:
                return "result of " + self.names.labels_ann.get(int(r.group(1), 16), r.group(1))
            m = re.match(r"^\$([0-9A-F]{2,4}),Z$", x or "")
            if m and int(m.group(1), 16) in self.names.ram:
                return self.names.ram[int(m.group(1), 16)]
            return x
        out = []
        for k in list(t.get("inputs", {}))[:3]:
            out.append(" x ".join(nm(x) for x in k))
        return "; ".join(out)

    def block(self, a):
        """Source lines of the table at a."""
        t = self.items[a]
        d = self.data
        c = t["cur"]
        u = lambda key: " " + c[key] if key in c else " ?"
        kind = t["kind"]
        out = [";" + "-" * 99]
        if kind in ("2D", "2Dr"):
            n = d[a]
            out.append("; %s ($%04X): 2D table, %d points%s" % (
                t["name"], a, n, ", " + FLAGS2D.get(d[a + 1], "flags $%02X" % d[a + 1]) if kind == "2D" else ""))
        elif kind in ("3D", "3Dn"):
            out.append("; %s ($%04X): 3D table, %d rows x %d columns, %s%s" % (
                t["name"], a, d[a], d[a + 1], "signed" if d[a + 2] else "unsigned",
                "" if kind == "3D" else ", columns by position 0-255"))
        elif kind == "cond":
            out.append("; %s ($%04X): condition list, %d entries (ConditionTable: the check passes only if every entry holds)" % (
                t["name"], a, d[a]))
        else:
            out.append("; %s ($%04X): %d rows of %d bytes" % (t["name"], a, t["rows"], t["row_size"]))
        if c.get("desc"):
            out.append("; " + c["desc"])
        if kind in ("2D", "2Dr") and ("x" in c or "y" in c):
            out.append("; x:%s, y:%s (units: docs/en/calibration.md)" % (u("x"), u("y")))
        if kind in ("3D", "3Dn") and c:
            out.append("; columns:%s, rows:%s, values:%s (units: docs/en/calibration.md)" % (u("x"), u("y"), u("z")))
        if t.get("inputs"):
            out.append("; Inputs: " + self.input_text(t))
        if t.get("calls"):
            cl = t["calls"]
            out.append("; Read at " + ", ".join("$%05X" % x for x in cl[:8]) + (" and %d more" % (len(cl) - 8) if len(cl) > 8 else ""))
        out.append(";" + "-" * 99)
        out.append("%s:" % t["name"])

        def row(vals, signed, note):
            txt = ",".join(str(v - 256 if signed and v > 127 else v) for v in vals)
            return "        dc.b    %-40s ; %s" % (txt, note) if len(txt) <= 40 else "        dc.b    %s ; %s" % (txt, note)
        if kind in ("2D", "2Dr"):
            n = d[a]
            out.append("        dc.b    %-40s ; points, %s" % ("%d,$%02X" % (n, d[a + 1]), "flags" if kind == "2D" else "unused"))
            signed = kind == "2D" and d[a + 1] == 0x20
            for i in range(0, n, 8):
                pts = range(i, min(n, i + 8))
                vals = []
                for j in pts:
                    x, y = d[a + 2 + 2 * j], d[a + 3 + 2 * j]
                    vals.append("%d,%d" % (x, y - 256 if signed and y > 127 else y) if kind == "2D" else "%d,%d" % (x, y))
                out.append("        dc.b    %-40s ; %s" % (", ".join(vals), "x, y" if kind == "2D" else "y, x"))
        elif kind in ("3D", "3Dn"):
            ny, nx, sg = d[a], d[a + 1], d[a + 2]
            out.append("        dc.b    %-40s ; rows, columns, signed" % ("%d,%d,$%02X" % (ny, nx, sg)))
            p = a + 3
            if kind == "3D":
                out.append(row(d[p:p + nx], False, "column axis"))
                p += nx
            for r in range(ny):
                out.append(row(d[p + r * nx:p + (r + 1) * nx], sg != 0, "row %d" % r))
        elif kind == "cond":
            out.append("        dc.b    %-40s ; entries" % ("$%02X" % d[a]))
            for e in range(d[a]):
                p = a + 1 + 4 * e
                b = d[p:p + 4]
                out.append("        dc.b    %-40s ; %s" % (",".join("$%02X" % x for x in b),
                                                          self.cond_text((b[0] << 8) | b[1], b[2], b[3])))
        elif kind == "monitors":
            for r in range(t["rows"]):
                p = a + r * t["row_size"]
                b = d[p:p + t["row_size"]]
                w = [(b[i] << 8) | b[i + 1] for i in range(0, len(b), 2)]
                fr = self.data[w[3]:w[3] + 10]
                conds = ", ".join(self.items[x]["name"] if x in self.items else "$%04X" % x for x in w[4:7])
                note = "%s, %s, run when MainLoopCounter & $%02X = 0; conditions %s; result %s & $%02X" % (
                    self.names.ram.get(w[1], "$%04X,Z" % w[1]),
                    "P%02X%02X" % (fr[6], fr[7]) if FAULT_TABLE <= w[3] < FAULT_TABLE + 10 * FAULT_ROWS and (w[3] - FAULT_TABLE) % 10 == 0
                    else "data " + self.names.ram.get(w[3], "$%04X" % w[3]),
                    b[5] & 0x3F, conds, self.names.ram.get(w[8], "$%04X" % w[8]), w[9] & 0xFF)
                out.append("        dc.b    " + ",".join("$%02X" % x for x in b[:10]) + " ; " + note)
                out.append("        dc.b    " + ",".join("$%02X" % x for x in b[10:]))
        else:
            for r in range(t["rows"]):
                b = d[a + r * t["row_size"]:a + (r + 1) * t["row_size"]]
                note = ""
                if t["kind"] == "fault" and (b[6] or b[7]):
                    note = " ; P%02X%02X, blink code %02X" % (b[6], b[7], b[2])
                out.append("        dc.b    " + ",".join("$%02X" % x for x in b) + note)
        out.append("")
        return out


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
    own, ref = annotation_set(data, os.path.splitext(os.path.basename(image_path))[0])
    names = Names(an, data, own, ref)
    cal = Calibration(data, an, names, own)
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
            if a in cal.items and a not in an.insn:
                lines += [""] + cal.block(a)
                a += cal.items[a]["size"]
                continue
            if a in cal.scalars and a not in an.insn:
                v = cal.scalars[a]
                lines.append("%s:" % v["name"])
                lines.append("        dc.b    %-40s ; %s" % (",".join("$%02X" % b for b in data[a:a + v.get("size", 1)]), v.get("desc", "")))
                a += v.get("size", 1)
                continue
            ins = an.insn.get(a)
            if ins is not None:
                mn, ops = format_insn(ins, lab, names.zsym_for(a), cal.extsym, cal.immsym)
                note = names.bit_note(ins, a, cal.extsym)
                if note:
                    lines.append("        %-7s %-40s ; %s" % (mn, ops, note))
                else:
                    lines.append("        %-7s %s" % (mn, ops) if ops else "        %s" % mn)
                a += ins.size
                continue
            run = []
            while a < end and a not in an.insn and len(run) < 16 and not (run and a in names.labels) \
                    and a not in cal.items and a not in cal.scalars:
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
        for bit, text in sorted(names.bits.get(s, {}).items(), key=lambda x: -int(x[0])):
            eq.append(";                 bit %s: %s" % (bit, text))
    open(os.path.join(outdir, "00_equates.asm"), "w").write("\n".join(eq) + "\n")
    # one name, one meaning: a clash between a label, a table and an equate would assemble wrongly
    seen = collections.defaultdict(set)
    for a, n in names.labels.items():
        seen[n].add(("code", a))
    for a, n in cal.labels.items():
        seen[n].add(("cal", a))
    for n, off in names.used.items():
        seen[n].add(("equ", off))
    clash = {n: v for n, v in seen.items() if len(v) > 1}
    if clash:
        raise SystemExit("name used twice: " + ", ".join("%s %s" % (n, sorted(v)) for n, v in sorted(clash.items())))
    return an, files, cal


def main():
    an, files, cal = generate(sys.argv[1], sys.argv[2])
    cov = sum(i.size for i in an.insn.values())
    print("%d instructions (%d bytes), %d labels, %d jump tables, %d unresolved indirect jumps, "
          "%d jumps into RAM, %d problems; %d calibration tables, %d named constants" % (
              len(an.insn), cov, len(an.labels), len(an.tables), len(an.indirect), len(an.ram_jumps),
              len(an.problems), len(cal.items), len(cal.scalars)))


if __name__ == "__main__":
    main()
