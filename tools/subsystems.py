"""Subsystem groups: top routine (or owner) -> (name prefix, category, subsystem text).

Used by tools/autoname.py for table names and tools/constants.py for constant names.
"""
G = {}
def grp(addrs, prefix, cat, text):
    for a in addrs:
        G[a] = (prefix, cat, text)
FUEL = "fuel calculation (main loop)"
grp([0x1001C, 0x105EC, 0x102FE, 0x104AE, 0x10A6E, 0x10AEC, 0x11074, 0x111E0], "Fuel", "Fuel", FUEL)
grp([0x10036], "FuelCut", "Fuel", "fuel cut-off: rev and speed limits, deceleration")
grp([0x106EC, 0x107EA], "AccelFuel", "Fuel", "acceleration enrichment (throttle and MAP rate)")
grp([0x10C00], "AfterStartFuel", "Fuel", "after-start enrichment (time since start x coolant)")
grp([0x112A8, 0x11F40, 0x1204A, 0x1202A, 0x12680], "FuelEvent", "Fuel", "fuel calculation per reference event")
grp([0x123C0], "CrankFuel", "Fuel", "cranking fuel")
grp([0x14160, 0x1424C, 0x142C8], "O2", "Closed loop", "oxygen-sensor closed loop and adaptive fuel")
grp([0x19000, 0x1A5CA, 0x1A688, 0x1A6E2, 0x1BA5E, 0x1BAAE, 0x2D086], "Idle", "Idle", "idle speed control")
grp([0x1D000, 0x1DB84, 0x1DC20, 0x1DEDC, 0x1E14E, 0x1E2B6, 0x39412], "Spark", "Spark", "spark advance")
grp([0x1F000, 0x1F408], "Knock", "Spark", "knock control")
grp([0x2A81A, 0x2A906, 0x2B456, 0x2AC02, 0x2B692], "Misfire", "Diagnostics", "misfire monitor (crankshaft segment times)")
grp([0x20284, 0x2197C, 0x231A8, 0x2432A, 0x245CC], "Diag", "Diagnostics", "on-board diagnostic monitors")
grp([0x2C1BC, 0x2C6DE, 0x2C7FE, 0x2CB0E, 0x2CB60, 0x2CCA8, 0x2D1F6, 0x2D698, 0x2DADE, 0x2DC88, 0x0EC3A], "Sensor", "Sensors", "sensor processing")
grp([0x3B800, 0x3C46E], "SpeedCtl", "Speed control", "speed control (cruise), probable")
grp([0x0D08C], "Start", "Startup", "initialisation at reset")
grp([0x0A02E], "Event", "Other", "reference-event interrupt (input capture 1)")
grp([0x17000, 0x17FC4, 0x183C2, 0x17A48, 0x17D44, 0x181BE, 0x187E8, 0x18A8E, 0x18B22, 0x18BAA, 0x18836],
    "FlexLearn", "Fuel", "flex-fuel ethanol content learning")
grp([0x39E1A, 0x3A7A4, 0x3A8D2, 0x3AA44, 0x3ABFE], "Fan", "Cooling fan", "radiator fan control (relay and PWM variants)")
grp([0x39686], "Egr", "EGR", "EGR control, probable")
grp([0x2F000], "AcCtl", "A/C", "A/C clutch control, probable")
grp([0x3D800], "Purge", "EVAP purge", "EVAP purge control, probable")
