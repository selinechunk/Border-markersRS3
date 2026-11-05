import base64
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

from border import block_border_loops, border_loops, chunk_id_to_grid, grid_to_chunk_id

Tile = tuple[int, int, int, int]
SPLIT = 127
MAX_TILES = 5000
MAX_IMPORT_TILES = 255
MAX_MARKER_NAME_LENGTH = 32


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
    one_per_chunk: bool = False,
    whole_chunks_per_import: bool = False,
    rollable_chunk_ids: Iterable[int] | None = None,
) -> ExportResult:
    """Build the import strings for a border walk, easing the marker count if needed."""
    if one_per_chunk and whole_chunks_per_import:
        raise ValueError("Choose either one chunk per import or multiple whole chunks per import.")
    if max_total_tiles < 1:
        raise ValueError("Maximum total tiles must be a positive integer.")
    if not 1 <= max_tiles_per_import <= MAX_IMPORT_TILES:
        raise ValueError(f"Maximum tiles per import must be between 1 and {MAX_IMPORT_TILES}.")
    adjacent_to_rollable: set[tuple[int, int]] | None = None
    if rollable_chunk_ids is not None:
        adjacent_to_rollable = set()
        for chunk_id in rollable_chunk_ids:
            grid_x, grid_y = chunk_id_to_grid(chunk_id)
            adjacent_to_rollable.update(
                {
                    (grid_x - 1, grid_y),
                    (grid_x + 1, grid_y),
                    (grid_x, grid_y - 1),
                    (grid_x, grid_y + 1),
                }
            )

    def filtered_walk(marker_count: int) -> list[Tile]:
        walked_tiles = walk(marker_count)
        if adjacent_to_rollable is None:
            return walked_tiles
        return [
            tile
            for tile in walked_tiles
            if tile[:2] in adjacent_to_rollable
        ]

    tiles = filtered_walk(count)
    n = len(tiles)
    if adjacent_to_rollable is not None and not tiles:
        return ExportResult(
            "",
            "",
            "",
            "",
            "No border markers fall within chunks adjacent to selected rollable chunks.",
            0,
        )
    if n > max_total_tiles:
        if count == 2 or len(filtered_walk(2)) > max_total_tiles:
            return ExportResult("", "", "", "", "That map is too big, sorry.", n)
        suggested = 2
        for candidate in range(2, count):
            if len(filtered_walk(candidate)) <= max_total_tiles:
                suggested = candidate
        return ExportResult(
            "",
            "",
            "",
            "",
            f"Too many tiles ({n}). Try a marker count of {suggested} or less.",
            n,
        )
    if one_per_chunk or whole_chunks_per_import:
        chunks: dict[tuple[int, int], list[Tile]] = {}
        for tile in tiles:
            chunks.setdefault(tile[:2], []).append(tile)
        ordered_chunks = sorted(
            chunks.items(), key=lambda item: (item[0][1], item[0][0])
        )
        if one_per_chunk:
            groups = [
                (
                    f"{name}-{grid_to_chunk_id(grid_x, grid_y)}",
                    f"Chunk {grid_to_chunk_id(grid_x, grid_y)}",
                    chunk_tiles,
                )
                for (grid_x, grid_y), chunk_tiles in ordered_chunks
            ]
        else:
            groups = []
            batch_tiles: list[Tile] = []
            batch_chunk_ids: list[int] = []

            def finish_chunk_group() -> None:
                groups.append(
                    (
                        f"{name}-" + "-".join(map(str, batch_chunk_ids)),
                        f"Chunks {', '.join(map(str, batch_chunk_ids))}",
                        batch_tiles.copy(),
                    )
                )

            for grid, chunk_tiles in ordered_chunks:
                grid_x, grid_y = grid
                chunk_id = grid_to_chunk_id(grid_x, grid_y)
                if len(chunk_tiles) > max_tiles_per_import:
                    return ExportResult(
                        "",
                        "",
                        "",
                        "",
                        f"Chunk {chunk_id} has {len(chunk_tiles)} markers, exceeding "
                        f"the per-import limit of {max_tiles_per_import}. Increase "
                        "the limit or lower the marker count.",
                        n,
                    )
                candidate_name = f"{name}-" + "-".join(
                    map(str, [*batch_chunk_ids, chunk_id])
                )
                if batch_tiles and (
                    len(batch_tiles) + len(chunk_tiles) > max_tiles_per_import
                    or len(candidate_name) > MAX_MARKER_NAME_LENGTH
                ):
                    finish_chunk_group()
                    batch_tiles = []
                    batch_chunk_ids = []
                    candidate_name = f"{name}-{chunk_id}"
                if len(candidate_name) > MAX_MARKER_NAME_LENGTH:
                    return ExportResult(
                        "",
                        "",
                        "",
                        "",
                        f"Chunk {chunk_id} cannot fit in the {MAX_MARKER_NAME_LENGTH}-character marker title limit. "
                        "Use a shorter map name.",
                        n,
                    )
                batch_tiles.extend(chunk_tiles)
                batch_chunk_ids.append(chunk_id)
            if batch_tiles:
                finish_chunk_group()
    else:
        groups = [(name, "", tiles)]

    strings = []
    labels = []
    for group_name, group_label, group_tiles in groups:
        part_count = (len(group_tiles) + max_tiles_per_import - 1) // max_tiles_per_import
        for part_index, offset in enumerate(
            range(0, len(group_tiles), max_tiles_per_import), start=1
        ):
            end = min(offset + max_tiles_per_import, len(group_tiles))
            if one_per_chunk:
                part_name = group_name if part_count == 1 else f"{group_name}-{part_index}"
                label = (
                    group_label
                    if part_count == 1
                    else f"{group_label} (part {part_index})"
                )
            elif whole_chunks_per_import:
                part_name = group_name
                label = group_label
            else:
                part_number = len(strings) + 1
                part_name = name if part_number == 1 else f"{name}{part_number}"
                label = _range_label(offset + 1, end)
            strings.append(
                encode_string(part_name, group_tiles[offset:end], color, fill_color)
            )
            labels.append(label)
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
    one_per_chunk: bool = False,
    whole_chunks_per_import: bool = False,
    rollable_chunk_ids: Iterable[int] | None = None,
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
        one_per_chunk,
        whole_chunks_per_import,
        rollable_chunk_ids,
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
