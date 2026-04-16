# Copyright 2026 RnD Center "ELVEES", JSC
import subprocess
from datetime import date

extensions = [
    "sphinx_rtd_theme",
    "sphinx_copybutton",
    "sphinxcontrib.programoutput",
]

project = "MCom-03 flash tools"
copyright = f'2021–{date.today().year} АО НПЦ "ЭЛВИС"'
language = "ru"
highlight_language = "bash"
version = subprocess.run(
    ["git", "describe", "--always"],
    text=True,
    check=True,
    capture_output=True,
).stdout.strip()

html_theme = "sphinx_rtd_theme"
html_show_sphinx = False
html_show_sourcelink = False
