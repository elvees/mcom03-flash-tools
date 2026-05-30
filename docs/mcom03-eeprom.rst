.. Copyright 2026 RnD Center "ELVEES", JSC

===================================
Прошивка I2C EEPROM (mcom03-eeprom)
===================================

Утилита mcom03-eeprom предназначена для прошивки I2C ID EEPROM на carrier board SMARC-модулей.
Согласно SMARC HW Specification Version 2.1, I2C ID EEPROM должна быть совместима с Atmel 24C32
и использовать I2C-адрес 0x57.

Справочник:

.. command-output:: mcom03-eeprom --help

.. _mcom03-eeprom-write:

Запись
======

Запись строки в EEPROM::

  mcom03-eeprom write <string>

Для выбора шины I2C предусмотрена опция ``-b``. Команда с выбором шины::

  mcom03-eeprom -b 0 write <string>

Перечень значений для прошивки в ID EEPROM носителей SMARC приведён в таблице:

.. csv-table::
   :header-rows: 1
   :delim: ;

   Плата-носитель                   ; Имя платы для прошивки
   NGFW-CB r1.0                     ; ngfwcb-r1.0
   ELV-SMARC-CB r1.0                ; elvsmarccb-r1.0
   ELV-SMARC-CB r2.9.1              ; elvsmarccb-r2.9
   ELV-SMARC-CB r2.10               ; elvsmarccb-r2.10
   ELV-SMARC-CB r2.10.3             ; elvsmarccb-r2.10.3
   ELV-SMARC-CB r3.1.0              ; elvsmarccb-r3.1.0
   ELV-SMARC-CB r3.2.1              ; elvsmarccb-r3.2.1
   ELV-SMARC-CB r3.3.0              ; elvsmarccb-r3.3.0

Для носителей, не указанных в таблице, прошивка ID EEPROM не требуется.

Справочник:

.. command-output:: mcom03-eeprom write --help

.. _mcom03-eeprom-read:

Чтение
======

Для чтения содержимого EEPROM используется команда read утилиты mcom03-eeprom. Утилита читает
и выводит в виде строки указанное с ключом ``-d`` количество байтов, записанных в EEPROM::

  mcom03-eeprom -d 128 read

Справочник:

.. command-output:: mcom03-eeprom read --help

.. _mcom03-eeprom-flasher:

Загрузка flasher
================

Загрузить прошивальщик по UART в RISC0 CRAM и проверить, что прошивальщик ожидает команды по UART.
Команда используется для отладки::

  mcom03-eeprom flasher

Справочник:

.. command-output:: mcom03-eeprom flasher --help
