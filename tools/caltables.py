#!/usr/bin/env python3
"""Find the calibration tables of an SBEC3 image from the calls to the table lookup routines.

    python3 tools/caltables.py roms/05293190AC.bin [--json out.json]

The lookup routines take the table address in X (XK is forced to 0, so all tables lie in bank 0).
For every call the code before it is searched for `LDX #table`, and for the registers that carry
the inputs. The table header then gives the size. Formats (see docs/en/calibration.md):

  2D   Lookup2D      n, flags, n x (x, y)                    x ascending, bytes
  2Dr  Lookup2DRev   n, -,     n x (y, x)                    the same with the pair reversed
  3D   Lookup3D      ny, nx, sign, nx axis bytes, ny x nx    row input 0-255, column input on the axis
  3Dn  Lookup3DNorm  ny, nx, sign, ny x nx                   both inputs 0-255 (no stored axis)
"""
import collections, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from analyse import Analysis

# lookup routines, found by the first 20 bytes of their code. The 256 KB program has them at
# $0C08E, $0C36A, $0C214 and $0C28C (05293190AC); the 128 KB programs use an older version of the
# 2D and 3D routines with the same table formats.
SIGNATURES = {
    "2D": ["342a3715379c275cc5003c02f801b730f8ffb72c", "342a3715379c275cc5003c02f801b72cf8ffb728"],
    "2Dr": ["34283715379cc500378700463c0248013783003a"],
    "3D": ["342a373ffff6275c274f277b3715379d8d075501", "342a37183715379c37193708275c3d03d800b30c"],
    "3Dn": ["342a373ffff6275c274f34013715379d8d075501", "342a37183715379c37193708450137013724275c"],
}
NAMES = {"2D": "Lookup2D", "2Dr": "Lookup2DRev", "3D": "Lookup3D", "3Dn": "Lookup3DNorm"}
ROUTINES = {}


def routines(data):
    """address -> table kind, for the lookup routines present in this image."""
    out = {}
    for kind, sigs in SIGNATURES.items():
        for sig in sigs:
            a = data.find(bytes.fromhex(sig))
            if a >= 0 and not a & 1:
                out[a] = kind
    return out
WRITES_X = {"LDX", "TZX", "TSX", "TYX", "XGDX", "XGEX", "XGXY", "PULM", "AIX", "ABX", "ADX", "AEX"}


def table_size(d, a, kind):
    if kind in ("2D", "2Dr"):
        return 2 + 2 * d[a]
    ny, nx = d[a], d[a + 1]
    return 3 + (nx if kind == "3D" else 0) + nx * ny


def source_of(prev, reg):
    """Last instruction before the call that loads reg (A or B) directly, as text."""
    names = {"A": ("LDAA",), "B": ("LDAB",)}[reg]
    for p in prev:
        if p.mn in names:
            return "%s %s" % (p.mn, p.mode), dict(p.vals)
        if p.mn.startswith("JSR"):
            t = p.target()
            if t in ROUTINES:
                return "result of $%05X" % t, {}
            return None, {}
        if reg == "A" and p.mn in ("TBA", "PULM", "XGAB", "LDD") or reg == "B" and p.mn in ("TAB", "XGAB", "LDD"):
            return p.mn, {}
    return None, {}


def operand(desc, vals):
    if desc is None:
        return "?"
    if "gggg" in vals and "IND16, Z" in desc:
        return "$%04X,Z" % vals["gggg"]
    if "ff" in vals and "IND8, Z" in desc:
        return "$%02X,Z" % vals["ff"]
    if "hhll" in vals:
        return "$%04X" % vals["hhll"]
    if "ii" in vals:
        return "#$%02X" % vals["ii"]
    return desc


def predecessors(an):
    """address -> instructions that can run right before it (fall-through and branches)."""
    pred = collections.defaultdict(list)
    for a, ins in an.insn.items():
        nxt = a + ins.size
        if ins.falls_through() and nxt in an.insn:
            pred[nxt].append(ins)
        t = ins.target()
        if t is not None and t in an.insn and ins.mn not in ("JSR", "BSR", "LBSR"):
            pred[t].append(ins)
    return pred


def paths_back(an, pred, a, depth=14):
    """All instruction sequences (newest first) of up to depth instructions leading to a."""
    out = []

    def walk(addr, seq):
        ps = pred.get(addr, [])
        if len(seq) >= depth or not ps:
            out.append(seq)
            return
        for p in ps:
            if p in seq:
                out.append(seq)
                continue
            if p.mn in ("JSR", "RTS", "RTI"):
                out.append(seq + [p])
            else:
                walk(p.addr, seq + [p])
    walk(a, [])
    return out


def find(data, an=None):
    an = an or Analysis(data).run()
    ROUTINES.clear()
    ROUTINES.update(routines(data))
    pred = predecessors(an)
    tables = {}
    unresolved = []
    for a in sorted(an.insn):
        ins = an.insn[a]
        if ins.mn != "JSR" or ins.target() not in ROUTINES:
            continue
        kind = ROUTINES[ins.target()]
        found = []
        for prev in paths_back(an, pred, a):
            tab = None
            for p in prev:
                if p.mn == "LDX" and p.mode == "IMM16":
                    tab = dict(p.vals)["jjkk"]
                    break
                if p.mn in WRITES_X:
                    break
            if tab is None:
                continue
            ina = operand(*source_of(prev, "A"))
            inb = operand(*source_of(prev, "B")) if kind == "3D" else None
            found.append((tab, (ina, inb) if inb else (ina,)))
        if not found:
            unresolved.append(a)
            continue
        dest = None
        b = a + ins.size
        for _ in range(6):
            n = an.insn.get(b)
            if n is None or n.mn in ("JSR", "RTS", "JMP", "BRA", "LBRA"):
                break
            if n.mn in ("STAA", "STAB", "STD", "STE") and n.mode.endswith(", Z"):
                v = dict(n.vals)
                dest = v.get("ff", v.get("gggg"))
                break
            b += n.size
        for tab, key in dict.fromkeys(found):
            t = tables.setdefault(tab, {"kind": kind, "size": table_size(data, tab, kind), "calls": [],
                                        "inputs": collections.Counter(), "dest": collections.Counter()})
            if dest is not None:
                t["dest"][dest] += 1
            if a not in t["calls"]:
                t["calls"].append(a)
            t["inputs"][key] += 1
    return an, tables, unresolved


def describe(d, a, kind):
    if kind in ("2D", "2Dr"):
        n = d[a]
        pts = [(d[a + 2 + 2 * i], d[a + 3 + 2 * i]) for i in range(n)]
        if kind == "2Dr":
            pts = [(x, y) for y, x in pts]
        return {"points": n, "flags": d[a + 1], "xy": pts}
    ny, nx, sign = d[a], d[a + 1], d[a + 2]
    out = {"rows": ny, "cols": nx, "signed": sign != 0}
    p = a + 3
    if kind == "3D":
        out["x_axis"] = list(d[p:p + nx])
        p += nx
    out["data"] = [list(d[p + r * nx:p + (r + 1) * nx]) for r in range(ny)]
    return out


def main():
    path = sys.argv[1]
    d = open(path, "rb").read()
    an, tables, unresolved = find(d)
    kinds = collections.Counter(t["kind"] for t in tables.values())
    print("%d tables (%s), %d calls with the table not in an LDX #" % (
        len(tables), ", ".join("%s: %d" % kv for kv in sorted(kinds.items())), len(unresolved)))
    for a in sorted(tables):
        t = tables[a]
        ins = "; ".join(" x ".join(k) + ("" if n == 1 else " (%d)" % n) for k, n in t["inputs"].most_common(3))
        print("$%04X %-3s %4d bytes  %2d calls  in: %s" % (a, t["kind"], t["size"], len(t["calls"]), ins))
    if "--json" in sys.argv:
        out = {"%04X" % a: {"kind": t["kind"], "size": t["size"],
                            "calls": ["%05X" % c for c in t["calls"]],
                            "inputs": [list(k) for k in t["inputs"]],
                            **describe(d, a, t["kind"])} for a, t in sorted(tables.items())}
        json.dump(out, open(sys.argv[sys.argv.index("--json") + 1], "w"), indent=1)


if __name__ == "__main__":
    main()
