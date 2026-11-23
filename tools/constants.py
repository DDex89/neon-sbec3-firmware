#!/usr/bin/env python3
"""Calibration constants of the reference image: every byte or word the code reads directly.

    python3 tools/constants.py [hand.json]

A constant is a calibration address read with extended addressing (LDAA $2611, CMPA $2853,
CPD $263F, BRSET $032E,#$40 ...) that is not part of a lookup table. For each one the script finds
its width, the routines that read it, what it is compared with or added to (the RAM variable last
loaded into the same register, or the next one it is compared with or stored to) and from that a
unit. Option bytes (read with BRSET/BRCLR) get one entry per bit used.

The entries go into the "scalars" of annotations/tables.json with "auto": true and a structural
name: the prefix of the hand-named tables of the reading routine (Idle, Surge, Misfire ...), the
variable it works with, and the role (Thresh for compares, Adder, Offset, Factor, Init for a value
stored into RAM, Value otherwise), numbered when repeated. Entries without "auto" are hand names
and are kept; hand.json (address -> {name, desc, unit, category, bits}) adds or replaces them.
"""
import collections, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import caltables
from subsystems import G

REG = {"A": "A", "B": "B", "D": "D", "E": "E", "X": "X", "Y": "Y"}
LOADS = {"LDAA": "A", "LDAB": "B", "LDD": "D", "LDE": "E", "LDX": "X", "LDY": "Y", "LDED": "E"}
CMPS = {"CMPA": "A", "CMPB": "B", "CPD": "D", "CPE": "E", "CPX": "X", "CPY": "Y"}
ADDS = {"ADDA": "A", "ADDB": "B", "ADDD": "D", "ADDE": "E", "ADCA": "A", "ADCB": "B", "ADCD": "D", "ADCE": "E"}
SUBS = {"SUBA": "A", "SUBB": "B", "SUBD": "D", "SUBE": "E", "SBCA": "A", "SBCB": "B", "SBCD": "D", "SBCE": "E"}
ANDS = {"ANDA": "A", "ANDB": "B", "ANDD": "D", "ANDE": "E", "ORAA": "A", "ORAB": "B", "ORD": "D", "ORE": "E",
        "EORA": "A", "EORB": "B", "EORD": "D", "EORE": "E", "BITA": "A", "BITB": "B"}
STORES = {"STAA": "A", "STAB": "B", "STD": "D", "STE": "E", "STX": "X", "STY": "Y"}
WORDREG = {"D", "E", "X", "Y"}
BITS = {"BRSET", "BRCLR", "BRSETW", "BRCLRW"}

# RAM variable -> unit of a byte access, of a word access
UNIT_BYTE = {"EngineRpm": "rpm32", "SegmentRpm": "rpm32", "IdleTarget": "rpm32", "CoolantTemp": "tempc",
             "AirTemp": "tempc", "StartCoolantTemp": "tempc", "StartCoolantTemp2": "tempc", "BatteryTemp": "tempc",
             "Map": "kpa", "MapLast": "kpa", "Baro": "kpa", "ManifoldVacuum": "kpa", "IdleMapLearned": "kpa",
             "BatteryVolts": "volt16", "BatteryVolts2": "volt16", "ChargeTargetVolts": "volt16"}
UNIT_WORD = {"EngineRpm": "rpmw", "SegmentRpm": "rpmw", "IdleTarget": "rpmw"}
WORDNAME = {"EngineRpm": "Rpm", "SegmentRpm": "SegRpm", "CoolantTemp": "Coolant", "StartCoolantTemp": "StartCoolant",
            "StartCoolantTemp2": "StartCoolant", "ThrottleAboveClosed": "Throttle", "VehicleSpeed": "Speed",
            "VehicleSpeedCoarse": "Speed", "VehicleSpeedRaw": "SpeedRaw", "BatteryVolts2": "Volts",
            "BatteryVolts": "Volts", "ManifoldVacuum": "Vacuum", "Count3s": "Time", "MainLoopCounter": "Loop"}
CAT_PREFIX = {"Fuel": "Fuel", "Idle": "Idle", "Spark": "Spark", "Knock": "Knock", "Diagnostics": "Diag",
              "Sensors": "Sensor", "EVAP purge": "Purge", "Speed control": "SpeedCtl", "EGR": "Egr",
              "Closed loop": "O2", "Cooling fan": "Fan", "A/C": "Ac", "Other": "Cal", "Startup": "Start"}


def words(name):
    return re.findall(r"[A-Z][a-z0-9]*|[A-Z]+(?![a-z])", name)


class Constants:
    def __init__(self, data, an, x, names, cal):
        self.d, self.an, self.x, self.names, self.cal = data, an, x, names, cal
        self.order = sorted(an.insn)
        self.index = {a: n for n, a in enumerate(self.order)}
        self.covered = set()
        for a, i in an.insn.items():
            self.covered.update(range(a, a + i.size))
        self.tabs = []
        for lo, t in cal.items.items():
            self.tabs.append((lo, lo + t["size"]))
        self.tables_of = collections.defaultdict(list)     # routine -> table names it reads
        for a, i in an.insn.items():
            v = dict(i.vals)
            if i.mn in ("LDX", "LDY") and "jjkk" in v and v["jjkk"] in cal.items:
                self.tables_of[x.owner(a)].append(cal.items[v["jjkk"]])

    def in_table(self, a):
        return any(lo <= a < hi for lo, hi in self.tabs)

    def ram_name(self, i):
        v = dict(i.vals)
        if not i.mode.endswith(", Z"):
            return None
        off = v.get("ff", v.get("gggg"))
        if off is None:
            return None
        return self.names.ram.get(off) or "V%04X" % off

    def prev(self, a, back):
        n = self.index.get(a)
        return [self.an.insn[self.order[k]] for k in range(n - 1, max(n - 1 - back, -1), -1)] if n else []

    def nxt(self, a, ahead):
        n = self.index.get(a)
        return [self.an.insn[self.order[k]] for k in range(n + 1, min(n + 1 + ahead, len(self.order)))]

    def source_of(self, a, reg):
        """What was last loaded into reg before the instruction at a."""
        for i in self.prev(a, 5):
            if LOADS.get(i.mn) == reg or (reg == "A" and i.mn == "LDD") or (reg == "B" and i.mn == "LDD"):
                return self.ram_name(i), i.mn == "LDD" and reg in "AB"
            if i.mn == "JSR":
                t = self.names.labels.get(i.target())
                if t and t.startswith("Lookup"):
                    for j in self.prev(i.addr, 4):
                        v = dict(j.vals)
                        if j.mn in ("LDX",) and "jjkk" in v and v["jjkk"] in self.cal.items:
                            return "result of " + self.cal.items[v["jjkk"]]["name"], False
                return None, False
            if i.mn in ("RTS", "RTI", "BRA", "LBRA", "JMP"):
                return None, False
            if i.mn in STORES or i.mn in CMPS or i.mn in BITS or i.mn.startswith("B") or i.mn.startswith("LB") \
                    or i.mn in ("CLC", "SEC", "TST", "TSTA", "TSTB", "TSTD", "TSTE", "PSHM", "PULM"):
                continue
            if reg in ("A", "D") and i.mn in ("TBA", "XGAB") or reg in ("B", "D") and i.mn in ("TAB", "XGAB"):
                return None, False
            if any(i.mn.endswith(r) for r in (reg, "D" if reg in "AB" else reg)) and i.mn not in LOADS:
                continue     # arithmetic on the same register: keep looking for the load
            return None, False
        return None, False

    def use_of(self, a, reg):
        """What the value loaded at a is compared with, added to or stored into."""
        for i in self.nxt(a, 4):
            nm = self.ram_name(i)
            if CMPS.get(i.mn) == reg and nm:
                return "Thresh", nm
            if STORES.get(i.mn) == reg and nm:
                return "Init", nm
            if (ADDS.get(i.mn) == reg or SUBS.get(i.mn) == reg) and nm:
                return "Value", nm
            if i.mn in ("MUL", "EMUL", "EMULS", "FMULS"):
                return "Factor", None
            if i.mn in ("JSR", "RTS") or i.mn.startswith("B") or i.mn.startswith("LB"):
                break
        return "Value", None

    def find(self):
        acc = collections.defaultdict(list)     # start address -> [(insn, width)]
        for a, i in self.an.insn.items():
            v = dict(i.vals)
            if "hhll" not in v or i.mn in ("JMP", "JSR") or i.mode.endswith(", Z"):
                continue
            h = v["hhll"]
            if h >= len(self.d) or h in self.covered or self.in_table(h):
                continue
            if i.mn.startswith("ST") or i.mn in ("CLR", "CLRW", "INC", "DEC", "BSET", "BCLR"):
                continue
            w = 2 if (i.mn in ("LDD", "LDE", "LDX", "LDY", "LDED") or CMPS.get(i.mn) in WORDREG or
                      ADDS.get(i.mn) in WORDREG or SUBS.get(i.mn) in WORDREG or ANDS.get(i.mn) in WORDREG or
                      i.mn.endswith("W")) else 1
            if i.mn == "LDED":
                w = 4
            acc[h].append((i, w))
        out = {}
        end = -1
        for h in sorted(acc):
            w = max(wd for _, wd in acc[h])
            if h < end:          # inside the previous constant
                out[max(k for k in out if k < h)]["inner"].append(h)
                out[max(k for k in out if k < h)]["uses"] += [self.use(i) for i, _ in acc[h]]
                continue
            nxt = [k for k in acc if h < k < h + w]
            out[h] = {"size": w, "uses": [self.use(i) for i, _ in acc[h]], "inner": nxt,
                      "flags": any(i.mn in BITS for i, _ in acc[h]) and all(i.mn in BITS for i, _ in acc[h])}
            end = h + w
        return out

    def use(self, i):
        v = dict(i.vals)
        mn = i.mn
        r = {"at": i.addr, "mn": mn, "owner": self.x.owner(i.addr)}
        if mn in BITS:
            r["mask"] = v.get("mm", v.get("mmmm"))
            r["role"] = "Flag"
        elif mn in CMPS:
            r["role"], (r["var"], _) = "Thresh", self.source_of(i.addr, CMPS[mn])
        elif mn in ADDS:
            r["role"], (r["var"], _) = "Adder", self.source_of(i.addr, ADDS[mn])
        elif mn in SUBS:
            r["role"], (r["var"], _) = "Offset", self.source_of(i.addr, SUBS[mn])
        elif mn in ANDS:
            r["role"], (r["var"], _) = "Mask", self.source_of(i.addr, ANDS[mn])
        elif mn in LOADS:
            r["role"], r["var"] = self.use_of(i.addr, LOADS[mn])
        elif mn in ("TST", "TSTW"):
            r["role"] = "Switch"
        else:
            r["role"] = "Value"
        return r

    def callers_of(self, o):
        if not hasattr(self, "_callers"):
            self._callers = collections.defaultdict(set)
            for a, i in self.an.insn.items():
                if i.mn in ("JSR", "BSR", "LBSR") and i.target() is not None:
                    self._callers[i.target()].add(self.x.owner(a))
        return self._callers.get(o, set())

    def nearest(self, owners, depth=4):
        """Owners, or failing tables there, the nearest callers that read tables."""
        level = set(owners)
        seen = set(level)
        for _ in range(depth + 1):
            hit = sorted(o for o in level if self.tables_of.get(o))
            if hit:
                return hit
            nxt = set()
            for o in level:
                nxt |= self.callers_of(o)
            level = nxt - seen
            seen |= level
        return []

    def prefix_direct(self, owners):
        votes = collections.Counter()
        for o in owners:
            for t in self.tables_of.get(o, []):
                w = words(t["name"])
                if w:
                    votes[w[0]] += 1
        if votes:
            return votes.most_common(1)[0][0]
        return None

    def category_direct(self, owners):
        cats = collections.Counter()
        for o in owners:
            for t in self.tables_of.get(o, []):
                cats[self.cat_of.get(t["name"])] += 1
        cats.pop(None, None)
        return cats.most_common(1)[0][0] if cats else None


FAULT_TABLE, FAULT_ROW = 0x4052, 10
REPORT = {0x245CC: "fail", 0x24160: "pass"}     # ReportFault, ReportPass: Y = fault table row


def fault_codes(data, an, x):
    """Routine -> P-codes it reports (LDY #row then JSR ReportFault/ReportPass)."""
    order = sorted(an.insn)
    idx = {a: n for n, a in enumerate(order)}
    out = collections.defaultdict(set)
    for a, i in an.insn.items():
        if i.mn != "JSR" or i.target() not in REPORT:
            continue
        for k in range(idx[a] - 1, max(idx[a] - 6, 0), -1):
            j = an.insn[order[k]]
            y = dict(j.vals).get("jjkk")
            if j.mn == "LDY" and y is not None:
                if FAULT_TABLE <= y < FAULT_TABLE + 256 * FAULT_ROW and (y - FAULT_TABLE) % FAULT_ROW == 0:
                    b = data[y + 6:y + 8]
                    if any(b):
                        out[x.owner(a)].add("P%02X%02X" % (b[0], b[1]))
                break
    return out


def build(data, an, x, names, cal, top=None, cats=None):
    """Structural entries for every constant; top(owner) -> routine used for the prefix."""
    c = Constants(data, an, x, names, cal)
    c.cat_of = cats or {}
    faults = fault_codes(data, an, x)
    found = c.find()
    entries = {}
    for h, k in found.items():
        uses = k["uses"]
        owners = sorted({u["owner"] for u in uses if u["owner"] is not None})
        own_g = next((G[o] for o in owners if o in G), None)
        pre, cat = (own_g[0], own_g[1]) if own_g else (c.prefix_direct(owners), c.category_direct(owners))
        if pre is None or cat is None:
            g = next((G.get(top(o)) for o in owners if top and G.get(top(o))), None)
            if g:
                pre, cat = pre or (g[0] if cat is None or cat == g[1] else None), cat or g[1]
        if cat is None:
            cat = c.category_direct(c.nearest(owners, 2))
        pre = pre or CAT_PREFIX.get(cat) or "Cal"
        roles = collections.Counter(u["role"] for u in uses)
        role = roles.most_common(1)[0][0]
        varc = collections.Counter(u.get("var") for u in uses if u.get("var"))
        var = varc.most_common(1)[0][0] if varc else None
        vword = None
        if var and not var.startswith("result of"):
            vword = WORDNAME.get(var, var)
            if vword.startswith(pre) and len(vword) > len(pre):
                vword = vword[len(pre):]
        elif var:
            vword = None
        unit = "raw"
        if var in UNIT_BYTE or var in UNIT_WORD:
            unit = (UNIT_WORD if k["size"] == 2 else UNIT_BYTE).get(var, "raw")
        e = {"size": k["size"], "unit": unit, "auto": True, "category": cat or "Other"}
        if k["flags"]:
            masks = collections.defaultdict(set)
            for u in uses:
                if u.get("mask") is not None:
                    masks[u["mask"]].add(u["owner"])
            e["bits"] = ["%02X" % m for m in sorted(masks)]
            e["base"] = pre + "Options"
            e["desc"] = "Option byte; bits tested: %s. Read by %s." % (
                ", ".join("$%02X" % m for m in sorted(masks)), routines_text(names, owners))
        else:
            e["base"] = pre + (vword or "") + role
            what = {"Thresh": "compared with", "Adder": "added to", "Offset": "subtracted from", "Mask": "mask for",
                    "Init": "stored into", "Factor": "multiplied", "Switch": "tested (zero = off)",
                    "Value": "used with", "Flag": "tested"}[role]
            ctx = ("%s %s" % (what, var)) if var else what
            if role == "Factor" and var:
                ctx = "factor, with " + var
            e["desc"] = "%s %s; read by %s." % ("Word" if k["size"] == 2 else ("Long" if k["size"] == 4 else "Byte"),
                                                ctx, routines_text(names, owners))
        codes = sorted(set().union(*[faults.get(o, set()) for o in owners])) if owners else []
        if codes:
            e["desc"] += " Fault: %s." % ", ".join(codes)
        entries["%04X" % h] = e
    # numbering of repeated names
    count = collections.Counter(e["base"] for e in entries.values())
    seen = collections.Counter()
    for k in sorted(entries):
        e = entries[k]
        b = e.pop("base")
        if count[b] > 1:
            seen[b] += 1
            e["name"] = b + str(seen[b])
        else:
            e["name"] = b
    return entries


TOPS = {0x0DC36, 0x0DBCA, 0x08344, 0x0A02E, 0x0D08C, 0x08520, 0x08DD4}   # as in autoname.py


def top_function(x, an):
    callers = collections.defaultdict(set)
    for a, i in an.insn.items():
        if i.mn == "JSR" and i.target() is not None:
            callers[i.target()].add(x.owner(a))

    def chain(o, seen=()):
        if o in TOPS or not callers.get(o) or len(seen) > 6:
            return [o]
        best = None
        for c in sorted(callers[o]):
            if c in seen:
                continue
            ch = chain(c, seen + (o,))
            if best is None or len(ch) < len(best):
                best = ch
        return [o] + (best or [])

    def top(o):
        ch = chain(o)
        return ch[-2] if len(ch) > 1 and ch[-1] in TOPS else ch[-1]
    return top


def routines_text(names, owners):
    ns = [names.labels.get(o, "Sub_%05X" % o) for o in owners]
    return ", ".join(ns[:3]) + (" +%d" % (len(ns) - 3) if len(ns) > 3 else "")


def main():
    os.chdir(ROOT)
    from xref import Xref
    from gen_source import Names, annotation_set, Calibration
    d = open("roms/05293190AC.bin", "rb").read()
    x = Xref(d); an = x.an
    own, ref = annotation_set(d, "05293190AC")
    names = Names(an, d, own, ref)
    p = "annotations/tables.json"
    tab = json.load(open(p))
    hand = {k: v for k, v in tab.get("scalars", {}).items() if not v.get("auto")}
    if len(sys.argv) > 1:
        for k, v in json.load(open(sys.argv[1])).items():
            hand[k] = {**hand.get(k, {}), **v}
    tab["scalars"] = dict(hand)
    cal = Calibration(d, an, names, lambda n: tab if n == "tables.json" else own(n))
    ents = build(d, an, x, names, cal, top_function(x, an),
                 {t["name"]: t.get("category") for t in tab["tables"].values()})
    tnames = {t["name"] for t in tab["tables"].values()} | set(names.ram.values())
    bad = sorted(v["name"] for v in hand.values() if v["name"] in tnames)
    if bad:
        raise SystemExit("constant names already used by a table or RAM variable: " + ", ".join(bad))
    seen = {}
    for k, v in sorted(hand.items()):
        seen.setdefault(v["name"], []).append(k)
    dup = sorted("%s (%s)" % (n, ", ".join(a)) for n, a in seen.items() if len(a) > 1)
    if dup:
        raise SystemExit("constant names used twice: " + "; ".join(dup))
    used = {v["name"] for v in hand.values()} | tnames
    used |= set(names.ram.values())
    out = dict(hand)
    for k, e in ents.items():
        if k in hand:
            for f in ("readers", "value"):
                out[k].pop(f, None)
            for f in ("size", "bits"):
                if f in e:
                    out[k][f] = e[f]
            out[k].setdefault("category", e["category"])
            continue
        n, base, i = e["name"], e["name"], 1
        while n in used:
            i += 1
            n = "%s_%d" % (base, i)
        e["name"] = n
        used.add(n)
        out[k] = e
    tab["scalars"] = dict(sorted(out.items()))
    json.dump(tab, open(p, "w"), indent=1)
    open(p, "a").write("\n")
    flags = sum(1 for e in out.values() if e.get("bits"))
    print("%d constants (%d hand, %d option bytes with %d bits)" % (
        len(out), len(hand), flags, sum(len(e.get("bits", {})) for e in out.values())))


if __name__ == "__main__":
    main()
