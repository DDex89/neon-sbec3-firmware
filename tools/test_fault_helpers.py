import unittest
from fault_helpers import fault_table_bounds, fault_row_code, fault_bits


def image(start, rows):
    return bytes(start) + b''.join(bytes(row) for row in rows)


def annotation(start):
    return {"special": {"%04X" % start: {"kind": "fault", "row_size": 10, "rows": 256}}}


def row(index, mask=1, offset=0, code=0):
    return [index, 1, 0, 0xC3, mask, offset, code >> 8, code & 255, 0, 0]


class FaultTableTests(unittest.TestCase):
    def test_image_specific_codes(self):
        for start, code in [(0x3505, 0x0751), (0x3530, 0x0133)]:
            d = image(start, [row(0, code=code), row(1, 2, code=0)])
            t = fault_table_bounds(d, annotation(start))
            self.assertEqual(t, (start, 2))
            self.assertEqual(fault_bits(d, t)["FaultSet00"]["0"], "P%04X" % code)
            self.assertEqual(fault_bits(d, t)["FaultMem00"]["0"], "P%04X" % code)
            self.assertEqual(fault_row_code(d, start + 10, t), "fault row $01, no P-code")
            self.assertIsNone(fault_row_code(d, start + 1, t))
            self.assertIsNone(fault_row_code(d, start + 20, t))

    def test_unknown_table(self):
        d = image(16, [row(0, code=0x0340)])
        t = fault_table_bounds(d, {})
        self.assertEqual(t, (0, 0))
        self.assertEqual(dict(fault_bits(d, t)), {})

    def test_numbering_and_truncation(self):
        d = image(16, [row(0), row(2), row(3)])
        self.assertEqual(fault_table_bounds(d, annotation(16)), (16, 1))
        d = image(16, [row(0), row(1)])[:-1]
        self.assertEqual(fault_table_bounds(d, annotation(16)), (16, 1))

    def test_ambiguous_and_invalid_bits(self):
        d = image(16, [row(0, code=0x0340), row(1, code=0x0601), row(2, 3),
                       row(3, 1, 0x1C), row(4, 4, 3, 0x0203)])
        t = fault_table_bounds(d, annotation(16))
        bits = fault_bits(d, t)
        self.assertEqual(dict(bits), {"FaultSet03": {"2": "P0203"}, "FaultMem03": {"2": "P0203"}})


if __name__ == "__main__":
    unittest.main()
