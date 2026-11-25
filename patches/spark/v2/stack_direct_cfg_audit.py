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
    def __init__(self, code, labels):
        self.code, self.labels = code, labels
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
                if arg not in self.labels:
                    result.issues.add(f"unresolved {line}")
                    continue
                child = self.solve(self.labels[arg])
                result.peak = max(result.peak, depth+4+child.peak)
                result.issues.update(child.issues)
                if child.returns:
                    advance()
            elif op in ("JMP", "BRA", "LBRA"):
                jump(arg)
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


def audit(pn):
    base = ROOT / "src" / pn
    a = Analyzer(*parse([(base / name).read_text() for name in ("bank0.asm", "bank1.asm")]))
    for name, expected in EXPECTED.items():
        r = a.root(name)
        assert r.returns and not r.issues and r.peak == expected, (pn, name, r)
        print(f"{pn}: {name}: {r.peak} bytes; direct flow balanced")
    for name in OPEN:
        r = a.root(name)
        print(f"{pn}: {name}: partial peak {r.peak}; unresolved {sorted(r.issues)}")
    print("No global maximum: computed dispatch, stack reset paths, IRQ nesting and stack writes remain open.")


if __name__ == "__main__":
    selftest()
    for pn in ("04887050", "05293013AC"):
        audit(pn)
