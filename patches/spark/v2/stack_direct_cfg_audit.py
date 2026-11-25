#!/usr/bin/env python3
"""Conservative direct-control-flow stack accounting for Spark V2.

Counts explicit stack operations and call frames according to cpu16sim.py.
Does NOT model asynchronous IRQ entry/nesting, arbitrary stack writes, or
resolve computed dispatch. Incomplete paths cannot certify RAM ownership.
Peak excludes the root's own call/exception frame. Branch conditions are
overapproximated; unresolved or abnormal paths are reported, not guessed.
"""
from pathlib import Path
import re
from dataclasses import dataclass, field

ROOT = Path(__file__).resolve().parents[3]
CALLS = {"JSR", "BSR", "LBSR"}
COND = re.compile(r"^L?B(CC|CS|EQ|NE|MI|PL|VC|VS|HI|LS|GE|LT|GT|LE)$")
RESET_STACK = re.compile(r"^(LDS|T[XYDEZ]S|TBSK|DES|INS|SWI|WAI|STOP|RESET)$")
EXPECTED = {
    "Lookup2D": 6, "Lookup3D": 16, "CalcSpark": 32,
    "SparkEventCalc": 16, "KnockSample": 10, "FuelEventCalc": 18,
    "Isr_GPT_OC2": 14, "Isr_GPT_OC3": 10, "Isr_GPT_OC4": 10,
    "Isr_IRQ2": 26, "Isr_IRQ4": 22, "Isr_SCI": 8,
}
OPEN = ("MainLoop", "Isr_GPT_IC1", "Isr_GPT_IC4OC5", "Isr_PIT")


@dataclass
class Result:
    peak: int = 0
    returns: bool = False
    issues: set = field(default_factory=set)


def parse(sources):
    code, labels = [], {}
    for source in sources:
        for line in source.splitlines():
            line = " ".join(line.split(";")[0].split())
            if not line:
                continue
            if re.fullmatch(r"\w+:", line):
                name = line[:-1]
                assert name not in labels, name
                labels[name] = len(code)
            else:
                code.append(line)
        code.append("BANK_END")
    return code, labels


class Analyzer:
    def __init__(self, code, labels, dispatch=None):
        self.code, self.labels = code, labels
        self.dispatch = dispatch or {}
        self.cache, self.active = {}, set()

    def solve(self, start, mode="sub"):
        key = (start, mode)
        if key in self.active:
            return Result(issues={f"recursive entry {start}"})
        if key in self.cache:
            return self.cache[key]
        self.active.add(key)
        result = Result()
        todo, seen = [(start, 0)], set()
        while todo:
            i, depth = todo.pop()
            if (i, depth) in seen:
                continue
            seen.add((i, depth))
            if not 0 <= i < len(self.code):
                result.issues.add("outside source")
                continue
            line = self.code[i]
            if depth < 0 or depth > 512 or len(seen) > 150000:
                result.issues.add(f"depth/state limit at {line}")
                continue
            result.peak = max(result.peak, depth)
            op, _, arg = line.partition(" ")

            def advance(d=depth):
                todo.append((i+1, d))

            def jump(name):
                if name in self.labels:
                    todo.append((self.labels[name], depth))
                else:
                    result.issues.add(f"unresolved {line}")

            if op in ("RTS", "RTI"):
                if depth != 0 or op != ("RTI" if mode == "irq" else "RTS"):
                    result.issues.add(f"return {op} depth {depth}")
                else:
                    result.returns = True
            elif op in ("PSHM", "PULM"):
                advance(depth + (2 if op == "PSHM" else -2) * len(arg.split(",")))
            elif op in ("PSHA", "PSHB", "PULA", "PULB"):
                advance(depth + (2 if op.startswith("PSH") else -2))
            elif op == "AIS":
                if not re.fullmatch(r"#\$[0-9A-Fa-f]{2}|#\$[0-9A-Fa-f]{4}", arg):
                    result.issues.add(f"unresolved {line}")
                    continue
                value = int(arg[2:], 16)
                bits = 8 if len(arg) == 4 else 16
                if value >= 1 << (bits-1):
                    value -= 1 << bits
                advance(depth-value)
            elif RESET_STACK.fullmatch(op):
                result.issues.add(f"stack/control {line}")
            elif op in CALLS:
                targets = [arg] if arg in self.labels else self.dispatch.get(arg)
                if not targets:
                    result.issues.add(f"unresolved {line}")
                    continue
                for target in targets:
                    child = self.solve(self.labels[target])
                    result.peak = max(result.peak, depth+4+child.peak)
                    result.issues.update(child.issues)
                    if child.returns:
                        advance()
            elif op in ("JMP", "BRA", "LBRA"):
                for target in self.dispatch.get(arg, [arg]) if op == "JMP" else [arg]:
                    jump(target)
            elif op in ("BRSET", "BRCLR", "LBRSET", "LBRCLR"):
                jump(arg.split(",")[-1])
                advance()
            elif COND.fullmatch(op):
                jump(arg)
                advance()
            elif op.lower().startswith(("dc.", "ds.", "org", "end", "align")) or op == "BANK_END":
                result.issues.add(f"data/end {line}")
            elif op.startswith(("PSH", "PUL")):
                result.issues.add(f"unknown stack op {line}")
            else:
                advance()
        self.active.remove(key)
        self.cache[key] = result
        return result

    def root(self, name):
        return self.solve(self.labels[name], "irq" if name.startswith("Isr_") else "sub")


def selftest():
    a = Analyzer(*parse(["root:\nPSHM D,E\nJSR child\nPULM E,D\nRTS\n"
                         "child:\nPSHB\nPULB\nRTS\n"]))
    r = a.root("root")
    assert r.returns and not r.issues and r.peak == 10
    a = Analyzer(*parse(["root:\nBEQ done\nJMP $00000,X\ndone:\nRTS\n"]))
    r = a.root("root")
    assert r.returns and r.issues == {"unresolved JMP $00000,X"}
    a = Analyzer(*parse(["root:\nPSHM D\nRTS\n"]))
    assert a.root("root").issues == {"return RTS depth 2"}
    a = Analyzer(*parse(["root:\nAIS #$FA\nAIS #$06\nRTS\n"]))
    r = a.root("root")
    assert r.returns and not r.issues and r.peak == 6


# Conditional table expansion only: every listed entry is explored, but
# the runtime index domain and correct K-bank state are separate obligations.
# Explicit lengths are essential: 1996 OBD/SCI tables are adjacent.
TABLES = {
    "04887050": {"0481A": 4, "05E38": 9, "145B6": 18, "1D8BC": 18,
                 "1D800": 33, "1D884": 14},
    "05293013AC": {"0481A": 4, "05E44": 9, "18EEC": 18, "1774C": 18,
                   "17B3A": 33, "17DCC": 14, "18086": 25},
}


def reviewed_dispatch(code, labels, pn):
    dispatch = {}
    for address, count in TABLES[pn].items():
        start = labels["JumpTable_" + address]
        entries = code[start:start+count]
        assert len(entries) == count
        assert all(re.fullmatch(r"JMP \w+", x) for x in entries), address
        targets = [x.split()[1] for x in entries]
        assert all(x in labels for x in targets), address
        arg = "$00000,X" if address.startswith("05E") else "$" + address + ",X"
        dispatch[arg] = targets
    address = "1F938" if pn == "04887050" else "1FA06"
    dispatch["$" + address + ",X"] = ["JumpTable_" + address,
        "L1F93E" if pn == "04887050" else "L1FA0C",
        "L1F944" if pn == "04887050" else "L1FA12", "ConditionEntry4"]
    return dispatch


def stock_sources(pn, sources, guard=True):
    """Expand only two byte sequences with reviewed instruction semantics."""
    a, b = [[" ".join(line.split(";")[0].split())
             for line in source.splitlines()] for source in sources]
    a, b = [x for x in a if x], [x for x in b if x]
    i = a.index("MisfireOptions:")
    assert a[i+1] == "dc.b $08", "Misfire calibration changed; review stack"
    is96 = pn == "04887050"
    addr = "1F938" if is96 else "1FA06"
    raw = "dc.b $FA,$01,$F9,$76" if is96 else "dc.b $FA,$01,$FA,$44"
    i = b.index("JumpTable_" + addr + ":")
    assert b[i+9] == raw
    # CPU16 FA = JSR EXT20, 58 = CMPA IND8,Y, B4 = BCC REL8.
    # BCC at $1F978/$1FA46 with displacement zero targets PC+6.
    b[i+9:i+10] = ["ConditionEntry4:", "JSR ConditionFourthCompare"]
    i = b.index("ConditionAbove:")
    j = b.index("dc.b $58,$03,$B4,$00", i)
    assert b[j+1] == ("L1F97A:" if is96 else "L1FA48:")
    b[j:j+1] = ["ConditionFourthCompare:", "CMPA $03,Y",
                "BCC " + ("L1F97E" if is96 else "L1FA4C")]
    # The selector reads offsets 0,6,12,18; all four entries are explored.
    i = b.index("ConditionTable:")
    assert "dc.b $00,$00,$00,$06,$00,$0C,$00,$12" in b[i:i+60]
    i = b.index("MisfireDevCalc:")
    target = "L19CC6" if is96 else "L1CDB4"
    op = "BRCLR >MisfireOptions,#$08," + target
    j = b.index(op, i)
    assert j-i < 15 and b[b.index(target + ":")+1] == "RTS"
    if guard:
        # Only the stock ROM option is fixed; no other branch is pruned.
        b[j] = "STOCK_MISFIRE_GUARD"
    return ["\n".join(a), "\n".join(b)]


def conditional_audit(pn, sources):
    code, labels = parse(stock_sources(pn, sources))
    # Negative regression: without the proven stock guard the imbalance
    # must still be reported, not suppressed globally.
    uc, ul = parse(stock_sources(pn, sources, guard=False))
    unguarded = Analyzer(uc, ul, reviewed_dispatch(uc, ul, pn))
    assert unguarded.root("MisfireDevCalc").issues == {"return RTS depth 4"}

    a = Analyzer(code, labels, reviewed_dispatch(code, labels, pn))
    pit = 38 if pn == "04887050" else 34
    for name, peak in (("ConditionTable", 12), ("MisfireDevCalc", 26),
                       ("Isr_GPT_IC1", 52), ("Isr_GPT_IC4OC5", 28), ("Isr_PIT", pit)):
        r = a.root(name)
        assert r.returns and not r.issues and r.peak == peak, (pn, name, r)
        print(f"{pn}: {name}: {r.peak} bytes; conditional table expansion")
    print(f"{pn}: MisfireOptions bit 3 guard required; unguarded imbalance reproduced")
    print("Table index bounds, bank state and asynchronous nesting are not certified.")


# Additional tables reached from MainLoop. Kept separate from the
# earlier IRQ regression so changes to main-loop coverage are explicit.
MAIN_TABLES = {
    "04887050": {"114A6": 5, "115AE": 6, "116E8": 5, "12700": 30,
                 "12778": 12, "127A8": 3, "127B4": 67, "19D1C": 10},
    "05293013AC": {"113A6": 5, "114AE": 6, "115E8": 5, "158C0": 30,
                   "15938": 12, "15968": 4, "15978": 67, "1E81A": 10},
}


def main_dispatch(code, labels, pn):
    dispatch = reviewed_dispatch(code, labels, pn)
    for address, count in MAIN_TABLES[pn].items():
        start = labels["JumpTable_" + address]
        entries = code[start:start+count]
        assert len(entries) == count
        assert all(re.fullmatch(r"JMP \w+", x) for x in entries), address
        targets = [x.split()[1] for x in entries]
        assert all(x in labels for x in targets), address
        dispatch["$" + address + ",X"] = targets
    # OBD monitor table is 11 pairs JSR + BRA (6 bytes per entry),
    # not a table of plain JMPs. Execute the entry, including its call.
    address = "1FAE2" if pn == "04887050" else "1FC22"
    end = "L1FB24" if pn == "04887050" else "L1FC64"
    start = labels["JumpTable_" + address]
    targets = ["JumpTable_" + address]
    for k in range(11):
        i = start + 2*k
        assert code[i].startswith("JSR ") and code[i][4:] in labels
        assert code[i+1] == "BRA " + end
        if k:
            target = f"L{int(address, 16)+6*k:05X}"
            assert labels[target] == i
            targets.append(target)
    assert labels[end] == start + 22
    dispatch["$" + address + ",Y"] = targets
    return dispatch


def mainloop_audit(pn, sources):
    # Normal main-loop entry invariant: SP=$F87FE; HardwareCheck is
    # called directly, so its entry SP=$F87FA. Recovery of a corrupt
    # SP is a separate path and is intentionally not certified here.
    stock = stock_sources(pn, sources)
    lines = stock[0].splitlines()
    start = lines.index("MainLoop:")
    end = lines.index("JMP MainLoop", start)
    roots = list(dict.fromkeys(x[4:] for x in lines[start:end]
                               if x.startswith("JSR ")))
    h = lines.index("HardwareCheck:")
    t = lines.index("TBSK", h)
    assert lines[t-2:t+3] == ["LDAB #$0F", "TBZK", "TBSK",
                               "LDZ #$8000", "CPS #$87FA"]
    target = "L0D5CC" if pn == "04887050" else "L0D71A"
    assert lines[t+3] == "BEQ " + target
    assert "LDS #$87FA" in lines[t+4:lines.index(target + ":", t)]
    lines[t] = "NORMAL_SKB"
    lines[t+3] = "BRA " + target
    code, labels = parse(["\n".join(lines), stock[1]])
    analyzer = Analyzer(code, labels, main_dispatch(code, labels, pn))
    complete, pending = {}, {}
    for name in roots:
        r = analyzer.root(name)
        peak = r.peak + 4  # include MainLoop JSR frame
        if r.returns and not r.issues:
            complete[name] = peak
        else:
            pending[name] = (peak, sorted(r.issues))
    expected = 131 if pn == "04887050" else 132
    assert len(roots) == expected
    assert len(complete) == expected-3
    assert max(complete.values()) == (56 if pn == "04887050" else 58)
    assert complete["ObdMonitorMain"] == max(complete.values())
    assert complete["SpeedCtlControl"] == 42
    assert complete["SpeedCtlSwitchRead"] == (34 if pn == "04887050" else 36)
    assert complete["ActuatorTestMain"] == 12
    assert set(pending) == {"ClosedLoopMain", "BusDataRequest", "CheckPowerDown"}
    assert any("recursive" in x for x in pending["ClosedLoopMain"][1])
    assert "unresolved JMP $F8700" in pending["BusDataRequest"][1]
    assert "stack/control TBSK" in pending["CheckPowerDown"][1]
    print(f"{pn}: main loop {len(complete)}/{len(roots)} direct roots balanced; "
          f"maximum among closed roots {max(complete.values())} bytes")
    for name, info in pending.items():
        print(f"{pn}: main loop OPEN {name}: {info}")
    print("Main loop result assumes normal initial SP and reviewed dispatch; not a global bound.")


def audit(pn):
    base = ROOT / "src" / pn
    sources = [(base / name).read_text() for name in ("bank0.asm", "bank1.asm")]
    a = Analyzer(*parse(sources))
    for name, expected in EXPECTED.items():
        r = a.root(name)
        assert r.returns and not r.issues and r.peak == expected, (pn, name, r)
        print(f"{pn}: {name}: {r.peak} bytes; direct flow balanced")
    for name in OPEN:
        r = a.root(name)
        print(f"{pn}: {name}: partial peak {r.peak}; unresolved {sorted(r.issues)}")
    conditional_audit(pn, sources)
    mainloop_audit(pn, sources)
    print("No global maximum: computed dispatch, stack reset paths, IRQ nesting and stack writes remain open.")


if __name__ == "__main__":
    selftest()
    for pn in ("04887050", "05293013AC"):
        audit(pn)
