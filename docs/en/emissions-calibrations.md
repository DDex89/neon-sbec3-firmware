# Factory emissions applications and ROM monitor enablement

Mopar uses FED for the U.S. federal emissions family, CAL for California and CAN for Canada. BUX expands to Built Up Export and does not identify a particular destination by itself. MEX denotes Mexico. FCA sometimes groups multiple markets in one service-flash listing, for example FED/CAN or FED/CAL. Treat the specific listing as the application evidence. [Mopar abbreviations](https://www.moparrepairconnect.com/dA/d1d37f47dc/acronyms-abbreviations.pdf) · [FCA FedWorld report](https://kb.fcawitech.com/assets/FedWorldReport.pdf)

| ROM header | Application evidence | Scope |
|---|---|---|
| 04887050 | 1996 FJ 2.0 DOHC automatic, FED/Taiwan/CAL service group | FCA FedWorld, printed p. 043 |
| 04887051 | 1996 FJ 2.0 DOHC manual, FED/CAL service group | FCA FedWorld, printed p. 043 |
| 05269833AH / 05269833AI | 1998 FJ 2.0 manual, FED/CAL service group | AH listed among predecessors of AI, printed p. 308 |
| 05269834AJ | 1998 FJ 2.0 automatic, FED/CAL service group | Printed p. 308. The supplied file named 05269834AI has AJ in its header. |
| 05293148AA | 1998–99 PL Neon 2.0 SOHC manual, FED service group | Listed among predecessors of 05293063AF, printed p. 314. The archived file named 05293063AC contains 05293148AA. |
| 05007038 | Matches the number of Mopar Performance P5007038, sold for 1997–99 Neon DOHC manual | The supplied catalog page 193 lists manual transmission. The official Mopar Performance catalog also lists the DOHC application. The exact ROM contains part-number BCD 05 00 70 38 and revision bytes 98 41 at $00302. |

The FCA rows describe service-flash applications. A label such as FED/CAL does not distinguish the individual vehicle’s certification or hardware. No verified market assignment was made here for 05293013AC, 05293014AC, 05293190AC or 05032017AA. [FCA FedWorld report](https://kb.fcawitech.com/assets/FedWorldReport.pdf) · [Mopar Performance catalog](https://starparts.chrysler.com/starlibrary/dto/PerformancePartsCatalog.pdf)

05007038 and 05293148AA share the family C implementation. The catalog and service listing associate them with different engine applications, so the calibration comparison does not isolate emissions market or performance tuning as a single variable. The existing exact-ROM comparison found 2,214 differing bytes and no differing code bytes. [Family C calibration differences](../diffs/05293148AA_05007038.md)

## Local monitor check

Run `python tools/obd_enablement.py` with the eleven archived ROMs or supply part numbers. The tool checks each SHA-256, decodes the per-image option rows and executes ObdRecordFlags with two starting values per status byte. It confirms bit 7 and preservation of the other bits. Counts below describe the rows this routine arms. Monitor readiness and completion also depend on runtime conditions.

| ROM | Rows armed | Comparison |
|---|---:|---|
| 04887050 / 04887051 | 9/13 each | Same row enablement |
| 05293013AC / 05293014AC | 9/13 each | Same row enablement |
| 05007038 / 05293148AA | 11/13 and 9/13 | At $0335, mask $20 arms the purge-flow row and mask $02 arms the leak-detection pump row in 05007038. Both rows are off in 05293148AA. |
| 05269833AH / 05269833AI / 05269834AJ | 12/16 each | Same row enablement across the revision and transmission variants tested |
| 05293190AC | 12/16 | Reference |
| 05032017AA | 0/16 | All rows unarmed by ObdRecordFlags in this exact ROM. Other diagnostic paths were outside this check. |

## Family C EVAP fault attributes

The two images have identical primary OBD descriptors, ObdFaultProcess and ObdFaultCondition. Seven FaultTable attributes differ. The values below are the raw bytes in the two exact ROMs.

| DTC | Fault row ID | 05007038 | 05293148AA |
|---|---:|---:|---:|
| P0601 | $02 | $03 | $C3 |
| P0441 | $71 | $CB | $0B |
| P1299 | $91 | $03 | $C3 |
| P0442 | $A0 | $CB | $0B |
| P0455 | $A1 | $CB | $0B |
| P1494 | $B8 | $03 | $0B |
| P1486 | $BB | $C3 | $03 |

In 24 isolated selector cases, the purge row $EEB0 on 05007038 could report P1486 or P0441, and the leak-detection row $EED8 could report P0442 or P0455. Each selected fault set its history bit. The switch branch for P1494 produced no report on either ROM. When both reportable inputs were set, P1486 took precedence over P0441 and P0442 over P0455. No case on 05293148AA reached ReportFault from those two OBD rows. The tests supplied the row status and result flags directly. Monitor enablement is covered by the separate option check. [Exact-ROM failure-side checks](sci-obd-128k.md#failure-side-writes-with-stock-descriptors)
