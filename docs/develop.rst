.. Copyright 2026 RnD Center "ELVEES", JSC

==========
Разработка
==========

Сборка документации:

.. code-block:: bash

   tox -e docs

Запуск локального сервера с автоматической пересборкой документации после обновления .rst-файлов
(откройте указанный URL в браузере):

.. code-block:: bash

   tox -e live-html
   ...
   The HTML pages are in docs/build/live-html.
   [sphinx-autobuild] Serving on http://<your-host>:8000
   [sphinx-autobuild] Waiting to detect changes...
