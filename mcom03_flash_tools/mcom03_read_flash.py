#!/usr/bin/env python3

# Copyright 2021 RnD Center "ELVEES", JSC

import argparse
import time

from mcom03_flash_tools import (
    UART,
    __version__,
    default_flasher,
    get_flash_type,
    read_image,
    upload_flasher,
)

__doc__ = """Tool to read QSPI0, QSPI1 memory connected to MCom-03 SoC (1892ВА018). Tool algorithm:

* upload baremetal binary flasher to CRAM memory via BootROM UART monitor
* command flasher to read data from QSPI
* receive data from flasher via UART

Intel HEX file baremetal SPI flasher to be executed on RISC0 is embedded with the tool.
"""


def main():
    class Formatter(argparse.ArgumentDefaultsHelpFormatter, argparse.RawDescriptionHelpFormatter):
        pass

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=Formatter)
    parser.add_argument("qspi", type=int, choices=[0, 1], help="number of QSPI controller to use")
    parser.add_argument("size", type=int, help="number of bytes to read from QSPI")
    parser.add_argument("image", help="path to save binary image")
    parser.add_argument(
        "-p",
        dest="port",
        default="/dev/ttyUSB0",
        help="serial port on host the device UART0 is connected to",
    )
    parser.add_argument(
        "--offset",
        type=lambda x: int(x, 0),
        default=0,
        help="read image from SPI starting from OFFSET bytes (e.g. 0x100 or 1024)",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="show UART traffic")
    parser.add_argument("--hide-progress-bar", action="store_true", help="do not show progress bar")
    parser.add_argument(
        "-f",
        "--flasher",
        default=default_flasher,
        help="path to Intel HEX baremetal application to be executed on RISC0",
    )
    parser.add_argument("--version", action="version", version=__version__)

    args = parser.parse_args()

    uart = UART(prompt="#", port=args.port, baudrate=115200, verbose=args.verbose)

    print("Uploading flasher...")
    upload_flasher(uart, args.flasher)

    response = uart.run(f"qspi {args.qspi}")
    if "Selected" not in response:
        raise Exception(f"Can not select QSPI controller: {response}")

    flash_type = get_flash_type(uart)
    if flash_type is not None:
        print(f"Found {flash_type.name}")
    else:
        print("Unknown SPI flash")

    print("Reading image...")
    time_start = time.monotonic()
    read_image(uart, args.offset, args.size, args.image, args.hide_progress_bar)
    duration = time.monotonic() - time_start
    print(f"Read done in {duration:0.3f} seconds ({args.size/duration:0.0f} B/s)")


if __name__ == "__main__":
    main()
