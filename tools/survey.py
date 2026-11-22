#!/usr/bin/env python3
"""Survey of SBEC3 flash images: vectors, header block, checksum, families.

Usage: python3 tools/survey.py roms/*.bin

For each image it prints the CPU16 reset vector words, the header block that the word at
$00202 points to (part number, revision, checksum correction byte), whether the 8-bit sum of
the whole image equals the last byte of the part number, the build stamp if one is present and
the code family (same reset entry and stack top).
"""
import hashlib, re, sys

def word(d, a):
    return (d[a] << 8) | d[a + 1]

def survey(path):
    d = open(path, "rb").read()
    hdr = word(d, 0x202)
    pn = "%02X%02X%02X%02X" % tuple(d[hdr:hdr + 4])
    rev = bytes(d[hdr + 4:hdr + 6])
    rev = rev.decode() if all(0x41 <= c <= 0x5A for c in rev) else "-"
    stamp = re.search(rb"[0-9]{12}", d)
    return dict(
        file=path.split("/")[-1], size=len(d), sha256=hashlib.sha256(d).hexdigest(),
        zk_sk_pk=word(d, 0), pc=word(d, 2), sp=word(d, 4), iz=word(d, 6),
        hdr=hdr, pn=pn, rev=rev, target=d[hdr + 3], correction=d[hdr + 13],
        total=sum(d) & 0xFF, stamp=stamp.group().decode() if stamp else "",
        doubled=len(d) == 0x40000 and d[:0x20000] == d[0x20000:])

def main():
    rows = [survey(p) for p in sys.argv[1:]]
    print("| File | Size | Part number | Header | Reset PC | Stack top | Checksum | Build stamp |")
    print("|---|---|---|---|---|---|---|---|")
    for r in rows:
        ok = "ok" if r["total"] == r["target"] else "sum %02X, expected %02X" % (r["total"], r["target"])
        if r["doubled"]:
            ok += " (file holds the 128 KB image twice)"
        print("| %s | %d KB | %s%s | $%05X | $%04X | $F%04X | %s | %s |" % (
            r["file"], r["size"] // 1024, r["pn"], r["rev"] if r["rev"] != "-" else "",
            r["hdr"], r["pc"], r["sp"], ok, r["stamp"]))

if __name__ == "__main__":
    main()
