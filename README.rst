.. Copyright 2021-2024 RnD Center "ELVEES", JSC

============================================
Инструменты прошивки модулей на базе MCom-03
============================================

.. Инструкция использует URL-адреса GitHub. Для разработки внутри компании НПЦ ЭЛВИС необходимо
   использовать URL ssh://gerrit.elvees.com:29418/mcom03/flash-tools.

.. Для просмотра инструкции в терминале можно использовать команду "rst2man README.rst | man -l -"

Поддерживаемые модули и памяти:

* MCom-03 BuB r1.3.0, r1.5.0 (QSPI0, QSPI1);
* NGFW-CB r1.0 с установленным ELV-MC03-SMARC r1.0, r1.1 (QSPI0);
* Congatec сonga-SEVAL с установленным ELV-MC03-SMARC r1.0, r1.1 (QSPI0);
* ROCK Pi N10 с установленным ELV-MC03-SMARC r1.0, r1.1 (QSPI0);
* ELV-SMARC-CB r1.0 с установленным ELV-MC03-SMARC r1.0, r1.1 (QSPI0);
* ELV-SMARC-CB r2.9.1 с установленным ELV-MC03-SMARC r2.2 (QSPI0);
* ELV-SMARC-CB r2.10.3 с установленным ELV-MC03-SMARC r1.0, r1.1 (QSPI0);
* ELV-MC03-CB r1.1.0 с установленным ELV-MC03 r1.2, r2.2 (QSPI0).

Прошивка выполняется по интерфейсу UART0: MCom-03 BootROM в режиме загрузки по UART принимает
образ spi-flasher, spi-flasher запускается на RISC0, повышает частоты, принимает образы для прошивки
по UART, прошивает соответствующую память QSPI.

Установка
=========

Проверялось на Python 3.6. Требуются свежие версии pip, setuptools::

  export PATH=~/.local/bin:$PATH
  python3 -m pip install --upgrade --user pip
  hash pip3
  pip3 install setuptools --upgrade

Пакет является стандартным пакетом Python. Установка выполняется любым из методов::

  git clone https://github.com/elvees/mcom03-flash-tools.git
  cd mcom03-flash-tools
  pip3 install . --user

  # or if you want to hack the code
  pip3 install -e . --user

  # or just
  pip3 install git+https://github.com/elvees/mcom03-flash-tools.git --user

.. note:: Пакет использует пакет setuptools scm, для работы пакета при установке требуется
   директория ``.git``. Установка из zip-файла не содержащего ``.git`` (например, zip-файл,
   загруженный через веб-интерфейс GitHub *Download ZIP*) не поддерживается.

Напряжение падов QSPI
=====================

Контроллер QSPI0 поддерживает только режим 1.8 В. Контроллер QSPI1 может настраивать пады
в режим 1.8 В или 3.3 В.

Для конфигурации падов QSPI1 в режим 1.8 В используется параметр ``--voltage18``. По умолчанию для
QSPI1 утилита настраивает режим 3.3 В. Для QSPI0 данный параметр игнорируется и не влияет на работу
падов.

.. important:: При использовании м/сх памяти, подключенных к QSPI1, с напряжением I/O 3.3 В
   указание параметра ``--voltage18`` может привести к повреждению падов MCom-03.

.. important:: Параметр ``--voltage18`` следует указывать для всех команд обращения к памяти
   (``flash``, ``read``, ``erase``).

Прошивка QSPI0
==============

#. Установить переключатели в режим загрузки с UART:

   * на модуле NGFW-CB (*BOOT2,1,0*): ON, OFF, OFF
   * на модуле MCom-03 BuB (*BOOT2,1,0*): OFF, ON, ON
   * на модуле conga-SEVAL (*BOOT_SEL2,1,0*): ON, OFF, OFF
   * на модуле ROCK Pi N10 снять джампер с пинов GPIO 25,26 (*GND,ADC_IN1*)
   * на модуле ELV-SMARC-CB r1.0 (*BOOT SOURCE: 1, 2, 3*): ON, OFF, OFF
   * на модуле ELV-SMARC-CB r2.9, r2.10.3 (*BTSL2,1,0*): ON, OFF, OFF
   * на модуле ELV-MC03-CB (*BOOT2,1,0*): OFF, ON, ON

#. Подключить кабель USB для UART-консоли модуля.

#. Подать питание на модуль (если модуль уже включен, то нажать кнопку *Reset*).

   Для модуля NGFW-CB необходимо дополнительно нажать кнопку *Power*.

#. Если на ПК открыто приложение использующее UART (``minicom``), то приложение необходимо закрыть.

#. Запустить::

     mcom03-flash --port /dev/ttyUSBx flash qspi0 <file-to-write>

   ``/dev/ttyUSBx`` — устройство терминала UART0 на ПК.

   .. note: Для указания начального смещения (аргумент --offset) и для любых указаний размеров
      можно использовать единицы измерения как в утилите ``dd``: 1K = 1024, 1M = 1024K, 1KB = 1000,
      1MB = 1000KB и т.д.

#. После завершения прошивки будет выведена фраза ``Checking succeeded`` и указана длительность и
   скорость прошивки. Скорость прошивки ограничена скоростью UART 115200 б/с и составляет ~8 КБ/с.

   .. note:: Если при запуске на модуле NGFW-CB будет выдано исключение из-за
      несовпадения CRC, возможно, после включения питания не была нажата кнопка *Power*.

.. important:: Для загрузки с QSPI0 установить переключатели в положения:

   * на модуле NGFW-CB (*BOOT2,1,0*): ON, ON, ON
   * на модуле MCom-03 BuB (*BOOT2,1,0*): OFF, OFF, OFF
   * на модуле conga-SEVAL (*BOOT_SEL2,1,0*): ON, ON, ON
   * на модуле ROCK Pi N10 установить джампер на пины GPIO 25,26 (*GND,ADC_IN1*)
   * на модуле ELV-SMARC-CB r1.0 (*BOOT SOURCE: 1, 2, 3*): ON, ON, ON
   * на модуле ELV-SMARC-CB r2.9, r2.10.3 (*BTSL2,1,0*): ON, ON, ON
   * на модуле ELV-MC03-CB (*BOOT2,1,0*): OFF, OFF, OFF

Чтение QSPI0
============

Для чтения образа используется команда read утилиты mcom03-flash::

  mcom03-flash --port /dev/ttyUSBx read qspi0 <output-file> [size-in-bytes]

Если размер не указан, то будет прочитано содержимое всей памяти.
Пример использования::

  mcom03-flash --port /dev/ttyUSB0 read qspi0 new-file.img 256K

Очистка QSPI0
=============

Для очистки памяти используется команда erase утилиты mcom03-flash::

  mcom03-flash --port /dev/ttyUSBx erase qspi0 [size-in-bytes]

Если размер не указан, то будет очищена вся память.
Пример использования::

  mcom03-flash --port /dev/ttyUSBx erase qspi0 1M

.. important: Размер очищаемой памяти будет округлён вверх и будет кратен размеру блоку стирания.
