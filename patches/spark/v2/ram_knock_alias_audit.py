#!/usr/bin/env python3
"""Freeze reviewed knock indexed-store paths for the Spark V2 RAM candidate.

These are source-level regression guards, not an ownership proof.
Assumes normal CPU16 K/Z state, reviewed call/return behavior and unchanged
factory code; no claim about arbitrary uploaded code, stack or other ISRs.
CRC32 fingerprints detect accidental source changes (not a security check).
"""
from pathlib import Path
import zlib

ROOT = Path(__file__).resolve().parents[3]
CAND = set(range(0x85F2, 0x85F7))
CONFIG = {"04887050":[32871,33654,17,7293,"KnockLearnUpdate"],"05293013AC":[32872,33680,19,7317,"Sub_153E0"]}
SIGNATURES = {
    "04887050": {
        "KnockLearn": 2501123509,
        "KnockEventDecayStep": 2113258651,
        "KnockLearnUpdate": 2405770121,
        "KnockLearnDecayFlag": 2323474353,
        "KnockSample": 2530997416,
        "KnockCylinderRetard": 1705216709,
        "Lookup2D": 987450232
    },
    "05293013AC": {
        "KnockLearn": 375162676,
        "KnockEventDecayStep": 3393197726,
        "Sub_153E0": 2907578390,
        "KnockLearnDecayFlag": 1770113171,
        "KnockSample": 908357171,
        "KnockCylinderRetard": 2437158011,
        "Lookup2D": 1963964123
    }
}

def normalized(path):
    return [s for l in path.read_text().splitlines()
            if (s := " ".join(l.split(";")[0].split()))]

def routine(lines, name):
    i = lines.index(name + ":")
    return lines[i:lines.index("RTS", i) + 1]

def seq(lines, *items):
    assert any(lines[i:i+len(items)] == list(items)
               for i in range(len(lines))), items

def audit(pn):
    cell, cyl, noise, end, update = CONFIG[pn]
    base = ROOT / "src" / pn
    a = normalized(base / "bank0.asm")
    b = normalized(base / "bank1.asm")
    for name, expected in SIGNATURES[pn].items():
        body = routine(a if name == "Lookup2D" else b, name)
        got = zlib.crc32("\n".join(body).encode("ascii"))
        assert got == expected, (pn, name, "review source again", got)
    seq(a, "Reset:", "ORP #$00E0", "LDAB #$0F", "TBSK",
        "LDS #$87FE", "TBZK", "LDZ #$8000")
    learn = routine(b, "KnockLearn")
    sample = routine(b, "KnockSample")
    retard = routine(b, "KnockCylinderRetard")
    seq(learn, "TZY", f"LDY #${cell:04X}",
        "LDAB >KnockLearnCellIndex,Z", "ABY")
    seq(learn, "TZX", f"LDX #${cyl:04X}", "CLRA",
        "LDAB >CylinderCount", "DECB", "TDE")
    seq(sample, "LDAB $00,X", "TZX", f"LDX #${cyl:04X}", "ABX")
    seq(sample, "TZY", f"LDY #${cyl:04X}", "CLRA",
        "LDAB >CylinderCount", "DECB", "TDE")
    seq(retard, "TZY", f"AIY #${noise:02X}", "LDX #KnockRpmSteps")
    seq(retard, "AIX #$02", "AIY #$01", f"CPX #${end:04X}")
    seq(routine(a, "Lookup2D"), "PULM K,Y,E", "RTS")
    # All byte values, including zero CylinderCount: DECB wraps to FF.
    # CLRA/TDE establishes a zero-extended offset, and the BPL loops
    # descend to zero. ABX/ABY likewise use unsigned B.
    # RPM noise walk advances Y once per ROM word, at most four times.
    groups = {
        "learn cell": {cell + i for i in range(256)},
        "cylinder": {cyl + i for i in range(256)},
        "noise": {0x8000 + noise + i for i in range(5)},
    }
    for name, touched in groups.items():
        assert not touched & CAND, (pn, name, touched & CAND)
        print(f"{pn}: {name}: ${min(touched):04X}..${max(touched):04X}; no Q4 overlap")
    print("Reviewed 10 indexed store instructions, not a global RAM proof.")

if __name__ == "__main__":
    for pn in CONFIG:
        audit(pn)
