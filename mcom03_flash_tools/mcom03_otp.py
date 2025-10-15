#!/usr/bin/env python3

# Copyright 2025 RnD Center "ELVEES", JSC

import argparse
import binascii
import io
import json
import os
import re
import sys
from collections import namedtuple
from typing import Optional

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    import tomli as tomllib  # type: ignore

from mcom03_flash_tools import UART, __version__, upload_flasher

BitField = namedtuple("BitField", ["hi", "lo", "name", "func_status"])
Record = namedtuple("Record", ["word_addr", "words_count", "name", "func_status", "bitfields"])
Cell = namedtuple("Cell", ["data", "ecc", "is_correct"])

OTP_WORDS_COUNT = 128


class OTP_Data:
    def __init__(self, data, otp_addr):
        if isinstance(data, bytes):
            self.data = []
            for i in range(len(data) // 4):
                val = int.from_bytes(data[i * 4 : i * 4 + 4], byteorder="little", signed=False)
                self.data.append(Cell(val, 0, True))
        else:
            self.data = data

        self.start_otp_addr = otp_addr

    def __getitem__(self, index):
        return self.data[index]

    def to_bytes(self):
        return b"".join([x.data.to_bytes(4, byteorder="little", signed=False) for x in self.data])

    def ecc_to_bytes(self):
        return b"".join([x.ecc.to_bytes(1, byteorder="little", signed=False) for x in self.data])

    def is_zero_filled(self, start_addr, count):
        pos = start_addr - self.start_otp_addr
        return not bool([x for x in self.data[pos : pos + count] if x.data])

    def is_addr_ecc_err(self, addr):
        return not self.data[addr].is_correct

    def is_record_ecc_err(self, record):
        addr_start = record.word_addr - self.start_otp_addr
        addr_end = addr_start + record.words_count
        return bool([x for x in self.data[addr_start:addr_end] if not x.is_correct])

    def get_data_by_addr(self, addr):
        return self.data[addr - self.start_otp_addr].data

    def get_bytes_for_record(self, record):
        addr_start = record.word_addr - self.start_otp_addr
        addr_end = addr_start + record.words_count
        if addr_start < 0 or len(self.data) < addr_end:
            return None

        rec_data = self.data[addr_start:addr_end]

        return b"".join([x.data.to_bytes(4, byteorder="little", signed=False) for x in rec_data])


def check_status_letter(uart: UART, letters: list[str], err_msg: str):
    success, response = uart.wait_for_string(letters)
    if not success or len(response) != 1:
        if response.startswith("E\n"):
            response = response[2:]

        if response.endswith("\n#"):
            response = response[:-2]

        raise Exception(f"{err_msg} error. Check for VPP voltage. Response: '{response}'")


def program(uart: Optional[UART], data: bytes, addr: int):
    print(f"Programming {len(data)} bytes ({data.hex(' ')}) to OTP from address {addr:#x}...")
    if (len(data) // 4 + addr) > OTP_WORDS_COUNT:
        print("Data doesn't fit to OTP memory", file=sys.stderr)
        sys.exit(1)
    elif len(data) % 4:
        print("Data size must be aligned by 4 bytes", file=sys.stderr)
        sys.exit(1)
    elif not data:
        print("No data to program", file=sys.stderr)
        sys.exit(1)

    if uart is None:
        return  # with --dry-run argument

    response = uart.run(f"program {addr}")
    if "Ready" not in response:
        raise Exception(f"Flasher error: {response}")

    size = len(data)
    crc = binascii.crc_hqx(data, 0xFFFF)
    uart.tty.write(size.to_bytes(2, "little"))
    uart.tty.write(crc.to_bytes(2, "little"))
    check_status_letter(uart, ["R"], "Size and CRC receive confirmation")
    uart.tty.write(data)
    check_status_letter(uart, ["R"], "Program confirmation")
    uart.wait_for_string(uart.prompt)
    print("Done")


def get_bitfield_value(bitfield: BitField, record_value: int) -> int:
    mask = (1 << (bitfield.hi - bitfield.lo + 1)) - 1
    return (record_value >> bitfield.lo) & mask


def boot_status(bitfield: BitField, record_value: int) -> Optional[str]:
    bitfield_value = get_bitfield_value(bitfield, record_value)
    return (
        "useless without 'boot_padoverride'"
        if bitfield_value and not (record_value & 0x8)
        else None
    )


def vs_en_status(bitfield: BitField, record_value: int) -> Optional[str]:
    bitfield_value = get_bitfield_value(bitfield, record_value)
    return (
        "useless without 'vs_en_padoverride'"
        if bitfield_value and not (record_value & 0x20)
        else None
    )


def bs_en_status(bitfield: BitField, record_value: int) -> Optional[str]:
    bitfield_value = get_bitfield_value(bitfield, record_value)
    return (
        "useless without 'bs_en_padoverride'"
        if bitfield_value and not (record_value & 0x80)
        else None
    )


def revocation_status(record, data):
    rev = data.get_data_by_addr(record.word_addr)
    rev_prot = data.get_data_by_addr(record.word_addr + 8)
    if rev == 0 and rev_prot == 0:
        return None
    elif rev == (rev_prot ^ 0xFFFFFFFF):
        return "ok"

    return "INVALID"


OTP_RECORDS = (
    [
        Record(
            0,
            1,
            "fuse1",
            None,
            [
                BitField(31, 31, "lock", None),
                BitField(30, 30, "lock_fw", None),
                BitField(29, 29, "lock_bootrom", None),
                BitField(28, 0, "user", None),
            ],
        ),
        Record(
            1,
            1,
            "fuse0",
            None,
            [
                BitField(31, 31, "lock", None),
                BitField(27, 27, "top_subs_disable", None),
                BitField(26, 26, "ddr_subs_disable", None),
                BitField(25, 25, "ls1_subs_disable", None),
                BitField(24, 24, "ls0_subs_disable", None),
                BitField(23, 23, "hs_subs_disable", None),
                BitField(22, 22, "media_subs_disable", None),
                BitField(21, 21, "sdr_subs_disable", None),
                BitField(20, 20, "cpu_subs_disable", None),
                BitField(19, 19, "scan_test_disable", None),
                BitField(18, 18, "mbist_test_disable", None),
                BitField(17, 17, "bsr_test_disable", None),
                BitField(16, 16, "ust_debug_disable", None),
                BitField(15, 15, "bringupdbg_disable", None),
                BitField(14, 14, "sdrtosecure_disable", None),
                BitField(13, 13, "trustedtosecure_disable", None),
                BitField(12, 12, "dpm_enable", None),
                BitField(10, 10, "dpm_lock_secure", None),
                BitField(9, 9, "dpm_lock_sdr", None),
                BitField(8, 8, "dpm_lock_trusted", None),
                BitField(7, 7, "bs_en_padoverride", None),
                BitField(6, 6, "bs_en", bs_en_status),
                BitField(5, 5, "vs_en_padoverride", None),
                BitField(4, 4, "vs_en", vs_en_status),
                BitField(3, 3, "boot_padoverride", None),
                BitField(2, 2, "boot2", boot_status),
                BitField(1, 1, "boot1", boot_status),
                BitField(0, 0, "boot0", boot_status),
            ],
        ),
        Record(
            2,
            1,
            "flags",
            None,
            [
                BitField(20, 20, "enable_watchdog", None),
                BitField(19, 19, "disable_log", None),
                BitField(17, 17, "force_encrypt", None),
                BitField(16, 16, "force_sign", None),
            ],
        ),
        Record(3, 1, "serial", None, []),
        Record(4, 4, "duk", None, []),
        Record(8, 8, "rotpk", None, []),
    ]
    + [Record(16 + x, 1, f"revocation{x}", revocation_status, []) for x in range(1, 8)]
    + [Record(24 + x, 1, f"revocation_prot{x}", None, []) for x in range(1, 8)]
    + [
        Record(32, 1, "fuse1_redundant", None, []),
        Record(33, 1, "fuse0_redundant", None, []),
        Record(34, 2, "risc0_fw_counter", None, []),
    ]
)


def read_otp(uart: Optional[UART], addr: int, count: int, flags: int):
    if uart is None:
        return OTP_Data(bytes(count * 4), addr)  # with --dry-run argument

    cells = []
    response = uart.run(f"read {addr} {count} {flags}")
    for line in response.split("\n"):
        if not line:
            continue

        m = re.findall(r"\[\d+\] Data: ([xa-fA-F\d]+), ECC: ([xa-fA-F\d]+) \((.+)\)", line)
        if not m:
            raise Exception(f"Error at 'read' command: {line}")

        data, ecc, is_correct = m[0]
        cells.append(Cell(int(data, 0), int(ecc, 0), is_correct == "ok"))

    return OTP_Data(cells, addr)


def get_record_by_name(name: str):
    """
    >>> get_record_by_name('word_addr_4') == Record(4, 1, 'word_addr_4', None, [])
    True
    >>> get_record_by_name('serial') == Record(3, 1, 'serial', None, [])
    True
    >>> get_record_by_name('word_addr_0x9') == Record(9, 1, 'word_addr_9', None, [])
    True
    >>> get_record_by_name('word_addr_132')
    Traceback (most recent call last):
     ...
    SystemExit: 1
    """
    if name.startswith("word_addr_"):
        addr = int(name[10:], 0)
        if addr >= OTP_WORDS_COUNT:
            print(
                f"Bad address {addr:#x} in record '{name}'. Must be below {OTP_WORDS_COUNT}",
                file=sys.stderr,
            )
            sys.exit(1)

        return Record(addr, 1, f"{name[:10]}{addr}", None, [])
    else:
        record = [x for x in OTP_RECORDS if x.name == name]
        if not record:
            print(f"OTP record '{name}' not found", file=sys.stderr)
            sys.exit(1)

        return record[0]


def get_record_by_address(addr):
    """
    >>> get_record_by_address(3) == Record(3, 1, "serial", None, [])
    True
    """
    records = [x for x in OTP_RECORDS if x.word_addr == addr]
    if not records:
        return Record(addr, 1, f"word_addr_{addr}", None, [])

    return records[0]


def get_bitfield_by_name(name: str, record: Record):
    if name.startswith("reserved_bit_"):
        bit = int(name[13:], 0)
        if bit >= (record.words_count * 32):
            print(f"Wrong bit number {bit} in bitfield '{record.name}.{name}'", file=sys.stderr)
            sys.exit(1)

        return BitField(bit, bit, name, None)
    else:
        bitfields = [x for x in record.bitfields if x.name == name]
        if not bitfields:
            print(f"Bitfield '{record.name}.{name}' not found", file=sys.stderr)
            sys.exit(1)

        return bitfields[0]


def cmd_program_record_int(uart: Optional[UART], name: str, value: int):
    record = get_record_by_name(name)
    data = value.to_bytes(record.words_count * 4, byteorder="little", signed=False)
    program(uart, data, record.word_addr)
    print("Verify...")
    read_data = (
        data if uart is None else read_otp(uart, record.word_addr, record.words_count, 0).to_bytes()
    )
    if read_data != data:
        read_value = int.from_bytes(read_data, byteorder="little", signed=False)
        print(f"Error: Expected {value:#x}, but read {read_value:#x}", file=sys.stderr)
        sys.exit(1)

    print("Verification passed")


def cmd_program_record_bytes(uart: Optional[UART], name: str, value: str):
    record = get_record_by_name(name)
    data = bytes.fromhex(value)
    if len(data) != record.words_count * 4:
        print(
            f"Value size is {len(data)} bytes, but record '{name}' must be "
            f"{record.words_count * 4} bytes",
            file=sys.stderr,
        )
        sys.exit(1)

    program(uart, data, record.word_addr)
    print("Verify...")
    read_data = (
        data if uart is None else read_otp(uart, record.word_addr, record.words_count, 0).to_bytes()
    )
    if read_data != data:
        print(f"Error: Expected {data.hex()}, but read {read_data.hex()}", file=sys.stderr)
        sys.exit(1)

    print("Verify done")


def bitfields_to_record(record: Record, toml_fields: dict):
    """Generate and return record value from fields dictionary

    >>> bitfields_to_record(get_record_by_name("fuse1"), {"user": 0x11, "lock": 1}) == 0x80000011
    True
    >>> bitfields_to_record(get_record_by_name("fuse1"), \
                            {"user": 0x11, "reserved_bit_30": 1}) == 0x40000011
    True
    >>> bitfields_to_record(get_record_by_name("fuse1"), {"user": 0x11, "lock": 2})
    Traceback (most recent call last):
     ...
    SystemExit: 1
    >>> bitfields_to_record(get_record_by_name("fuse1"), {"unexisted": 0x11})
    Traceback (most recent call last):
     ...
    SystemExit: 1
    """
    record_value = 0
    record_mask = 0
    for field_name, field_value in toml_fields.items():
        bitfield = get_bitfield_by_name(field_name, record)
        bitfield_value_mask = (1 << (bitfield.hi - bitfield.lo + 1)) - 1
        bitfield_mask = bitfield_value_mask << bitfield.lo
        if record_mask & bitfield_mask:
            print(
                f"Error: bitfield {record.name}.{field_name} is overlaps another bitfield",
                file=sys.stderr,
            )
            sys.exit(1)

        if field_value > bitfield_value_mask or field_value < 0:
            print(
                f"Error: value {field_value} can not fit into {record.name}.{field_name}",
                file=sys.stderr,
            )
            sys.exit(1)

        record_mask |= bitfield_mask
        record_value |= field_value << bitfield.lo

    return record_value


def cmd_program_toml(uart: Optional[UART], toml_file_obj: io.BufferedReader, fname_to_save: str):
    """Program OTP by values from TOML file.
    Function will prepare dictionary with records and program non-zero records to OTP."""
    toml = tomllib.load(toml_file_obj)
    toml_otp = toml["otp"]
    otp = {}
    for record_name, record_value in toml_otp.items():
        record = get_record_by_name(record_name)
        if type(record_value) is dict:
            new_value = bitfields_to_record(record, record_value)
            otp[record_name] = new_value
        else:
            if type(record_value) is int:
                record_mask = (1 << (record.words_count * 32 + 1)) - 1
                if record_value > record_mask or record_value < 0:
                    print(
                        f"Error: value {record_value:#x} can not fit into {record.name}",
                        file=sys.stderr,
                    )
                    sys.exit(1)
            elif type(record_value) is str:
                data = bytes.fromhex(record_value)
                if len(data) > record.words_count * 4:
                    print(
                        f"Error: value '{record_value:#x}' ({len(data)} bytes) can not fit "
                        f"into {record.name}",
                        file=sys.stderr,
                    )
                    sys.exit(1)

            otp[record_name] = record_value

    if fname_to_save is not None:
        with open(fname_to_save, "wb") as f:
            f.seek(OTP_WORDS_COUNT * 4 - 1, os.SEEK_SET)
            f.write(b"\0")
            for record_name, record_value in otp.items():
                record = get_record_by_name(record_name)
                f.seek(record.word_addr * 4, os.SEEK_SET)
                if type(record_value) is int:
                    f.write(int(record_value).to_bytes(record.words_count * 4, byteorder="little"))
                else:
                    f.write(bytes.fromhex(record_value).ljust(record.words_count * 4))

    for record_name, record_value in otp.items():
        if type(record_value) is int:
            if not record_value:
                continue  # skip empty record

            print(f"Program {record_name} = {record_value:#x}...")
            cmd_program_record_int(uart, record_name, record_value)
        else:
            if record_value == "".ljust(len(record_value), "0"):
                continue  # skip empty record

            print(f"Program {record_name} = {record_value}...")
            cmd_program_record_bytes(uart, record_name, record_value)


def cmd_bist(uart: Optional[UART], is_bisr: bool, addr: int, count: Optional[int]):
    if count is None:
        count = OTP_WORDS_COUNT - addr

    if addr < 0 or count <= 0 or addr + count > OTP_WORDS_COUNT:
        print(
            f"Wrong --addr or --count values. Total count of OTP words is {OTP_WORDS_COUNT}.",
            file=sys.stderr,
        )
        sys.exit(1)

    if uart is not None:
        cmd = "bisr" if is_bisr else "bist"
        result = uart.run(f"{cmd} {addr} {count}")
    else:
        result = "Ok"

    if result.strip() == "Ok":
        print("Success")
    else:
        print(result.strip(), file=sys.stderr)
        sys.exit(1)


def dump_bitfield(record, record_data, bitfield, max_name_len, is_toml):
    record_value = int.from_bytes(record_data, byteorder="little", signed=False)
    bitfield_value = get_bitfield_value(bitfield, record_value)
    if is_toml:
        print(f"otp.{record.name}.{bitfield.name} = {bitfield_value:#d}")
    else:
        if bitfield.func_status is not None:
            status = bitfield.func_status(bitfield, record_value)
            status = f" ({status})" if status is not None else ""
        else:
            status = ""

        name = f"{bitfield.name}:"
        fmt = "#x" if bitfield.hi - bitfield.lo == 31 else "d"
        print(f"        {name:{max_name_len + 1}} {bitfield_value:{fmt}}{status}")


def dump_record(data: OTP_Data, record: Record, records_max_name_len, is_toml):
    record_data = data.get_bytes_for_record(record)
    if record_data is None:
        return

    if not is_toml:
        if record.func_status is not None:
            status = record.func_status(record, data)
            status = f" ({status})" if status is not None else ""
        else:
            status = ""

        name = f"{record.name}:"
        addr = f"[{record.word_addr}]"
        if data.is_record_ecc_err(record):
            status = " ECC Error" + status

        if record.words_count <= 2:
            value = int.from_bytes(record_data, byteorder="little", signed=False)
            print(f"{addr:5} {name:{records_max_name_len + 1}} {value:#x} ({value:d}){status}")
        else:
            print(f"{addr:5} {name:{records_max_name_len + 1}} {record_data.hex()}{status}")

    bitfields_max_name_len = max([len(x.name) for x in record.bitfields]) if record.bitfields else 0
    ecc_err = "  # ECC Error" if data.is_record_ecc_err(record) else ""
    if record.bitfields:
        tmp_value = int.from_bytes(record_data, byteorder="little", signed=False)
        if is_toml:
            print(f"# otp.{record.name} = {tmp_value:#x}{ecc_err}")

        record_mask = (1 << (record.words_count * 2)) - 1
        for bitfield in record.bitfields:
            dump_bitfield(record, record_data, bitfield, bitfields_max_name_len, is_toml)
            if tmp_value:
                bitfield_mask = ((1 << (bitfield.hi - bitfield.lo + 1)) - 1) << bitfield.lo
                tmp_value &= bitfield_mask ^ record_mask
        if tmp_value:
            bit = 0
            while tmp_value:
                if tmp_value & 0x1:
                    if is_toml:
                        print(f"otp.{record.name}.reserved_bit_{bit} = 1")
                    else:
                        print(f"        reserved_bit_{bit}: 1")

                tmp_value >>= 1
                bit += 1

        if not is_toml:
            print("")
    elif is_toml:
        if record.words_count <= 2:
            value = int.from_bytes(record_data, byteorder="little", signed=False)
            print(f"otp.{record.name} = {value:#x}{ecc_err}")
        else:
            print(f'otp.{record.name} = "{record_data.hex()}"{ecc_err}')


def cmd_dump(
    uart: Optional[UART], f_obj: Optional[io.BufferedReader], count: int, flags: int, is_toml: bool
):
    """Print all records from OTP"""
    if count is None:
        count = OTP_WORDS_COUNT

    if count > OTP_WORDS_COUNT:
        print(
            f"Wrong --count values. Total count of OTP words is {OTP_WORDS_COUNT}.", file=sys.stderr
        )
        sys.exit(1)

    if f_obj is not None:
        data = OTP_Data(f_obj.read(count * 4), 0)
    else:
        data = read_otp(uart, 0, count, flags)

    records_max_name_len = max([len(x.name) for x in OTP_RECORDS])
    next_address = 0
    while next_address < OTP_WORDS_COUNT:
        record = get_record_by_address(next_address)
        next_address += record.words_count
        is_zero_filled = data.is_zero_filled(record.word_addr, record.words_count)
        if not record.name.startswith("word_addr_") or not is_zero_filled:
            dump_record(data, record, records_max_name_len, is_toml)


def cmd_read(
    uart: Optional[UART], fname: str, addr: int, count: int, flags: int, output_format: str
):
    def write_to_file(f_obj, data):
        if output_format == "bin":
            f_obj.write(data.to_bytes())
            f_obj.write(data.ecc_to_bytes())
        else:
            if output_format == "json":
                res = {}
                for idx, (value, ecc, is_correct) in enumerate(data):
                    res[idx + addr] = {"value": value, "ecc": ecc, "is_correct": is_correct}

                json.dump(res, f_obj, indent=2)
                print("")
            else:
                for idx, (value, ecc, is_correct) in enumerate(data):
                    f_obj.write(
                        f"[{idx + addr}] value: {value:#010x}, ecc: {ecc:#04x}, "
                        f"correct: {is_correct}\n"
                    )

    if count is None:
        count = OTP_WORDS_COUNT - addr

    if addr < 0 or count <= 0 or addr + count > OTP_WORDS_COUNT:
        print(
            f"Wrong --addr or --count values. Total count of OTP words is {OTP_WORDS_COUNT}.",
            file=sys.stderr,
        )
        sys.exit(1)

    data = read_otp(uart, addr, count, flags)
    if fname is None:
        f_obj = sys.stdout.buffer if output_format == "bin" else sys.stdout
        write_to_file(f_obj, data)
    else:
        mode = "wb" if output_format == "bin" else "wt"
        with open(fname, mode) as f_obj:
            write_to_file(f_obj, data)


def main() -> int:
    class Formatter(argparse.ArgumentDefaultsHelpFormatter, argparse.RawDescriptionHelpFormatter):
        pass

    def int0(x):
        return int(x, 0)

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=Formatter)
    subparsers = parser.add_subparsers(dest="command", required=True)
    parser_prog_int = subparsers.add_parser(
        "program-integer", help="Program single record of OTP memory by integer value"
    )
    parser_prog_bytes = subparsers.add_parser(
        "program-bytes", help="Program single record of OTP memory by raw value"
    )
    parser_prog_toml = subparsers.add_parser(
        "program-toml", help="Progream OTP by data from TOML file"
    )
    parser_bist = subparsers.add_parser(
        "bist", help="Run BIST for OTP region (check for leaky bits)"
    )
    parser_bisr = subparsers.add_parser(
        "bisr", help="Run BISR for OTP region (fix for 1 leaky bit per cell)"
    )
    parser_read = subparsers.add_parser("read", help="Read data from OTP and save to file")
    parser_dump = subparsers.add_parser(
        "dump", help="Read data from OTP and show all records of OTP"
    )
    subparsers.add_parser("print-records", help="Print known OTP records and bitfields")

    for p in [parser_prog_int, parser_prog_bytes]:
        p.add_argument("name", help="Name of record (see 'print-records' command)")

    parser_prog_int.add_argument(
        "value", type=int0, help="Integer value to program. Will write as little-endian."
    )

    parser_prog_bytes.add_argument(
        "value",
        help=(
            "Raw hex data to program (example: 016578616d706c65). First bytes will write to "
            "lower address (as big-endian)"
        ),
    )

    parser_prog_toml.add_argument(
        "toml_file", type=argparse.FileType(mode="rb"), help="Name of TOML file"
    )
    parser_prog_toml.add_argument("--save-to-bin-file", help="Also save result to binary image")

    parser_read.add_argument("fname", nargs="?", help="File name to save")
    parser_read.add_argument(
        "--output-format", default="text", choices=["text", "bin", "json"], help="Output format"
    )

    parser_dump.add_argument(
        "--from-file",
        type=argparse.FileType(mode="rb"),
        help="If specified then use this binary image file instead of real OTP",
    )
    parser_dump.add_argument("--toml", action="store_true", help="Output in TOML format")

    for p in [parser_read, parser_dump, parser_bist, parser_bisr]:
        p.add_argument("--count", type=int0, default=None, help="Count of OTP words to process")

    for p in [parser_read, parser_bist, parser_bisr]:
        p.add_argument(
            "--addr",
            type=int0,
            default=0,
            help="Process data starting from ADDR (in words)",
        )

    for p in [
        parser_read,
        parser_dump,
    ]:
        p.add_argument(
            "--ecc-disable",
            action="store_const",
            const=0x1,
            default=0,
            help="Disable ECC correction",
        )
        p.add_argument(
            "--ecc-generate",
            action="store_const",
            const=0x2,
            default=0,
            help="With --ecc-disable will recalc ECC for data",
        )
        p.add_argument(
            "--ecc-test",
            action="store_const",
            const=0x4,
            default=0,
            help="Read syndrome instead of ECC",
        )
        p.add_argument(
            "--brp-disable",
            action="store_const",
            const=0x8,
            default=0,
            help="Disable invert even if BRP used",
        )
        p.add_argument(
            "--brp-generate",
            action="store_const",
            const=0x10,
            default=0,
            help="Force data inversion and ECC even if BRP in not used",
        )
    parser.add_argument(
        "-p",
        "--port",
        default="/dev/ttyUSB0",
        help="serial port on host the device UART0 is connected to",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="show UART traffic")
    parser.add_argument(
        "-f",
        "--flasher",
        help=(
            "path to Intel HEX baremetal application to be executed on RISC0"
            "(use HEX distributed with the tool if not specified)"
        ),
    )
    parser.add_argument(
        "-n", "--dry-run", action="store_true", help="Only print messages but do not access to OTP"
    )
    parser.add_argument("--version", action="version", version=__version__)

    args = parser.parse_args()

    if args.command in ["read", "dump"]:
        flags = (
            args.ecc_disable
            | args.ecc_generate
            | args.ecc_test
            | args.brp_disable
            | args.brp_generate
        )
    else:
        flags = 0

    if args.command == "dump" and args.from_file is not None:
        cmd_dump(None, args.from_file, args.count, flags, args.toml)
        return 0
    elif args.command == "print-records":
        for record in OTP_RECORDS:
            print(
                f"{record.name:20} - addr: {record.word_addr:d}, count: {record.words_count}"
                " word(s)"
            )
            for bitfield in record.bitfields:
                bits = (
                    f"[{bitfield.hi}]"
                    if bitfield.hi == bitfield.lo
                    else f"[{bitfield.hi}:{bitfield.lo}]"
                )
                print(f"    {bits:7s} {bitfield.name}")

        print("")
        print(" Any 32-bit word also can be specified by name 'word_addr_XX' where XX is OTP")
        print(" word address. Address can be specified from 0 to 127.")
        print(" Example: word_addr_3 which corresponds to 'serial'")
        return 0

    if args.dry_run:
        uart = None
    else:
        uart = UART(prompt="#", port=args.port, baudrate=115200, verbose=args.verbose)
        upload_flasher(uart, "otp-flasher-mips-ram.hex", "OTP Flasher", args.flasher)

    if args.command == "program-integer":
        cmd_program_record_int(uart, args.name, args.value)
    elif args.command == "program-bytes":
        cmd_program_record_bytes(uart, args.name, args.value)
    elif args.command == "program-toml":
        cmd_program_toml(uart, args.toml_file, args.save_to_bin_file)
    elif args.command == "bist":
        cmd_bist(uart, False, args.addr, args.count)
    elif args.command == "bisr":
        cmd_bist(uart, True, args.addr, args.count)
    elif args.command == "read":
        cmd_read(uart, args.fname, args.addr, args.count, flags, args.output_format)
    elif args.command == "dump":
        cmd_dump(uart, None, args.count, flags, args.toml)
    else:
        raise Exception(f"Unknown command {args.command}")  # Unreachable error

    return 0


if __name__ == "__main__":
    sys.exit(main())
