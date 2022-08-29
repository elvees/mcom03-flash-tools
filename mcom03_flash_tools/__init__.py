# Copyright 2021 RnD Center "ELVEES", JSC

import sys
import time
from collections import namedtuple

import pkg_resources
import serial

FlashType = namedtuple("FlashType", "name size sector page id_bytes")

KiB = 1024
MiB = 1024 * KiB
FLASH_LIST = [
    FlashType("M25P32", 4 * MiB, 64 * KiB, 256, [0x20, 0x20, 0x16, 0x10]),
    FlashType("S25FL128S", 16 * MiB, 64 * KiB, 256, [0x1, 0x20, 0x18, 0x4D, 0x1, 0x80]),
    FlashType("S25FL256S", 32 * MiB, 64 * KiB, 256, [0x1, 0x2, 0x19, 0x4D, 0x1, 0x80]),
    FlashType("W25Q32", 4 * MiB, 64 * KiB, 256, [0xEF, 0x40, 0x16]),
    FlashType("W25Q128JV-IN/IQ/JQ", 16 * MiB, 64 * KiB, 256, [0xEF, 0x40, 0x18]),
    FlashType("W25Q128JV-IM/JM", 16 * MiB, 64 * KiB, 256, [0xEF, 0x70, 0x18]),
    FlashType("W25Q128FW", 16 * MiB, 64 * KiB, 256, [0xEF, 0x60, 0x18]),
]
default_flasher = pkg_resources.resource_filename("mcom03_flash_tools", "spi-flasher-mips-ram.hex")

try:
    __version__ = pkg_resources.get_distribution(__name__).version
except pkg_resources.DistributionNotFound:
    # package is not installed
    __version__ = ""


class UART(object):
    """Class for work with UART console."""

    def __init__(self, prompt, port, newline=b"\r", verbose=False, baudrate=115200, timeout=0.5):
        """Parameters
        ----------
        prompt : str
            expected command line prompt
        port : str
            serial port for use (example: /dev/ttyUSB0)
        newline : str
            new line delimeter
        verbose : bool
            if True then will show UART transactions
        baudrate : int
            UART speed in bit/sec
        timeout : float
            timeout for read() operations and affects the accuracy of the command execution time
        """
        self.prompt = prompt
        self.newline = newline
        self.verbose = verbose
        self.tty = serial.Serial(port=port, baudrate=baudrate, timeout=timeout)

    def wait_for_string(self, expected, timeout=1):
        """Method to wait for pattern `expected` to be received from UART.

        Parameters
        ----------
        expected : list or str
            string or list of strings for wait.
        timeout : float
            time in seconds. If function does not receive string `expected` in this time then will
            return with False. If None then will wait infinite for expected string.

        Returns
        -------
        bool
            True if pattern `expected` was received
        str
            received data
        """

        def endswith(resp, expected):
            if not isinstance(expected, (list, tuple)):
                expected = (expected,)

            return any(map(resp.endswith, expected))

        if timeout is not None:
            time_end = time.monotonic() + timeout
        else:
            time_end = sys.float_info.max
        resp = ""
        while (time.monotonic() <= time_end) and not endswith(resp, expected):
            ch = self.tty.read(1)
            if not ch:
                continue
            resp += ch.decode("utf-8")

        result = resp.replace("\r", "")
        if self.verbose and result:
            print(result, end="")
        if not endswith(resp, expected):
            return False, result

        return True, result

    def run(self, cmd, timeout=5, strip_echo=True):
        """Run command and wait for prompt.

        Parameters
        ----------
        cmd : str
            command
        timeout : float
            argument for wait_for_string()
        strip_echo : bool
            if true then will remove echo from response string

        Returns
        -------
        str
            response string
        """
        self.tty.reset_input_buffer()
        self.tty.write(cmd.encode("utf-8") + self.newline)
        success, resp = self.wait_for_string(self.prompt, timeout)
        if not success:
            return None

        # Return only output of command (without cmd + "\n" and command prompt)
        return resp[len(cmd) + 1 : -len(self.prompt)] if strip_echo else resp


def print_progress_bar(percentage: float, width: int = 20):
    """Update progress bar"""
    PROGRESS_SYMBOLS = [""] + [chr(0x258F - x) for x in range(7)]
    count = min(width * percentage / 100, width)
    count_full = int(count)
    bar = chr(0x2588) * count_full
    rest_char_id = int((count - count_full) * 8)
    bar += PROGRESS_SYMBOLS[rest_char_id]
    bar += " " * (width - len(bar))
    print(f"\r[{bar}] {percentage:5.1f}%", end="")
    sys.stdout.flush()


def clear_progress_bar(width: int = 20):
    """Clear progress bar after use print_percentage()"""
    print("\r" + " " * (width + 10) + "\r", end="")


def read_image(uart: UART, offset: int, size: int, fname: str, hide_progress_bar: bool):
    uart.run(f"read {offset} {size} bin")
    complete = 0
    with open(fname, "wb") as f:
        while complete < size:
            if not hide_progress_bar:
                print_progress_bar(complete / size * 100)
            block_size = size - complete if size - complete < 256 else 256
            data = uart.tty.read(block_size)
            complete += len(data)
            f.write(data)

    uart.wait_for_string("#")
    if not hide_progress_bar:
        clear_progress_bar()


def upload_flasher(uart: UART, flasher: str):
    """Communicate with BootROM to upload"""
    QSPI_FLASHER = "QSPI Flasher"

    # recognize if flasher is already executing. Upload only if BootROM terminal
    # is found
    response = uart.run("")
    if response is None:
        raise RuntimeError("BootROM UART terminal prompt not found")
    if QSPI_FLASHER in response:
        print("Flasher is already executing")
        return

    print("Sending flasher...")
    with open(flasher, "rb") as f:
        # BootROM doesn't have command, just send ihex file
        uart.tty.write(f.read())

    # BUG: After uploading ihex file BootROM sends prompt twice
    uart.wait_for_string(uart.prompt, timeout=1)
    uart.wait_for_string(uart.prompt, timeout=1)

    response = uart.run("run")  # BootROM command to execute flasher
    if response is None or QSPI_FLASHER not in response:
        raise Exception(f"{QSPI_FLASHER} does not respond, response {response}")

    time.sleep(0.1)  # Delay for flasher startup


def _get_flash_type(uart: UART):
    response = uart.run("custom 0x9f 6")  # READ ID command
    ids = [int(x, 16) for x in response.strip().split(" ")]
    for flash in FLASH_LIST:
        if flash.id_bytes == ids[: len(flash.id_bytes)]:
            return flash
    else:
        return FlashType(None, None, None, None, ids)


def get_flash_type(uart: UART, flash_size: int, flash_sector: int, flash_page: int):
    """Read device ID bytes and detect SPI flash type. Replace flash parameters with custom
    values (if value is not None). Return FlashType with name is None for unknown SPI flash.
    """
    flash = _get_flash_type(uart)

    # Create custom flash type if any of parameters is not None
    if [x for x in [flash_size, flash_sector, flash_page] if x is not None]:
        # Create list with parameters.
        params = zip([flash_size, flash_sector, flash_page], [flash.size, flash.sector, flash.page])
        params = [auto if manual is None else manual for manual, auto in params]  # type: ignore

        # None in params is mean that current flash is unknown and not all parameters are specified
        if None not in params:  # type: ignore
            name = "custom" if flash.name is None else f"custom (based on {flash.name})"
            flash = FlashType._make([name] + params + [flash.id_bytes])  # type: ignore

    return flash
