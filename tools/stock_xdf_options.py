#!/usr/bin/env python3
"""Stock ROM option metadata from family-specific, code-reviewed hand annotations.

Keep original option masks whose semantics remain uncertain, but remove stale
reference-family names. Add independently reviewed individual bits. Never edit ROM.
"""
import argparse
import json
import re
from copy import deepcopy
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
FAMILIES = {
    "04887050": "04887050", "04887051": "04887050",
    "05293013AC": "05293013AC", "05293014AC": "05293013AC",
    "05007038": "05007038", "05293148AA": "05007038",
}

def hand_options(pn):
    if pn not in FAMILIES:
        return {}
    data = json.loads((ROOT / "annotations" / "hand" / FAMILIES[pn] /
                       "bits.json").read_text(encoding="utf-8"))
    return {name: {1 << int(bit): note for bit, note in bits.items()}
            for name, bits in data.items()
            if re.fullmatch(r"Options[0-9A-F]{4}", name)}

def title(name, mask, note):
    short = re.split(r"[:;(]", note, maxsplit=1)[0].strip() if note else "(unverified inherited mask)"
    return f"{name} bit ${mask:02X} {short}"

def description(name, mask, note):
    note = note or ("Inherited mask; meaning not independently verified for this ROM family. "
                    "Do not assume reference-family semantics.")
    return f"{note} Stock ROM option ${name[7:]} mask ${mask:02X}."

def apply_stock_options(root, pn):
    """Post-process generated XDF, retaining existing flag IDs and all unrelated nodes."""
    reviewed = hand_options(pn)
    if not reviewed:
        return
    items = [e for e in root if e.tag in ("XDFTABLE", "XDFCONSTANT", "XDFFLAG")]
    uid = max(int(e.get("uniqueid"), 0) for e in items)
    for name, notes in reviewed.items():
        group = [e for e in items if (e.findtext("title") or "").split(" bit $")[0] == name]
        if not group:
            raise ValueError(f"{pn}: missing {name}")
        addr = int(name[7:], 16)
        for e in group:
            em = e.find("EMBEDDEDDATA")
            if (e.tag not in ("XDFCONSTANT", "XDFFLAG") or em is None
                    or int(em.get("mmedaddress"), 0) != addr
                    or int(em.get("mmedelementsizebits"), 0) != 8):
                raise ValueError(f"{pn}: invalid layout for {name}")
        old = {int(e.findtext("mask"), 0): e for e in group if e.tag == "XDFFLAG"}
        raw = next((e for e in group if e.tag == "XDFCONSTANT"), None)
        cats = group[0].findall("CATEGORYMEM")
        pos = list(root).index(group[0])
        for e in group:
            root.remove(e)
        for mask in sorted(set(old) | set(notes)):
            if mask in old:
                ident = old[mask].get("uniqueid")
            elif raw is not None:
                ident, raw = raw.get("uniqueid"), None
            else:
                uid += 1
                ident = f"0x{uid:X}"
            e = ET.Element("XDFFLAG", uniqueid=ident, flags="0x0")
            ET.SubElement(e, "title").text = title(name, mask, notes.get(mask))
            ET.SubElement(e, "description").text = description(name, mask, notes.get(mask))
            for cat in cats:
                e.append(deepcopy(cat))
            ET.SubElement(e, "EMBEDDEDDATA", mmedaddress=f"0x{addr:X}", mmedelementsizebits="8")
            ET.SubElement(e, "mask").text = f"0x{mask:02X}"
            root.insert(pos, e)
            pos += 1

def verify(root, pn):
    """Check exact coverage of reviewed bits; never label an inherited mask as reviewed."""
    notes = hand_options(pn)
    ids = set()
    flags = {}
    for e in root:
        if e.tag in ("XDFTABLE", "XDFCONSTANT", "XDFFLAG"):
            ident = int(e.get("uniqueid"), 0)
            if ident in ids:
                raise ValueError(f"{pn}: duplicate ID {ident}")
            ids.add(ident)
        name = (e.findtext("title") or "").split(" bit $")[0]
        if name not in notes:
            continue
        if e.tag != "XDFFLAG":
            raise ValueError(f"{pn}: raw option {name} should be split into flags")
        mask = int(e.findtext("mask"), 0)
        em = e.find("EMBEDDEDDATA")
        key = (name, mask)
        if key in flags or int(em.get("mmedaddress"), 0) != int(name[7:], 16) or int(em.get("mmedelementsizebits"), 0) != 8:
            raise ValueError(f"{pn}: incorrect or duplicate flag {key}")
        if (e.findtext("title") != title(name, mask, notes[name].get(mask))
                or e.findtext("description") != description(name, mask, notes[name].get(mask))):
            raise ValueError(f"{pn}: stale option semantics for {key}")
        flags[key] = e
    missing = {(name, mask) for name, bits in notes.items() for mask in bits} - flags.keys()
    if missing:
        raise ValueError(f"{pn}: missing reviewed bits {missing}")
    return sum(map(len, notes.values())), len(flags)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", required=True)
    parser.parse_args()
    for pn in FAMILIES:
        root = ET.parse(ROOT / "xdf" / (pn + ".xdf")).getroot()
        verified, flags = verify(root, pn)
        # The generator's post-processing must be semantically idempotent.
        clone = deepcopy(root)
        apply_stock_options(clone, pn)
        verify(clone, pn)
        def signature(tree):
            return [(e.tag, e.attrib, e.findtext("title"), e.findtext("description"),
                     e.findtext("mask"), tuple(c.attrib.items() for c in e.findall("CATEGORYMEM")))
                    for e in tree]
        if signature(root) != signature(clone):
            raise ValueError(f"{pn}: stock option post-processing not idempotent")
        print(f"{pn}: {verified} reviewed bits; {flags - verified} unverified inherited masks; metadata OK")

if __name__ == "__main__":
    main()
