#!/usr/bin/env python3
"""Instruction-level CPU16 (68HC16) simulator for running single routines of an image.

It is not a model of the ECU: there are no peripherals, interrupts or timing. It runs one routine
on a 1 MB address space holding the image (from address 0) and a RAM area, with registers and
RAM set by the caller, and reports the registers, the RAM it changed and what it read. That is
enough to compare two versions of a calculation (for example a stock fuel routine and a patch)
over a grid of inputs before any hardware is involved.

    from cpu16sim import CPU
    cpu = CPU(open("roms/05293190AC.bin", "rb").read())
    cpu.ram_word(0x0A7E, ...)                 # RAM offsets are Z-relative (Z = $F8000)
    cpu.call(0x11F40)                         # runs until the routine returns
    cpu.ram_word(0x07E2)                      # read back a result

Semantics follow the CPU16 Reference Manual (CPU16RM/AD): 20-bit effective addresses from the
K extension fields, SP pointing at the next free word (PSHM stores then decrements by 2, TSX/TSY/
TSZ give SP + 2), PSHM order D, E, X, Y, Z, K, CCR and PULM the reverse, JSR stacking PC and CCR
(with PK), MUL/EMUL setting C from the top bit of the low half (for rounding with ADC), IDIV and
FDIV with quotient in IX and remainder in D. Word accesses may be on odd addresses. An opcode the
simulator does not implement raises NotImplemented with its address, so a run never goes on with
a wrong guess.
"""
import os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cpu16 import decode, sext

M20 = 0xFFFFF
RAM_BASE = 0xF8000


class Halt(Exception):
    pass


class CPU:
    def __init__(self, image, ram_size=0x1000):
        self.mem = bytearray(1 << 20)
        self.mem[0:len(image)] = image
        self.rom_size = len(image)
        self.ram_size = ram_size
        self.reads, self.writes = set(), set()
        self.reset_regs()

    # ----- registers
    def reset_regs(self):
        self.a = self.b = 0
        self.e = 0
        self.ix = self.iy = 0
        self.iz = 0x8000
        self.xk = self.yk = 0
        self.zk = 0xF
        self.ek = 0
        self.sk, self.sp = 0xF, RAM_BASE + self.ram_size - 2 - 0xF0000
        self.pk, self.pc = 0, 0
        self.n = self.z = self.v = self.c = self.h = 0
        self.steps = 0

    @property
    def d(self):
        return (self.a << 8) | self.b

    @d.setter
    def d(self, v):
        v &= 0xFFFF
        self.a, self.b = v >> 8, v & 0xFF

    def k(self):
        return (self.xk << 12) | (self.yk << 8) | (self.zk << 4) | self.ek

    def set_k(self, v):
        self.xk, self.yk, self.zk, self.ek = (v >> 12) & 15, (v >> 8) & 15, (v >> 4) & 15, v & 15

    def ccr(self):
        return (self.n << 15) | (self.v << 14) | (self.h << 13) | (self.z << 12) | (self.c << 8) | 0x00E0 | self.pk

    def set_ccr(self, v, pk=True):
        self.n, self.v, self.h, self.z, self.c = v >> 15 & 1, v >> 14 & 1, v >> 13 & 1, v >> 12 & 1, v >> 8 & 1
        if pk:
            self.pk = v & 15

    def reg20(self, r):
        return {"X": (self.xk << 16) | self.ix, "Y": (self.yk << 16) | self.iy,
                "Z": (self.zk << 16) | self.iz}[r]

    def set20(self, r, v):
        v &= M20
        if r == "X":
            self.xk, self.ix = v >> 16, v & 0xFFFF
        elif r == "Y":
            self.yk, self.iy = v >> 16, v & 0xFFFF
        elif r == "Z":
            self.zk, self.iz = v >> 16, v & 0xFFFF
        elif r == "S":
            self.sk, self.sp = v >> 16, v & 0xFFFF

    # ----- memory
    def rb(self, a):
        a &= M20
        self.reads.add(a)
        return self.mem[a]

    def wb(self, a, v):
        a &= M20
        if a < self.rom_size:
            raise Halt("write to ROM at $%05X (pc $%05X)" % (a, self.pc))
        self.writes.add(a)
        self.mem[a] = v & 0xFF

    def rw(self, a):
        return (self.rb(a) << 8) | self.rb(a + 1)

    def ww(self, a, v):
        self.wb(a, v >> 8)
        self.wb(a + 1, v)

    def ram_byte(self, off, v=None):
        if v is None:
            return self.mem[RAM_BASE + off]
        self.mem[RAM_BASE + off] = v & 0xFF

    def ram_word(self, off, v=None):
        if v is None:
            return (self.mem[RAM_BASE + off] << 8) | self.mem[RAM_BASE + off + 1]
        self.mem[RAM_BASE + off] = (v >> 8) & 0xFF
        self.mem[RAM_BASE + off + 1] = v & 0xFF

    def push(self, v):
        s = (self.sk << 16) | self.sp
        self.ww(s, v)
        self.set20("S", s - 2)

    def pull(self):
        s = ((self.sk << 16) | self.sp) + 2
        self.set20("S", s)
        return self.rw(s)

    # ----- flags
    def nz(self, v, bits):
        m = (1 << bits) - 1
        v &= m
        self.n = v >> (bits - 1) & 1
        self.z = int(v == 0)
        return v

    def add(self, x, y, bits, carry=0):
        m = (1 << bits) - 1
        r = x + y + carry
        self.c = int(r > m)
        self.v = int(((x ^ r) & (y ^ r)) >> (bits - 1) & 1)
        if bits == 8:
            self.h = int(((x & 15) + (y & 15) + carry) > 15)
        return self.nz(r, bits)

    def sub(self, x, y, bits, borrow=0):
        m = (1 << bits) - 1
        r = (x - y - borrow) & m
        self.c = int(x < y + borrow)
        self.v = int(((x ^ y) & (x ^ r)) >> (bits - 1) & 1)
        return self.nz(r, bits)

    def cond(self, mn):
        n, z, v, c = self.n, self.z, self.v, self.c
        t = mn[1:] if mn.startswith("LB") else mn[1:]
        if mn.startswith("LB"):
            t = mn[2:]
        return {"RA": True, "RN": False, "CC": not c, "CS": c, "EQ": z, "NE": not z, "MI": n, "PL": not n,
                "VC": not v, "VS": v, "HI": not (c or z), "LS": c or z, "GE": n == v, "LT": n != v,
                "GT": not z and n == v, "LE": z or n != v}[t]

    # ----- operands
    def ea(self, ins):
        f = dict(ins.vals)
        mode = ins.mode
        if mode == "EXT":
            return (self.ek << 16) | f["hhll"]
        if mode == "EXT20":
            return f["zbhhll"]
        if mode.startswith("IND8"):
            return (self.reg20(mode[-1]) + f["ff"]) & M20
        if mode.startswith("IND16"):
            return (self.reg20(mode[-1]) + sext(f["gggg"], 16)) & M20
        if mode.startswith("IND20"):
            return (self.reg20(mode[-1]) + sext(f["zggggg"], 20)) & M20
        if mode.startswith("E, "):
            return (self.reg20(mode[-1]) + sext(self.e, 16)) & M20
        raise NotImplementedError("operand mode %s at $%05X" % (mode, ins.addr))

    def src8(self, ins):
        if ins.mode == "IMM8":
            return dict(ins.vals)["ii"]
        return self.rb(self.ea(ins))

    def src16(self, ins):
        f = dict(ins.vals)
        if ins.mode == "IMM16":
            return f["jjkk"]
        if ins.mode == "IMM8":                 # sign-extended 8-bit immediate (e.g. ADDD #, AIX #)
            return sext(f["ii"], 8) & 0xFFFF
        return self.rw(self.ea(ins))

    # ----- execution
    def call(self, entry, max_steps=200000):
        """Run the routine at entry until it returns; returns the number of instructions run."""
        self.reads, self.writes = set(), set()
        self.steps = 0
        sentinel = 0xFFFFE
        self.push(sentinel & 0xFFFF)
        self.push(self.ccr() & 0xFFF0 | (sentinel >> 16))
        self.pk, self.pc = entry >> 16, entry & 0xFFFF
        while True:
            pc = (self.pk << 16) | self.pc
            if pc == sentinel:
                return self.steps
            if self.steps >= max_steps:
                raise Halt("step limit at $%05X" % pc)
            self.step(pc)

    def jump(self, a):
        a &= M20
        self.pk, self.pc = a >> 16, a & 0xFFFF

    def step(self, pc):
        ins = decode(self.mem, pc)
        if ins is None:
            raise Halt("undefined opcode at $%05X" % pc)
        self.steps += 1
        self.ins = ins
        nxt = (pc + ins.size) & M20
        self.jump(nxt)
        mn, f = ins.mn, dict(ins.vals)
        h = getattr(self, "op_" + mn, None)
        if h is not None:
            h(ins, f, nxt)
            return
        # generic groups
        if mn in ("BRA", "BRN", "BCC", "BCS", "BEQ", "BNE", "BMI", "BPL", "BVC", "BVS", "BHI", "BLS",
                  "BGE", "BLT", "BGT", "BLE") or (mn.startswith("LB") and mn not in ("LBSR", "LBEV", "LBMV")):
            if self.cond(mn):
                self.jump(ins.target())
            return
        reg8 = {"A": "a", "B": "b"}
        if mn[:-1] in ("LDA", ) or mn in ("LDAA", "LDAB"):
            r = reg8[mn[-1]]
            setattr(self, r, self.nz(self.src8(ins), 8)); self.v = 0
            return
        if mn in ("STAA", "STAB"):
            v = getattr(self, reg8[mn[-1]])
            self.wb(self.ea(ins), v); self.nz(v, 8); self.v = 0
            return
        w16 = {"D": "d", "E": "e", "X": "ix", "Y": "iy", "Z": "iz", "S": "sp"}
        if mn in ("LDD", "LDE", "LDX", "LDY", "LDZ", "LDS"):
            setattr(self, w16[mn[-1]], self.nz(self.src16(ins), 16)); self.v = 0
            return
        if mn in ("STD", "STE", "STX", "STY", "STZ", "STS"):
            v = getattr(self, w16[mn[-1]])
            self.ww(self.ea(ins), v); self.nz(v, 16); self.v = 0
            return
        if mn in ("ADDA", "ADDB", "ADCA", "ADCB", "SUBA", "SUBB", "SBCA", "SBCB", "CMPA", "CMPB",
                  "ANDA", "ANDB", "ORAA", "ORAB", "EORA", "EORB", "BITA", "BITB"):
            r = reg8[mn[-1]]; x = getattr(self, r); y = self.src8(ins); op = mn[:-1]
            if op in ("ADD", "ADC"):
                setattr(self, r, self.add(x, y, 8, self.c if op == "ADC" else 0))
            elif op in ("SUB", "SBC"):
                setattr(self, r, self.sub(x, y, 8, self.c if op == "SBC" else 0))
            elif op == "CMP":
                self.sub(x, y, 8)
            else:
                res = {"AND": x & y, "ORA": x | y, "EOR": x ^ y, "BIT": x & y}[op]
                self.nz(res, 8); self.v = 0
                if op != "BIT":
                    setattr(self, r, res)
            return
        if mn in ("ADDD", "ADDE", "ADCD", "ADCE", "SUBD", "SUBE", "SBCD", "SBCE", "CPD", "CPE", "CPX", "CPY",
                  "CPZ", "CPS", "ANDD", "ANDE", "ORD", "ORE", "EORD", "EORE"):
            r = w16[mn[-1]]; x = getattr(self, r); y = self.src16(ins); op = mn[:-1]
            if op in ("ADD", "ADC"):
                setattr(self, r, self.add(x, y, 16, self.c if op == "ADC" else 0))
            elif op in ("SUB", "SBC"):
                setattr(self, r, self.sub(x, y, 16, self.c if op == "SBC" else 0))
            elif op == "CP":
                self.sub(x, y, 16)
            else:
                res = {"AND": x & y, "OR": x | y, "EOR": x ^ y}[op]
                setattr(self, r, self.nz(res, 16)); self.v = 0
            return
        if mn in ("AIX", "AIY", "AIZ", "AIS"):
            reg = mn[-1]
            v = (self.reg20(reg) if reg != "S" else (self.sk << 16) | self.sp) + sext(self.src16(ins), 16)
            self.set20(reg, v)
            if reg != "S":
                self.z = int((v & 0xFFFF) == 0)
            return
        # read-modify-write memory and accumulators
        rmw = ("CLR", "COM", "NEG", "INC", "DEC", "TST", "ASL", "ASR", "LSR", "ROL", "ROR")
        for op in rmw:
            if mn == op:                      # byte in memory
                a = self.ea(ins); v = self.rmw(op, self.rb(a), 8)
                if op != "TST":
                    self.wb(a, v)
                return
            if mn == op + "W":                # word in memory
                a = self.ea(ins); v = self.rmw(op, self.rw(a), 16)
                if op != "TST":
                    self.ww(a, v)
                return
            if mn in (op + "A", op + "B"):
                r = reg8[mn[-1]]; v = self.rmw(op, getattr(self, r), 8)
                if op != "TST":
                    setattr(self, r, v)
                return
            if mn in (op + "D", op + "E"):
                r = w16[mn[-1]]; v = self.rmw(op, getattr(self, r), 16)
                if op != "TST":
                    setattr(self, r, v)
                return
        raise NotImplementedError("%s (%s) at $%05X" % (mn, ins.mode, pc))

    def rmw(self, op, v, bits):
        m = (1 << bits) - 1; top = bits - 1
        if op == "CLR":
            self.n = self.v = self.c = 0; self.z = 1; return 0
        if op == "TST":
            self.nz(v, bits); self.v = self.c = 0; return v
        if op == "COM":
            r = self.nz(~v, bits); self.v = 0; self.c = 1; return r
        if op == "NEG":
            r = self.sub(0, v, bits); return r
        if op == "INC":
            r = self.nz(v + 1, bits); self.v = int(v == (1 << top) - 1); return r
        if op == "DEC":
            r = self.nz(v - 1, bits); self.v = int(v == 1 << top); return r
        if op == "ASL":
            self.c = v >> top & 1; r = self.nz(v << 1, bits); self.v = self.n ^ self.c; return r
        if op == "ASR":
            self.c = v & 1; r = self.nz((v >> 1) | (v & (1 << top)), bits); self.v = self.n ^ self.c; return r
        if op == "LSR":
            self.c = v & 1; r = self.nz(v >> 1, bits); self.v = self.c; return r
        if op == "ROL":
            c = self.c; self.c = v >> top & 1; r = self.nz((v << 1) | c, bits); self.v = self.n ^ self.c; return r
        if op == "ROR":
            c = self.c; self.c = v & 1; r = self.nz((v >> 1) | (c << top), bits); self.v = self.n ^ self.c; return r
        raise NotImplementedError(op)

    # ----- individual instructions
    def op_BRSET(self, ins, f, nxt):
        if self.rb(self.ea(ins)) & f["mm"] == f["mm"]:
            self.jump(ins.target())

    def op_BRCLR(self, ins, f, nxt):
        if self.rb(self.ea(ins)) & f["mm"] == 0:
            self.jump(ins.target())

    def op_BSET(self, ins, f, nxt):
        a = self.ea(ins); v = self.nz(self.rb(a) | f["mm"], 8); self.v = 0; self.wb(a, v)

    def op_BCLR(self, ins, f, nxt):
        a = self.ea(ins); v = self.nz(self.rb(a) & ~f["mm"], 8); self.v = 0; self.wb(a, v)

    def op_BSETW(self, ins, f, nxt):
        a = self.ea(ins); v = self.nz(self.rw(a) | f["mmmm"], 16); self.v = 0; self.ww(a, v)

    def op_BCLRW(self, ins, f, nxt):
        a = self.ea(ins); v = self.nz(self.rw(a) & ~f["mmmm"], 16); self.v = 0; self.ww(a, v)

    def op_JMP(self, ins, f, nxt):
        self.jump(f["zbhhll"] if ins.mode == "EXT20" else self.ea(ins))

    def op_JSR(self, ins, f, nxt):
        target = f["zbhhll"] if ins.mode == "EXT20" else self.ea(ins)
        self.push(nxt & 0xFFFF)
        self.push(self.ccr() & 0xFFF0 | (nxt >> 16))
        self.jump(target)

    def op_BSR(self, ins, f, nxt):
        self.push(nxt & 0xFFFF)
        self.push(self.ccr() & 0xFFF0 | (nxt >> 16))
        self.jump(ins.target())

    op_LBSR = op_BSR

    def op_RTS(self, ins, f, nxt):
        pk = self.pull() & 15
        pc = self.pull()
        self.jump((pk << 16) | pc)

    def op_PSHM(self, ins, f, nxt):
        m = f["ii"]
        for bit, r in enumerate(("D", "E", "X", "Y", "Z", "K", "CCR")):
            if m >> bit & 1:
                self.push({"D": self.d, "E": self.e, "X": self.ix, "Y": self.iy, "Z": self.iz,
                           "K": self.k(), "CCR": self.ccr()}[r])

    def op_PULM(self, ins, f, nxt):
        m = f["ii"]
        for bit, r in enumerate(("CCR", "K", "Z", "Y", "X", "E", "D")):
            if m >> bit & 1:
                v = self.pull()
                if r == "D":
                    self.d = v
                elif r == "E":
                    self.e = v
                elif r == "X":
                    self.ix = v
                elif r == "Y":
                    self.iy = v
                elif r == "Z":
                    self.iz = v
                elif r == "K":
                    self.set_k(v)
                else:
                    self.set_ccr(v, pk=False)

    def op_PSHA(self, ins, f, nxt):
        self.push(self.a)

    def op_PSHB(self, ins, f, nxt):
        self.push(self.b)

    def op_PULA(self, ins, f, nxt):
        self.a = self.pull() & 0xFF

    def op_PULB(self, ins, f, nxt):
        self.b = self.pull() & 0xFF

    # transfers
    def op_TAB(self, ins, f, nxt): self.b = self.nz(self.a, 8); self.v = 0
    def op_TBA(self, ins, f, nxt): self.a = self.nz(self.b, 8); self.v = 0
    def op_TDE(self, ins, f, nxt): self.e = self.nz(self.d, 16); self.v = 0
    def op_TED(self, ins, f, nxt): self.d = self.nz(self.e, 16); self.v = 0
    def op_XGAB(self, ins, f, nxt): self.a, self.b = self.b, self.a
    def op_XGDE(self, ins, f, nxt): d = self.d; self.d = self.e; self.e = d
    def op_XGDX(self, ins, f, nxt): d = self.d; self.d = self.ix; self.ix = d
    def op_XGDY(self, ins, f, nxt): d = self.d; self.d = self.iy; self.iy = d
    def op_XGDZ(self, ins, f, nxt): d = self.d; self.d = self.iz; self.iz = d
    def op_XGEX(self, ins, f, nxt): self.e, self.ix = self.ix, self.e
    def op_XGEY(self, ins, f, nxt): self.e, self.iy = self.iy, self.e
    def op_XGEZ(self, ins, f, nxt): self.e, self.iz = self.iz, self.e
    def op_TXY(self, ins, f, nxt): self.set20("Y", self.reg20("X"))
    def op_TXZ(self, ins, f, nxt): self.set20("Z", self.reg20("X"))
    def op_TYX(self, ins, f, nxt): self.set20("X", self.reg20("Y"))
    def op_TYZ(self, ins, f, nxt): self.set20("Z", self.reg20("Y"))
    def op_TZX(self, ins, f, nxt): self.set20("X", self.reg20("Z"))
    def op_TZY(self, ins, f, nxt): self.set20("Y", self.reg20("Z"))
    def op_TSX(self, ins, f, nxt): self.set20("X", ((self.sk << 16) | self.sp) + 2)
    def op_TSY(self, ins, f, nxt): self.set20("Y", ((self.sk << 16) | self.sp) + 2)
    def op_TSZ(self, ins, f, nxt): self.set20("Z", ((self.sk << 16) | self.sp) + 2)
    def op_TXS(self, ins, f, nxt): self.set20("S", self.reg20("X") - 2)
    def op_TYS(self, ins, f, nxt): self.set20("S", self.reg20("Y") - 2)
    def op_TZS(self, ins, f, nxt): self.set20("S", self.reg20("Z") - 2)
    def op_TBXK(self, ins, f, nxt): self.xk = self.b & 15
    def op_TBYK(self, ins, f, nxt): self.yk = self.b & 15
    def op_TBZK(self, ins, f, nxt): self.zk = self.b & 15
    def op_TBEK(self, ins, f, nxt): self.ek = self.b & 15
    def op_TBSK(self, ins, f, nxt): self.sk = self.b & 15
    def op_TXKB(self, ins, f, nxt): self.b = self.xk
    def op_TYKB(self, ins, f, nxt): self.b = self.yk
    def op_TZKB(self, ins, f, nxt): self.b = self.zk
    def op_TEKB(self, ins, f, nxt): self.b = self.ek
    def op_TSKB(self, ins, f, nxt): self.b = self.sk
    def op_TPA(self, ins, f, nxt): self.a = self.ccr() >> 8
    def op_TAP(self, ins, f, nxt): self.set_ccr((self.a << 8) | (self.ccr() & 0xFF), pk=False)
    def op_TPD(self, ins, f, nxt): self.d = self.ccr()
    def op_TDP(self, ins, f, nxt): self.set_ccr(self.d, pk=False)
    def op_NOP(self, ins, f, nxt): pass
    def op_SXT(self, ins, f, nxt): self.a = 0xFF if self.b & 0x80 else 0
    def op_CLRA(self, ins, f, nxt): self.a = 0; self.n = self.v = self.c = 0; self.z = 1
    def op_CLRB(self, ins, f, nxt): self.b = 0; self.n = self.v = self.c = 0; self.z = 1
    def op_CLRD(self, ins, f, nxt): self.d = 0; self.n = self.v = self.c = 0; self.z = 1
    def op_CLRE(self, ins, f, nxt): self.e = 0; self.n = self.v = self.c = 0; self.z = 1

    # 20-bit pointer arithmetic
    def op_ABX(self, ins, f, nxt): self.set20("X", self.reg20("X") + self.b)
    def op_ABY(self, ins, f, nxt): self.set20("Y", self.reg20("Y") + self.b)
    def op_ABZ(self, ins, f, nxt): self.set20("Z", self.reg20("Z") + self.b)
    def op_ADX(self, ins, f, nxt): self.set20("X", self.reg20("X") + sext(self.d, 16))
    def op_ADY(self, ins, f, nxt): self.set20("Y", self.reg20("Y") + sext(self.d, 16))
    def op_ADZ(self, ins, f, nxt): self.set20("Z", self.reg20("Z") + sext(self.d, 16))
    def op_AEX(self, ins, f, nxt): self.set20("X", self.reg20("X") + sext(self.e, 16))
    def op_AEY(self, ins, f, nxt): self.set20("Y", self.reg20("Y") + sext(self.e, 16))
    def op_AEZ(self, ins, f, nxt): self.set20("Z", self.reg20("Z") + sext(self.e, 16))

    # accumulator arithmetic
    def op_ABA(self, ins, f, nxt): self.a = self.add(self.a, self.b, 8)
    def op_SBA(self, ins, f, nxt): self.a = self.sub(self.a, self.b, 8)
    def op_CBA(self, ins, f, nxt): self.sub(self.a, self.b, 8)
    def op_ADE(self, ins, f, nxt): self.e = self.add(self.e, self.d, 16)
    def op_SDE(self, ins, f, nxt): self.e = self.sub(self.e, self.d, 16)
    def op_ACE(self, ins, f, nxt): self.e = self.add(self.e, self.d, 16)

    def op_MUL(self, ins, f, nxt):
        r = self.a * self.b
        self.d = r
        self.c = r >> 7 & 1

    def op_EMUL(self, ins, f, nxt):
        r = self.e * self.d
        self.e, self.d = r >> 16, r & 0xFFFF
        self.n = r >> 31 & 1; self.z = int(r == 0); self.c = r >> 15 & 1

    def op_EMULS(self, ins, f, nxt):
        r = (sext(self.e, 16) * sext(self.d, 16)) & 0xFFFFFFFF
        self.e, self.d = r >> 16, r & 0xFFFF
        self.n = r >> 31 & 1; self.z = int(r == 0); self.c = r >> 15 & 1

    def op_FMULS(self, ins, f, nxt):
        r = (sext(self.e, 16) * sext(self.d, 16) * 2) & 0xFFFFFFFF
        self.v = int(self.e == 0x8000 and self.d == 0x8000)
        self.e, self.d = r >> 16, r & 0xFFFF
        self.n = r >> 31 & 1; self.z = int(r == 0); self.c = r >> 15 & 1

    def op_IDIV(self, ins, f, nxt):
        if self.ix == 0:
            self.ix = 0xFFFF; self.c = 1; return
        q, r = divmod(self.d, self.ix)
        self.ix, self.d = q, r
        self.z = int(q == 0); self.v = 0; self.c = 0

    def op_FDIV(self, ins, f, nxt):
        if self.ix == 0:
            self.ix = 0xFFFF; self.c = 1; return
        if self.ix <= self.d:
            self.ix = 0xFFFF; self.v = 1; return
        q, r = divmod(self.d << 16, self.ix)
        self.ix, self.d = q & 0xFFFF, r
        self.z = int(q == 0); self.v = 0; self.c = 0

    def op_EDIV(self, ins, f, nxt):
        num = (self.e << 16) | self.d
        if self.ix == 0:
            self.c = 1; return
        q, r = divmod(num, self.ix)
        self.v = int(q > 0xFFFF)
        self.ix, self.d = q & 0xFFFF, r
        self.z = int(q & 0xFFFF == 0); self.c = 0


def run_routine(image, entry, ram=None, regs=None, ram_size=0x1000):
    """Convenience: run one routine with RAM words/bytes set; returns the CPU after the run."""
    cpu = CPU(image, ram_size)
    for off, v in (ram or {}).items():
        if isinstance(v, tuple):              # (value, width)
            (cpu.ram_word if v[1] == 2 else cpu.ram_byte)(off, v[0])
        else:
            cpu.ram_byte(off, v)
    for r, v in (regs or {}).items():
        setattr(cpu, r, v)
    cpu.call(entry)
    return cpu
