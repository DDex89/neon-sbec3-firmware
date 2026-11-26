# Diagnostic condition flags: cross-family audit

Static code audit; all addresses hexadecimal. RAM offsets are relative to Z ($F8000). No calibration or executable instruction changes.

| Representative image | MisfireFlags2 | MonStatusO2Heater | DiagStatusFlags | Misfire primary (bit 0) | Misfire secondary (bit 1) | Heater primary | Heater secondary |
|---|---|---|---|---|---|---|---|
| 04887050 | 0243 | 00B8 | 00DF | 2FF1 | 302E | 2D40 | 2D7D |
| 05293013AC | 025B | 00C0 | 00E7 | 301C | 3059 | 2D6B | 2DA8 |
| 05007038 | 02C5 | 00C5 | 0110 | 3373 | 33B0 | 30C2 | 30FF |
| 05269833AH / AI | 0624 | 00B1 | 00D8 | 3B67 | 3BA4 | 36B9,375C,37FF,38A2 | 36F6,3799,383C,38DF |
| 05293190AC | 0624 | 00B1 | 00D8 | 3C31 | 3C6E | O2HeaterMonitorConds,3,5,7 | O2HeaterMonitorConds2,4,6,8 |
| 05032017AA | 0624 | 00B2 | 00D9 | 41D8 | 4215 | 3D2A,3DCD,3E70,3F13 | 3D67,3E0A,3EAD,3F50 |

## Semantics

- MisfireFlags2.0: the primary list failed. On that path MisfireEnableCheck returns A=0; on the passed path A=$FF. Bit 1 records secondary-list failure but does not itself cause an immediate return: primary evaluation follows. Earlier gates may leave these flags unchanged. In 05007038 and the reference 256 KB code the MonEnableFlags2.7 set path clears both bits and bypasses these lists.
- MonStatusO2Heater.0: primary group failed, start path exits. Bit 1 records secondary group failure; the later completion path tests it before clearing the sensor-monitor bit 7 flags. It is not an unconditional start inhibit. The 128 KB code calls one list per group; the examined 256 KB code calls four per group, with short circuit on first failure.
- DiagStatusFlags.0/.1: current descriptor list at +$0A/+$0C respectively failed, when evaluated by ObdMonitorMain. Not persistent DTC flags. Both are cleared before computing the current result; some paths bypass the evaluation, including selected 256 KB descriptor paths. The +$08 list can clear descriptor status mask $C9 on failure under its own gating. Do not confuse it with either result bit.
- 04887050 and 05293013AC: primary misfire list has 8 rows, secondary and both heater lists have zero rows. 05269833AH/AI: 2 and 7 misfire rows, respectively; each of the eight heater lists has one row. 05032017AA: all ten listed tables have zero rows. Empty list succeeds; this does not disable other code-level monitor gates.
- 05269833AH heater list $36B9 contains 0A 9A 06 03: unsigned raw VehicleSpeed byte must be strictly below 3. Physical speed units are not inferred here.
- Full bank0 source retrieval for 05007038 and 05293190AC exceeded the connector text limit; their call-site names/addresses are documented, but their table contents were not audited in this pass. Other variants without representative source were not independently reconstructed.
- FaultSet/FaultMem mapping and full MonEnableFlags2 producer/consumer audit remain separate. CI unavailable due to user-reported limits.

