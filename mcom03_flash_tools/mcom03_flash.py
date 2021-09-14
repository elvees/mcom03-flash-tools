#!/usr/bin/env python3

# Copyright 2021 RnD Center "ELVEES", JSC

import argparse
import binascii
import math
import os
import time

from mcom03_flash_tools import (
    UART,
    __version__,
    clear_progress_bar,
    default_flasher,
    get_flash_type,
    print_progress_bar,
    upload_flasher,
)


def flash(uart: UART, offset: int, fname: str, hide_progress_bar: bool):
    response = uart.run(f"write {offset}")
    if "Ready" not in response:
        raise Exception(f"Flash error: {response}")

    file_size = os.stat(fname).st_size
    complete = 0
    with open(fname, "rb") as f:
        while True:
            if not hide_progress_bar:
                print_progress_bar(complete / file_size * 100)
            data = f.read(256)
            size = len(data)
            complete += size
            crc = binascii.crc_hqx(data, 0xFFFF)
            for _ in range(3):
                uart.tty.write(size.to_bytes(2, "little"))
                uart.tty.write(crc.to_bytes(2, "little"))
                if not data:
                    if not hide_progress_bar:
                        clear_progress_bar()
                    uart.wait_for_string(uart.prompt)
                    return

                uart.tty.write(data)
                success, response = uart.wait_for_string(["R", "C"])
                if not success:
                    Exception(f"Wrong response while flashing: {response}")

                if response.strip() == "R":  # Ready for next block
                    break
            else:
                raise Exception("CRC errors threshold exceeded 3 times")


def erase(uart: UART, offset: int):
    response = uart.run(f"erase {offset}", timeout=10)
    if "Error" in response:
        raise Exception(f"Erase error: {response}")


def verify(uart: UART, offset: int, size: int, fname: str):
    with open(fname, "rb") as f:
        crc = binascii.crc_hqx(f.read(), 0xFFFF)

    response = uart.run(f"readcrc {offset} {size}", timeout=size / 10000 + 5)
    read_crc = int(response, 0)
    if read_crc != crc:
        raise Exception(f"Verification failed. Expected CRC {crc:#x}, but read {read_crc:#x}")


__doc__ = """Tool to flash QSPI0, QSPI1 memory connected to MCom-03 SoC (1892ВА018). Tool algorithm:

* upload baremetal binary flasher to CRAM memory via BootROM UART monitor
* upload image to CRAM memory (or part of it) and command flasher to flash it
* repeat previous step multiple time till whole image is flashed to SPI

Intel HEX file baremetal SPI flasher to be executed on RISC0 is embedded with the tool.
"""


def main():
    class Formatter(argparse.ArgumentDefaultsHelpFormatter, argparse.RawDescriptionHelpFormatter):
        pass

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=Formatter)
    parser.add_argument("qspi", type=int, choices=[0, 1], help="number of QSPI controller to use")
    parser.add_argument("image", help="path binary image to flash to SPI")
    parser.add_argument(
        "-p",
        "--port",
        default="/dev/ttyUSB0",
        help="serial port on host the device UART0 is connected to",
    )
    parser.add_argument(
        "--offset",
        type=lambda x: int(x, 0),
        default=0,
        help="flash image to SPI starting from OFFSET bytes (e.g. 0x100 or 1024)",
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

    file_size = os.stat(args.image).st_size
    uart = UART(prompt="#", port=args.port, baudrate=115200, verbose=args.verbose)

    print("Uploading flasher to on-chip RAM...")
    upload_flasher(uart, args.flasher)

    response = uart.run(f"qspi {args.qspi}")
    if "Selected" not in response:
        raise Exception(f"Failed to select QSPI controller: {response}")

    flash_type = get_flash_type(uart)
    if flash_type is not None:
        print(f"Found {flash_type.name} memory on QSPI{args.qspi}")
    else:
        print(f"Unknown SPI flash on QSPI{args.qspi}")

    print("Erasing...")
    sectors = int(math.ceil(file_size / 65536))
    time_start = time.monotonic()
    for i in range(sectors):
        if not args.hide_progress_bar:
            print_progress_bar(i / sectors * 100)
        erase(uart, i * 65536)

    duration_erase = time.monotonic() - time_start
    if not args.hide_progress_bar:
        clear_progress_bar()
    print(f"Writing to flash {file_size/1024:.2f} KB...")
    flash(uart, args.offset, args.image, args.hide_progress_bar)
    duration_write = time.monotonic() - time_start - duration_erase

    print("Checking...")
    verify(uart, args.offset, file_size, args.image)
    duration_check = time.monotonic() - time_start - duration_erase - duration_write
    print("Checking succeeded")
    print(f"Erase. Duration: {duration_erase:0.1f} seconds ({file_size/duration_erase:0.0f} B/s)")
    print(f"Write. Duration: {duration_write:0.1f} seconds ({file_size/duration_write:0.0f} B/s)")
    print(f"Check. Duration: {duration_check:0.1f} seconds ({file_size/duration_check:0.0f} B/s)")
    duration_total = duration_erase + duration_write + duration_check
    print(f"Total. Duration: {duration_total:0.1f} seconds ({file_size/duration_total:0.0f} B/s)")


if __name__ == "__main__":
    main()
