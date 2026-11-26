"""Image-local SBEC3 fault table decoding (annotations only)."""
import collections
FAULT_ROW_SIZE = 10
FAULT_BITMAP_BYTES = 0x1C


def fault_table_bounds(data, annotations):
    """Return the start and numbered row count of this image's annotated fault table."""
    tables = [(int(k, 16), v) for k, v in annotations.get("special", {}).items()
              if v.get("kind") == "fault" and v.get("row_size") == FAULT_ROW_SIZE]
    if len(tables) != 1:
        return 0, 0
    start, _ = tables[0]
    if not 0 <= start < len(data):
        return 0, 0
    n = 0
    while (n < 256 and start + FAULT_ROW_SIZE * (n + 1) <= len(data)
           and data[start + FAULT_ROW_SIZE * n] == n):
        n += 1
    return start, n


def fault_row_code(data, address, table):
    """Decode a row pointer only if it points to a complete, numbered row."""
    start, count = table
    delta = address - start
    if not 0 <= delta < count * FAULT_ROW_SIZE or delta % FAULT_ROW_SIZE:
        return None
    row = data[address:address + FAULT_ROW_SIZE]
    if len(row) != FAULT_ROW_SIZE or row[0] != delta // FAULT_ROW_SIZE:
        return None
    if row[6] or row[7]:
        return "P%02X%02X" % (row[6], row[7])
    return "fault row $%02X, no P-code" % row[0]


def fault_bits(data, table):
    """FaultSetNN / FaultMemNN bit -> image-local DTC; omit ambiguous mappings."""
    start, count = table
    candidates = collections.defaultdict(list)
    for r in range(count):
        address = start + FAULT_ROW_SIZE * r
        row = data[address:address + FAULT_ROW_SIZE]
        if (len(row) != FAULT_ROW_SIZE or row[0] != r
                or bin(row[4]).count("1") != 1 or row[5] >= FAULT_BITMAP_BYTES):
            continue
        candidates[(row[5], row[4].bit_length() - 1)].append(fault_row_code(data, address, table))
    out = collections.defaultdict(dict)
    for (offset, bit), codes in candidates.items():
        if len(codes) != 1:
            continue
        for arr in ("FaultSet", "FaultMem"):
            out["%s%02X" % (arr, offset)][str(bit)] = codes[0]
    return out
