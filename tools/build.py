#!/usr/bin/env python3
"""Assemble the generated sources and verify them against the known SHA-256 of each image.

    python3 tools/build.py            # every source folder listed in tools/variants.json
    python3 tools/build.py 05293190AC # one image

Output goes to build/<part number>.bin. No ROM image is needed.
"""
import hashlib, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from asm16 import assemble


def main():
    variants = json.load(open(os.path.join(ROOT, "tools", "variants.json")))
    names = sys.argv[1:] or list(variants)
    os.makedirs(os.path.join(ROOT, "build"), exist_ok=True)
    bad = 0
    for n in names:
        v = variants[n]
        src = os.path.join(ROOT, "src", n)
        files = sorted(os.path.join(src, f) for f in os.listdir(src) if f.endswith(".asm"))
        img = assemble(files, v["size"])
        open(os.path.join(ROOT, "build", n + ".bin"), "wb").write(img)
        h = hashlib.sha256(img).hexdigest()
        ok = h == v["sha256"]
        bad += not ok
        print("%-12s %s  %s" % (n, "OK - byte-identical" if ok else "MISMATCH", h))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
