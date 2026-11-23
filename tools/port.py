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
   different length are aligned on their common runs (difflib) when they are at least 60 %
   similar. A callee is taken over from a call site only if the two callees look alike as well
   (35 % similar, or the same first instructions), since a run of calls shifts when a call is
   added or removed. This repeats until nothing new is found.
4. Fuzzy pass: for the routines still open, the best candidate by mnemonic similarity and by
   agreement of the already matched callers and callees, accepted only when it is the best in
   both directions by a clear margin. These pairs are aligned on longer runs only, and their
   operand votes are used only where the other pairs give none.

The aligned instructions give an address map for code labels, and their operands give the maps
for RAM offsets (`$xxxx,Z`) and calibration addresses (`LDX #table`, `$xxxx`). A RAM or
calibration address is carried over only when the aligned instructions agree on it; when two
reference names land on the same new address, the one with more votes keeps it (a tie: neither).

Structures taken over with the reference's row count are cut where the next item or code starts.
For images in VIA, the names of an image of a closer family (ported first) fill what the
reference left open.
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
        self.call_min = 0.35
        self.loose = set()      # pairs found by the fuzzy pass: aligned on longer runs only
        self.weak = {"ram": collections.defaultdict(collections.Counter),     # their votes, used
                     "cal": collections.defaultdict(collections.Counter),     # only where the strict
                     "imm": collections.defaultdict(collections.Counter)}     # pairs give none

    def add(self, r, n, queue, check=False):
        if r in self.pairs or n in self.pairs.values():
            return
        if r not in self.ref.body or n not in self.new.body:
            return
        if check and not self.callee_alike(r, n):
            # a call matched only by its place in two aligned runs: runs of calls shift when a
            # call is added or removed, so the two callees must also look alike
            return
        self.pairs[r] = n
        queue.append((r, n))

    def callee_alike(self, r, n):
        """Alike as a whole, or the same start (a routine that grew or shrank at its end)."""
        if self.similar(r, n) >= self.call_min:
            return True
        ka = [x.mn for x in self.ref.body[r]][:12]
        kb = [x.mn for x in self.new.body[n]][:12]
        return min(len(ka), len(kb)) >= 4 and difflib.SequenceMatcher(None, ka, kb, autojunk=False).ratio() >= 0.6

    def similar(self, r, n):
        """Mnemonic similarity of two paired routines (0..1)."""
        ka = [x.mn for x in self.ref.body.get(r, [])]
        kb = [x.mn for x in self.new.body.get(n, [])]
        return difflib.SequenceMatcher(None, ka, kb, autojunk=False).ratio() if ka and kb else 0.0

    def align(self, r, n, queue):
        a, b = self.ref.body[r], self.new.body[n]
        loose = (r, n) in self.loose
        ram, cal, imm = ((self.weak["ram"], self.weak["cal"], self.weak["imm"]) if loose
                         else (self.ram, self.cal, self.imm))
        # the tables read, in call order: matched pairwise when the kinds agree
        ta = [self.ref.calltab[x.addr][0] for x in a if len(self.ref.calltab.get(x.addr, [])) == 1]
        tb = [self.new.calltab[x.addr][0] for x in b if len(self.new.calltab.get(x.addr, [])) == 1]
        if ta and len(ta) == len(tb) and [k for k, _ in ta] == [k for k, _ in tb]:
            for (_, x), (_, y) in zip(ta, tb):
                imm[x][y] += 1
        ka, kb = [x.key for x in a], [x.key for x in b]
        if ka == kb:
            blocks = [(0, 0, len(ka))]
        else:
            sm = difflib.SequenceMatcher(None, ka, kb, autojunk=False)
            if sm.ratio() < (0.5 if loose else self.min_ratio):
                return
            blocks = [m for m in sm.get_matching_blocks() if m[2] >= (6 if loose else 3)]
        for i0, j0, size in blocks:
            for k in range(size):
                x, y = a[i0 + k], b[j0 + k]
                self.insn[x.addr] = y.addr
                vx, vy = ops(x), ops(y)
                tx, ty = x.target(), y.target()
                if tx is not None and ty is not None:
                    if x.mn in ("JSR", "BSR", "LBSR"):
                        self.add(tx, ty, queue, check=True)
                        if self.pairs.get(tx) == ty:          # a call target maps only with its pair
                            self.insn.setdefault(tx, ty)
                    else:
                        self.insn.setdefault(tx, ty)
                if x.mode.endswith(", Z"):
                    for f in ("ff", "gggg"):
                        if f in vx and f in vy:
                            ram[vx[f]][vy[f]] += 1
                if "hhll" in vx and "hhll" in vy and x.mn not in ("JMP", "JSR"):
                    cal[vx["hhll"]][vy["hhll"]] += 1
                if x.mode == "IMM16" and x.mn in ("LDX", "LDY", "ADDD"):
                    imm[vx["jjkk"]][vy["jjkk"]] += 1

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
        # last pass, repeated while it finds something: routines that are similar but not equal
        # (difflib ratio of the mnemonic sequences), helped by matched callers and callees, taken
        # only when the pair is the best choice in both directions by a clear margin
        while self.fuzzy(q):
            self.drain(q)
        return self

    def result(self, kind):
        """ref value -> new value: the strict votes first, then the fuzzy-pair votes for the ref
        values still open, on new values nothing has taken yet."""
        out = self.agreed(getattr(self, kind))
        taken = set(out.values())
        rest = {k: collections.Counter({v: n for v, n in c.items() if v not in taken})
                for k, c in self.weak[kind].items() if k not in out}
        out.update(self.agreed({k: c for k, c in rest.items() if c}))
        return out

    def fuzzy(self, q):
        def graph(p):
            calls, callers = collections.defaultdict(set), collections.defaultdict(set)
            for s, body in p.body.items():
                for x in body:
                    t = x.target()
                    if x.mn in ("JSR", "BSR", "LBSR") and t in p.body:
                        calls[s].add(t)
                        callers[t].add(s)
            return calls, callers
        rc, rr = graph(self.ref)
        nc, nr = graph(self.new)
        inv = {v: k for k, v in self.pairs.items()}
        free_r = [s for s in self.ref.body if s not in self.pairs and len(self.ref.body[s]) >= 4]
        free_n = [s for s in self.new.body if s not in inv and len(self.new.body[s]) >= 4]
        mn = {("r", s): [x.mn for x in self.ref.body[s]] for s in free_r}
        mn.update({("n", s): [x.mn for x in self.new.body[s]] for s in free_n})
        score = {}
        for n in free_n:
            b = mn[("n", n)]
            for r in free_r:
                a = mn[("r", r)]
                if not 0.5 < len(a) / len(b) < 2:
                    continue
                sm = difflib.SequenceMatcher(None, b, a, autojunk=False)
                if sm.real_quick_ratio() < 0.5 or sm.quick_ratio() < 0.5:
                    continue
                ratio = sm.ratio()
                ctx_n = len(nc[n]) + len(nr[n])
                ok = sum(1 for x in nc[n] if inv.get(x) in rc[r]) + sum(1 for x in nr[n] if inv.get(x) in rr[r])
                ctx = ok / ctx_n if ctx_n else 0
                if ratio >= 0.75 or (ratio >= 0.55 and ctx >= 0.4):
                    score[(r, n)] = ratio + 0.5 * ctx
        best_n, best_r = {}, {}
        for (r, n), v in score.items():
            best_n.setdefault(n, []).append((v, r))
            best_r.setdefault(r, []).append((v, n))
        found = 0
        for n, lst in best_n.items():
            lst.sort(reverse=True)
            v, r = lst[0]
            if len(lst) > 1 and v - lst[1][0] < 0.15:
                continue
            other = sorted(best_r[r], reverse=True)
            if other[0][1] != n or (len(other) > 1 and v - other[1][0] < 0.15):
                continue
            if r not in self.pairs and n not in self.pairs.values():
                self.loose.add((r, n))
            self.add(r, n, q)
            found += 1
        return found

    def drain(self, q):
        while q:
            r, n = q.pop()
            self.align(r, n, q)

    @staticmethod
    def agreed(votes, minimum=1):
        """ref value -> new value where the votes agree (at least 80 % for one value). When several
        ref values land on the same new value, only the one with the most votes keeps it."""
        out, best = {}, {}
        for k, c in votes.items():
            v, n = c.most_common(1)[0]
            if n >= minimum and n >= 0.8 * sum(c.values()):
                if v not in best or n > best[v][0]:
                    best[v] = (n, k)
                elif n == best[v][0]:
                    best[v] = (n, None)      # a tie: neither name is trusted
        for v, (n, k) in best.items():
            if k is not None:
                out[k] = v
        return out


def load(name, base=ANN):
    p = os.path.join(base, name)
    d = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}
    if isinstance(d, dict):
        d.pop("_comment", None)
    return d


# images whose names are also carried over from an image of a closer family, ported first: the
# names the reference gives are kept, the closer image only fills what is still open
VIA = {"05293013AC": "05007038", "05293014AC": "05007038",
       "04887050": "05293013AC", "04887051": "05293013AC"}
# hand annotations made on one image of a family (annotations/hand/<PN>/), valid for every image
# with the same code: they override what was carried over
HAND = {"05007038": "05007038", "05293148AA": "05007038",
        "04887050": "04887050", "04887051": "04887050"}


def overlay(base, hand):
    """hand names win at their address; a carried-over copy of the same name elsewhere goes."""
    names = set(hand.values())
    out = {k: v for k, v in base.items() if v not in names and k not in hand}
    out.update(hand)
    return out


def apply_hand(pn, labels, ramn, tables_out):
    code = HAND.get(pn)
    hdir = os.path.join(ANN, "hand", code) if code else None
    if not hdir or not os.path.isdir(hdir):
        return None, {}
    labels = overlay(labels, load("labels.json", hdir))
    ramn = overlay(ramn, load("ram.json", hdir))
    ht = load("tables.json", hdir)
    for part in ("tables", "scalars", "special"):
        hp = ht.get(part, {})
        hn = {v["name"] for v in hp.values()}
        cur = {k: v for k, v in tables_out[part].items() if v["name"] not in hn and k not in hp}
        for k, v in hp.items():
            base = tables_out[part].get(k, {})
            cur[k] = dict(base, **v)          # a hand entry may only rename or describe
        tables_out[part] = cur
    extra = {}
    for f in ("routines.md", "bits.json"):
        if os.path.exists(os.path.join(hdir, f)):
            extra[f] = open(os.path.join(hdir, f), encoding="utf-8").read()
    return (labels, ramn, tables_out), extra


def carry(ref, new, base, routines):
    """Names of the image `ref` (annotations in `base`) carried over to `new`."""
    load_ = lambda name: load(name, base)
    m = Matcher(ref, new).run()
    ram = m.result("ram")
    cal = m.result("cal")
    imm = m.result("imm")

    labels = {}
    ref_labels = load_("labels.json")
    weak = set()
    for k, v in ref_labels.items():          # routine starts whose bodies agree first
        a = int(k, 16)
        if a in m.pairs:
            if m.similar(a, m.pairs[a]) >= 0.6:
                labels["%05X" % m.pairs[a]] = v
            else:
                weak.add(a)
    for k, v in ref_labels.items():          # then labels inside routines, where still free
        a = int(k, 16)
        b = m.insn.get(a)
        if a not in m.pairs and b is not None:
            labels.setdefault("%05X" % b, v)
    for k, v in ref_labels.items():          # pairs found only through a call site come last
        a = int(k, 16)
        if a in weak:
            labels.setdefault("%05X" % m.pairs[a], v)
    # routine notes travel with the routine
    rnames = {}
    for a, r in routines.items():
        b = m.pairs.get(a, m.insn.get(a))
        if b is not None:
            rnames["%05X" % b] = r["name"]
            labels.setdefault("%05X" % b, r["name"])
    ramn = {}
    for k, v in load_("ram.json").items():
        o = int(k, 16)
        if o in ram:
            ramn["%04X" % ram[o]] = v
    tab = load_("tables.json")
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
    an_ref = load_("analysis.json")
    analysis = {"z_not_base": []}
    for lo, hi, why in an_ref.get("z_not_base", []):
        a, b = m.insn.get(int(lo, 16)), m.insn.get(int(hi, 16))
        if a is not None and b is not None:
            analysis["z_not_base"].append(["%05X" % a, "%05X" % b, why])

    return m, ram, labels, ramn, tables_out, analysis


def rename_options(tables_out):
    """Option bytes are named by their address (Options0331); in another image the same byte can sit
    elsewhere, so a carried-over option takes the name of its new address. Returns old -> new."""
    alias = {}
    for k, v in tables_out["scalars"].items():
        if re.match(r"^Options[0-9A-F]{4}$", v["name"]):
            alias[v["name"]] = "Options" + k
    sub = lambda t: re.sub(r"\bOptions[0-9A-F]{4}\b", lambda m: alias.get(m.group(0), m.group(0)), t)
    for part in ("tables", "scalars", "special"):
        for k, v in tables_out[part].items():
            v = dict(v, name=alias.get(v["name"], v["name"]))
            if "desc" in v:
                v["desc"] = sub(v["desc"])
            tables_out[part][k] = v
    return alias


def clamp(new, tables_out):
    """A structure taken over with the reference's row count must not run into the next item or code."""
    starts = sorted({int(k, 16) for part in ("tables", "scalars", "special") for k in tables_out[part]} |
                    {x for x in new.an.insn if x < len(new.data)})
    for k, v in tables_out["special"].items():
        b = int(k, 16)
        if isinstance(v.get("rows"), int) and isinstance(v.get("row_size"), int) and v["row_size"] > 0:
            nxt = next((x for x in starts if x > b), len(new.data))
            fit = (nxt - b) // v["row_size"]
            if v.get("kind") == "bitmaps":
                # every entry of a bit map is unused (offset and mask 0) or tests a single bit; two bad
                # rows in a row mark the end (the reference has single odd rows inside its list)
                def good(r):
                    for e in range(8):
                        o = b + r * 32 + e * 4
                        if o + 3 >= len(new.data):
                            return False
                        off, mask = (new.data[o] << 8) | new.data[o + 1], new.data[o + 2]
                        if not ((off == 0 and mask == 0) or bin(mask).count("1") == 1):
                            return False
                    return True
                fit = min(fit, next((r for r in range(v["rows"]) if not good(r) and not good(r + 1)), v["rows"]))
            if v.get("size"):                       # a list with its own byte count
                size = min(v["size"], nxt - b)
                if v["row_size"] > 1 and v["rows"] > 1:
                    size -= size % v["row_size"]
                if 0 < size < v["size"]:
                    tables_out["special"][k] = dict(v, size=size, rows=max(1, min(v["rows"], size // v["row_size"])))
            elif 0 < fit < v["rows"]:
                tables_out["special"][k] = dict(v, rows=fit)


def merge(first, second, keyed=lambda v: v):
    """second fills the addresses first leaves open, with names first does not use."""
    out = dict(first)
    used = {keyed(v) for v in first.values()}
    for k, v in second.items():
        if k not in out and keyed(v) not in used:
            out[k] = v
            used.add(keyed(v))
    return out


def main():
    path = sys.argv[1]
    pn = os.path.splitext(os.path.basename(path))[0]
    import gen_source
    ref = Program(open(REF, "rb").read())
    new = Program(open(path, "rb").read())
    m, ram, labels, ramn, tables_out, analysis = carry(ref, new, ANN, gen_source.load_routines())
    tab = load("tables.json")
    via = VIA.get(pn)
    if via:
        vdir = os.path.join(ANN, "ports", via)
        vimg = os.path.join(ROOT, "roms", via + ".bin")
        vdata = open(vimg, "rb").read()
        if json.load(open(os.path.join(vdir, "stats.json"))).get("sha256") != hashlib.sha256(vdata).hexdigest():
            sys.exit("%s: port %s first" % (pn, via))
        _, _, l2, r2, t2, _ = carry(Program(vdata), new, vdir, {})
        labels = merge(labels, l2)
        ramn = merge(ramn, r2)
        for part in ("tables", "scalars", "special"):
            tables_out[part] = merge(tables_out[part], t2[part], keyed=lambda v: v["name"])
    hand, hand_files = apply_hand(pn, labels, ramn, tables_out)
    if hand:
        labels, ramn, tables_out = hand
    clamp(new, tables_out)
    hand_bits = json.loads(hand_files.pop("bits.json", "{}"))
    hand_bits.pop("_comment", None)
    alias = rename_options(tables_out)
    ref_bits = load("bits.json")
    bits = {n: dict(ref_bits.get(o, {})) for o, n in alias.items()}
    for k, v in hand_bits.items():
        bits[k] = dict(bits.get(k, ref_bits.get(k, {})), **v)

    out = os.path.join(ANN, "ports", pn)
    os.makedirs(out, exist_ok=True)
    note = ("Carried over from 05293190AC%s by tools/port.py; do not edit by hand, edit the reference "
            "annotations and re-run." % (" (gaps filled through %s)" % via if via else ""))

    def dump(name, d):
        json.dump({"_comment": note, **dict(sorted(d.items()))} if name != "tables.json" else
                  {"_comment": note, **d}, open(os.path.join(out, name), "w"), indent=1, ensure_ascii=False)
        open(os.path.join(out, name), "a").write("\n")
    dump("labels.json", labels)
    dump("ram.json", ramn)
    dump("tables.json", tables_out)
    dump("analysis.json", analysis)
    p = os.path.join(out, "routines.md")
    if "routines.md" in hand_files:
        open(p, "w", encoding="utf-8").write(hand_files["routines.md"])
    elif os.path.exists(p):
        os.remove(p)
    # bit texts for this image: the option bytes under their new names, plus the hand texts; they
    # replace the reference texts of the same name
    dump("bits.json", bits)
    nr = len(ref.body)
    stats = {
        "sha256": hashlib.sha256(new.data).hexdigest(),
        "routines_matched": len(m.pairs), "routines_ref": nr,
        "instructions_mapped": len(m.insn), "instructions_ref": len(ref.an.insn),
        "options_renamed": {o: n for o, n in sorted(alias.items()) if o != n},
        "via": via, "hand": HAND.get(pn) if hand_files or hand else None,
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
