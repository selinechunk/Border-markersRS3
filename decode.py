"""Read a TM2 import string back into its tiles. The inverse of `export.py`.

This is a checking tool, not part of the window. Run it on a string to see what is
actually in it:

    python3 Border-markersRS3/decode.py TM2IQNWV0gcgODBEpECkQKiBJECs...

Tiles come back sorted by packed value, which is how the string stores them. The order
the border was walked in is not recorded, so it cannot be recovered.
"""

import base64
import binascii
import sys
from dataclasses import dataclass

from border import format_point

Tile = tuple[int, int, int, int]
PREFIX = "TM2"
VERSION = 0x21
STYLE_LENGTH = 11


class BadString(Exception):
    """The text is not a TM2 string this tool can read."""


@dataclass
class Decoded:
    name: str
    tiles: list[Tile]
    style: bytes
    trailer: bytes


def read_leb(data: bytes, index: int) -> tuple[int, int]:
    value = 0
    shift = 0
    while True:
        if index >= len(data):
            raise BadString("The string ends in the middle of a number.")
        byte = data[index]
        index += 1
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return value, index
        shift += 7


def deinterleave(value: int, nbits: int = 8) -> tuple[int, int]:
    a = b = 0
    for bit in range(nbits):
        if (value >> (2 * bit)) & 1:
            b |= 1 << bit
        if (value >> (2 * bit + 1)) & 1:
            a |= 1 << bit
    return a, b


def unpack_tile(value: int) -> Tile:
    grid_x, grid_y = deinterleave(value >> 12)
    local_x, local_y = deinterleave(value & 0xFFF, 6)
    return grid_x, grid_y, local_x, local_y


def decode_string(text: str) -> Decoded:
    text = text.strip()
    if not text.startswith(PREFIX):
        raise BadString(f"A tile marker string starts with {PREFIX}.")
    body = text[len(PREFIX):]
    try:
        data = base64.urlsafe_b64decode(body + "=" * ((4 - len(body) % 4) % 4))
    except (binascii.Error, ValueError) as error:
        raise BadString("The string is not valid base64.") from error
    if len(data) < 3:
        raise BadString("The string is too short.")
    if data[0] != VERSION:
        raise BadString(f"Unknown version byte 0x{data[0]:02x}.")

    name_length = data[1]
    index = 2 + name_length
    if index >= len(data):
        raise BadString("The string ends inside the name.")
    try:
        name = data[2:index].decode()
    except UnicodeDecodeError as error:
        raise BadString("The name is not valid UTF-8.") from error

    count = data[index]
    index += 1
    if count == 0:
        raise BadString("The string holds no tiles.")

    packed, index = read_leb(data, index)
    values = [packed]
    for _ in range(count - 1):
        gap, index = read_leb(data, index)
        packed += gap
        values.append(packed)

    style = data[index:index + STYLE_LENGTH]
    if len(style) < STYLE_LENGTH:
        raise BadString("The string ends before its colour.")
    return Decoded(name, [unpack_tile(value) for value in values], style, data[index + STYLE_LENGTH:])


def describe(decoded: Decoded) -> str:
    lines = [
        f"name     {decoded.name}",
        f"tiles    {len(decoded.tiles)}",
        f"colour   {decoded.style.hex()}",
    ]
    grids = sorted({(grid_x, grid_y) for grid_x, grid_y, _lx, _ly in decoded.tiles})
    tile_xs = [grid_x * 64 + local_x for grid_x, _gy, local_x, _ly in decoded.tiles]
    tile_ys = [grid_y * 64 + local_y for _gx, grid_y, _lx, local_y in decoded.tiles]
    lines.append(f"grids    {len(grids)}: {', '.join(f'({x}, {y})' for x, y in grids)}")
    lines.append(f"covers   x {min(tile_xs)}-{max(tile_xs)}   y {min(tile_ys)}-{max(tile_ys)}")
    lines.append("")
    for grid_x, grid_y, local_x, local_y in decoded.tiles:
        point = format_point(grid_x, grid_y, local_x, local_y)
        lines.append(f"{point:<24}tile ({grid_x * 64 + local_x}, {grid_y * 64 + local_y})")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(f"usage: {argv[0] if argv else 'decode.py'} TM2...", file=sys.stderr)
        return 2
    try:
        print(describe(decode_string(argv[1])))
    except BadString as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
