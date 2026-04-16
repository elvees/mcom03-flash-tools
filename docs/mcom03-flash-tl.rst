.. Copyright 2022-2024 RnD Center "ELVEES", JSC

=================================================================
Прошивка tl-образов для загрузки c помощью BootROM в память QSPI0
=================================================================

Состав tl-образов для загрузки c помощью BootROM:

* образ <BOARD>-bootrom.sbimg (загружается с помощью BootROM);
* образ sbl-tl-<DTB>.sbimg (загружается с помощью вторичного загрузчика sbl-tl);
* конфигурация загрузчика (sbl-tl-otp.bin).

Для записи образов используется команда flash-tl утилиты mcom03-flash::

  mcom03-flash --port /dev/ttyUSBx flash-tl qspi0 \
    <path_to>/*-bootrom.sbimg <path_to>/sbl-tl-*.sbimg <path_to>/sbl-tl-otp.bin

Для записи образов из определенной директории используется команда flash-tl-dir::

  mcom03-flash --port /dev/ttyUSBx flash-tl-dir qspi0 <tl_images_dir> \
    [ *-bootrom.sbimg sbl-tl-*.sbimg sbl-tl-otp.bin ]

.. note:: Имеет значение порядок перечисления образов после указанной директории.
   Если образы не указаны, используется список образов по умолчанию:

   *-bootrom.sbimg, sbl-tl-*.sbimg, sbl-tl-otp.bin

Для игнорирования записи любого образа можно использовать символ "_" вместо имени образа.
В примерах ниже будет записан только образ sbl-tl.sbimg::

  mcom03-flash flash-tl qspi0 _ <path_to>/sbl-tl-*.sbimg _
  mcom03-flash flash-tl-dir qspi0 <tl_images_dir> _ sbl-tl-*.sbimg _

Для записи образов из архива `tl-image` используется команда flash-tl-image::

  mcom03-flash --port /dev/ttyUSBx flash-tl-image qspi0 <path_to>/*.tl-image

В состав архива `*.tl-image` входит описание пакета `package.toml`, представляющее собой
набор профилей. Профилем по умолчанию является первый найденый профиль в `package.toml`.
Каждый профиль содержит набор действий. Действием по умолчанию является ``all``. При этом
выполняются все действия профиля. Весь перечень профилей и действий см. в `package.toml`.

Выбор профиля осуществляется передачей аргумента `--profile`::

  mcom03-flash --port /dev/ttyUSBx flash-tl-image --profile <profile> qspi0 \
    <path_to>/*.tl-image

Выбор сценария профиля осуществляется передачей аргумента `--action`::

  mcom03-flash --port /dev/ttyUSBx flash-tl-image --profile <profile> --action <action> qspi0 \
    <path_to>/*.tl-image

.. note:: При вызове команд flash-tl, flash-tl-dir или flash-tl-image, не допускается
   использование параметров `qspi1` и `--voltage18`. Такой запрос вернет ошибку.

.. important:: Для загрузки в режиме BootROM RISC0/QSPI0 необходимо установить переключатели
   в положение указанное ниже и нажать кнопку *Reset*:

   * на модуле NGFW-CB (*BOOT2,1,0*): ON, ON, OFF
   * на модуле MCom-03 BuB (*BOOT2,1,0*): OFF, OFF, ON
   * на модуле Trustphone (*BOOT2,1,0*): ON, ON, OFF

   Опционально, в режиме загрузки BootROM RISC0/UART можно перевести процессор в режим
   загрузки BootROM RISC0/QSPI0 вводом команды `boot 1`.
