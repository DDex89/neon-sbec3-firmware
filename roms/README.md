# ROM images / Образы ПЗУ

ROM images are not part of this repository. Put the flash images here, named by the part number
and revision from their header block (not by the file name they came with). 128 KB controllers
give a 131,072-byte image; if a 128 KB chip was read as 256 KB, keep only the first half.

Образы ПЗУ в репозиторий не входят. Положите сюда образы flash с именами по номеру детали и ревизии
из блока заголовка (а не по имени, с которым файл пришёл). Блоки на 128 КБ дают образ на 131 072 байта;
если микросхему на 128 КБ прочитали как 256 КБ, оставьте только первую половину.

| File / Файл | Size / Размер | SHA-256 |
|---|---|---|
| `04887050.bin` | 128 KB | `4d564f3b3a49b4e3eba838562c7001fe5fa10b82756cf4e57aae0019ed3138ef` |
| `04887051.bin` | 128 KB | `5bcb410b08030ba24973e72e352bfb7e1b456b28546cecba8d1de40c32aba8ec` |
| `05007038.bin` | 128 KB | `82581758ea9cfbe3f45e01e27b425a1569caa99b6170c1f88fd6cdab9694f651` |
| `05032017AA.bin` | 256 KB | `0b6be604c5220be79236bfa92bbccf1e87c4726a52a09708e733f39fa3e980a4` |
| `05269833AH.bin` | 256 KB | `91cb7e264c3cc657153ccab9c8137ef2ae12d96ce5dae670ed29a4a3ed6af9da` |
| `05269833AI.bin` | 256 KB | `37101ef3beed81f736004091597991b0876fd4085f91479fbaec2b69561d66fd` |
| `05269834AJ.bin` | 256 KB | `936d4a4fb642824c13a29b67d426ec562623260f4b1c072c557891f4d4e991d3` |
| `05293013AC.bin` | 128 KB | `e2cd98527a32d0618d0c3f0bc0b637440d3a10e3447f93a51ae2fff49e539f23` |
| `05293014AC.bin` | 128 KB | `504d2b0cd16be82dc8590188b55885e74e5107e45736d8d2d40fead4c373b487` |
| `05293148AA.bin` | 128 KB | `1c39aaef1f4702d2c4aeb1c35612083495a25a243705c62e99df11ba4ecb3951` |
| `05293190AC.bin` | 256 KB | `f7d154bebd58973b2e57dfca394391320c7d60e7af79af1cd1ad83e829d505ea` |

Sources / Откуда: 05293190AC and 05293013AC were published by Dino Yancey on the 2GNT forum
(https://nawdu.de/files/bins/); the other images come from the project owner's collection. A dump
read from your own controller with SBECBootLoader works as well.

05293190AC и 05293013AC опубликовал Дино Янси на форуме 2GNT (https://nawdu.de/files/bins/);
остальные образы — из коллекции владельца проекта. Подойдёт и дамп, считанный с собственного блока
через SBECBootLoader.
