# Routine notes for 04887050 (family A)

Read from the code of 04887050; also valid for 04887051 (same code). Routines not listed here carry
their name over from 05293190AC or 05293013AC (tools/port.py).

## 06EFC FuelCorrections
Main-loop fuel corrections with everything inline that later programs call as subroutines
(FlexFuelFactors, WarmupFuel, PartThrottleFuelCalc in 05293190AC): the flex fuel factors (with
Options0324 bit 0 every 8th pass from ethanol content and coolant, otherwise neutral; 05007038 keeps
only the neutral part, FlexFactorDefaults), the warm-up factors, EgrFuelCorrection while the EGR
solenoid is on, the returnless fuel pressure scale and the air temperature and MAP corrections.

## 11212 FlexSensorCheck
Flex fuel sensor: P0176 (circuit), P0178 and P0179 (signal low and high).

## 0DB5A GptRegisterCheck
GPT register check of HardwareCheck (HwCheckCode). There are three variants of it for different
hardware: HardwareCheck calls GptRegisterCheck with Options031D bits 5-6, GptRegisterCheck2 with
bits 3-4, GptRegisterCheck3 with bits 0-2 or 7.

## 158AE EgrFlowMonitor
EGR flow monitor (P0401): EgrMonitorTask runs it from the OBD monitor list, EgrMonTest and
EgrMonCalc measure the change while EGR is switched, EgrFlowReport reports.

## 16F00 FuelSysTooRich1Monitor
Fuel system monitors, bank 1 and 2, too rich and too lean (FuelSysTooRich1Monitor,
FuelSysTooRich2Monitor, FuelSysTooLean1Monitor, FuelSysTooLean2Monitor) from the adaptive values
and the short-term trims; FuelSysMonStep is their shared step.

## 18846 CatMonitorBank1
Catalyst monitor, bank 1 (MonStatusCatBank1); CatMonitorBank2 for bank 2. CatMonConditions
checks the entry conditions, CatMonEnableTimer and CatMonO2Activity prepare them.

## 18434 O2DownResponseMonitor
Downstream O2 sensor slow response (P0139).

## 1AF40 O2HighVoltMonitor
O2 sensors shorted high: P0132, P0152, P0138, P0158 from the descriptor list at $1AF00.

## 1A2B2 LdpCircuitCheck
Leak detection pump solenoid circuit (P1495).

## 1B0CA IdleRpmMonitor
Idle speed not reached (P1294); IdleMonitorEnable checks the conditions.

## 1B388 PnSwitchMonitor
Park/neutral switch (P1899), two checks (PnSwitchMonitor2).

## 1B482 CoolantWarmupMonitor
Closed-loop temperature not reached in time (P0125).

## 1A9FC FieldCircuitCheck
Generator field output circuit check (row without a P-code).

## 121B8 SriMileageStore
Queues service reminder mileage. P1697 records an unusable EEPROM ring.

## 1C92E CheckedSparkTrim
A spark trim byte kept with its complement ($62/$63): used only when the two agree, limited to
plus or minus 12.
