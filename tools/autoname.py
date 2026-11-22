#!/usr/bin/env python3
"""Structured names for the calibration tables of the reference image that have no curated name.

    python3 tools/autoname.py

The name is the subsystem prefix (from the routine that reads the table and the scheduled routine
above it) plus the inputs (Coolant, Rpm, Map ...; V0A91 for a RAM variable without a name yet),
numbered when repeated. Entries are written to annotations/tables.json with "auto": true; entries
without that flag are curated and never touched, and OVR below holds names given by hand. Re-run
after naming RAM variables or routines to refresh the structural names.
"""
import os, sys, collections, json, re
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, "tools")
from xref import Xref
from gen_source import Names, annotation_set, Calibration

d = open("roms/05293190AC.bin", "rb").read()
x = Xref(d); an = x.an
own, ref = annotation_set(d, "05293190AC")
names = Names(an, d, own, ref)
cal = Calibration(d, an, names, own)
nm = lambda a: names.labels.get(a, "%05X" % a)

callers = collections.defaultdict(set)
for a, i in an.insn.items():
    if i.mn == "JSR" and i.target() is not None:
        callers[i.target()].add(x.owner(a))
TOPS = {0x0DC36, 0x0DBCA, 0x08344, 0x0A02E, 0x0D08C, 0x08520, 0x08DD4}


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


# top routine (or the owner itself) -> (name prefix, category, subsystem text)
G = {}
def grp(addrs, prefix, cat, text):
    for a in addrs:
        G[a] = (prefix, cat, text)
FUEL = "fuel calculation (main loop)"
grp([0x1001C, 0x105EC, 0x102FE, 0x104AE, 0x10A6E, 0x10AEC, 0x11074, 0x111E0], "Fuel", "Fuel", FUEL)
grp([0x10036], "FuelCut", "Fuel", "fuel cut-off: rev and speed limits, deceleration")
grp([0x106EC, 0x107EA], "AccelFuel", "Fuel", "acceleration enrichment (throttle and MAP rate)")
grp([0x10C00], "AfterStartFuel", "Fuel", "after-start enrichment (time since start x coolant)")
grp([0x112A8, 0x11F40, 0x1204A, 0x1202A, 0x12680], "FuelEvent", "Fuel", "fuel calculation per reference event")
grp([0x123C0], "CrankFuel", "Fuel", "cranking fuel")
grp([0x14160, 0x1424C, 0x142C8], "O2", "Closed loop", "oxygen-sensor closed loop and adaptive fuel")
grp([0x19000, 0x1A5CA, 0x1A688, 0x1A6E2, 0x1BA5E, 0x1BAAE, 0x2D086], "Idle", "Idle", "idle speed control")
grp([0x1D000, 0x1DB84, 0x1DC20, 0x1DEDC, 0x1E14E, 0x1E2B6, 0x39412], "Spark", "Spark", "spark advance")
grp([0x1F000, 0x1F408], "Knock", "Spark", "knock control")
grp([0x2A81A, 0x2A906, 0x2B456, 0x2AC02, 0x2B692], "Misfire", "Diagnostics", "misfire monitor (crankshaft segment times)")
grp([0x20284, 0x2197C, 0x231A8, 0x2432A, 0x245CC], "Diag", "Diagnostics", "on-board diagnostic monitors")
grp([0x2C1BC, 0x2C6DE, 0x2C7FE, 0x2CB0E, 0x2CB60, 0x2CCA8, 0x2D1F6, 0x2D698, 0x2DADE, 0x2DC88, 0x0EC3A], "Sensor", "Sensors", "sensor processing")
grp([0x3B800, 0x3C46E], "SpeedCtl", "Speed control", "speed control (cruise), probable")
grp([0x0D08C], "Start", "Startup", "initialisation at reset")
grp([0x0A02E], "Event", "Other", "reference-event interrupt (input capture 1)")
grp([0x17000, 0x17FC4, 0x183C2, 0x17A48, 0x17D44, 0x181BE, 0x187E8, 0x18A8E, 0x18B22, 0x18BAA, 0x18836],
    "FlexLearn", "Fuel", "flex-fuel ethanol content learning")
grp([0x39E1A, 0x3A7A4, 0x3A8D2, 0x3AA44, 0x3ABFE], "Fan", "Cooling fan", "radiator fan control (relay and PWM variants)")
grp([0x39686], "Egr", "EGR", "EGR control, probable")
grp([0x2F000], "AcCtl", "A/C", "A/C clutch control, probable")
grp([0x3D800], "Purge", "EVAP purge", "EVAP purge control, probable")
OTHER = {0x08DD4: "Pit", 0x2C708: "Sys2C708", 0x2F000: "Sys2F000", 0x39686: "Sys39686",
         0x39E1A: "Sys39E1A", 0x3AE3C: "Sys3AE3C", 0x3D800: "Sys3D800"}
for a, p in OTHER.items():
    G.setdefault(a, (p, "Other", "not identified yet (top routine %s)" % nm(a)))

WORD = {"EngineRpm": "Rpm", "SegmentRpm": "SegRpm", "CoolantTemp": "Coolant", "AirTemp": "AirTemp", "Map": "Map",
        "MapLast": "Map", "Baro": "Baro", "ManifoldVacuum": "Vacuum", "Throttle": "Throttle",
        "ThrottleAboveClosed": "Throttle", "ThrottleLast": "Throttle", "VehicleSpeed": "Speed",
        "VehicleSpeedCoarse": "Speed", "BatteryVolts": "Volts", "BatteryVolts2": "Volts",
        "StartCoolantTemp": "StartCoolant", "StartCoolantTemp2": "StartCoolant", "Count3s": "Time",
        "IdleTarget": "IdleTarget", "O2UpBank1Raw": "O2", "O2UpBank2Raw": "O2", "O2UpBank1": "O2", "O2UpBank2": "O2",
        "ShortTermTrim1": "Trim", "ShortTermTrim2": "Trim", "CoolantRaw": "CoolantRaw", "AirTempRaw": "AirTempRaw"}
UNIT = {"Rpm": "rpm32", "SegRpm": "rpm32", "IdleTarget": "rpm32", "Coolant": "tempc", "AirTemp": "tempc",
        "StartCoolant": "tempc", "Map": "kpa", "Baro": "kpa", "Vacuum": "kpa", "Volts": "volt16"}


def var_of(s):
    m = re.match(r"^\$([0-9A-F]{2,4}),Z$", s or "")
    return names.ram.get(int(m.group(1), 16)) if m else None


LOOKUPS = {a for a, k in __import__("caltables").routines(d).items()}
ORDER = sorted(an.insn)
INDEX = {a: i for i, a in enumerate(ORDER)}


def role(calls):
    """How the result is used right after the lookup: Factor, Adder, Limit, Scale or ''."""
    votes = collections.Counter()
    for c in calls:
        i = INDEX[c] + 1
        for _ in range(5):
            if i >= len(ORDER):
                break
            n = an.insn[ORDER[i]]
            i += 1
            t = n.target()
            if n.mn == "JSR" and t in LOOKUPS:
                votes["Scale"] += 1
                break
            if n.mn == "JSR" and names.labels.get(t) == "ScaleByFraction" or n.mn in ("MUL", "EMUL", "EMULS"):
                votes["Factor"] += 1
                break
            if n.mn in ("ADDA", "ADDB", "ABA", "ADDD", "ADE", "ADDE", "ADCE"):
                votes["Adder"] += 1
                break
            if n.mn in ("CMPA", "CMPB", "CBA", "CPD", "CPE"):
                votes["Limit"] += 1
                break
            if n.mn in ("JSR", "RTS", "BRA", "LBRA", "JMP") or n.mn.startswith("ST"):
                break
    return votes.most_common(1)[0][0] if votes else ""


# variant of a table chosen by a flag test right before its LDX #table:
# BRCLR flag,L / LDX #table  -> the table is used while the flag is set
FLAGS = {(0x0055, 0x20): "AC", (0x0C31, 0x20): "PN", (0x0C30, 0x80): "Closed", (0x0C30, 0x40): "Wot",
         (0x0943, 0x01): "AcOn"}
VARIANT = {}
for _a in ORDER:
    _i = an.insn[_a]
    if _i.mn == "LDX" and _i.mode == "IMM16":
        _j = INDEX[_a]
        if _j == 0:
            continue
        _p = an.insn[ORDER[_j - 1]]
        _v = dict(_p.vals)
        if _p.mn in ("BRCLR", "BRSET") and _p.addr + _p.size == _a:
            off = _v.get("ff", _v.get("gggg"))
            key = (off, _v.get("mm"))
            if key in FLAGS and _p.mode.endswith(", Z"):
                VARIANT.setdefault(dict(_i.vals)["jjkk"], set()).add(FLAGS[key] if _p.mn == "BRCLR" else "No" + FLAGS[key])


def variant(a):
    v = VARIANT.get(a, set())
    return "".join(sorted(x for x in v if not x.startswith("No"))) if len(v) == 1 or all(not x.startswith("No") for x in v) else ""


def word(s):
    if not s:
        return "X"
    if s.startswith("result of"):
        return "Scaled"
    v = var_of(s)
    if v:
        return WORD.get(v, v)
    m = re.match(r"^\$([0-9A-F]{2,4}),Z$", s)
    if m:
        return "V%04X" % int(m.group(1), 16)
    if s.startswith("#"):
        return "Const"
    if re.match(r"^\$[0-9A-F]{4}$", s):
        return "Cal"
    return "X"


cur = json.load(open("annotations/tables.json"))
T = cur["tables"]
if len(sys.argv) > 1:      # merge hand names given as a JSON file {addr: {name, desc, category, x, y, z}}
    for k, v in json.load(open(sys.argv[1])).items():
        T[k] = dict(v, auto=False)
used = set(names.labels.values()) | set(names.ram.values()) | set(names.regs.values()) | \
    {v["name"] for v in T.values() if not v.get("auto")}
used |= {v["name"] for v in cur.get("scalars", {}).values()} | {v["name"] for v in cur.get("special", {}).values()}

OVR = {
    "0E6C": ("FuelAirTempCorr", "Fuel multiplier against intake air temperature (scaled by the rpm and MAP weights)", {"x": "tempc", "y": "mult256"}),
    "0E82": ("FuelAirTempRpmWeight", "Weight of the air-temperature fuel correction against rpm", {"x": "rpm32", "y": "mult256"}),
    "0E7A": ("FuelAirTempMapWeight", "Weight of the air-temperature fuel correction against MAP", {"x": "kpa", "y": "mult256"}),
    "0D2B": ("PartThrottleFuelMain", "17 x 17 fuel correction, MAP x rpm, used by the main-loop fuel calculation (Sub_10F1C) and by Sys39686; PartThrottleFuel is the per-event one", {"x": "rpm32", "y": "pos256", "z": "fuelcorr"}),
    "0E60": ("MapBaroOffset", "Added to MAP against barometric pressure before the part-throttle MAP scale (main-loop fuel, Sys39686, diagnostics)", {"x": "kpa", "y": "kpa"}),
    "17B2": ("O2VoltageScale", "Upstream O2 sensor ADC counts to the value used by closed loop and its monitor", {"x": "raw", "y": "raw"}),
    "17C2": ("O2VoltageScale2", "Second copy of the O2 voltage scale (same values as O2VoltageScale)", {"x": "raw", "y": "raw"}),
    "24E5": ("KnockRetardLimit", "Knock retard against MAP (rows) and rpm; signed; result scaled by the current knock level into $0D04", {"x": "rpm32", "y": "pos256", "z": "spark"}),
}
gen = {}
count = collections.Counter()
for a in sorted(cal.items):
    t = cal.items[a]
    key = "%04X" % a
    if t["kind"] not in ("2D", "2Dr", "3D", "3Dn") or key in T and not T[key].get("auto") and key not in OVR:
        continue
    owners = collections.Counter(x.owner(c) for c in t.get("calls", []))
    o = owners.most_common(1)[0][0] if owners else None
    tp = top(o) if o is not None else None
    pre, cat, text = G.get(o) or G.get(tp) or ("Misc", "Other", "read by %s" % nm(o or 0))
    inputs = list(t.get("inputs", {}))
    k = t["kind"]
    if k in ("2D", "2Dr"):
        xin = inputs[0][0] if inputs else None
        parts = [word(xin)]
        units = {"x": UNIT.get(parts[0], "raw") if parts[0] != "Scaled" else "pos256", "y": "raw"}
    elif k == "3D":
        rf = list(t.get("row_from", {}))
        # the row comes from a scale table: name the row by that table's own input (Map, Coolant ...)
        sc = cal.items.get(rf[0]) if rf else None
        sin = list(sc.get("inputs", {})) if sc else []
        if sin and not sin[0][0].startswith("result"):
            row = word(sin[0][0])
        else:
            row = "Scaled" if inputs and inputs[0][0].startswith("result") else word(inputs[0][0] if inputs else None)
        col = word(inputs[0][1]) if inputs and len(inputs[0]) > 1 else "X"
        parts = [row, col] if row != "Scaled" else [col]
        units = {"x": UNIT.get(col, "raw"), "y": "pos256", "z": "raw"}
    else:
        parts = ["Table"]
        units = {"y": "pos256", "z": "raw"}
    if key in OVR:
        name, desc, units = OVR[key]
    else:
        base = pre + "".join(p for p in dict.fromkeys(parts) if p not in ("X",)) + role(t.get("calls", [])) + variant(a)
        if base == pre:
            base = pre + "Table"
        name, n = base, 1
        while name in used:
            n += 1
            name = "%s%d" % (base, n)
        dest = [names.ram.get(dd, "$%04X,Z" % dd) for dd in t.get("dest", {})]
        desc = "Subsystem: %s (by the routine that reads it, %s). Inputs: %s.%s" % (
            text, nm(o or 0), cal.input_text(t) or "?", (" Result to %s." % ", ".join(dest)) if dest else "")
    used.add(name)
    e = {"name": name, "desc": desc, "category": cat, "auto": key not in OVR}
    e.update(units)
    gen[key] = e

# curated entries get their category too
CAT = {"Fuel": "Fuel", "Spark": "Spark", "Knock": "Spark", "Idle": "Idle", "Thermistor": "Sensors",
       "Throttle": "Sensors", "Injector": "Fuel"}
for k, v in T.items():
    if "category" not in v:
        v["category"] = next((c for w, c in CAT.items() if w in v["name"]), "Other")
for k, v in gen.items():
    T[k] = v
cur["tables"] = dict(sorted(T.items()))
json.dump(cur, open("annotations/tables.json", "w"), indent=1, ensure_ascii=False)
open("annotations/tables.json", "a").write("\n")
cats = collections.Counter(v["category"] for v in T.values())
print(len(T), "tables named;", dict(cats))
