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
