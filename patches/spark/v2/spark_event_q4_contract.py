#!/usr/bin/env python3
"""Spark V2 event arithmetic contract; host-only, no ROM modification.

Approved scope: keep stock knock detection, learning, accumulator, recovery,
calibration, sample windows, and all stock control predicates. Convert signed
legacy corrections to Q4 only in the consumer. Knock V2 is out of scope.
The legacy angle remains authoritative for scheduling and diagnostics.
The model starts after stock correction selection and ramp update.
"""
from itertools import product


def stock(base, corrections, minimum, ramp, running=True, suppressed=False):
    if not running:
        return 0x12
    ac, pair, event, knock = (0, 0, 0, 0) if suppressed else corrections
    total = base + pair + ac - event - knock
    if total < minimum:
        total = minimum
    elif total > 127:
        total = 127
    return min(total, ramp)


def shadow(base, fine_base, corrections, minimum, ramp, running=True,
           suppressed=False, forced=False):
    old = stock(base, corrections, minimum, ramp, running, suppressed)
    if not running or suppressed or forced:
        return old * 8
    assert -1024 <= fine_base <= 1016
    ac, pair, event, knock = corrections
    total = fine_base + 8 * (pair + ac - event - knock)
    return min(max(total, 8 * minimum), 1016, 8 * ramp)


def main():
    # Factory correction bytes are sign-extended by SXT. Synthetic extrema
    # include unreachable states, testing arithmetic not operating envelope.
    grid = (-128, -127, -8, -1, 0, 1, 8, 126, 127)
    limits = ((-128,127),(-12,42),(0,0),(127,-128),(-1,0),(0,-1))
    cases = 0
    for base, ac, pair, event, knock in product(grid, repeat=5):
        c = ac, pair, event, knock
        for lower, upper in limits:
            old = stock(base,c,lower,upper)
            assert shadow(base,8*base,c,lower,upper) == 8*old
            cases += 1
    fractional = 0
    for base in range(-128,128):
        for residual in range(-8,9):
            q = base*8 + residual
            if not -1024 <= q <= 1016:
                continue
            for c in ((0,0,0,0),(3,-5,2,8),(-128,-128,127,127),
                      (127,127,-128,-128)):
                for lower, upper in limits:
                    old = stock(base,c,lower,upper)
                    fine = shadow(base,q,c,lower,upper)
                    assert abs(fine-8*old) <= abs(residual)
                    assert -1024 <= fine <= 1016
                    assert shadow(base,q,c,lower,upper,forced=True) == 8*old
                    assert shadow(base,q,c,lower,upper,running=False) == 144
                    assert shadow(base,q,c,lower,upper,suppressed=True) == 8*stock(base,c,lower,upper,suppressed=True)
                    fractional += 1
    print(f'{cases} integer equivalence cases; {fractional} fractional cases with forced/suppressed/start controls')
    print('Host-only arithmetic; no CPU16 execution, RAM allocation, ISR or hardware proof.')


if __name__ == '__main__':
    main()
