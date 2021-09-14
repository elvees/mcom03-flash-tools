============================================
Инструменты прошивки модулей на базе MCom-03
============================================

.. Инструкция использует URL-адреса GitHub. Для разработки внутри компании НПЦ ЭЛВИС необходимо
   использовать URL ssh://gerrit.elvees.com:29418/mcom03/flash-tools.

.. Для просмотра инструкции в терминале можно использовать команду "rst2man README.rst | man -l -"

Поддерживаемые модули и памяти:

.. csv-table::
   :header-rows: 1
   :delim: ;

   Модуль             ; Память        ; Примечание
   MCom-03 BuB r1.3.0 ; QSPI0, QSPI1  ; —
   ELV-MC03-SMARC r1.0; QSPI0         ; В составе NGFW-CB r1.0. QSPI1 не установлен на SMARC-модуле.

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

Прошивка QSPI0
==============

#. Установить переключатели *BOOT2,1,0* в режим загрузки с UART:

   * на модуле NGFW-CB: ON, OFF, OFF,
   * на модуле MCom-03 BuB: OFF, ON, ON.

#. Подключить кабель USB для UART-консоли модуля.

#. Подать питание на модуль (если модуль уже включен, то нажать кнопку *Reset*).

   Для модуля NGFW-CB необходимо дополнительно нажать кнопку *Power*.

#. Если на ПК открыто приложение использующее UART (``minicom``), то приложение необходимо закрыть.

#. Запустить::

     mcom03-flash 0 <file-to-write> --port /dev/ttyUSBx

   ``/dev/ttyUSBx`` — устройство терминала UART0 на ПК.

#. После завершения прошивки будет выведена фраза ``Checking succeeded`` и указана длительность и
   скорость прошивки. Скорость прошивки ограничена скоростью UART 11520 Кб/с и составляет ~8 КБ/с.

   .. note:: Если при запуске на модуле NGFW-CB будет выдано исключение из-за
      несовпадения CRC, возможно, после включения питания не была нажата кнопка *Power*.

.. important: Для загрузки с QSPI0 установить переключатели *BOOT2,1,0* в положения:

   * на модуле NGFW-CB: ON, ON, ON,
   * на модуле MCom-03 BuB: OFF, OFF, OFF.

Чтение QSPI0
============

Для чтения образа используется mcom03-read-flash::

  mcom03-read-flash 0 <size-in-bytes> <output-file> --port /dev/ttyUSBx
