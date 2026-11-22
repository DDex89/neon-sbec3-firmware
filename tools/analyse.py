"""Code-flow analysis of an SBEC3 flash image.

Starts from the reset entry and the exception vectors (16-bit addresses in bank 0), follows
branches, calls and EXT20 jumps, and resolves jump tables of the form

    (index scaled by 4 in X)  JMP $base,X      ; base: a run of 4-byte JMP $xxxxx entries

Everything reached is code; the rest is treated as data until later stages say otherwise.
"""
import os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cpu16 import decode


class Analysis:
    def __init__(self, data):
        self.data = data
        self.insn = {}          # address -> Insn
        self.labels = {}        # address -> reason
        self.tables = {}        # base -> number of entries (jump tables)
        self.indirect = []      # indirect jumps that were not resolved
        self.problems = []

    def vectors(self):
        d = self.data
        out = [((d[2] << 8) | d[3], "reset")]
        for a in range(8, 0x200, 2):
            out.append(((d[a] << 8) | d[a + 1], "vector %d" % (a // 2)))
        return out

    def run(self, extra=()):
        work = []
        for a, why in list(self.vectors()) + list(extra):
            self.labels.setdefault(a, why)
            work.append(a)
        while work:
            a = work.pop()
            while a not in self.insn:
                if a & 1 or a >= len(self.data):
                    self.problems.append(("bad address", a)); break
                ins = decode(self.data, a)
                if ins is None:
                    self.problems.append(("undefined opcode", a)); break
                self.insn[a] = ins
                t = ins.target()
                if t is not None:
                    if t < len(self.data):
                        self.labels.setdefault(t, "target")
                        work.append(t)
                    else:
                        self.problems.append(("target outside image", a))
                if ins.mn in ("JMP", "JSR") and ins.mode.startswith("IND20"):
                    work.extend(self.jump_table(ins))
                if not ins.falls_through():
                    break
                a += ins.size
        return self

    def jump_table(self, ins):
        base = dict(ins.vals)["zggggg"]
        limit = 256
        prev = [self.insn.get(ins.addr - k) for k in range(2, 24, 2)]
        for p in prev:
            if p is not None and p.mn == "CMPB" and p.mode == "IMM8":
                limit = dict(p.vals)["ii"] + 1
                break
        if ins.mode != "IND20, X" or base & 1 or base >= len(self.data):
            self.indirect.append(ins.addr)
            return []
        out = []; n = 0
        while n < limit:
            e = decode(self.data, base + 4 * n)
            if e is None or e.mn != "JMP" or e.mode != "EXT20":
                break
            out.append(base + 4 * n); n += 1
        if not n:
            self.indirect.append(ins.addr)
            return []
        self.tables[base] = max(n, self.tables.get(base, 0))
        self.labels.setdefault(base, "jump table")
        return out

    def covered(self):
        c = bytearray(len(self.data))
        for a, i in self.insn.items():
            c[a:a + i.size] = b"\x01" * i.size
        return c
