.. Copyright 2026 RnD Center "ELVEES", JSC

=========
Установка
=========

.. Инструкция использует URL-адреса GitHub. Для разработки внутри компании
   использовать внутренний сервер.

Проверялось на Python 3.12. Требуется свежая версия pip. Актуальные поддерживаемые версии
Python см. в tox.ini:

.. code-block:: bash

   export PATH=~/.local/bin:$PATH
   python3 -m pip install --upgrade --user pip
   hash pip3

Пакет является стандартным пакетом Python. Установка выполняется `стандартными методами`__:

__ https://packaging.python.org/en/latest/tutorials/installing-packages/

.. code-block:: bash

   git clone https://github.com/elvees/mcom03-flash-tools.git
   cd mcom03-flash-tools
   pip3 install . --user

   # or just
   pip3 install git+https://github.com/elvees/mcom03-flash-tools.git --user

Проверить вызов утилиты:

.. command-output:: mcom03-flash --version

С использованием uvx:

.. code-block:: bash

   uvx --from git+https://github.com/elvees/mcom03-flash-tools --python 3.12 mcom03-flash --version

.. note:: Пакет использует setuptools scm, при установке требуется директория
   ``.git``. Установка из zip-файла, не содержащего ``.git`` (например, zip-файл,
   загруженный через веб-интерфейс GitHub *Download ZIP*), не поддерживается.
