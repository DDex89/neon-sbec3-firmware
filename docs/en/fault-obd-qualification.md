# Pending fault timing and OBD two-failure qualification

## Periodic pending-counter service: families A, B and C

MainLoop calls MainLoopCounters before the phase dispatch in 04887050, 05293013AC, 05007038 and 05293148AA. Exact-ROM tests ran the real counter increment and all 256 dispatch phases on each image. The branch selects FaultPendingAge only at MainLoopCounter = $80, once per regular 256-pass rollover. The two unrelated calls immediately before FaultPendingAge were skipped in the dispatch test. Elapsed time in seconds depends on the main loop on the ECU.

ReportFault increments its pending count toward the descriptor threshold. FaultPendingAge decrements the two active pending counts and clears their IDs at zero. For the separate recovery state used by ReportPass, it increments the age and clears the pair when the incremented value exceeds the descriptor threshold. The 3,047 isolated age cases covered all aligned fault indices on the four images at and around those thresholds. Writes stayed in the six pending and recovery bytes. This mechanism runs periodically within a drive cycle. [Exact-ROM regression script](https://github.com/DDex89/recore-sbec3/blob/dinofuel-128k/patches/spark/v2/stock_obd_failure_audit.py)

## Independent OBD qualification mechanism (05293190AC)

ObdFaultReport searches 22 ten-byte descriptors starting at $75FA within FaultStatusMap ($758C). FaultTwoTripRows is the count byte ($16) at $7746. A separate cross-family audit verified the prior-failure and result offsets across the corresponding table on the 256 KiB images. [Diagnostic symbol canonicalization](diagnostic-symbol-canonicalization.md)

For a matching fault index, the descriptor comprises a fault row pointer (+0), first RAM offset (+2), first mask (+5), second RAM offset (+6) and second mask (+9). The first pair holds the previous-failure state; the second pair holds the current test result. The code checks the referenced fault row attribute bit 7 and the current result bit.

- Enabled fault with result bit set, previous-failure bit already set: call ReportFault.
- Enabled fault with result bit set, previous-failure bit clear: set previous-failure bit; if descriptor attribute bit 6 is set, call FreezeFrameCapture with A=1 and B=fault row index.
- Result bit clear: conditionally call FreezeFrameStore when FreezeFrame00 < 3 and FreezeFrame01 matches the fault row; clear both descriptor bitmap bits.
- Disabled fault: clear both descriptor bitmap bits directly.
- Unmatched index: return without applying any descriptor.

The first-pair bytes are named ObdPriorFailSwitch, ObdPriorFailO2 and ObdPriorFailMisc. A repeated invocation with the result set is sufficient at this routine boundary.

## Reset retention on the five stock 256 KiB images

The same 22-row mechanism was exercised on 05293190AC, 05269833AH, 05269833AI, 05269834AJ and 05032017AA. Its row block and count move to $7629/$7775 on 05032017AA. The prior-failure bytes are $F809D–$F809F on the first four and $F809E–$F80A0 on 05032017AA. The corresponding current-result bytes are $F8658–$F865A throughout.

The tests executed the end of CheckPowerDown, including the stock NvChecksum call, the store to ResetCheckWord, and the jump to Reset. NvChecksum sums $F800A–$F82ED. It includes the prior-failure bytes. The current-result bytes lie beyond the checked range. With the saved checksum intact, Reset chose marker $4AB5. All three prior bytes survived through ObdResetInit to MainLoop, and all three result bytes cleared. With a deliberately mismatched saved checksum, Reset chose $4AB6 and cleared both groups. The ten startup runs supplied peripheral-ready status and zero QSPI receive data. The 513 distinct-per-image EEPROM restore destinations and their fixed service-byte stores exclude both groups. [CPU16 reference manual](https://www.nxp.com/docs/en/reference-manual/CPU16RM.pdf)

Across 550 direct qualification calls, every row was checked for an initial failure, a repeat, a successful result, and a new failure after each reset path. The enabled rows numbered 12, 12, 12, 16 and 6 in the ROM order above. A repeat with retained first-failure state called ReportFault and set its history bit. With cold-reset state, the same supplied failure set the prior bit on enabled rows. In 15 separate calls across three clear routines, MonitorFlagsClear zeroed both groups, while ObdClearCodes and ClearFaultHistoryAndCurrentState preserved them individually. The stock OBD, SCI and diagnostic clear paths in bank 3 call the three routines in sequence.

## Verified qualification at two monitor entry points

SwitchMonitors selects VssMonitor at counter phases $1F, $3F, $5F, $7F, $9F, $BF, $DF and $FF on all five images. The 1,280 phase checks ran MainLoopCounters and the actual branch to the VSS call. In 30 isolated VssMonitor calls with eligible inputs, a first qualified P0500 failure set the prior and result bits. The same failure sample with the result bit already set skipped ObdFaultReport. After warm reset cleared the result and preserved the prior flag, a new qualified failure wrote the history bit. After cold reset it began qualification again. A qualifying nonzero-speed sample cleared the paired bits.

The 25 isolated TransMilRequest calls checked its guards and two P0700 paths. The direct branch reached ReportFault without a prior-failure flag when a newly received transmission status satisfied its guards. The exact 05269834AJ and 05032017AA descriptors accepted it and recorded P0700. The other three descriptors rejected it. A separate transmission-status branch entered ObdFaultReport for first-failure qualification.

Run `python patches/spark/v2/stock_obd_reset_retention_audit.py` from ReCore with the five 256 KiB ROMs in `roms/`. [Exact-ROM regression script](https://github.com/DDex89/recore-sbec3/blob/dinofuel-128k/patches/spark/v2/stock_obd_reset_retention_audit.py)

## Downstream oxygen and warm activity callers

The first downstream high/low failure for an enabled DTC sets the prior and current-result bits through O2DownCircuitCheck. The current-result bit blocks an immediate repeat. After a modeled warm reset, a fresh qualified failure records P0137 or P0138 on 05293190AC, 05269833AH, 05269833AI and 05269834AJ. P0157 and P0158 are disabled on all five images. On 05032017AA all four downstream circuit fault descriptors are disabled.

The tested high fault starts above raw $42 and the low fault starts below $04. Counting uses MainLoopPhaseMask $08 for high and $80 for low. The 1,280 phase checks confirm one selected high phase per 16 passes and one low phase per 256 passes. The fault-count thresholds are $96 high and $1C low, with a low threshold of $13 on 05032017AA. The pass thresholds are $4B high and $0A low. These are firmware counts. [Reference bank 2 source](../../src/05293190AC/bank2.asm)

A qualifying healthy sample with a retained prior failure sets a completion bit in MonFlags101 and its matching hold bit in O2DownFlags. O2DownResult waits while the hold bit is set. Warm reset preserves the completion and clears the hold. The next O2DownResult call clears the prior failure through ObdFaultReport without writing history. The cold controls cleared both the completion and prior flags.

In O2ActivityWarm, a running downstream P0140 test below speed threshold $50 takes a distinct branch on 05269833AH. At $4F, AH calls ObdFaultReport with a clear result and clears the supplied prior-failure flag. The other four ROMs cancel the test at that speed and leave the supplied flags intact. At speed $50 with raw below the bias threshold, all five take the clear path under the tested states. [AH bank 2 source](../../src/05269833AH/bank2.asm)

## Body bus, brake and park/neutral callers

BodyBusTimeout starts P1698 qualification at timeout count $C8. Only 05269834AJ and 05032017AA set the paired flags and accept a new qualified timeout after warm reset. On those two images, a supplied heard-module state below the timeout threshold sets MonFlags101.7 and O2DownFlags.7. The next warm reset keeps the former and clears the latter. BodyBusTimeout then clears the retained first failure through ObdFaultReport.

For P0703, the checked BrakeSwitchMonitor failure branch needs Options0340.5 and an enabled FaultTable descriptor. Only 05032017AA passes the option and its P0703 descriptor is disabled. 05269834AJ enables the descriptor and blocks the examined fault branch at the option. The successful-result path clears the paired bits. For P1899, the tested startup state reaches PnSwitchMonitor qualification only on 05269834AJ. A retained prior failure then records P1899. On 05032017AA the descriptor is enabled, Options0333.2 blocks the startup check, and Options0340.6 is clear, disabling the running check.

The local script ran 232 isolated caller invocations, 28 modeled resets and 1,280 phase selections on the five hash-verified ROMs. The model used stock checksum publication, supplied peripheral-ready states, and supplied sensor and bus inputs. [Exact-ROM caller script](https://github.com/DDex89/recore-sbec3/blob/dinofuel-128k/patches/spark/v2/stock_obd_caller_audit.py)

## Direct call inventory

The five exact ROMs contain 37 direct calls to ObdFaultReport each, with 34 on 05269833AH. All are in bank 2. The reference source maps them to 16 routines. The AH difference comes from EgrPositionMonitor, which has a single shared qualification call in that ROM.

| 05293190AC callers | Calls | Descriptor coverage |
|---|---:|---|
| O2ActivityWarm, O2DownCircuitCheck, O2DownResult, CatMonSwitchRatio | 9 | P0133, P0137, P0138, P0140, P0153, P0157, P0158, P0160 |
| EgrPositionMonitor | 4 | P0404 |
| TransMilRequest, BodyBusTimeout | 5 | P0700, P1698 |
| FuelSenderMonitor, ThermostatMonitor, ThermostatWarmCheck | 9 | P0460, P0462, P0463, P1281, P0125 |
| BrakeSwitchMonitor, PnSwitchMonitor, TccMonitor, IdleRpmMonitor, PspSwitchMonitor, VssMonitor | 10 | P0703, P1899, P0740, P1294, P0551, P0500 |

The inventory covers direct call sites. Full monitor traces for the remaining paths and physical timing remain open.

## EGR position, fuel sender and torque converter clutch

### EGR position

The stock bank 3 EGR dispatcher bypasses EgrControl on all five 256 KiB ROMs because Options0335.2 is clear. In isolated EgrPositionMonitor tests, the tracking comparison accepts a target only from a calibrated minimum through a maximum. The minimum is $66 on four images and $26 on 05032017AA. The maximum is $00 on all five. Sweeping all 256 targets confirmed that none passes.

The raw-position branch hands P0405 to ReportFault below $08 on all five images. The high branch hands it P0406 above $F0 on 05269833AH and above $FA on the other four. Those calls require phase mask $04. The P0404, P0405 and P0406 descriptors all have attributes $03, with reporting disabled. The raw-position sweep made 23 calls on AH and 13 per other ROM, with no current or history writes for those codes. P0404 cleanup was checked under supplied states. The AH shared call was isolated after the target gate, and the other four ROMs also exercised their separate zero-check branch. P0403 and physical solenoid response remain outside these checks.

On 05269833AH, MainLoop at call site $0DE3C enters EgrMain at $39686. The IRQ2 call at $088B0 enters Irq2Dispatch at $0890C. The corrected names are recorded in the port map and tracked ASM. In both repositories the substitution reverses exactly, and the tracked and freshly generated ASM assemble to the archived ROM byte for byte.

### Fuel sender

MainLoop selects FuelSenderMonitor at $20, $60, $A0 and $E0. The electrical checks use raw above $E6 for P0463 and at or below $05 for P0462. The fault count must exceed $07 on 05293190AC, 05269833AH, 05269833AI and 05269834AJ, or $08 on 05032017AA. The recovery count must exceed $07 on the first four or $04 on 05032017AA.

On the first four images, a qualified electrical fault sets the prior and result bits. The same result is skipped. A new qualified failure after warm reset records history. A healthy sample can instead set the corresponding MonFlags101.5/.4 completion and O2DownFlags hold bits. After another warm reset, FuelSenderMonitor uses the retained completion to clear the first-failure bit. These paths were executed with 24 modeled warm resets.

For P0460, a fresh baseline captures $6D through $FF on the four enabled ROMs under the supplied gates. None of the 256 input values enters the low band because capture requires at least $6D and the low band requires below $6D. The low-band comparison was exercised separately with a supplied flag. For both tested bands, movement equality clears the prior flag. With movement one below its threshold, reaching the mileage accumulator threshold selects a failure. SriMileageStore increments that accumulator. On 05032017AA, the option blocks the P0460 path and all three fuel-sender descriptors are disabled.

### Torque converter clutch

SwitchMonitors selects TccMonitor on odd counter phases. On four ROMs the unsigned ratio gate requires a filtered ratio byte below $00. All 256 byte values were exercised, and none reached the P0740 qualification branch. 05269833AH also omits the A/C-request guard at the start of the routine. On 05032017AA the numerical gates admit the supplied states. The branch qualifies a failure after count $03, or marks completion when ratio drop reaches $0403. The P0740 fault descriptor has attributes $03 in all five ROMs, and neither branch recorded P0740. With stock EquipmentInit state, AcRequestUpdate cleared the A/C-request bit on all five.

The local audit ran 8,926 cases across the five exact ROMs. It includes 3,865 EGR cases, 1,040 TCC caller cases, five A/C-request controls, 152 fuel-sender threshold and transition cases, 1,280 fuel baseline samples, 2,560 scheduler phase selections, and 24 modeled warm resets. The tests supply sensor values and intermediate monitor state. [Exact-ROM monitor script](https://github.com/DDex89/recore-sbec3/blob/dinofuel-128k/patches/spark/v2/stock_obd_monitor_audit.py)

## Thermostat, idle speed and power-steering pressure

On the five hash-verified 256 KiB images, the real main-loop counter and
SwitchMonitors called the P1281 monitor every pass, P1294 every eight
passes, P0551 every 16 and P0125 every 128. The P1281 branch was enabled
on all five. It starts within raw coolant [$79,$E4) with battery at least
$68 and passes at coolant $C7 or higher under the tested conditions.
At the failure boundary it requires Count3s=$FF, speed at least $38
and MonSpeedCounter=$FF. The P0125 check passed at coolant $7D or higher.
With start coolant $63 its stock lookup gave $BD and the failure branch
required Count3s above $BD.

The idle check treated offsets at −$0320 and +$0640 as inside the accepted
band. The tested fault required startup delay $C8, idle reference below
$01E0 and drop count reaching two. The P0551 switch-on failure required
speed above $64, RPM high byte below $FF and count reaching $C7.
The switch-off recovery also used $C7.

The enabled routines set the retained first failure on the first qualifying
run, skipped repeat qualification in the same modeled cycle and recorded a
new failure after warm reset. A subsequent healthy result cleared the prior
failure. Cold reset started a new qualification. On 05032017AA,
Options0340=$20 blocks P0125, P1294 and P0551. The P0551 descriptor remains
enabled and EquipmentInit sets the equipment flag. The P0125 and P1294
descriptors are disabled on that ROM.

The audit ran 269 monitor calls, 34 modeled resets, 1,280 dispatch phases
and five EquipmentInit controls. The tests used supplied inputs and the
stock routine and reset paths. [Local audit](https://github.com/DDex89/recore-sbec3/blob/dinofuel-128k/patches/spark/v2/stock_obd_switch_thermal_audit.py)

## Cold oxygen activity and slow response

On all five images, O2NoActivityCold maps its four channels to
P0131/P0151/P0137/P0157 and calls ReportFault directly. The four CCD images
enable P0131 and P0137. Options0340.0 disables the whole cold check on
05032017AA. In the CCD tests, a past warm condition could arm the retained
check at coolant $C7 or higher. Sampling needed start coolant below $A6,
a start-coolant and battery-temperature difference below $07, and a raw O2
value below $08. The 41st below-limit sample marked the channel once its
counter had reached $28. Count191ms at $19 or higher admitted reporting
when the matching shutdown flag was also retained. O2ActivityWarm has its
own descriptors for P0134/P0154/P0140/P0160.

The catalyst switch-ratio completion path qualified P0133 through
ObdFaultReport on the four CCD images. In the supplied completion state,
eight switches passed. Below eight, three retries preceded the first
qualified failure. Another failure after warm reset and startup delays
recorded P0133. A healthy result cleared the retained bit. The dedicated
idle response row separately reached ReportFault directly when the
simulated window exceeded its limit and the sensor was active and ready.
P0153 remained disabled on all five. 05032017AA also disabled P0133 in both
checked paths.

The audit ran 2,867 cold activity, 104 catalyst and 25 idle response cases,
with 38 modeled resets. Whole-cycle reachability and physical signal timing
remain open. [Local audit](https://github.com/DDex89/recore-sbec3/blob/dinofuel-128k/patches/spark/v2/stock_obd_o2_audit.py)

From the ReCore checkout, with the five archived ROMs in `roms/`, run
`python patches/spark/v2/stock_obd_o2_audit.py` and
`python patches/spark/v2/stock_obd_switch_thermal_audit.py`.

## Upstream warm oxygen activity (P0134)

All five images armed the first-channel heater test with qualifying coolant,
runtime and raw oxygen input. In the supplied startup cases the raw value
had to be strictly between $12 and $1E and the counter above $13. The
starting coolant threshold was $CD, with Count3s at least $2C. The heater
wait took $6E calls. With the raw value at or above $4D, the counter below
$2A advanced only at main-loop phases $00 and $80.

The failure completion called ReportFault directly and set current and
history on all five. The four CCD images also advanced the MIL count and
called FreezeFrameCapture. The $83 descriptor on 05032017AA left both of
those actions inactive. 05269833AH retained O2TestFlags.0 and count $2A on
completion. The next observed call with a recovered sensor input cleared
them. The other images clear the bit and count in the reporting call.

A healthy sample ended the heater test and left recorded current/history
intact. A modeled warm reset kept history and cleared current and the test
state. A cold reset cleared both fault bits. A new healthy test after either
reset left history in the state set by the reset. P0154 was disabled
throughout the five images.

The regression passed 3,400 monitor calls, 1,280 stock main-loop phase
ticks and ten modeled resets. Run
`python patches/spark/v2/stock_warm_o2_audit.py` from ReCore with the five
archived ROMs in `roms/`. [Local audit](https://github.com/DDex89/recore-sbec3/blob/dinofuel-128k/patches/spark/v2/stock_warm_o2_audit.py)

## Downstream warm oxygen activity (P0140 and P0160)

The four CCD ROMs armed P0140 at speed $50 or higher when raw oxygen was
strictly between $12 and $1E and the baseline count exceeded $13. The
baseline counts at MainLoopCounter $7F and $FF. After $6E heater calls,
raw at or above $4D advances the failure count at $00 and $80. The
next qualifying call after count $2A completes the failure.

The first failure set prior/result and captured priority $01 freeze
frame without current or history writes. The same-cycle repeat could
not re-arm. A modeled warm reset kept the prior bit and frame and
cleared the result. A second failure after that reset logged current
and history, incremented the MIL count and promoted the frame to $03.
A cold reset restarted qualification.

A healthy completion after the first-failure warm reset cleared the
prior/result bits and matching priority-$01 frame. After a logged
failure and warm reset, a healthy test kept the history and priority-$03
frame. The pre-heater healthy path also cleared pending state unless the
descriptor sensor-state byte Z+$071D had bit $10 or $20 set. AH kept
its channel bit and count until the next observed cleanup call.

P0160 is disabled in all five images, and 05032017AA also disables P0140.
The disabled descriptors rejected supplied active test states. The
regression ran 5,704 monitor calls, 2,048 stock counter steps and 12
modeled resets. Run `python patches/spark/v2/stock_warm_downstream_o2_audit.py`
from ReCore with the five exact ROMs in `roms/`. Real sensor waveforms and
drive-cycle timing remain open. [Exact-ROM downstream audit](https://github.com/DDex89/recore-sbec3/blob/dinofuel-128k/patches/spark/v2/stock_warm_downstream_o2_audit.py)

## Monitor-data EEPROM shadow

The stock MainLoop calls MonEnableTasks, EepromWriteService and
EepromWriteQueue in that order. MonEnableCheck clears MonEnableFlags2.7
when its enable gates fail. When the gates first admit it, it sets bit 7,
clears bit 6 and calls MonDataReset. MonDataReset copies the persistent
shadow values into the working bytes, masks MonData646 with $7F, clears
MonData648 and sets bit 4. Its MonData647 mask is $7F on 05293190AC and
$3F on 05269833AH, 05269833AI, 05269834AJ and 05032017AA.

MonDataStore checks the six entries in the order $CC, $CD, $CE, $CF, $D0,
$80 when bit 4 is set. It sets bit 5 on a detected difference and clears
it when there is none. It queues at most one byte, and it leaves a pending
request in place. For $CE it ignores bit 6 during comparison. On a
difference in any other bit, it merges bit 6 from the shadow into the
working byte and writes Scratch0 even with a request pending elsewhere.
The shadow addresses in RAM are Z+$064C–$0650 and Z+$0634.

In the successful serial sequences, the shadow stayed unchanged during
program setup, the busy poll and verified readback. EepromWriteQueue
advanced the cursor and reread the matching byte into the shadow after
the program request finished. Both modeled reset paths discarded the
pending request and repopulated the shadow from the supplied read data.

A verification mismatch or two supplied busy polls closed the failed
request and scheduled rereading of the same record. When that read
returned the original value, the discrepancy remained and MonDataStore
issued a new request. In consecutive failures without pending-fault
aging, the ninth attempt recorded P1696. Once current status was set,
later attempts skipped another ReportFault call.

The five ROMs passed 150 enable cases, 1,280 monitor-data resets, 6,400
store cases, 30 serial successes, 100 failed attempts and ten modeled
restarts. Actual EEPROM persistence and interruption timing remain open.

Run `python patches/spark/v2/stock_obd_eeprom_shadow_audit.py` from ReCore
with the five archived ROMs in `roms/`. [Exact-ROM EEPROM audit](https://github.com/DDex89/recore-sbec3/blob/dinofuel-128k/patches/spark/v2/stock_obd_eeprom_shadow_audit.py)

## Fault history and MIL state clearing (05293190AC)

ClearFaultHistoryAndCurrentState calls ClearMilRequestState, clears Z+$0122 through $014C and Z+$0500 through $0523 inclusive, and zeroes MilFaultCount. ClearMilRequestState ($24210) clears MilRequestFlags mask $03, DiagStatusFlags masks $08/$80 and ControlFlagsC39 mask $10.

## Scope

The periodic service was checked on 128 KiB ROMs. The 256 KiB cases cover the modeled reset and tested routine states. Electrical standby-RAM retention through power loss, actual key timing, elapsed scheduler cadence, and the preceding state for other monitor callers remain open.
