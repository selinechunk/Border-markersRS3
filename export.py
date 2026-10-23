import base64
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

from border import block_border_loops, border_loops

Tile = tuple[int, int, int, int]
SPLIT = 127
MAX_TILES = 5000
MAX_IMPORT_TILES = 255


@dataclass
class ExportResult:
    first: str
    second: str
    first_label: str
    second_label: str
    error: str | None
    tile_count: int
    strings: list[str] = field(default_factory=list)
    labels: list[str] = field(default_factory=list)
STYLE = bytes.fromhex("0164ff69ff50cc548c0c14")
DEFAULT_COLOR = "#64ff69"
DEFAULT_FILL_COLOR = "#50cc54"


def _rgb_from_color(color: str) -> bytes:
    if len(color) != 7 or color[0] != "#":
        raise ValueError("Color must use #RRGGBB format.")
    try:
        rgb = bytes.fromhex(color[1:])
    except ValueError as error:
        raise ValueError("Color must use #RRGGBB format.") from error
    if len(rgb) != 3:
        raise ValueError("Color must use #RRGGBB format.")

    return rgb


def style_for_color(color: str, fill_color: str | None = None) -> bytes:
    rgb = _rgb_from_color(color)
    fill_rgb = (
        bytes(channel * 4 // 5 for channel in rgb)
        if fill_color is None
        else _rgb_from_color(fill_color)
    )
    return STYLE[:1] + rgb + b"\xff" + fill_rgb + STYLE[8:]


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


def encode_string(
    name: str,
    tiles: list[Tile],
    color: str = DEFAULT_COLOR,
    fill_color: str | None = None,
) -> str:
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
        + style_for_color(color, fill_color)
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


def export_walk(
    walk: Callable[[int], list[Tile]],
    count: int,
    name: str,
    color: str = DEFAULT_COLOR,
    max_total_tiles: int = MAX_TILES,
    max_tiles_per_import: int = SPLIT,
    fill_color: str | None = None,
) -> ExportResult:
    """Build the import strings for a border walk, easing the marker count if needed."""
    if max_total_tiles < 1:
        raise ValueError("Maximum total tiles must be a positive integer.")
    if not 1 <= max_tiles_per_import <= MAX_IMPORT_TILES:
        raise ValueError(f"Maximum tiles per import must be between 1 and {MAX_IMPORT_TILES}.")
    tiles = walk(count)
    n = len(tiles)
    if n > max_total_tiles:
        if count == 2 or len(walk(2)) > max_total_tiles:
            return ExportResult("", "", "", "", "That map is too big, sorry.", n)
        suggested = 2
        for candidate in range(2, count):
            if len(walk(candidate)) <= max_total_tiles:
                suggested = candidate
        return ExportResult(
            "",
            "",
            "",
            "",
            f"Too many tiles ({n}). Try a marker count of {suggested} or less.",
            n,
        )
    strings = []
    labels = []
    for offset in range(0, n, max_tiles_per_import):
        part_number = len(strings) + 1
        part_name = name if part_number == 1 else f"{name}{part_number}"
        end = min(offset + max_tiles_per_import, n)
        strings.append(encode_string(part_name, tiles[offset:end], color, fill_color))
        labels.append(_range_label(offset + 1, end))
    first = strings[0]
    second = strings[1] if len(strings) > 1 else ""
    first_label = labels[0]
    second_label = labels[1] if len(labels) > 1 else ""
    return ExportResult(
        first,
        second,
        first_label,
        second_label,
        None,
        n,
        strings,
        labels,
    )


def export_borders(
    chunk_ids: Iterable[int],
    count: int,
    name: str,
    color: str = DEFAULT_COLOR,
    max_total_tiles: int = MAX_TILES,
    max_tiles_per_import: int = SPLIT,
    fill_color: str | None = None,
) -> ExportResult:
    chunk_list = list(chunk_ids)
    return export_walk(
        lambda c: unique_walk(chunk_list, c),
        count,
        name,
        color,
        max_total_tiles,
        max_tiles_per_import,
        fill_color,
    )


def export_block_borders(
    blocks: Iterable[tuple[int, int]],
    count: int,
    name: str,
    color: str = DEFAULT_COLOR,
    max_total_tiles: int = MAX_TILES,
    max_tiles_per_import: int = SPLIT,
    fill_color: str | None = None,
) -> ExportResult:
    block_list = list(blocks)
    return export_walk(
        lambda c: unique_tiles(block_border_loops(block_list, c)),
        count,
        name,
        color,
        max_total_tiles,
        max_tiles_per_import,
        fill_color,
    )
