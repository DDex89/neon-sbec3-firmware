#!/usr/bin/env python3
"""EventTimingLimit IC1 predicate audit, host-only; no ROM or scheduler change.

The fine threshold can be numerically better without being control-equivalent.
Do not use it to authorize or suppress an output compare until ISR reachability
and physical scheduling are demonstrated. The selected research baseline keeps
the stock gate; fine threshold is shadow-only.
"""
from collections import Counter

def stock_limit(raw):
    return 86 + 56 * min(raw, 127) // 127

def fine_limit(q):
    return 86 + 7 * min(q & 2047, 1016) // 127

def ic1_gate(period, limit):
    assert 0 <= period <= 65535
    if period >> 8:
        return False
    if period < 0x4E:
        return True
    if period >= 0x82:
        return False
    return limit >= period

def main():
    counts = Counter()
    examples = {}
    for raw in range(256):
        signed = raw if raw < 128 else raw - 256
        old = stock_limit(raw)
        assert fine_limit(signed * 8) == old
        for residual in range(-8, 9):
            q = signed * 8 + residual
            if not -1024 <= q <= 1016:
                continue
            counts["pairs"] += 1
            fine = fine_limit(q)
            wraps = (signed < 0) != (q < 0)
            counts["wraps"] += wraps
            guarded = old if wraps else fine
            # Every predicate-changing region is covered exhaustively.
            # Outside the window, the original branches ignore the limit.
            for period in (0, 0x4D, *range(0x4E, 0x82), 0x82, 0xFF, 0x100, 0xFFFF):
                o, f = ic1_gate(period, old), ic1_gate(period, guarded)
                if not 0x4E <= period < 0x82:
                    assert o == f
                    counts["outside"] += 1
                    continue
                counts["window"] += 1
                if o != f:
                    kind = "new_enable" if f else "new_disable"
                    counts[kind] += 1
                    examples.setdefault(kind, (raw, q, period, old, guarded))
                if o != (o and f):
                    counts["and_policy_changes"] += 1
                if o != (o or f):
                    counts["or_policy_changes"] += 1
    expected = dict(pairs=4336, wraps=9, outside=26016, window=225472,
                    new_enable=197, new_disable=190,
                    and_policy_changes=190, or_policy_changes=197)
    assert dict(counts) == expected, (counts, expected)
    print(dict(counts))
    print("Counterexamples (raw, Q4, period, legacy limit, fine limit):", examples)
    print("Decision: keep stock IC1 predicate; fine threshold shadow-only.")
    print("Host arithmetic only; no IRQ reachability, dwell or hardware proof.")

if __name__ == "__main__":
    main()
