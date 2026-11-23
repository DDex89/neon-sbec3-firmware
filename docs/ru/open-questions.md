# Открытые вопросы и проверки

Что код пока не объясняет, и проверки аннотаций. Списки ниже собраны из `annotations/` и
эталонного образа 05293190AC; тексты пунктов взяты из самих аннотаций, поэтому они на английском.

## Проверки

- `tools/xdfcheck.py`: все 11 XDF, 0 ошибок. Предупреждения: неупорядоченные оси x в `Tab2D_04FB`
  (04887050/04887051, 05293013AC/05293014AC) и в `Tab2D_050D` и `Tab2D_2C31` (05293148AA). Это таблицы
  этих образов, которые читаются по немонотонному входу; оставлены как есть.
- `tools/edittest.py` (в CI): правка в исходнике ячейки топливной таблицы, константы и бита
  настроек меняет ровно эти три байта, XDF указывает именно на них, а `tools/fixsum.py`
  восстанавливает сумму одним байтом коррекции.
- Перенесённые таблицы и константы (10 образов): каждый элемент найден через читающую его
  инструкцию, так что его место следует из кода, а не из значения. Значения всё равно сравнены
  с эталоном: другое число точек, заглушки из одной точки (функция выключена) и другие числа — это
  различия калибровок, а не сдвинутые элементы. Пары, где значения выглядят переставленными
  (например `LdpStrokeFilter`/`LdpStrokeTimeValid` в семействах A и B, `BattLowSetCount`/`BattLowClearCount`
  в семействах D, E и G), проверены по коду: читающие инструкции совпадают, калибровки действительно разные.

## Что выяснено по коду в этом проходе

- `MonFlags09D`-`09F` — биты ожидания второй поездки (two-trip), а не «тест ещё не пройден»:
  `ObdFaultReport` ставит бит при первом отказе, при втором отказе с поставленным битом заносит
  неисправность, а при прохождении теста снимает его вместе с битом результата. `SwitchMonFlags`,
  `O2MonFlags` и `MonFlags65A` — результат, который передаёт монитор (1 = отказ). `MonTaskE` снимает
  запрос MIL только при нулевых байтах ожидания.
- В `FaultStatusMap` 44 строки (последняя, P0300, читалась как заполнитель); счётчики строк после
  неё названы `FaultStatusMapRows` (44, их просматривает `SciDiagCommand`) и `FaultTwoTripRows` (22
  строки с $75FA, их ищет `ObdFaultReport`).
- `ObdMonitorOptionBits` ($20CBE): бит настроек для каждой из 16 строк мониторов OBD; он ставит бит 7
  байта статуса монитора, а `ObdMonitorMain` выполняет только строки с этим битом. Отсюда смысл
  битов 7, 6, 4, 3 `Options033E` (мониторы отклика O2 и катализатора) и бита 3 `Options033F`
  (мониторы топливной системы).
- Бит 6 `SwitchInputs2` — датчик давления гидроусилителя руля (тест P0551 и добавки холостого
  хода); константа `IacAcRequestAdder` переименована в `IacPsSwitchAdder`. Бит 7 — запрос
  кондиционера, бит 4 — выключатель круиз-контроля.
- Кривая `FlexSensorCurve` оказалась кривой датчика температуры катализатора (`CatTempSensorCurve`):
  `CatTempMonitor` выдаёт по ней P1482/P1483 (замыкание датчика на массу/питание) и P1484
  (перегрев). Вход $0A8E общий с датчиком состава топлива.
- `CcdTransmitList` содержит адреса формирователей сообщений в банке 3, а не адреса RAM; 18
  формирователей и их таблица переходов `CcdTxJumpTable` ($30100) названы по ID и содержимому
  сообщения CCD (`CcdTxE4Map`, `CcdTx75AcSensor`, ...).
- Константы подогрева O2 относятся к `O2HeaterMonitor`, который работает после выключения
  зажигания из `CheckPowerDown`.
- `KnockRpmSteps` — точки оборотов, сравниваемые с `EngineRpm`; PCI — это SAE J1850 VPW.
- Ещё четыре недостижимые процедуры ($0C482, $0C9F8, $0CA5C и пропускаемый блок $1E418 внутри
  `SparkEventCalc`) и таблицы слов-масок битов по $0C9D8 и $367F4. Обходимый блок и
  `UnusedCylSparkOverride` ($1E65C) — отключённая поцилиндровая подмена угла по команде с шины (см.
  architecture.md, недостижимый код).
- 31 байт по $048A — это три вещи: `StartPulseOffset` (6 слов со знаком) и `StartPulseFactor` (6
  слов-множителей) работающего поцилиндрового стартового импульса в `StartInjectorPulse`, затем
  неиспользуемые `CylSparkOverrideBase` и `CylSparkOverrideValues`.
- Массив детонации в RAM $0092 — десять обученных значений по ячейкам обороты/давление
  (`KnockLearnCells`, индекс `KnockLearnCellIndex`), а не поцилиндровые откаты; константы и процедура
  затухания, которые с ним работают, переименованы в `KnockLearnCell*`.
- `GetSparkAdvance` стоит на месте `UnusedCylSparkOverride`: интерфейс тот же, а вызывающий код
  по-прежнему передаёт номер цилиндра в A.
- Тексты битов регистров GPT, SCI, QSPI, SIM и ADC, которые использует код, и бит 7 (а где его
  использует карта неисправностей — и бит 4) всех 16 байтов статуса мониторов.

## Что всё ещё помечено «probably»

Имена и описания:

| Элемент | Где | Текст |
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

Биты флагов:

| Байт | Бит | Текст |
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

## Ещё не разобранные данные

Блоки от 24 байт в эталонном образе, которые не являются ни кодом, ни таблицей, ни константой, ни
разобранным блоком данных, с процедурами, которые их читают (по адресу в X или Y):

| Адрес | Байт | Читает |
|---|---|---|
| $3688E | 338 | не найдено |
| $14048 | 280 | не найдено |
| $310D2 | 268 | `PciPitTick`, `PciReceive`, `PciTimeoutRestart` |
| $3896C | 242 | `CcdTransmit`, `PciPitTick` |
| $328A0 | 202 | `ObdRequest` |
| $24816 | 144 | `EventOptionStep` |
| $017E4 | 143 | не найдено |
| $3A2B6 | 128 | `FanRelayControl` |
| $358E8 | 124 | не найдено |
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
| $2C000 | 40 | не найдено |
| $0753F | 36 | `InjectorSequence` |
| $08A48 | 36 | `Irq2Dispatch` |
| $21F5E | 36 | `O2NoActivityCold` |
| $24040 | 36 | не найдено |
| $3A5F0 | 36 | `FanAcStage` |
| $3FFDC | 35 | не найдено |
| $02BA5 | 32 | не найдено |
| $08094 | 32 | не найдено |
| $0A000 | 30 | `InjectorFuelAccount`, `SegmentTimeCapture`, `StartInjectorPulse` |
| $10000 | 28 | `ChecksumCheck`, `FinishFuelPulse` |
| $32BA6 | 28 | не найдено |
| $02069 | 26 | `Irq2Dispatch` |
| $01799 | 25 | не найдено |
| $03257 | 25 | `CatMonConditions` |
| $160DE | 24 | `TrimPeakTrack` |
| $39E3C | 24 | `FanControl` |

## Биты без текста

Около 750 позиций битов примерно в 190 байтах затрагиваются битовыми инструкциями, но не имеют
текста в `annotations/bits.json`. Многие из этих байтов — счётчики, таймеры, временные байты или
словные регистры, которые проверяются по битам (`MainLoopCounter`, `Scratch*`, `EepromAddr`,
`IoDriver6x`), им текст по битам не нужен; остальные — байты флагов, биты которых пока описаны
только окружающим кодом. Неиспользуемый блок калибровки по $017E4 (143 байта, в основном $06) не
читается ни в одном образе.
