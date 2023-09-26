#!/usr/bin/env python3

# Copyright 2021 RnD Center "ELVEES", JSC

import argparse
import binascii
import glob
import math
import os
import sys
import time

from mcom03_flash_tools import (
    UART,
    __version__,
    clear_progress_bar,
    default_flasher,
    get_flash_type,
    print_progress_bar,
    read_image,
    upload_flasher,
)


def flash(uart: UART, offset: int, fname: str, hide_progress_bar: bool, page_size: int):
    response = uart.run(f"write {offset} {page_size}")
    if "Ready" not in response:
        raise Exception(f"Flash error: {response}")

    file_size = os.stat(fname).st_size
    page_offset = offset & (page_size - 1)
    complete = 0
    with open(fname, "rb") as f:
        while True:
            if not hide_progress_bar:
                print_progress_bar(complete / file_size * 100)

            if not complete and page_offset:
                data = f.read(page_size - page_offset)
            else:
                data = f.read(page_size)

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


def erase_sector(uart: UART, offset: int):
    response = uart.run(f"erase {offset}", timeout=10)
    if response is None:
        raise Exception("Erase error: flash is not ready for write/erase")

    if "Error" in response:
        raise Exception(f"Erase error: {response}")


def erase(uart: UART, offset: int, size: int, hide_progress_bar: bool, flash_type):
    if offset & (flash_type.sector - 1):
        print(
            f"Offset must be aligned with erase sector size ({flash_type.sector})", file=sys.stderr
        )
        sys.exit(1)

    first_sector = offset // flash_type.sector
    last_sector = int(math.ceil((offset + size) / flash_type.sector)) - 1
    sectors = last_sector - first_sector + 1
    rounded_str = (
        f", rounded to {sectors*flash_type.sector} bytes"
        if (sectors * flash_type.sector) != size
        else ""
    )
    print(f"Erasing {size} bytes{rounded_str} ({sectors} sectors, starting from {first_sector})...")
    for i in range(first_sector, last_sector + 1):
        if not hide_progress_bar:
            print_progress_bar((i - first_sector) / sectors * 100)
        erase_sector(uart, i * flash_type.sector)

    if not hide_progress_bar:
        clear_progress_bar()


def verify(uart: UART, offset: int, size: int, fname: str):
    with open(fname, "rb") as f:
        crc = binascii.crc_hqx(f.read(), 0xFFFF)

    response = uart.run(f"readcrc {offset} {size}", timeout=size / 10000 + 5)
    read_crc = int(response, 0)
    if read_crc != crc:
        raise Exception(f"Verification failed. Expected CRC {crc:#x}, but read {read_crc:#x}")


def cmd_flash(uart: UART, image: str, offset: int, hide_progress_bar: bool, flash_type):
    file_size = os.stat(image).st_size
    limit = offset + file_size
    if limit > flash_type.size:
        print(image + " doesn't fit to flash memory", file=sys.stderr)
        sys.exit(1)

    time_start = time.monotonic()
    erase(uart, offset, file_size, hide_progress_bar, flash_type)
    duration_erase = time.monotonic() - time_start
    print(f"Erase: {duration_erase:0.1f} s ({file_size/duration_erase/1024:0.0f} KiB/s)")

    print(f"Writing to flash {file_size/1024:.2f} KB...")
    flash(uart, offset, image, hide_progress_bar, flash_type.page)
    duration_write = time.monotonic() - time_start - duration_erase
    print(f"Write: {duration_write:0.1f} s ({file_size/duration_write/1024:0.0f} KiB/s)")

    print("Checking...")
    verify(uart, offset, file_size, image)
    duration_check = time.monotonic() - time_start - duration_erase - duration_write
    print(f"Check: {duration_check:0.1f} s ({file_size/duration_check/1024:0.0f} KiB/s)")
    duration_total = duration_erase + duration_write + duration_check
    print(f"Total: {duration_total:0.1f} s")


def cmd_read(uart: UART, fname: str, offset: int, size: int, hide_progress_bar: bool, flash_type):
    read_size = size if size is not None else flash_type.size - offset
    limit = offset + read_size
    if limit > flash_type.size:
        print("Out of flash memory read requested", file=sys.stderr)
        sys.exit(1)

    print(f"Reading {read_size/1024:.2f} KiB...")
    time_start = time.monotonic()
    read_image(uart, offset, read_size, fname, hide_progress_bar)
    duration = time.monotonic() - time_start
    print(f"Read done in {duration:0.3f} seconds ({read_size/duration/1024:0.0f} KiB/s)")


def cmd_erase(uart: UART, offset: int, size: int, hide_progress_bar: bool, flash_type):
    erase_size = size if size is not None else flash_type.size - offset
    limit = offset + erase_size
    if limit > flash_type.size:
        print("Out of flash memory erase requested", file=sys.stderr)
        sys.exit(1)

    time_start = time.monotonic()
    erase(uart, offset, erase_size, hide_progress_bar, flash_type)
    duration_erase = time.monotonic() - time_start
    print(f"Erase: {duration_erase:0.1f} s ({erase_size/duration_erase/1024:0.0f} KiB/s)")


def int_size(size):
    """
    >>> int_size('1K') == int_size('1k') == int_size('0x400') == 1024
    True
    >>> int_size('1M') == int_size('1m') == int_size('0x100000') == 1048576
    True
    >>> int_size('1kB') == int_size('1kb') == 1000
    True
    >>> int_size('1MB') == int_size('1mb') == 1_000_000
    True
    """
    units = {"K": 1024, "M": 1024 * 1024, "kB": 1000, "MB": 1000 * 1000}
    for unit, factor in units.items():
        if size.lower().endswith(unit.lower()):
            size = size[: len(size) - len(unit)]
            return int(size) * factor
    else:
        return int(size, 0)


__doc__ = """Tool to flash/read/erase QSPI0, QSPI1 memory connected to MCom-03 SoC (1892ВА018).
Tool algorithm:

* upload baremetal binary flasher to CRAM memory via BootROM UART monitor
* upload image to CRAM memory (or part of it) and command flasher to flash it
* repeat previous step multiple time till whole image is flashed to SPI

Intel HEX file baremetal SPI flasher to be executed on RISC0 is embedded with the tool.
Size options (including --offset) can be in hexidecimal (0x) and decimal format. Decimals may be
followed by the multiplicative  suffixes (similar to dd utility): kB=1000, K=1024, MB=1000*1000,
M=1024*1024, binary prefixes can be used, too: KiB=K, MiB=M, and so on.
"""


def main() -> int:
    class Formatter(argparse.ArgumentDefaultsHelpFormatter, argparse.RawDescriptionHelpFormatter):
        pass

    def to_size(value):
        units = ["B", "KiB", "MiB", "GiB"]
        unit_idx = 0
        while (value // 1024) * 1024 == value and unit_idx < len(units) - 1:
            unit_idx += 1
            value //= 1024

        return f"{value} {units[unit_idx]}"

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=Formatter)
    subparsers = parser.add_subparsers(dest="command")

    parser_flash = subparsers.add_parser("flash", help="Flash image to QSPI")
    parser_flash_tl = subparsers.add_parser("flash-tl", help="Flash tl images to QSPI")
    parser_flash_tl_dir = subparsers.add_parser(
        "flash-tl-dir", help="Flash tl images to QSPI relative to directory"
    )
    parser_read = subparsers.add_parser("read", help="Read data from QSPI")
    parser_erase = subparsers.add_parser("erase", help="Erase data on QSPI")
    for p in [parser_flash, parser_flash_tl, parser_flash_tl_dir, parser_read, parser_erase]:
        p.add_argument("qspi", choices=["qspi0", "qspi1"], help="QSPI controller to use")
        p.add_argument(
            "--voltage18",
            action="store_true",
            help="Setup QSPI1 to 1.8V. Not used for QSPI0",
        )
    help_msg = (
        "size to read/erase. Examples: 65536, 128K (131072 bytes), 4M (4194304 bytes), "
        + "128kB (128000 bytes), 4MB (4000000 bytes). If not defined then will be used all rest "
        + "of flash (after --offset)"
    )
    parser_flash.add_argument("image", help="path binary image to flash to SPI")
    parser_read.add_argument("fname", help="file name to save")
    for p in [parser_read, parser_erase]:
        p.add_argument("size", type=int_size, nargs="?", help=help_msg)
    for p in [parser_flash, parser_read, parser_erase]:
        p.add_argument(
            "--offset",
            type=int_size,
            default=0,
            help="Process data starting from OFFSET bytes (e.g. 0x100, 1024, 128K)",
        )
    parser_flash_tl.add_argument(
        "bootrom_sbimg",
        metavar="*-bootrom.sbimg",
        help="Path to BootROM SBIMG to flash to SPI",
    )
    parser_flash_tl.add_argument(
        "sbl_tl_sbimg",
        metavar="sbl-tl*.sbimg",
        help="Path to SBL-TL SBIMG to flash to SPI",
    )
    parser_flash_tl.add_argument(
        "sbl_tl_otp",
        metavar="sbl-tl-otp.bin",
        help="Path to sbl-tl-otp.bin",
    )
    parser_flash_tl_dir.add_argument(
        "tl_images_dir",
        type=str,
        help="Path where to search tl images",
    )
    parser_flash_tl_dir.add_argument(
        "tl_images",
        nargs="*",
        default=["*-bootrom.sbimg", "sbl-tl*.sbimg", "sbl-tl-otp.bin"],
        help="List of tl images (paths relative to images dir)."
        + "'_' placeholder can be used to skip image flashing",
    )
    parser.add_argument(
        "-p",
        "--port",
        default="/dev/ttyUSB0",
        help="serial port on host the device UART0 is connected to",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="show UART traffic")
    parser.add_argument(
        "--hide-progress-bar",
        action="store_true",
        help="do not show progress bar (progress bar is hidden in non-interactive shell)",
    )
    parser.add_argument("--flash-size", type=int_size, help="redefine flash total size")
    parser.add_argument("--flash-sector", type=int_size, help="redefine flash erase sector size")
    parser.add_argument("--flash-page", type=int_size, help="redefine flash page size")
    parser.add_argument(
        "-f",
        "--flasher",
        default=default_flasher,
        help="path to Intel HEX baremetal application to be executed on RISC0",
    )
    parser.add_argument("--version", action="version", version=__version__)

    args = parser.parse_args()

    if not sys.stdout.isatty():
        args.hide_progress_bar = True

    # TODO In Python 3.7 added 'required' for add_subparsers() method.
    # While we use Python 3.6 we need to check args.command manually.
    if args.command is None:
        print("Command is not specified")
        return 1
    elif args.command == "flash-tl":
        if args.qspi != "qspi0":
            print("Unsupported QSPI controller")
            return 1

    if args.qspi == "qspi0" and args.voltage18:
        print("Unsupported QSPI0 setings: --voltage18 is forbidden")
        return 1

    uart = UART(prompt="#", port=args.port, baudrate=115200, verbose=args.verbose)

    print("Uploading flasher to on-chip RAM...")
    upload_flasher(uart, args.flasher)

    response = uart.run(f"qspi {args.qspi[-1:]} {int(args.voltage18)}")
    if response is None or "Selected" not in response:
        raise Exception(f"Failed to select QSPI controller: {response}")

    flash_type = get_flash_type(uart, args.flash_size, args.flash_sector, args.flash_page)
    if flash_type.name is not None:
        print(f"Found {flash_type.name} memory on {args.qspi.upper()}")
        print(
            f"Flash size: {to_size(flash_type.size)}, erase sector: {to_size(flash_type.sector)}, "
            + f"page: {to_size(flash_type.page)}"
        )
    else:
        ids = ", ".join([hex(x) for x in flash_type.id_bytes])
        print(f"Unknown SPI flash on {args.qspi.upper()} (ID: {ids})")
        print(
            "Use --flash-size, --flash-sector and --flash-page options to specify flash parameters"
        )
        return 1

    def flash_images(images: dict, image_dir: str = ""):
        for offset, image in images.items():
            if image == "_":
                continue
            paths = glob.glob(os.path.join(image_dir, image))
            if len(paths) == 0:
                print(f"Wrong path to {image}", file=sys.stderr)
                sys.exit(1)
            print(f"Flash {paths[0]} starting from {hex(offset)} bytes")
            cmd_flash(
                uart,
                paths[0],
                offset,
                args.hide_progress_bar,
                flash_type,
            )
        return

    if args.command == "flash":
        cmd_flash(uart, args.image, args.offset, args.hide_progress_bar, flash_type)
    elif args.command == "read":
        cmd_read(uart, args.fname, args.offset, args.size, args.hide_progress_bar, flash_type)
    elif args.command == "erase":
        cmd_erase(uart, args.offset, args.size, args.hide_progress_bar, flash_type)
    elif args.command == "flash-tl":
        flash_images(
            {0: args.bootrom_sbimg, 0x200000: args.sbl_tl_sbimg, 0xA00000: args.sbl_tl_otp}
        )
    elif args.command == "flash-tl-dir":
        if os.path.isdir(args.tl_images_dir) is False:
            print(f"Path {args.tl_images_dir} is not valid directory")
            return 1
        if len(args.tl_images) != 3:
            print("Wrong number of images is provided")
            return 1
        flash_images(
            {0: args.tl_images[0], 0x200000: args.tl_images[1], 0xA00000: args.tl_images[2]},
            args.tl_images_dir,
        )
    else:
        print("Unknown command")
        return 1

    if args.command == "flash-tl" or args.command == "flash-tl-dir":
        # The tl software uses 2 pages to store its non-volatile settings at 0xC10000 offset.
        # They have to be cleaned after flashing new tl images.
        cmd_erase(uart, 0xC10000, int_size("128K"), args.hide_progress_bar, flash_type)

    return 0


if __name__ == "__main__":
    sys.exit(main())
