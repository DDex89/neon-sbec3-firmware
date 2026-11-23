# Open questions and checks

What the code does not settle yet, and the checks run on the annotations. The lists below are
built from `annotations/` and the reference image 05293190AC; the item texts are the annotation
texts themselves.

## Checks

- `tools/xdfcheck.py`: all 11 XDFs, 0 errors. Warnings: unordered x axes in `Tab2D_04FB`
  (04887050/04887051, 05293013AC/05293014AC) and in `Tab2D_050D` and `Tab2D_2C31` (05293148AA). These
  are tables of those images read with an input that is not monotonic there; they are left as they are.
- `tools/edittest.py` (in CI): a source edit of a fuel cell, a constant and an option bit changes
  exactly those three bytes, they are the cells the XDF points at, and `tools/fixsum.py` restores the
  checksum through the single correction byte.
- Ported tables and constants (10 images): every carried item is found through the instruction that
  reads it, so its place follows the code, not the value. The values were still compared with the
  reference: differences in point counts, one-point stubs (a feature switched off) and changed
  numbers are calibration differences, not misplaced items. Pairs whose values look swapped
  (for example `LdpStrokeFilter`/`LdpStrokeTimeValid` in families A and B, `BattLowSetCount`/`BattLowClearCount`
  in families D, E and G) were checked in the code: the reading instructions match, so the calibrations
  really differ.

## Settled from the code in this pass

- `MonFlags09D`-`09F` are the two-trip pending bits, not "test not passed yet": `ObdFaultReport`
  sets the bit on a first failure, reports the fault on a second failure while it is set, and clears
  it (with the result bit) on a pass. `SwitchMonFlags`, `O2MonFlags` and `MonFlags65A` hold the
  result the monitor hands over (set = failed). `MonTaskE` clears the MIL request only with all
  pending bytes clear.
- `FaultStatusMap` has 44 rows (the last, P0300, was read as padding); the row counts that follow it
  are named `FaultStatusMapRows` (44, scanned by `SciDiagCommand`) and `FaultTwoTripRows` (22 rows
  from $75FA, searched by `ObdFaultReport`).
- `ObdMonitorOptionBits` ($20CBE): the option bit of each of the 16 OBD monitor rows; it sets bit 7
  of the monitor status byte, and `ObdMonitorMain` runs only rows with that bit set. This gives the
  meaning of `Options033E` bits 7, 6, 4, 3 (O2 response and catalyst monitors) and `Options033F` bit 3
  (fuel system monitors).
- `SwitchInputs2` bit 6 is the power steering pressure switch (the P0551 test and the idle adders);
  the constant formerly called `IacAcRequestAdder` is `IacPsSwitchAdder`. Bit 7 is the A/C request
  switch, bit 4 the speed control on/off switch.
- The curve formerly called `FlexSensorCurve` is the catalyst temperature sensor curve
  (`CatTempSensorCurve`): `CatTempMonitor` reports P1482/P1483 (sensor shorted low/high) and P1484
  (overheat) for it. Input $0A8E is shared with the flex-fuel sensor.
- `CcdTransmitList` holds bank-3 addresses of message builders, not RAM addresses; the 18 builders
  and their jump table `CcdTxJumpTable` ($30100) are named by CCD message ID and content
  (`CcdTxE4Map`, `CcdTx75AcSensor`, ...).
- The O2 heater constants belong to `O2HeaterMonitor`, which runs at key-off from `CheckPowerDown`.
- `KnockRpmSteps` are rpm break points compared with `EngineRpm`; PCI is SAE J1850 VPW.
- Four more unreached routines ($0C482, $0C9F8, $0CA5C and a skipped block at $1E418 inside the spark
  start ramp) and the bit-mask word tables at $0C9D8 and $367F4.
- Bit texts for the GPT, SCI, QSPI, SIM and ADC register bits the code uses, and bit 7 (and, where
  the fault map uses it, bit 4) of all 16 monitor status bytes.

## Still marked "probably"

Names and descriptions:

| Item | Where | Text |
|---|---|---|
| `FlexLearnLevelFactor` | table $08B4 | Flex-fuel learning: value FlexLearnLevelValue against FuelLevelScaled (probably fuel level) |
| `IacFieldDutyScale` | table $0A50 | Filtered duty of the CS2 input $106E.5 (probably the generator field) to row position of IacFieldDutyRpm |
| `AcSensorCurve` | table $7095 | A/C sensor (probably refrigerant pressure): ADC AcSensorRaw to AcSensor |
| `StarterCutHold` | constant $0606 | Starter control (StarterCut, Options0333 bit 2, probably the starter relay): hold count (StarterCutTimer) after rpm drops |
| `DiagDataList1` | data block $379FE | Lists of RAM addresses ($FFFF ends a group): data the SCI diagnostic service can send, probably |
| `DiagDataList2` | data block $37BFC | Lists of RAM addresses: monitor status and closed-loop data for the diagnostic service, probably |
| `DiagDataList3` | data block $37C5A | Lists of RAM addresses: leak detection pump and fuel system monitor data, probably |
| `DiagDataList4` | data block $37800 | Lists of RAM addresses: O2 heater status and EGR data, probably |
| `DiagDataList5` | data block $378AE | Lists of RAM addresses: fault bits and flex learning data, probably |
| `DiagDataList6` | data block $3795E | Lists of RAM addresses: misfire counters, probably |
| `DiagDataList7` | data block $37CAE | Lists of RAM addresses: segment times and misfire data, probably |
| `DiagDataList8` | data block $37D74 | Lists of RAM addresses: O2 monitor and other monitor data, probably |
| `KnockWindowSetup` | data block $254E | Knock chip set-up values sent by KnockChipConfig (KnockWindowInit, KnockWindowUpdate); 9 per row, probably one per window position |

Flag bits:

| Byte | Bit | Text |
|---|---|---|
| `AcFlags` | 4 | A/C idle bump pending, probably (IdleTargetControl); set at reset |
| `ControlFlags943` | 4 | ASD relay on, probably: set with bit 3 for the key-on prime (RunModeSwitch), cleared at stall; circuit checks of ASD-powered outputs read it |
| `ControlFlags943` | 3 | fuel pump relay on, probably (set and cleared with bit 4) |
| `ControlFlags944` | 4 | radiator fan relay, probably (FanControl, BusTempFlag, output test) |
| `ControlFlags944` | 3 | second fan relay, probably; driven only with A/C fitted |
| `DiagStatusFlags` | 7 | fault with a MIL request being processed, probably (ObdFaultProcess, cleared by MilRequest) |
| `DiagStatusFlags` | 6 | a fault aged out this pass, probably (ObdFaultAging) |
| `DriveFlags` | 7 | drive engagement handling in progress (GearStateUpdate), probably |
| `FuelPulseFlags` | 7 | injector timers loaded for the current event (FuelEventCalc), probably |
| `IacStepFlags` | 3 | stepper direction: opening, probably (IacStepperDrive) |
| `IacStepFlags` | 0 | rolling idle control active, probably (IacRollingControl); IdleStateUpdate treats it as off-idle |
| `IdleFlags` | 4 | idle air target set from the coolant branch of IdleTargetControl, probably; read by IacLearn |
| `IoCfg1FL` | 3 | tested by Isr_GPT_OC4 (ignition driver status, probably) |
| `IoCfg1FL` | 2 | tested by Isr_GPT_OC3 (ignition driver status, probably) |
| `IoCfg1FL` | 1 | tested by Isr_GPT_OC2 (ignition driver status, probably) |
| `IoInputs0` | 3 | key off, probably: the monitors skip while it is set and CheckPowerDown starts the power-down path |
| `IoInputs0` | 2 | ASD relay output present, probably (AsdRelayCheck, the reference-event code) |
| `IoStatus0B` | 5 | SCI line status, probably (SciPitService) |
| `LdpFlags` | 5 | leak test step result: small leak or not settled, probably |
| `LdpFlags3` | 3 | MonTaskC phase 2: ASD relay held off (ControlFlags943 bit 4), probably part of a key-off test |
| `Options032A` | 6 | engine variant used by the event, fuel accounting and misfire code (cylinder layout, probably) |
| `Options0331` | 4 | fuel level from the bus instead of the sender, probably |
| `SecurityFlags` | 5 | SKIM state count past $14: engine start blocked, probably (StarterCut, CrankFuel, EventCorrections read it) |
| `SkimFlags` | 2 | SKIM present on the bus, probably |
| `SkimFlags` | 0 | SKIM: key not valid / security request pending, probably (set by SkimState and CcdReceive, cleared on a good key) |
| `SparkFlags` | 7 | set at a reference event while IoInputs0 bit 2 (ASD output present, probably) is high (Isr_GPT_IC1) |
| `SpeedCtlState` | 4 | coast hold, probably (after SpeedCtlCoastHoldTime) |
| `SpeedCtlState` | 0 | set or resume engaged, probably |
| `SystemFlags945` | 6 | QSPI command RAM reloaded for an output driver status read, probably (QspiOutputStatus) |
| `SystemFlags945` | 0 | PCI frame timer running, probably (PciTimeoutRestart) |
| `ThrottleState` | 4 | closed position stepped to a new minimum, probably (ThrottleClosedLearn only) |
| `ThrottleState` | 3 | closed position taken from the calibration default, probably (ThrottleClosedLearn only) |
| `ThrottleState` | 1 | set by a diagnostic bus request (BusDataRequest), cleared by IdleRpmTarget or another request; probably a test hold of idle and spark |

## Data not decoded yet

Blocks of 24 bytes or more in the reference image that are neither code, a table, a constant nor
a decoded data block, with the routines that read them (by an address loaded into X or Y):

| Address | Bytes | Read by |
|---|---|---|
| $14000 | 352 | none found |
| $3688E | 338 | none found |
| $310D2 | 268 | `PciPitTick`, `PciReceive`, `PciTimeoutRestart` |
| $3896C | 242 | `CcdTransmit`, `PciPitTick` |
| $328A0 | 202 | `ObdRequest` |
| $24816 | 144 | `EventOptionStep` |
| $017E4 | 143 | none found |
| $3A2B6 | 128 | `FanRelayControl` |
| $358E8 | 124 | none found |
| $38000 | 104 | `Q`, `QspiOutputStatus` |
| $31000 | 90 | `PciRxProcess`, `QspiStop` |
| $22056 | 88 | `O2ActivityWarm` |
| $074E9 | 74 | `MisfireSegmentTime` |
| $352E8 | 72 | `DiagRunRamCode`, `SciRequestReceive` |
| $07000 | 71 | `IacStepperDrive`, `ObdRequest`, `PciBuildMessage`, `Reset`, `SegmentTimeCapture` |
| $30148 | 52 | `CcdTxEepromMsg`, `Irq2BusHandler`, `Irq4BusHandler` |
| $21BAE | 48 | `OutputDriverCheck` |
| $33776 | 48 | `MonTaskC` |
| $24000 | 44 | `OutputFaultReport` |
| $28000 | 42 | `O2ActivityCount` |
| $2C000 | 40 | none found |
| $0753F | 36 | `InjectorSequence` |
| $08A48 | 36 | `Irq2Dispatch` |
| $21F5E | 36 | `O2NoActivityCold` |
| $24040 | 36 | none found |
| $3A5F0 | 36 | `FanAcStage` |
| $3FFDC | 35 | none found |
| $02BA5 | 32 | none found |
| $08094 | 32 | none found |
| $0A000 | 30 | `InjectorFuelAccount`, `SegmentTimeCapture`, `StartInjectorPulse` |
| $10000 | 28 | `ChecksumCheck`, `FinishFuelPulse` |
| $32BA6 | 28 | none found |
| $02069 | 26 | `Irq2Dispatch` |
| $01799 | 25 | none found |
| $03257 | 25 | `CatMonConditions` |
| $160DE | 24 | `TrimPeakTrack` |
| $39E3C | 24 | `FanControl` |

## Bits without a text

About 750 bit positions in about 190 bytes are touched by bit instructions without a text in
`annotations/bits.json`. Many of these bytes are counters, timers, scratch bytes or word registers
tested bit by bit (`MainLoopCounter`, `Scratch*`, `EepromAddr`, `IoDriver6x`), so they need no
per-bit text; the rest are flag bytes whose bits are still described only by the code around them.
The unused calibration block at $017E4 (143 bytes, mostly $06) has no reader in any image.
