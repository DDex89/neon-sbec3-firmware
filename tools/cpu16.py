"""Motorola CPU16 (68HC16) instruction decoder.

The opcode table tools/cpu16_isa.json was extracted from the CPU16 Reference Manual (CPU16RM/AD,
Table 6-36 "Instruction Set Summary", cross-checked against Tables 7-2 to 7-5 "Page n Opcodes").
Keys are the opcode bytes as hex: two digits for page 0, four digits for pages 1-3 (prebytes $17,
$27, $37). Every instruction is a whole number of 16-bit words.

Operand fields (in instruction-stream order):
  ff      8-bit unsigned offset (IND8) or IXP offset    ii    8-bit immediate
  gggg    16-bit signed offset (IND16)                  jjkk  16-bit immediate
  hhll    16-bit address (EXT; bank from EK)            hhll2 second address of MOVB/MOVW EXT to EXT
  rr      8-bit signed branch offset                    rrrr  16-bit signed branch offset
  mm      8-bit bit mask                                mmmm  16-bit bit mask
  zggggg  20-bit offset (IND20)                         zbhhll 20-bit address (EXT20)
  xoyo    MAC / RMAC operand: X and Y offset nibbles

Branch targets are relative to the address of the instruction plus 6 (CPU16RM 7.3). Branch,
JMP/JSR and IND20 arithmetic is on 20 bits (PK : PC).
"""
import json, os

_ISA = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "cpu16_isa.json")))
PREBYTES = (0x17, 0x27, 0x37)
SIZES = {"ff": 1, "ii": 1, "gggg": 2, "hhll": 2, "hhll2": 2, "jjkk": 2, "rr": 1, "rrrr": 2, "mm": 1,
         "mmmm": 2, "zggggg": 3, "zbhhll": 3, "xoyo": 1}

# Control flow classes
UNCOND = {"BRA", "LBRA", "JMP", "RTS", "RTI"}          # no fall-through
CALLS = {"BSR", "LBSR", "JSR"}
STOPS = {"RTS", "RTI"}

def sext(v, bits):
    m = 1 << (bits - 1)
    return (v ^ m) - m


class Insn:
    __slots__ = ("addr", "size", "key", "mn", "mode", "vals", "raw")

    def __init__(self, addr, size, key, mn, mode, vals, raw):
        self.addr, self.size, self.key, self.mn, self.mode, self.vals, self.raw = \
            addr, size, key, mn, mode, vals, raw

    def target(self):
        """Static code target (20-bit) of a branch, call or EXT20 jump, else None."""
        for f, v in self.vals:
            if f == "rr":
                return (self.addr + 6 + sext(v, 8)) & 0xFFFFF
            if f == "rrrr":
                return (self.addr + 6 + sext(v, 16)) & 0xFFFFF
            if f == "zbhhll" and self.mn in ("JMP", "JSR"):
                return v & 0xFFFFF
        return None

    def falls_through(self):
        return self.mn not in UNCOND

    def __repr__(self):
        return "%05X %-6s %-10s %s" % (self.addr, self.mn, self.mode,
                                      " ".join("%s=%X" % fv for fv in self.vals))


def decode(data, addr, base=0):
    """Decode one instruction at absolute address addr; data[0] is at address base.
    Returns an Insn or None for an undefined opcode."""
    i = addr - base
    if i < 0 or i + 2 > len(data):
        return None
    b0 = data[i]
    if b0 in PREBYTES:
        key = "%02X%02X" % (b0, data[i + 1]); p = i + 2
    else:
        key = "%02X" % b0; p = i + 1
    e = _ISA.get(key)
    if e is None or i + e["size"] > len(data):
        return None
    vals = []
    for f in e["fields"]:
        n = SIZES[f]
        v = int.from_bytes(data[p:p + n], "big")
        if f in ("zggggg", "zbhhll"):
            v &= 0xFFFFF
        vals.append((f, v)); p += n
    return Insn(addr, e["size"], key, e["mn"], e["mode"], vals, bytes(data[i:i + e["size"]]))


def opcode_entries():
    return _ISA
