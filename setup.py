# Copyright 2021 RnD Center "ELVEES", JSC

import setuptools

install_requires = [
    "pyserial>=3.0,<4.0",
    "tomli==2.0.1",
]

setuptools.setup(
    name="mcom03-flash-tools",
    version="1.0",
    description="Tool to flash QSPI on MCom-03",
    python_requires=">=3.6,<4.0",
    packages=setuptools.find_packages(),
    package_dir={"mcom03_flash_tools": "mcom03_flash_tools"},
    package_data={"mcom03_flash_tools": ["spi-flasher-mips-ram.hex"]},
    use_scm_version=True,
    setup_requires=["setuptools_scm"],
    install_requires=install_requires,
    entry_points={
        "console_scripts": [
            "mcom03-flash = mcom03_flash_tools.mcom03_flash:main",
        ],
    },
)
