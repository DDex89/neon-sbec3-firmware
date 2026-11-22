#!/usr/bin/env python3
"""Small two-pass assembler for the CPU16 syntax of tools/syntax16.py.

Directives: `org $xxxxx`, `dc.b` (bytes or "strings"), `dc.w`, `label:` and `name equ value`.
Comments start with `;`. The output is a flat image; bytes not written keep the fill value.

Usage: python3 tools/asm16.py -o out.bin --size 0x40000 file1.asm file2.asm ...
"""
import argparse, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cpu16 import opcode_entries, SIZES

ISA = opcode_entries()
BY_MN = {}
for key, e in ISA.items():
    BY_MN.setdefault(e["mn"], {})[e["mode"]] = (key, e)


class AsmError(Exception):
    pass


def num(tok, syms, need=True):
    tok = tok.strip()
    width = None
    if tok.startswith(">>"):
        width, tok = 5, tok[2:]
    elif tok.startswith(">"):
        width, tok = 4, tok[1:]
    elif tok.startswith("<"):
        width, tok = 2, tok[1:]
    if width:
        return num(tok, syms, need)[0], width
    if tok.startswith("$"):
        return int(tok[1:], 16), len(tok) - 1
    if re.fullmatch(r"-?\d+", tok):
        return int(tok), None
    if tok in syms:
        return syms[tok], None
    if need:
        raise AsmError("undefined symbol " + tok)
    return 0, None


def split_ops(s):
    return [p.strip() for p in s.split(",")] if s.strip() else []


def pick(mn, text, syms, final):
    """Return (key, entry, field values) for mnemonic mn and operand text."""
    modes = BY_MN.get(mn)
    if not modes:
        raise AsmError("unknown mnemonic " + mn)
    ops = split_ops(text)

    def has(m):
        return m in modes

    def res(m, vals):
        k, e = modes[m]
        return k, e, vals

    if not ops:
        return res("INH", [])
    if mn in ("PSHM", "PULM") and not ops[0].startswith("#"):
        names = ["D", "E", "X", "Y", "Z", "K", "CCR"] if mn == "PSHM" else \
            ["CCR", "K", "Z", "Y", "X", "E", "D"]
        return res("IMM8", [("ii", sum(1 << names.index(r) for r in ops))])
    if ops[0].startswith("#") and len(ops) == 1:
        v, nd = num(ops[0][1:], syms, final)
        if has("IMM8") and (nd == 2 or not has("IMM16")):
            f = modes["IMM8"][1]["fields"][0]
            return res("IMM8", [(f, v)])
        return res("IMM16", [("jjkk", v)])
    if ops[0] == "E" and len(ops) == 2:
        return res("E, " + ops[1], [])
    if mn in ("MOVB", "MOVW"):
        if len(ops) == 3 and ops[1] == "X+":
            return res("IXP to EXT", [("ff", num(ops[0], syms)[0]), ("hhll", num(ops[2], syms)[0])])
        if len(ops) == 3 and ops[2] == "X+":
            return res("EXT to IXP", [("ff", num(ops[1], syms)[0]), ("hhll", num(ops[0], syms)[0])])
        return res("EXT to EXT", [("hhll", num(ops[0], syms)[0]), ("hhll2", num(ops[1], syms)[0])])
    # address part, optional index register, optional #mask, optional target
    addr = ops[0]; rest = ops[1:]; reg = None
    if rest and rest[0] in ("X", "Y", "Z"):
        reg = rest[0]; rest = rest[1:]
    mask = None
    if rest and rest[0].startswith("#"):
        mask = rest[0][1:]; rest = rest[1:]
    target = rest[0] if rest else None
    if not reg and mask is None and target is None:
        if has("REL8") or has("REL16"):
            m = "REL8" if has("REL8") else "REL16"
            return res(m, [("rel", num(addr, syms, final)[0])])
        v, nd = num(addr, syms, final)
        if has("EXT20") and (nd in (5, None) or not has("EXT")):
            return res("EXT20", [("zbhhll", v)])
        return res("EXT", [("hhll", v)])
    v, nd = num(addr, syms, final)
    if reg:
        if nd == 2:
            m = "IND8, " + reg
        elif nd == 5:
            m = "IND20, " + reg
        else:
            m = "IND16, " + reg
    else:
        m = "EXT"
    k, e = modes[m]
    vals = []
    for f in e["fields"]:
        if f in ("ff", "gggg", "hhll", "zggggg"):
            vals.append((f, v))
        elif f in ("mm", "mmmm"):
            vals.append((f, num(mask, syms)[0]))
        elif f in ("rr", "rrrr"):
            vals.append(("rel", num(target, syms, final)[0]))
    return k, e, vals


def encode(key, e, vals, pc, final=True):
    out = bytes.fromhex(key)
    fields = list(e["fields"])
    vi = iter(vals)
    for f in fields:
        _, v = next(vi)
        n = SIZES[f]
        if f in ("rr", "rrrr"):
            if not final:
                v = pc + 6
            off = v - (pc + 6)
            lim = 1 << (8 * n - 1)
            if not -lim <= off < lim:
                raise AsmError("branch out of range")
            v = off & ((1 << (8 * n)) - 1)
        out += (v & ((1 << (8 * n)) - 1)).to_bytes(n, "big")
    return out


def parse_dc(arg, syms, width, final=True):
    out = b""
    for tok in re.findall(r'"[^"]*"|[^,]+', arg):
        tok = tok.strip()
        if tok.startswith('"'):
            out += tok[1:-1].encode("latin-1")
        else:
            out += (num(tok, syms, final)[0] & ((1 << (8 * width)) - 1)).to_bytes(width, "big")
    return out


def assemble(files, size, fill=0xFF):
    lines = []
    for fn in files:
        for n, raw in enumerate(open(fn, encoding="utf-8")):
            lines.append((fn, n + 1, raw.split(";", 1)[0].rstrip()))
    syms = {}
    for final in (False, True):
        image = bytearray([fill]) * size
        pc = 0
        for fn, ln, text in lines:
            try:
                if not text.strip():
                    continue
                m = re.match(r"^([A-Za-z_][\w]*):\s*(.*)$", text)
                if m:
                    if not final:
                        syms[m.group(1)] = pc
                    text = m.group(2)
                    if not text.strip():
                        continue
                m = re.match(r"^\s*([A-Za-z_]\w*)\s+equ\s+(.+)$", text, re.I)
                if m:
                    syms[m.group(1)] = num(m.group(2), syms)[0]
                    continue
                parts = text.split(None, 1)
                op = parts[0].lower(); arg = parts[1] if len(parts) > 1 else ""
                if op == "org":
                    pc = num(arg, syms)[0]
                    continue
                if op in ("dc.b", "dc.w"):
                    data = parse_dc(arg, syms, 1 if op == "dc.b" else 2, final)
                    image[pc:pc + len(data)] = data
                    pc += len(data)
                    continue
                key, e, vals = pick(parts[0].upper(), arg, syms, final)
                code = encode(key, e, vals, pc, final)
                image[pc:pc + len(code)] = code
                pc += len(code)
            except AsmError as ex:
                raise AsmError("%s:%d: %s" % (fn, ln, ex))
    return bytes(image)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-o", required=True)
    ap.add_argument("--size", type=lambda s: int(s, 0), default=0x40000)
    ap.add_argument("files", nargs="+")
    a = ap.parse_args()
    open(a.o, "wb").write(assemble(a.files, a.size))


if __name__ == "__main__":
    main()
