#!/usr/bin/env python3
"""Cross-reference of RAM variables (offsets from Z) and calibration addresses.

    python3 tools/xref.py roms/05293190AC.bin 0A6A 0A6C        # who reads and writes $0A6A,Z ...
    python3 tools/xref.py roms/05293190AC.bin --cal 19DC       # who reads calibration $19DC

For each access: address, instruction, read or write, width and the routine it is in.
"""
import bisect, collections, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from analyse import Analysis

WRITE = {"STAA", "STAB", "STD", "STE", "STX", "STY", "STZ", "STS", "STED", "CLR", "CLRW", "INC", "INCW", "DEC",
         "DECW", "COM", "COMW", "NEG", "NEGW", "ASL", "ASLW", "ASR", "ASRW", "LSR", "LSRW", "ROL", "ROLW", "ROR",
         "RORW", "BSET", "BCLR", "BSETW", "BCLRW"}
WORD = {"LDD", "LDE", "LDX", "LDY", "LDZ", "LDS", "STD", "STE", "STX", "STY", "STZ", "STS", "CPD", "CPE", "CPX",
        "CPY", "CPZ", "CPS", "ADDD", "ADDE", "SUBD", "SUBE", "ADCD", "ADCE", "SBCD", "SBCE", "ANDD", "ANDE", "ORD",
        "ORE", "EORD", "EORE", "CLRW", "INCW", "DECW", "COMW", "NEGW", "ASLW", "ASRW", "LSRW", "ROLW", "RORW",
        "TSTW", "BSETW", "BCLRW", "BRSETW", "BRCLRW", "LDED", "STED"}
RMW = {"INC", "INCW", "DEC", "DECW", "COM", "COMW", "NEG", "NEGW", "ASL", "ASLW", "ASR", "ASRW", "LSR", "LSRW",
       "ROL", "ROLW", "ROR", "RORW", "BSET", "BCLR", "BSETW", "BCLRW"}


class Xref:
    def __init__(self, data, an=None, z_not_base=()):
        self.an = an or Analysis(data).run()
        self.ram = collections.defaultdict(list)    # offset -> [(addr, ins, kind)]
        self.cal = collections.defaultdict(list)    # 16-bit address -> [(addr, ins, kind)]
        starts = set()
        for a, i in self.an.insn.items():
            if i.mn in ("JSR", "BSR", "LBSR") and i.target() is not None:
                starts.add(i.target())
        starts |= {(data[2 * n] << 8) | data[2 * n + 1] for n in range(1, 256) if n not in (2, 3)}
        self.starts = sorted(starts)
        for a, i in self.an.insn.items():
            v = dict(i.vals)
            kind = "rw" if i.mn in RMW else ("w" if i.mn in WRITE else "r")
            width = 2 if i.mn in WORD else 1
            if i.mode.endswith(", Z") and not any(lo <= a < hi for lo, hi in z_not_base):
                off = v.get("ff", v.get("gggg"))
                if off is not None:
                    for k in range(width):
                        self.ram[off + k].append((a, i, kind))
            elif "hhll" in v and i.mn not in ("JMP", "JSR"):
                for k in range(width):
                    self.cal[v["hhll"] + k].append((a, i, kind))

    def owner(self, a):
        j = bisect.bisect_right(self.starts, a) - 1
        return self.starts[j] if j >= 0 else None

    def writers(self, off):
        return sorted({self.owner(a) for a, i, k in self.ram.get(off, []) if "w" in k} - {None})

    def readers(self, off):
        return sorted({self.owner(a) for a, i, k in self.ram.get(off, []) if "r" in k} - {None})


def main():
    args = sys.argv[1:]
    d = open(args[0], "rb").read()
    x = Xref(d)
    cal = "--cal" in args
    for t in [a for a in args[1:] if a != "--cal"]:
        off = int(t, 16)
        acc = (x.cal if cal else x.ram).get(off, [])
        print("%s $%04X: %d accesses" % ("cal" if cal else "ram", off, len(acc)))
        for a, i, k in sorted(acc, key=lambda e: e[0]):
            print("  %05X %-2s %-6s in $%05X" % (a, k, i.mn, x.owner(a) or 0))


if __name__ == "__main__":
    main()
