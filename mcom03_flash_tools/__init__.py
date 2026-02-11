# Copyright 2021 RnD Center "ELVEES", JSC

import abc
import importlib.metadata
import importlib.resources
import sys
import time
from collections import namedtuple
from typing import Optional

import serial

FlashType = namedtuple("FlashType", "name size sector page id_bytes")

KiB = 1024
MiB = 1024 * KiB
FLASH_LIST = [
    FlashType("FM25W128", 16 * MiB, 64 * KiB, 256, [0xA1, 0x28, 0x18]),
    FlashType("M25P32", 4 * MiB, 64 * KiB, 256, [0x20, 0x20, 0x16, 0x10]),
    FlashType("S25FL128S", 16 * MiB, 64 * KiB, 256, [0x1, 0x20, 0x18, 0x4D, 0x1, 0x80]),
    FlashType(
        "S25FL128S(sector:256K)", 16 * MiB, 256 * KiB, 512, [0x1, 0x20, 0x18, 0x4D, 0x0, 0x80]
    ),
    FlashType("S25FL256S", 32 * MiB, 64 * KiB, 256, [0x1, 0x2, 0x19, 0x4D, 0x1, 0x80]),
    FlashType("W25Q16JW-IM", 2 * MiB, 64 * KiB, 256, [0xEF, 0x80, 0x15]),
    FlashType("W25Q16JW-IQ/JQ", 2 * MiB, 64 * KiB, 256, [0xEF, 0x60, 0x15]),
    FlashType("W25Q32", 4 * MiB, 64 * KiB, 256, [0xEF, 0x40, 0x16]),
    FlashType("W25Q128JV-IN/IQ/JQ", 16 * MiB, 64 * KiB, 256, [0xEF, 0x40, 0x18]),
    FlashType("W25Q128JV-IM/JM", 16 * MiB, 64 * KiB, 256, [0xEF, 0x70, 0x18]),
    FlashType("W25Q128FW", 16 * MiB, 64 * KiB, 256, [0xEF, 0x60, 0x18]),
    FlashType("W25Q256JW", 32 * MiB, 64 * KiB, 256, [0xEF, 0x60, 0x19]),
    FlashType("W25Q256JW-IM", 32 * MiB, 64 * KiB, 256, [0xEF, 0x80, 0x19]),
]


try:
    __version__ = importlib.metadata.version(__package__)
except importlib.metadata.PackageNotFoundError:
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
            new line delimiter
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
            resp += ch.decode("utf-8", errors="ignore")

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


def upload_flasher(
    uart: UART, default_flasher_name: str, flasher_msg: str, flasher: Optional[str] = None
):
    """Communicate with BootROM to upload"""

    print("Uploading flasher to on-chip RAM...")

    # recognize if flasher is already executing. Upload only if BootROM terminal is found
    response = uart.run("")
    if response is None:
        raise RuntimeError("BootROM UART terminal prompt not found")
    if flasher_msg in response:
        print("Flasher is already executing")
        return

    if flasher is None:
        ref = importlib.resources.files(__package__) / default_flasher_name
        with ref.open("rb") as file_:
            # BootROM doesn't have command, just send ihex file
            uart.tty.write(file_.read())
    else:
        with open(flasher, "rb") as file_:
            uart.tty.write(file_.read())

    # BUG: After uploading ihex file BootROM sends prompt twice
    uart.wait_for_string(uart.prompt, timeout=1)
    uart.wait_for_string(uart.prompt, timeout=1)

    response = uart.run("run")  # BootROM command to execute flasher
    if response is None or flasher_msg not in response:
        raise Exception(f"{flasher_msg} does not respond, response {response}")

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


def _check_int_type(*args):
    for arg in args:
        if not isinstance(arg, int):
            raise TypeError("Only int is supported")


def _swap_bit_range(range_):
    if range_[1] > range_[0]:
        range_ = [range_[1], range_[0]]
    return range_


def BIT(n):
    return 1 << n


def GENMASK(bit_range):
    _check_int_type(bit_range[0], bit_range[1])
    bit_range = _swap_bit_range(bit_range)
    return (BIT(bit_range[0] - bit_range[1] + 1) - 1) << bit_range[1]


def FIELD_GET(mask, reg):
    """
    >>> FIELD_GET(0b111, 0b10111)
    7
    >>> FIELD_GET(0b100, 0b10111)
    1
    >>> FIELD_GET(0b10100, 0b10111)
    5
    """

    def __bf_shf(mask):
        if mask == 0:
            return 0
        s = bin(mask)
        return len(s) - len(s.rstrip("0"))

    _check_int_type(mask, reg)
    return (mask & reg) >> __bf_shf(mask)


# TODO: Support OTP protection
class Protector(abc.ABC):
    # Commands
    WRR = 0x01
    WRDI = 0x04
    RDSR1 = 0x05
    WREN = 0x06

    def __init__(self, uart: UART):
        self._uart = uart

    @staticmethod
    def _hex(d):
        s = hex(d)[2:]
        return f"0x{s}" if len(s) % 2 == 0 else f"0x0{s}"

    def _wait_complete(self, timeout):
        time_ = time.monotonic()
        while time.monotonic() - time_ < timeout:
            # Wait until WIP = 0 - device in standby mode
            if FIELD_GET(BIT(0), self._custom(self.RDSR1, 1)) == 0:
                return True
        return False

    def _custom(self, tx_data, rx_data_len):
        tx_data = self._hex(tx_data)
        cmd = f"custom {tx_data} {rx_data_len}"
        ret = self._uart.run(cmd)
        return int(ret, base=16) if rx_data_len else 0

    @abc.abstractmethod
    def unprotect(self):
        """Unprotect entire QSPI flash"""
        pass

    @abc.abstractmethod
    def protect(self):
        """Protect entire QSPI flash"""
        pass

    @property
    @abc.abstractmethod
    def is_protected(self) -> bool:
        pass


class ProtectorS25FL128S(Protector):
    """
    Bit protection in a nutshell (there are not all features, e.g., we don't use OTP - separate 1024
    byte one-time programmable section - section 10.1):

    * The chip has a block protection function. Data is split into 8 sectors; we can protect some
      part of the data or the entire memory. Bits BP[2:0] in Status Register 1 display which sectors
      are protected.
    * Configuration Register 1, bit BPNV (Bit Protection Non-Volatile), defines whether or not the
      BP[2:0] are volatile or non-volatile. The bit is one-time programmable, default value is 0 -
      When BPNV is set to a 0 the BP[2:0] bits are non-volatile.
    * The chip has WP# pin. When WP# is LOW and SRWD (Status Register Write Disable in the Status
      Register 1) is set to 1, the Status and Configuration register is protected from alteration.
      This mode is called as hardware protection.

    The class implements approaches to protect/unprotect memory over BP[2:0] bits.
    * If BPNV=0 then BP state will be retained after memory reset or power cycle, because BP[2:0]
      are non-volatile.
    * If BPNV=1 then BP state will be reset to 0b111 value (all sectors are protected) after memory
      reset or power cycle. Until these actions BP will be preserve its state, in other words,
      you can unprotect memory until reset or power cycle for example.

    The class will be useless for cases when WP# is LOW, in other words, hardware protection isn't
    supported.
    """

    BP_MASK = GENMASK([4, 2])
    WEL = BIT(1)

    POLL_TIMEOUT = 1

    def protect(self):
        rdsr = self._custom(self.RDSR1, 1)
        self._custom(self.WREN, 0)
        self._custom((self.WRR << 8) | self.BP_MASK | (rdsr & ~self.WEL), 0)

        if not self._wait_complete(self.POLL_TIMEOUT):
            raise RuntimeError("Write still in progress")
        rdsr = self._custom(self.RDSR1, 1)
        if rdsr & self.BP_MASK != self.BP_MASK:
            raise RuntimeError(f"Failed to protect flash: SR1 = {hex(rdsr)}")

    def unprotect(self):
        self._custom(self.WREN, 0)
        self._custom((self.WRR << 8), 0)

        if not self._wait_complete(self.POLL_TIMEOUT):
            raise RuntimeError("Write still in progress")
        rdsr = self._custom(self.RDSR1, 1)
        if rdsr & self.BP_MASK:
            raise RuntimeError(f"Failed to unprotect flash: SR1 = {hex(rdsr)}")

    @property
    def is_protected(self) -> bool:
        ret = self._custom(self.RDSR1, 1)
        return bool(FIELD_GET(self.BP_MASK, ret))


def get_flash_protector(flash_type: FlashType, uart: UART):
    if flash_type is None:
        raise RuntimeError("Flash type is required")

    TYPE2CLS = {
        "S25FL128S": ProtectorS25FL128S,
        "S25FL128S(sector:256K)": ProtectorS25FL128S,
        "S25FL256S": ProtectorS25FL128S,
    }
    cls = TYPE2CLS.get(flash_type.name)
    if cls is None:
        raise RuntimeError(f"Protection operations aren't supported for {flash_type}")
    return cls(uart)
