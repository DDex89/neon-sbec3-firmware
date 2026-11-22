"""Code-flow analysis of an SBEC3 flash image.

Starts from the reset entry and the exception vectors (16-bit addresses in bank 0), follows
branches, calls and EXT20 jumps, and resolves jump tables reached by indexed JMPs (see
jump_table). Everything reached is code; the rest is data. Jumps into RAM ($F8000 and up) are
code downloaded at run time and are listed in ram_jumps.
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
        self.ram_jumps = []     # jumps into RAM ($F8000 and up): downloaded code

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
                    elif t >= 0xF8000:
                        self.ram_jumps.append(a)    # code downloaded into RAM, not in the image
                    else:
                        self.problems.append(("target outside image", a))
                if ins.mn in ("JMP", "JSR") and ins.mode.startswith("IND20"):
                    work.extend(self.jump_table(ins))
                if not ins.falls_through():
                    break
                a += ins.size
        return self

    def jump_table(self, ins):
        """Entries of a jump table reached by an indexed JMP/JSR, or [] if not recognised.

        Recognised forms (the index is already scaled in the index register):
          JMP $base,X   base: 4-byte JMP $xxxxx entries, or 4-byte JSR $xxxxx entries that
                        run on into each other, or 6-byte JSR $xxxxx / BRA pairs
          JMP $base,Y   the same, Y loaded from a parameter block
          LDX #base ... CPX #limit ... JMP $00000,X   entries between base and limit (4-byte JMPs or 2-byte code)
        A CMPB #n shortly before the jump limits the number of 4-byte entries to n + 1. If entry 0
        is not a jump but entry 1 is, the caller never uses index 0 and the table starts at entry 1.
        """
        v = dict(ins.vals)
        base = v["zggggg"]
        prev = [self.insn.get(ins.addr - k) for k in range(2, 30, 2)]
        limit = 256
        for p in prev:
            if p is not None and p.mn == "CMPB" and p.mode == "IMM8":
                limit = dict(p.vals)["ii"] + 1
                break
        out = []
        if base == 0 and ins.mode == "IND20, X":
            ldx = next((p for p in prev if p is not None and p.mn == "LDX" and p.mode == "IMM16"), None)
            cpx = next((p for p in prev if p is not None and p.mn == "CPX" and p.mode == "IMM16"), None)
            if ldx and cpx:
                lo, hi = dict(ldx.vals)["jjkk"], dict(cpx.vals)["jjkk"]
                e = decode(self.data, lo)
                stride = 4 if e and e.mn == "JMP" and e.mode == "EXT20" else 2
                out = list(range(lo, hi, stride))
        elif not base & 1 and base < len(self.data):
            first = decode(self.data, base)
            second = decode(self.data, base + 4) if first else None
            if first and first.mn == "JMP" and first.mode == "EXT20" or second and second.mn == "JMP" \
                    and second.mode == "EXT20":
                # 4-byte JMP entries; an entry may instead hold a short inline stub ending in RTS
                stride = 4
                ok = lambda e, a: e and (e.mn == "JMP" and e.mode == "EXT20" or self._inline_stub(a))
            elif first and first.mn == "JSR" and first.mode == "EXT20" and second and second.mn in ("BRA", "LBRA") and second.size == 2:
                stride = 6
                ok = lambda e, a: e and e.mn == "JSR" and e.mode == "EXT20" and \
                    (decode(self.data, a + 4) or e).mn in ("BRA",)
            elif first and first.mn == "JSR" and first.mode == "EXT20":
                stride, ok = 4, lambda e, a: e and e.mn == "JSR" and e.mode == "EXT20"
            else:
                stride, ok = 0, None
            n = 0
            if ok and stride == 4 and not ok(first, base):
                n = 1           # index 0 is excluded by the caller; the table starts at entry 1
            while ok and n < limit:
                a = base + stride * n
                if not ok(decode(self.data, a), a):
                    break
                out.append(a); n += 1
        if not out:
            self.indirect.append(ins.addr)
            return []
        tb = out[0]
        self.tables[tb] = max(len(out), self.tables.get(tb, 0))
        self.labels.setdefault(tb, "jump table")
        for a in out:
            self.labels.setdefault(a, "jump table entry")
        return out

    def _inline_stub(self, a):
        """True if the 4 bytes at a are one 2-byte instruction followed by RTS, or RTS itself."""
        e = decode(self.data, a)
        if e is None:
            return False
        if e.mn == "RTS":
            return True
        nxt = decode(self.data, a + 2) if e.size == 2 else None
        return nxt is not None and nxt.mn == "RTS"

    def covered(self):
        c = bytearray(len(self.data))
        for a, i in self.insn.items():
            c[a:a + i.size] = b"\x01" * i.size
        return c
