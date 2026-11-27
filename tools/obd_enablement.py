"""Compare stock OBD row enablement with ObdRecordFlags on each archived ROM.

Run with python tools/obd_enablement.py [part numbers].
"""
import hashlib
import json
from pathlib import Path
import sys

from cpu16sim import CPU

ROOT = Path(__file__).resolve().parents[1]
# Routine, primary row table, option table, row count.
GROUPS = {
    ("04887050", "04887051"): (0x1F584, 0x1F000, 0x1F550, 13),
    ("05293013AC", "05293014AC"): (0x1F604, 0x1F006, 0x1F5D0, 13),
    ("05007038", "05293148AA"): (0x1FB1C, 0x1EE60, 0x1FAE8, 13),
    ("05269833AH", "05269833AI", "05269834AJ"): (0x20CD4, 0x20000, 0x20C94, 16),
    ("05293190AC",): (0x20CFE, 0x20000, 0x20CBE, 16),
    ("05032017AA",): (0x20CD6, 0x20000, 0x20C96, 16),
}
CONFIG = {pn: config for group, config in GROUPS.items() for pn in group}


def verify(pn, variants):
    entry, primary, options, count = CONFIG[pn]
    data = (ROOT / "roms" / f"{pn}.bin").read_bytes()
    ann = ROOT / "annotations"
    if pn != "05293190AC":
        ann = ann / "ports" / pn
    spec = variants.get(pn) or json.loads((ann / "stats.json").read_text(encoding="utf-8"))
    if hashlib.sha256(data).hexdigest() != spec["sha256"]:
        raise ValueError(f"{pn} ROM hash differs from its archive entry")
    names = json.loads((ann / "ram.json").read_text(encoding="utf-8"))
    cpu = CPU(data, 0x800 if len(data) == 0x20000 else 0x1000)

    def word(address):
        return int.from_bytes(data[address:address + 2], "big")

    all_bits = primary in (0x1F000, 0x1F006)
    rows = []
    for index in range(count):
        status = word(primary + 20 * index + 2)
        address = word(options + 4 * index)
        mask = data[options + 4 * index + 3]
        masked = data[address] & mask
        enabled = bool(masked) and (not all_bits or masked == mask)
        rows.append((status, address, mask, enabled))

    assert len({status for status, *_ in rows}) == count
    for seed in (0x25, 0xDA):
        cpu.reset_regs()
        for status, *_ in rows:
            cpu.ram_byte(status, seed)
        cpu.call(entry, max_steps=1400)
        assert cpu.sp == 0x8000 + cpu.ram_size - 2
        for status, _, _, enabled in rows:
            expected = (seed & 0x7F) | (0x80 if enabled else 0)
            assert cpu.ram_byte(status) == expected, (pn, status, seed, expected)

    enabled_count = sum(enabled for _, _, _, enabled in rows)
    print(f"{pn} {enabled_count}/{count} rows enabled")
    for status, address, mask, enabled in rows:
        print(f"  {status:04X} {names.get(f'{status:04X}', 'unnamed'):<27} "
              f"{address:04X} & {mask:02X} = {data[address] & mask:02X}  "
              f"{'on' if enabled else 'off'}")


def main():
    variants = json.loads((ROOT / "tools" / "variants.json").read_text(encoding="utf-8"))
    for pn in sys.argv[1:] or CONFIG:
        verify(pn, variants)


if __name__ == "__main__":
    main()
