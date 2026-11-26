# Сверка инженерных обозначений SBEC3 / ReCore (26.11.2026)

Штатные 04887050 и 05293013AC: исходные bank0/bank1/00_equates и 11 штатных XDF совпадают по blob SHA. [Таблица адресов, зависимостей и источников](../en/stock-128k-symbol-review.md).

- EepromWrite947 → EepromAddrLow, младший байт адреса.
- EepromWrite949 → EepromDataLow, младший байт данных.
- EepromWrite94B → EepromReadbackTableOffset, индекс таблицы перечитывания, не счётчик повторов.
- PowerDownCount → StoredFlexEthanol (кандидат; дополнительные проверки на ноль ещё изучаются).
- F8032/F8034 → VssQualifiedEventCounter (кандидат).
- UnexpectedIrqStack4/6 — контекстные поля; нельзя глобально назвать PC/CCR.
- ResetCheckWord — рабочий ключ байт/дополнение или маркер режима сброса, не текущая контрольная сумма.

NvChecksum — сумма 258/306 байтов, не CRC. SriMileage обновляется при запросе записи; DistancePulses — приращение CCD, не одометр. QSPI RX $FFD18 — MMIO. Последние ROM-фикстуры не исполнены. Новые имена — описательные алиасы; штатные идентификаторы, адреса, параметры и XDF не изменены. [EEPROM](../en/eeprom-128k-audit.md), [архитектура](architecture.md), [SCI/PIT](sci-obd-128k.md), [топливо/CCD](fuel-pulse.md).
