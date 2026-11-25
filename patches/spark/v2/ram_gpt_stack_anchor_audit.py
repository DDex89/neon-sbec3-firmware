#!/usr/bin/env python3
"""Spark V2: reviewed GPT selector/table and stock stack-entry anchors.

Partial source audit. Does not prove interrupt nesting, maximum stack depth,
injector-index bounds, computed pointer reachability or RAM ownership.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[3]
CAND = set(range(0x85F2, 0x85F7))

def normalized(path):
    return [s for line in path.read_text().splitlines()
            if (s := " ".join(line.split(";")[0].split()))]

def audit(pn):
    base = ROOT / "src" / pn
    a = normalized(base / "bank0.asm")
    b = normalized(base / "bank1.asm")
    p = a.index("JumpTable_0481A:")
    # Data immediately before the known $481A jump table; $4816..4819
    # are the final four bytes.
    assert a[p-1] == "dc.b $28,$88,$24,$88,$2C,$10,$04,$EF,$FB,$40,$20,$F9,$1A,$F9,$18"
    raw = bytes(int(x[1:], 16) for x in a[p-1].split()[1].split(","))
    ptrs = [int.from_bytes(raw[i:i+2], "big") for i in (11, 13)]
    assert ptrs == [0xF91A, 0xF918]
    ic1 = a[a.index("Isr_GPT_IC1:"):a.index("Isr_GPT_OC3:")]
    selectors = [i for i, op in enumerate(ic1) if op == "STAB <Temp4F0,Z"]
    assert len(selectors) == 3
    for i in selectors:
        block = ic1[i-7:i+1]
        assert block[0] == "CLRB" and block[2] == "INCB"
        assert block[1].startswith("BRSET >CrankSyncFlags,Z,#$20,")
        assert block[3] == block[1].split(",")[-1] + ":"
        assert block[4].startswith("BRCLR >Options031D,#$04,")
        assert block[5] == "EORB #$01"
        assert block[6] == block[4].split(",")[-1] + ":"
    loads = [i for i, op in enumerate(ic1) if op == "LDY #$4816"]
    assert len(loads) == 4
    for i in loads:
        tail = ic1[i+1:i+5]
        assert tail[:3] == ["ABY", "ABY", "LDX $00,Y"] or tail == [
            "LDAB <Temp4F0,Z", "ABY", "ABY", "LDX $00,Y"]
    for bit in (0, 1):
        for invert in (0, 1):
            index = bit ^ invert
            addr = ptrs[index]
            assert not {addr, addr+1} & CAND
    ops = [x for x in a+b if re.match(r"^(LDS|T[XY]S|TDS|TES|TBSK|DES|INS)\b", x)]
    assert ops == ["TBSK", "LDS #$87FE", "TBSK", "LDS #$87FE",
                   "TBSK", "LDS #$87FA"]
    print(f"{pn}: 3 selector producers, 4 table loads, fixed GPT entries verified")
    print(f"{pn}: minimum SP-anchor separation {0x87FA-max(CAND)} bytes")
    print("Stack depth and remaining GPT indirect paths NOT proven.")

if __name__ == "__main__":
    for pn in ("04887050", "05293013AC"):
        audit(pn)
