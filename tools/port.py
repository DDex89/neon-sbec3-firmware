#!/usr/bin/env python3
"""Carry the annotations of the reference image over to another image.

    python3 tools/port.py roms/05269833AH.bin            # writes annotations/ports/05269833AH/

The two programs are matched routine by routine:

1. Anchors: the reset entry and the handler of every exception vector.
2. Routines whose instruction sequence (opcodes and addressing modes, operands left out) occurs
   exactly once in each image; then routines that read the same sequence of 3D table shapes;
   then routines whose sequence of mnemonics alone is unique.
3. Propagation: two matched routines with the same sequence are aligned instruction by
   instruction; the targets of their calls and branches are matched in turn. Routines of
   different length are aligned on their common runs (difflib) when they are at least 90 %
   similar. This repeats until nothing new is found.

The aligned instructions give an address map for code labels, and their operands give the maps
for RAM offsets (`$xxxx,Z`) and calibration addresses (`LDX #table`, `$xxxx`). A RAM or
calibration address is carried over only when the aligned instructions agree on it.
"""
import re, bisect, collections, difflib, hashlib, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from analyse import Analysis
import caltables

ANN = os.path.join(ROOT, "annotations")
REF = os.path.join(ROOT, "roms", "05293190AC.bin")


class Program:
    def __init__(self, data):
        self.data = data
        self.an = Analysis(data).run()
        an = self.an
        starts = {an.vectors()[0][0]}
        for a, i in an.insn.items():
            if i.mn in ("JSR", "BSR", "LBSR") and i.target() in an.insn:
                starts.add(i.target())
        self.vec = {}
        for n in range(4, 256):
            t = (data[2 * n] << 8) | data[2 * n + 1]
            if t in an.insn:
                self.vec[n] = t
        handlers = collections.Counter(self.vec.values())
        starts |= {t for t, c in handlers.items() if c < 8}
        self.starts = sorted(starts)
        order = sorted(an.insn)
        self.body = {}
        for k, s in enumerate(self.starts):
            end = self.starts[k + 1] if k + 1 < len(self.starts) else 1 << 20
            i = bisect.bisect_left(order, s)
            seq = []
            while i < len(order) and order[i] < end:
                seq.append(an.insn[order[i]])
                i += 1
            self.body[s] = seq
        self.sig = {s: hashlib.sha1("|".join(x.key for x in b).encode()).hexdigest() for s, b in self.body.items()}
        # the shapes of the 3D tables each routine reads, in call order: survives code changes
        self.tables = caltables.find(data, an)[1]
        shape = {}
        for a, t in self.tables.items():
            if t["kind"] in ("3D", "3Dn"):
                for c in t["calls"]:
                    shape[c] = (t["kind"], data[a], data[a + 1], data[a + 2] != 0)
        self.calltab = collections.defaultdict(list)     # lookup call -> tables (kind, address)
        for a, t in self.tables.items():
            for c in t["calls"]:
                self.calltab[c].append((t["kind"], a))
        self.tabsig = {}
        for s, b in self.body.items():
            seq = tuple(shape[x.addr] for x in b if x.addr in shape)
            if seq:
                self.tabsig[s] = seq
        self.reset = an.vectors()[0][0]


def ops(ins):
    return dict(ins.vals)


class Matcher:
    def __init__(self, ref, new):
        self.ref, self.new = ref, new
        self.pairs = {}         # ref routine -> new routine
        self.insn = {}          # ref instruction address -> new instruction address
        self.ram = collections.defaultdict(collections.Counter)
        self.cal = collections.defaultdict(collections.Counter)
        self.imm = collections.defaultdict(collections.Counter)
        self.min_ratio = 0.6

    def add(self, r, n, queue):
        if r in self.pairs or n in self.pairs.values():
            return
        if r not in self.ref.body or n not in self.new.body:
            return
        self.pairs[r] = n
        queue.append((r, n))

    def align(self, r, n, queue):
        a, b = self.ref.body[r], self.new.body[n]
        # the tables read, in call order: matched pairwise when the kinds agree
        ta = [self.ref.calltab[x.addr][0] for x in a if len(self.ref.calltab.get(x.addr, [])) == 1]
        tb = [self.new.calltab[x.addr][0] for x in b if len(self.new.calltab.get(x.addr, [])) == 1]
        if ta and len(ta) == len(tb) and [k for k, _ in ta] == [k for k, _ in tb]:
            for (_, x), (_, y) in zip(ta, tb):
                self.imm[x][y] += 1
        ka, kb = [x.key for x in a], [x.key for x in b]
        if ka == kb:
            blocks = [(0, 0, len(ka))]
        else:
            sm = difflib.SequenceMatcher(None, ka, kb, autojunk=False)
            if sm.ratio() < self.min_ratio:
                return
            blocks = [m for m in sm.get_matching_blocks() if m[2] >= 3]
        for i0, j0, size in blocks:
            for k in range(size):
                x, y = a[i0 + k], b[j0 + k]
                self.insn[x.addr] = y.addr
                vx, vy = ops(x), ops(y)
                tx, ty = x.target(), y.target()
                if tx is not None and ty is not None:
                    if x.mn in ("JSR", "BSR", "LBSR"):
                        self.add(tx, ty, queue)
                    self.insn.setdefault(tx, ty)
                if x.mode.endswith(", Z"):
                    for f in ("ff", "gggg"):
                        if f in vx and f in vy:
                            self.ram[vx[f]][vy[f]] += 1
                if "hhll" in vx and "hhll" in vy and x.mn not in ("JMP", "JSR"):
                    self.cal[vx["hhll"]][vy["hhll"]] += 1
                if x.mode == "IMM16" and x.mn in ("LDX", "LDY", "ADDD"):
                    self.imm[vx["jjkk"]][vy["jjkk"]] += 1

    def run(self):
        q = []
        self.add(self.ref.reset, self.new.reset, q)
        for n, t in self.ref.vec.items():
            if n in self.new.vec and list(self.ref.vec.values()).count(t) < 8:
                self.add(t, self.new.vec[n], q)
        by_sig_new = collections.defaultdict(list)
        for s, h in self.new.sig.items():
            by_sig_new[h].append(s)
        by_sig_ref = collections.defaultdict(list)
        for s, h in self.ref.sig.items():
            by_sig_ref[h].append(s)
        for h, rs in by_sig_ref.items():
            ns = by_sig_new.get(h, [])
            if len(rs) == 1 and len(ns) == 1 and len(self.ref.body[rs[0]]) >= 4:
                self.add(rs[0], ns[0], q)
        self.drain(q)
        # routines that read the same sequence of 3D table shapes, unique in both images
        tr = collections.defaultdict(list)
        tn = collections.defaultdict(list)
        used = set(self.pairs.values())
        for s, v in self.ref.tabsig.items():
            if s not in self.pairs:
                tr[v].append(s)
        for s, v in self.new.tabsig.items():
            if s not in used:
                tn[v].append(s)
        for v, rs in tr.items():
            ns = tn.get(v, [])
            if len(rs) == 1 and len(ns) == 1:
                self.add(rs[0], ns[0], q)
        self.drain(q)
        # second pass: unique routines compared by mnemonics only (addressing modes may differ
        # between program generations), among the routines not matched yet
        def loose(p, s):
            return hashlib.sha1("|".join(x.mn for x in p.body[s]).encode()).hexdigest()
        free_r = [s for s in self.ref.body if s not in self.pairs]
        used = set(self.pairs.values())
        free_n = [s for s in self.new.body if s not in used]
        hr = collections.defaultdict(list)
        hn = collections.defaultdict(list)
        for s in free_r:
            hr[loose(self.ref, s)].append(s)
        for s in free_n:
            hn[loose(self.new, s)].append(s)
        for h, rs in hr.items():
            ns = hn.get(h, [])
            if len(rs) == 1 and len(ns) == 1 and len(self.ref.body[rs[0]]) >= 6:
                self.add(rs[0], ns[0], q)
        self.drain(q)
        return self

    def drain(self, q):
        while q:
            r, n = q.pop()
            self.align(r, n, q)

    @staticmethod
    def agreed(votes, minimum=1):
        """ref value -> new value where the votes agree (at least 80 % for one value)."""
        out = {}
        for k, c in votes.items():
            v, n = c.most_common(1)[0]
            if n >= minimum and n >= 0.8 * sum(c.values()):
                out[k] = v
        return out


def load(name):
    p = os.path.join(ANN, name)
    d = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}
    if isinstance(d, dict):
        d.pop("_comment", None)
    return d


def main():
    path = sys.argv[1]
    pn = os.path.splitext(os.path.basename(path))[0]
    ref = Program(open(REF, "rb").read())
    new = Program(open(path, "rb").read())
    m = Matcher(ref, new).run()
    ram = m.agreed(m.ram)
    cal = m.agreed(m.cal)
    imm = m.agreed(m.imm)

    labels = {}
    for k, v in load("labels.json").items():
        a = int(k, 16)
        b = m.pairs.get(a, m.insn.get(a))
        if b is not None:
            labels["%05X" % b] = v
    # routine notes travel with the routine
    rnames = {}
    import gen_source
    for a, r in gen_source.load_routines().items():
        b = m.pairs.get(a, m.insn.get(a))
        if b is not None:
            rnames["%05X" % b] = r["name"]
            labels.setdefault("%05X" % b, r["name"])
    ramn = {}
    for k, v in load("ram.json").items():
        o = int(k, 16)
        if o in ram:
            ramn["%04X" % ram[o]] = v
    tab = load("tables.json")
    tables_out = {"units": tab.get("units", {}), "tables": {}, "scalars": {}, "special": {}}
    reft = caltables.find(ref.data, ref.an)[1]
    newt = caltables.find(new.data, new.an)[1]
    for k, v in tab.get("tables", {}).items():
        a = int(k, 16)
        b = imm.get(a)
        if b is not None and b in newt and newt[b]["kind"] == reft.get(a, {}).get("kind", newt[b]["kind"]):
            # the unit of the input axis only holds if the table is read with the same input
            def offs(t):
                out = set()
                for key in t.get("inputs", {}):
                    for x in key:
                        mo = re.match(r"^\$([0-9A-F]{2,4}),Z$", x or "")
                        if mo:
                            out.add(int(mo.group(1), 16))
                return out
            ri, ni = {ram.get(o, -1) for o in offs(reft.get(a, {}))}, offs(newt[b])
            dummy = reft.get(a, {}).get("kind") in ("2D", "2Dr") and ref.data[a] == 1 and new.data[b] > 1
            if ((ri and ni and not (ri & ni)) or dummy) and v.get("x", "raw") != "raw":
                v = dict(v, x="raw", desc=(v.get("desc", "") + "; read here with another input than in 05293190AC, so the x unit is not carried").lstrip("; "))
            tables_out["tables"]["%04X" % b] = v
    for k, v in tab.get("scalars", {}).items():
        a = int(k, 16)
        if a in cal:
            tables_out["scalars"]["%04X" % cal[a]] = v
    for k, v in tab.get("special", {}).items():
        a = int(k, 16)
        b = imm.get(a)
        if b is not None:
            tables_out["special"]["%04X" % b] = v
    an_ref = load("analysis.json")
    analysis = {"z_not_base": []}
    for lo, hi, why in an_ref.get("z_not_base", []):
        a, b = m.insn.get(int(lo, 16)), m.insn.get(int(hi, 16))
        if a is not None and b is not None:
            analysis["z_not_base"].append(["%05X" % a, "%05X" % b, why])

    out = os.path.join(ANN, "ports", pn)
    os.makedirs(out, exist_ok=True)
    note = "Carried over from 05293190AC by tools/port.py; do not edit by hand, edit the reference annotations and re-run."

    def dump(name, d):
        json.dump({"_comment": note, **dict(sorted(d.items()))} if name != "tables.json" else
                  {"_comment": note, **d}, open(os.path.join(out, name), "w"), indent=1, ensure_ascii=False)
        open(os.path.join(out, name), "a").write("\n")
    dump("labels.json", labels)
    dump("ram.json", ramn)
    dump("tables.json", tables_out)
    dump("analysis.json", analysis)
    nr = len(ref.body)
    stats = {
        "sha256": hashlib.sha256(new.data).hexdigest(),
        "routines_matched": len(m.pairs), "routines_ref": nr,
        "instructions_mapped": len(m.insn), "instructions_ref": len(ref.an.insn),
        "labels": "%d of %d" % (len(labels), len({int(k, 16) for k in load("labels.json")} | set(gen_source.load_routines()))),
        "ram": "%d of %d" % (len(ramn), len(load("ram.json"))),
        "tables": "%d of %d" % (len(tables_out["tables"]), len(tab.get("tables", {}))),
        "scalars": "%d of %d" % (len(tables_out["scalars"]), len(tab.get("scalars", {}))),
        "ram_identity": sum(1 for k, v in ram.items() if k == v), "ram_moved": sum(1 for k, v in ram.items() if k != v),
    }
    json.dump(stats, open(os.path.join(out, "stats.json"), "w"), indent=1)
    print(pn, json.dumps(stats))


if __name__ == "__main__":
    main()
