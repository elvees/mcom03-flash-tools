.. Copyright 2026 RnD Center "ELVEES", JSC

===================================
Прошивка I2C EEPROM (mcom03-eeprom)
===================================

Согласно SMARC HW Specification Version 2.1, I2C ID EEPROM должна быть совместима с Atmel 24C32
и использовать I2C адрес 0x57.

Для записи данных в EEPROM используется команда write утилиты mcom03-eeprom::

  mcom03-eeprom write <string>

Для выбора шины I2C предусмотрена опция ``-b``. Команда с выбором шины::

  mcom03-eeprom -b 0 write <string>

Информация о других флагах (выбор адреса I2C, регистра и т. д.) доступна в справке утилиты::

  mcom03-eeprom --help

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

Чтение данных из I2C ID EEPROM
==============================

Для чтения содержимого EEPROM используется команда read утилиты mcom03-eeprom. Утилита читает
и выводит в виде строки указанное с ключом ``-d`` количество байтов, записанных в EEPROM::

  mcom03-eeprom -d 128 read
