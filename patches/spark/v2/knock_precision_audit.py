#!/usr/bin/env python3
"""Host-only knock Q4 adapter audit for the two factory 128 KiB variants.

Keep the stock detector, adaptive cells, per-cylinder bytes, decrement mask,
fault paths and sampling windows. Lift the actual signed or unsigned
correction only at the consumer; no new RAM and no change to protection.
A separate hypothetical fine step illustrates why widening the accumulator
is NOT yet an equivalent replacement. No production patch or ECU execution.
"""
from collections import Counter

def step_table(signal):
    assert 0 <= signal <= 255
    return 128 + 127 * max(0, min(48, signal - 16)) // 48

def signed(raw):
    return raw if raw < 128 else raw - 256

def stock_step(signal, factor):
    return (step_table(signal) * factor + 128) // 256

def proposed_step_q4(signal, factor):
    return (step_table(signal) * factor + 16) // 32

def main():
    # Source: KnockSample, KnockLearn and SparkEventCalc in both ROMs.
    # Nonnegative accumulator domain and factory active cap values only.
    c = Counter()
    for signal in range(256):
        for factor in (4, 12):
            step = stock_step(signal, factor)
            fine = proposed_step_q4(signal, factor)
            c["step_cases"] += 1
            c["step_less"] += fine < 8 * step
            c["step_more"] += fine > 8 * step
            for old in range(128):
                for cap in (0, 6, 7, 8):
                    stock = 8 * min(127, cap, old + step)
                    lifted = min(1016, 8 * cap, 8 * old + 8 * step)
                    assert lifted == stock
                    c["exact"] += 1
                    candidate = min(1016, 8 * cap, 8 * old + fine)
                    c["less"] += candidate < stock
                    c["more"] += candidate > stock
                    c["same"] += candidate == stock
                    c["max_difference"] = max(c["max_difference"], abs(candidate-stock))
    assert dict(c) == dict(step_cases=512, step_less=39, step_more=46,
                           exact=262144, less=282, more=313, same=261549,
                           max_difference=4), c
    # KnockLearn: DECA/BPL/CLRA, for nonnegative per-cylinder bytes.
    for old in range(128):
        stock = max(0, old - 1)
        assert 8 * stock == max(0, 8 * old - 8)
    # SparkEventCalc explicitly SXT's the byte then SUBD's it.
    # CalcSpark adds the signed adaptive correction; preserve its sign.
    for raw in range(256):
        for angle in range(-128, 128):
            assert 8 * (angle - signed(raw)) == 8 * angle - 8 * signed(raw)
            assert 8 * (angle + signed(raw)) == 8 * angle + 8 * signed(raw)
    print(dict(c))
    print("128 decay states and 65536 signed angle/correction pairs exact.")
    print("Decision: exact lift at the consumer; fractional knock accumulation shadow only.")
    print("No sampling-window, ISR interleaving, RAM or hardware proof.")

if __name__ == "__main__":
    main()
