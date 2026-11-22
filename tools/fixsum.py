#!/usr/bin/env python3
"""Check or correct the checksum of an SBEC3 flash image.

    python3 tools/fixsum.py edited.bin            # check only
    python3 tools/fixsum.py edited.bin --fix      # write the correction byte in place

The 8-bit sum of the whole image must equal the last byte of the part number in the header (the
header address is the word at $00202). The byte at header + 13 is the correction byte that makes
the sum come out right. After editing tables, run this with --fix before flashing.
"""
import sys


def main():
    path = sys.argv[1]
    d = bytearray(open(path, "rb").read())
    hdr = (d[0x202] << 8) | d[0x203]
    target = d[hdr + 3]
    total = sum(d) & 0xFF
    pn = "".join("%02X" % b for b in d[hdr:hdr + 4])
    print("part number %s, header $%05X, sum $%02X, must be $%02X: %s" % (
        pn, hdr, total, target, "OK" if total == target else "WRONG"))
    if total != target and "--fix" in sys.argv:
        d[hdr + 13] = (d[hdr + 13] + target - total) & 0xFF
        assert sum(d) & 0xFF == target
        open(path, "wb").write(d)
        print("correction byte at $%05X set to $%02X" % (hdr + 13, d[hdr + 13]))
    sys.exit(0 if total == target or "--fix" in sys.argv else 1)


if __name__ == "__main__":
    main()
