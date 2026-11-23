# Routine notes for 05007038 (family C)

Read from the code of 05007038; also valid for 05293148AA (same code). Routines not listed here
carry their name over from 05293190AC (tools/port.py) and have no note of their own.

## 07764 HardwareCheck
Called once per main-loop pass. Compares the SIM, clock, RAM, QSM and chip-select registers with
their reset values and writes them back where they differ; each repair leaves a code in
HwCheckCode. Calls GptRegisterCheck for the timer module. Same job as HardwareCheck in 05293190AC.

## 0FD7C GptRegisterCheck
GPT part of HardwareCheck: GPTMCR, ICR, DDRGP, OC1M, TCTL1/2, TMSK1/2, PACTL, PWMC; a register
found changed is rewritten and its code ($0028, $0029, ...) stored in HwCheckCode.

## 0DA94 DevPortInit
Development port, reset part. Only with Options0331 bit 4, which is clear in 05007038 and
05293148AA: the port is off in both. Chip select 1 is set up at reset for a
16 KB block at $20000 (CSBAR1 $0203), probably the dual-port RAM of a calibration tool; the
256 KB families have flash there. Clears the channel
masks and the work words, and writes 1 to the eight mailbox words at $24000-$2400E. With the same
bit FinishFuelPulse, StartInjectorPulse and SparkEventCalc also write per-injector and per-event
values to the device ($2262A-$22652 and up), each selected by a bit of FinishFuel911.

## 0DAFC DevPortService
Development port, main loop. Only with Options0331 bit 4. Writes three calibration words
($03F4-$03F8) to the device and compares a device word with $03FA. On a mismatch (no device) all
channel masks are cleared; otherwise the write and read channel masks and three parameter words
are taken from the device. The mailbox at $24000 is a busy flag: written 0, read back until 0.

## 0DBDC DevPortChannel1
One of eight copies (channels 1-8, called from the main loop, the PIT and the reference interrupt,
so at different rates). Only with Options0331 bit 4 and the channel's bit in DevPortWriteMask or
DevPortReadMask. Write part: a list of RAM addresses at $20400 (bytes, then words, each list ended
by 0) gets the values from $20600: the device overrides RAM. Read part: the RAM at the addresses
listed at $20500 is copied to $20700: the device logs RAM. Channel n uses the block at
$20000 + n * $400. This looks like a calibration tool interface (live RAM override and logging); the
car does not use it.

## 089FA FlexFactorDefaults
Sets the flex fuel factors to their neutral values (factor $0100, coolant factors $40).

## 08BA0 AdaptiveFuelBank1
Bank 1 fuel correction: purge cell correction (unless closed loop off, purge off, cold flex start,
coolant fault or WOT), plus the long-term adaptive value and the short-term trim. AdaptiveFuelBank2
is the same for bank 2.

## 07F22 FuelCutControl
Deceleration fuel cut, rev limiter (RevLimit, RevLimitAlt in gear), speed limiter
(Options032E bit 5) and the fuel-cut delay counter; the flags go to RevLimitFlags.

## 0831A WotModeDelay
WOT mode with a delay: above a vehicle speed the WOT flag in FuelModeFlags is set only after
WotDelayTimer has run up (one step per 383 ms); below it at once.

## 0D954 PurgeDutyOutput
From IRQ2: purge solenoid duty to the output driver register ($086C bits 13 and 14 for 0 % and
100 %), duty limited to 2-98 %.

## 0A554 RefPeriodUpdate
From the reference interrupt: reference period, RefPeriodLow and the crank period work words.

## 10F2A FanWarmupState
Fan warm-up state (FanFlags bit 2) from coolant, battery temperature, vehicle speed and
FanWarmupCount. FanWarmupTimer counts FanWarmupCount up every 3.1 s.

## 1167E BusRpmHold
Holds the rpm sent on the bus while the A/C idle bus timer runs (IacAcFlags bit 1,
BusRpmHoldTimer).

## 11838 CcdReceive
CCD bus receive in this program: security exchange (messages $AA and $16), body and transmission
messages; P1695 and P1698 for missing messages.

## 11B28 SecurityTimeoutStore
On a security timeout stores the security count (SecurityStatus) in the EEPROM (address 8).

## 11B90 SecurityExchange
Security message exchange over the CCD bus (SecurityFlags bits 2, 3, 6, 7; SecurityMsgTimer).

## 11FCA CcdA4StatusBytes
Builds the two status bytes of CCD message $A4 (switch bits through CollectBits, speed control,
throttle, MIL). CcdTxA4 sends it now, CcdTxA4Queue queues it from IC4/OC5.

## 13A60 ThrottleInputs
Throttle sensor range (P0122, P0123) and rationality against MAP (P0121), then the closed-position
learning (ThrottleClosed, ThrottleRelearnCounter).

## 14C06 MapSensorMonitor
MAP sensor: key-on reading against baro, range and rationality (P0106, P0107, P0108, P1297).

## 1335C BatteryTempSensorCheck
Battery temperature sensor range (P1492, P1493); otherwise Thermistor3Curve gives BatteryTemp,
rate-limited to one step per pass.

## 14D6A ThermostatMonitor
Coolant warm-up against time and vehicle speed; reports the thermostat row (no P-code in this
program) once per drive cycle.

## 1501E O2HighVoltMonitor
Upstream O2 sensors shorted high (P0132, P0152).

## 15294 O2LowVoltMonitor
After a cold soak (coolant close to battery temperature) the O2 voltages must leave the low range:
P0131, P0151, P0137, P0157 from the descriptor list at $15244.

## 15524 PurgeCircuitCheck
Purge solenoid circuit (P0443).

## 15AEC SensorSupplyCheck
5 V sensor supply low (P1496).

## 15B2C PspSwitchMonitor
Power steering pressure switch (P0551).

## 15B86 TransMilRequest
MIL request from the transmission controller (P0700).

## 15DAE FuelSenderMonitor
Fuel level sender range and rationality (rows without a P-code).

## 19DA6 MilRequestControl
MIL request (ControlFlagsC39 bit 4) from the fault memory, the transmission request and the
diagnostic commands; diagnostic command $0A runs MilFlashCodes.

## 19CB6 MilFlashCodes
Flashes the stored fault codes on the MIL, digit by digit (MilFlashState).

## 19E9C MilLampOutput
Puts the MIL request on the output (ControlFlags944 bit 0) and sends CCD message $A4 when it
changes.

## 1B506 ActuatorTestMain
Actuator tests through a jump table; only below a reference period limit (engine stopped).
ActuatorTestCancel ends the test at the first reference pulse.

## 1FC8A ObdReadiness
Readiness from the monitor descriptor list at $1FC1E (12 bytes per monitor): sets
ReadinessIncomplete for each supported monitor not yet complete.

## 1EC9C QspiStartupConfig
QSPI transmit RAM and SPCR2 set-up at reset, then QspiCommandInit when the QSPI is idle. Sits where
05293190AC calls EepromReadStartup.

## 08872 EmptyHook08872
RTS only. Called from TipInFuelControl and IacFuelControl where 05293190AC calls FlexFactorApply.
The other EmptyHook routines are also RTS only: empty slots of the main loop (08DBC, 102DA,
10896, 10898, 15564, 1DF30) and of the PIT (0AE60, with Options032C bit 4).
