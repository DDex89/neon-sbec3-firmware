# Сверка инженерных обозначений SBEC3 / ReCore (26.11.2026)

Штатные 04887050 и 05293013AC: исходные bank0/bank1/00_equates и 11 штатных XDF совпадают по blob SHA. [Таблица адресов, зависимостей и источников](../en/stock-128k-symbol-review.md).

- EepromWrite947 → EepromAddrLow, младший байт адреса.
- EepromWrite949 → EepromDataLow, младший байт данных.
- EepromWrite94B → EepromReadbackTableOffset, индекс таблицы перечитывания, не счётчик повторов.
- PowerDownCount → StoredFlexEthanol (прямые проверки на ноль ставят запрос на очистку EEPROM $00C).
- F8032/F8034 → VssQualifiedEventCounter.
- UnexpectedIrqStack4/6 — контекстные поля; нельзя глобально назвать PC/CCR.
- ResetCheckWord — рабочий ключ байт/дополнение или маркер режима сброса, не текущая контрольная сумма.

NvChecksum — сумма 258/306 байтов, не CRC. SriMileage обновляется при запросе записи; DistancePulses — приращение CCD, не одометр. QSPI RX $FFD18 — MMIO. Последние ROM-фикстуры не исполнены. Имена EEPROM, StoredFlexEthanol и оба обозначения VSS внедрены в ASM и аннотации A/B; прочие кандидаты остаются алиасами. Адреса, инструкции, параметры и XDF сохранены. [EEPROM](../en/eeprom-128k-audit.md), [архитектура](architecture.md), [SCI/PIT](sci-obd-128k.md), [топливо/CCD](fuel-pulse.md).

Миграция: [SBEC3 4e9cfff](https://github.com/DDex89/neon-sbec3-firmware/commit/4e9cfff96a3018d99b125c0ed9bff58f129408b8), [ReCore 9359bc6](https://github.com/DDex89/recore-sbec3/commit/9359bc64a21efbc3de45fe4bc227277b33c38f82). Проверка обратной подстановкой имён и разбор JSON пройдены; полная регенерация и сборка ROM не запускались. Для PowerDownCount подтверждены прямые потребители RunModeSwitch и (только B) MonTaskB: при ненулевом сохранённом байте и свободном EEPROM сервисе ставится запрос на обнуление $00C. Масштаб значения и косвенные обращения требуют дальнейшей проверки.

Миграция: [SBEC3 2d52496](https://github.com/DDex89/neon-sbec3-firmware/commit/2d5249633efdaaa3e843d75ab7d9ae53595d49a6), [ReCore ae9007d](https://github.com/DDex89/recore-sbec3/commit/ae9007d377e5468faa0415a003d5d7e8b92f3078). VssQualifiedEventCounterLow — младший байт $F8033/$F8035. Семь обращений к сохранённому этанолу и десять обращений к счётчику VSS заменены без изменения адресов и ширины операндов. Обратная подстановка восстанавливает исходный текст банков. Проверки ReCore адаптированы, но не исполнены. Уточнение EEPROM: BRSET #03 требует оба бита, поэтому слоты SRI 0/2/4/6 не используют раздельную ветку записи; BCLR #A0 очищает оба флага 7 и 5. См. [аудит](../en/eeprom-128k-audit.md).
