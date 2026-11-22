"""Assembly syntax shared by the source generator and the assembler.

The syntax is close to Motorola's, but every operand width is explicit, so that the assembler can
always pick the same encoding as the original:

  INH          ABA
  IMM8/IMM16   LDAA #$12      LDD #$1234       (2 hex digits = 8 bit, 4 = 16 bit)
  IND8/16/20   LDAA $12,Z     LDAA $1234,Z     JMP $12345,X
  EXT/EXT20    LDAA $1234     JSR $12345 or JSR label
  E,X          LDAA E,X
  REL          BRA label      (Bcc = 8-bit offset, LBcc = 16-bit offset)
  bit ops      BCLR $12,Z,#$01   BCLR $1234,#$01   BCLRW $1234,X,#$0001
  bit branch   BRCLR $12,Z,#$01,label     BRCLR $1234,Z,#$01,label     BRCLR $1234,#$01,label
  MOVB/MOVW    MOVB $05,X+,$1234   MOVB $1234,$05,X+   MOVB $1234,$5678
  PSHM/PULM    PSHM #$2F (register mask)      MAC/RMAC   MAC #$11 (X and Y offset nibbles)

Numbers are written in hex with a fixed number of digits; labels may replace branch, call and jump
targets. A 16-bit index offset is written unsigned ($FFFE,X is -2).
"""

def h(v, n):
    return "$%0*X" % (n, v)


PSHM_REGS = ["D", "E", "X", "Y", "Z", "K", "CCR"]      # mask bit 0..6 (CPU16RM 5.8)
PULM_REGS = ["CCR", "K", "Z", "Y", "X", "E", "D"]      # mask bit 0..6


def reg_list(mn, mask):
    names = PSHM_REGS if mn == "PSHM" else PULM_REGS
    if mask & 0x80 or not mask:
        return "#" + h(mask, 2)
    return ",".join(n for b, n in enumerate(names) if mask >> b & 1)


def format_insn(ins, label=None, zsym=None, extsym=None):
    """Text of an instruction.

    label(addr)        -> name of a code label, or None
    zsym(offset)       -> name for an offset from Z (RAM or module register), or None
    extsym(addr)       -> name for a 16-bit extended address (calibration), or None
    A symbol in an indexed or extended operand gets a width prefix: < 8-bit, > 16-bit.
    """
    lab = label or (lambda a: None)
    zs = zsym or (lambda o: None)
    es = extsym or (lambda a: None)
    v = dict(ins.vals)
    m = ins.mode

    def tgt(addr):
        return lab(addr) or h(addr, 5)

    reg = m[-1] if m.startswith(("IND", "E, ")) else None
    if m == "INH":
        ops = ""
    elif ins.mn in ("PSHM", "PULM"):
        ops = reg_list(ins.mn, v["ii"])
    elif m == "IMM8":
        ops = "#" + h(v.get("ii", v.get("xoyo", 0)), 2)
    elif m == "IMM16":
        ops = "#" + h(v["jjkk"], 4)
    elif m.startswith("E, "):
        ops = "E," + reg
    elif m in ("REL8", "REL16"):
        ops = tgt(ins.target())
    elif m == "IXP to EXT":
        ops = "%s,X+,%s" % (h(v["ff"], 2), h(v["hhll"], 4))
    elif m == "EXT to IXP":
        ops = "%s,%s,X+" % (h(v["hhll"], 4), h(v["ff"], 2))
    elif m == "EXT to EXT":
        ops = "%s,%s" % (h(v["hhll"], 4), h(v["hhll2"], 4))
    else:
        if "ff" in v:
            sym = zs(v["ff"]) if reg == "Z" else None
            base = ("<" + sym if sym else h(v["ff"], 2)) + "," + reg
        elif "gggg" in v:
            sym = zs(v["gggg"]) if reg == "Z" else None
            base = (">" + sym if sym else h(v["gggg"], 4)) + "," + reg
        elif "zggggg" in v:
            base = h(v["zggggg"], 5) + "," + reg
        elif "zbhhll" in v:
            base = tgt(v["zbhhll"]) if ins.mn in ("JMP", "JSR") else h(v["zbhhll"], 5)
        else:
            sym = es(v["hhll"])
            base = ">" + sym if sym else h(v["hhll"], 4)
        ops = base
        if "mm" in v:
            ops += ",#" + h(v["mm"], 2)
        if "mmmm" in v:
            ops += ",#" + h(v["mmmm"], 4)
        if "rr" in v or "rrrr" in v:
            ops += "," + tgt(ins.target())
    return ins.mn, ops
