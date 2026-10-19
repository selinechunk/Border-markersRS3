import base64
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from border import block_border_loops, border_loops

Tile = tuple[int, int, int, int]
SPLIT = 127
MAX_TILES = 232


@dataclass
class ExportResult:
    first: str
    second: str
    first_label: str
    second_label: str
    error: str | None
    tile_count: int
STYLE = bytes.fromhex("0164ff69ff50cc548c0c14")


def interleave(a: int, b: int, nbits: int = 8) -> int:
    value = 0
    for bit in range(nbits):
        if (b >> bit) & 1:
            value |= 1 << (2 * bit)
        if (a >> bit) & 1:
            value |= 1 << (2 * bit + 1)
    return value


def pack_tile(tile: Tile) -> int:
    grid_x, grid_y, local_x, local_y = tile
    return (interleave(grid_x, grid_y) << 12) + interleave(local_x, local_y)


def write_leb(n: int) -> bytes:
    out = bytearray()
    while True:
        byte = n & 0x7F
        n >>= 7
        if n:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def encode_string(name: str, tiles: list[Tile]) -> str:
    ordered = sorted(tiles, key=pack_tile)
    name_bytes = name.encode()
    steps = b"".join(
        write_leb(pack_tile(ordered[index + 1]) - pack_tile(ordered[index]))
        for index in range(len(ordered) - 1)
    )
    payload = (
        bytes([0x21, len(name_bytes)])
        + name_bytes
        + bytes([len(ordered)])
        + write_leb(pack_tile(ordered[0]))
        + steps
        + STYLE
        + bytes(len(ordered))
    )
    return "TM2" + base64.urlsafe_b64encode(payload).rstrip(b"=").decode()


def unique_tiles(loops: Iterable[list[Tile]]) -> list[Tile]:
    seen: set[Tile] = set()
    tiles: list[Tile] = []
    for loop in loops:
        for tile in loop:
            if tile not in seen:
                seen.add(tile)
                tiles.append(tile)
    return tiles


def unique_walk(chunk_ids: Iterable[int], count: int) -> list[Tile]:
    return unique_tiles(border_loops(chunk_ids, count))


def _range_label(start: int, end: int) -> str:
    return f"Tiles {start}–{end}"


def export_walk(walk: Callable[[int], list[Tile]], count: int, name: str) -> ExportResult:
    """Build the import strings for a border walk, easing the marker count if needed."""
    tiles = walk(count)
    n = len(tiles)
    if n > MAX_TILES:
        if count == 2 or len(walk(2)) > MAX_TILES:
            return ExportResult("", "", "", "", "That map is too big, sorry.", n)
        suggested = 2
        for candidate in range(2, count):
            if len(walk(candidate)) <= MAX_TILES:
                suggested = candidate
        return ExportResult(
            "",
            "",
            "",
            "",
            f"Too many tiles ({n}). Try a marker count of {suggested} or less.",
            n,
        )
    first_tiles = tiles[:SPLIT]
    second_tiles = tiles[SPLIT:]
    first = encode_string(name, first_tiles)
    if second_tiles:
        return ExportResult(
            first,
            encode_string(name + "2", second_tiles),
            _range_label(1, SPLIT),
            _range_label(SPLIT + 1, n),
            None,
            n,
        )
    return ExportResult(first, "", _range_label(1, n), "", None, n)


def export_borders(chunk_ids: Iterable[int], count: int, name: str) -> ExportResult:
    chunk_list = list(chunk_ids)
    return export_walk(lambda c: unique_walk(chunk_list, c), count, name)


def export_block_borders(
    blocks: Iterable[tuple[int, int]], count: int, name: str
) -> ExportResult:
    block_list = list(blocks)
    return export_walk(
        lambda c: unique_tiles(block_border_loops(block_list, c)), count, name
    )
