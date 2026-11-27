# SBEC3 stock bench validation

The first pass uses stock firmware on an isolated bench, with no firmware writes and no powered injector or ignition loads. The ROM archive is enough for CPU16 instruction tests. A physical capture applies to the firmware and board identified in that capture.

| Hardware available | Highest-value first pass | Evidence that stays open |
|---|---|---|
| Exact 05293013AC | Establish reset-to-first-normal-SCI baseline and collect any naturally occurring reset or exception observation. With suitable trace, correlate execution milestones with external timing. | Hardware response to the aging read remains unknown unless an ordinary run reaches it and there is adequate board-level evidence. |
| Exact 04887050 | Use the same baseline and capture format. The simulated aging read for this ROM lands in SRAM. | Board behavior of 05293013AC remains open. |
| Only a different 128 KiB SBEC3 | Use the unit for capture setup. Compare PCB revision, MCU marking and ROM ID before using any timing as reference evidence. | Both exact-target board outcomes remain open. |
| Only 256 KiB SBEC3 or no ECU | Run exact-ROM local fixtures. Keep physical results pending. | Board mapping and timing for the 128 KiB targets remain open. |

## Evidence to record

1. Record controller part number, PCB revision and MCU marking if visible, installed ROM identifier and SHA-256 when a verified read-only image is available. A housing label alone does not establish firmware or PCB identity.
2. Start with passive observation. Record the conditions at power-up, the reset reference, and the first normal diagnostic response when it is observable. Record which channels share a timebase and their sampling resolution. Record clock or bus signals only when the board and probe access are known. Keep stimuli and calibration consistent across controllers.
3. Distinguish external timing from internal execution evidence. Reset and SCI edges can time the external response. A stack depth, specific IRQ overlap or memory access needs suitable CPU state or bus evidence. Use a known compatible read-only trace method if available. Do not infer an internal event from an external gap alone.
4. Keep the stock comparison separate from experimental integration. Begin from the known stock image, record the complete initial state and report the observed interval. Use model tests for conditions that available hardware cannot observe. Avoid forced memory accesses, diagnostic writes, active fault injection and cross-flashing variants for this pass.

## Local results

Exact-ROM decoding pinned 31 nominal reset register values on each target. Under those values, the 04887050 earlier-match aging address is in SRAM. The 05293013AC address is outside the nominal SRAM and enabled external chip-select windows. The firmware's vector and exception prefix also passed isolated tests with supplied frames. The local tests establish the programmed map and firmware response to an already supplied frame. The board response, acknowledgements, interrupt arrival time and real frame contents remain unmeasured. [NXP M68HC16 Z-series manual](https://www.nxp.com/docs/en/data-sheet/MC68HC16ZUM.pdf)

For ReCore release evidence, the remaining artifacts are a stock timing reference on the available board, then independently reviewed RAM ownership, stack coverage and compatible DinoFuel V2 / Spark V2 integration traces. Report the observed stack maximum with its exact scenario. A global bound also requires coverage of unobserved states and nesting.

A compact capture record should include ECU/PCB/MCU identification, ROM hash, stock or experimental status, test scenario, inputs and initial state, timebase and sample rate, capture filename, observations and unresolved assertions.

## External protocol references

- **CCD capture and framing.** Chrysler manual PF-8219 describes 7,812.5 baud, frame boundaries, bus bias and termination. Its description of the CCD transceiver's SCI host interface applies to the microcontroller-to-transceiver link. The bench checklist uses SCI for the PCM diagnostic link. CCDLibrary provides monitor and filter examples for an Arduino Mega with a CCD transceiver. [Chrysler PF-8219 manual](https://chryslerccdsci.wordpress.com/wp-content/uploads/2020/05/880586-ccdbususersmanual.pdf) · [CCDLibrary examples](https://github.com/laszlodaniel/CCDLibrary/tree/master/examples)
- **CCD reference trace.** The local CPU16 check seeded telemetry values from the published trace and scanned all 128 transmit slots on each of `04887050`, `05293013AC` and `05293190AC`. On each ROM the stock RAM transmit queue reproduced frames `$E4`, `$24` and `$8C` byte for byte, including the additive checksum. This verifies the queued bytes in the model. Measuring wire timing and reception remains part of bench capture. [Published CCD trace](https://chryslerccdsci.wordpress.com/2019/09/29/replaying-ccd-bus-messages/) · [Local reference check](https://github.com/DDex89/recore-sbec3/blob/dinofuel-128k/patches/spark/v2/stock_bus_reference_audit.py)
- **SCI scanner log.** The high-speed SCI example contains millisecond timestamps added by the scanner and shows how it presents returned values. Use it for offline log parsing. Capture the PCM line directly for wire timing and use the exact ROM to identify its addresses. [High-speed SCI log](https://chryslerccdsci.wordpress.com/2019/09/27/sneak-peek-into-the-high-speed-realm-of-the-sci-bus/)
- **PCI/J1850 VPW.** The stock `Options032E.2` selector chooses PCI on `05032017AA` and CCD on `05293190AC`, `05269833AH`, `05269833AI` and `05269834AJ`. The two 128 KiB bench targets above use CCD and diagnostic SCI. For the PCI bench target, J1850VPWCore offers a receive-only initialization and implements the wire CRC-8/SAE-J1850. The PCM's internal QSPI receive buffer has its own additive checksum. Identify the bench board before choosing the physical interface. [Local ROM check](https://github.com/DDex89/recore-sbec3/blob/dinofuel-128k/patches/spark/v2/stock_bus_reference_audit.py) · [J1850VPWCore source](https://github.com/laszlodaniel/J1850VPWCore/blob/main/src/J1850VPWCore.cpp)
- **DRB III metadata.** DRBDBReader can inspect an external `database.mem` offline and obtain field offsets, scales and units from a matching module profile. The reader repository does not provide that database. Verification against the exact PCM profile is pending. [DRBDBReader](https://github.com/MWisBest/DRBDBReader) · [Conversion record format](https://github.com/MWisBest/DRBDBReader/blob/master/DRBDBReader/DB/Records/DADRecord.cs)
