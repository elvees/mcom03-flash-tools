#!/usr/bin/env python3

# Copyright 2024 RnD Center "ELVEES", JSC

import argparse
import sys

from mcom03_flash_tools import UART, __version__, upload_flasher


def cmd_write(uart: UART, data: str):
    uart.tty.write((data + "\0").encode())

    success, response = uart.wait_for_string("Done\n")
    if not success:
        raise Exception(f"Wrong response while writing: {response}")

    print(f"Data has been written to EEPROM\nData size: {len(data) + 1} bytes")


__doc__ = """Tool to write/read data to EEPROM on carrier board."""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)

    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("read", help="Read EEPROM")
    subparsers.add_parser("flasher", help="Write flasher to QSPI")

    parser_write = subparsers.add_parser("write", help="Write new data to EEPROM")
    parser_write.add_argument("name", default="", help="String to write in EEPROM")

    parser.add_argument(
        "-a",
        "--addr",
        default=0x57,
        type=lambda x: int(x, 0),
        help="Address of device on I2C bus",
    )
    parser.add_argument(
        "-b",
        "--bus",
        default=0,
        type=int,
        help="i2c bus number",
    )
    parser.add_argument(
        "-d",
        "--datasize",
        default=0,
        type=int,
        help="data size to read or write",
    )
    parser.add_argument(
        "-f",
        "--flasher",
        help=(
            "path to Intel HEX baremetal application to be executed on RISC0"
            "(use HEX distributed with the tool if not specified)"
        ),
    )
    parser.add_argument(
        "-l",
        "--length",
        default=2,
        type=int,
        choices=range(1, 5),
        help="i2c address length in bytes",
    )
    parser.add_argument(
        "-m",
        "--mode",
        default="text",
        choices=["text", "bin"],
        help="i2c read mode ('text' or 'bin')",
    )
    parser.add_argument(
        "-p",
        "--port",
        default="/dev/ttyUSB0",
        help="Serial port on host the device UART0 is connected to",
    )
    parser.add_argument(
        "-r",
        "--regaddr",
        default=0,
        type=int,
        help="i2c register address",
    )
    parser.add_argument(
        "-s",
        "--speed",
        default=0,
        type=int,
        choices=range(0, 2),
        help="i2c speed (0 - slow, 1 - fast)",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Show UART traffic")
    parser.add_argument("--version", action="version", version=__version__)

    args = parser.parse_args()

    if args.command is None:
        print("Command is not specified")
        return 1

    if args.command == "write" and not args.name.isascii():
        print("String must contain ASCII symbols only")
        return 1

    uart = UART(prompt="#", port=args.port, baudrate=115200, verbose=args.verbose)
    upload_flasher(uart, "spi-flasher-mips-ram.hex", "QSPI Flasher", args.flasher)

    if args.command == "flasher":
        return 0

    uart.run(f"i2c_dev {args.bus} {args.speed}")

    if args.command == "read":
        response = uart.run(f"i2c_read {args.addr} {args.regaddr} {args.length} {args.datasize}")
        print(response)

    if args.command == "write":
        if args.datasize == 0:
            args.datasize = len(args.name) + 1

        response = uart.run(f"i2c_write {args.addr} {args.regaddr} {args.length} {args.datasize}")
        print(response)
        cmd_write(uart, args.name)

    return 0


if __name__ == "__main__":
    sys.exit(main())
