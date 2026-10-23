"""Small Python bridge used by the static browser app."""

from export import DEFAULT_COLOR, MAX_TILES, SPLIT, export_borders, export_block_borders


def format_unlocked_chunks(chunk_ids: list[int], delimiter: str = " ") -> str:
    return delimiter.join(str(chunk_id) for chunk_id in sorted(set(chunk_ids)))


def generate_chunks(
    chunk_ids: list[int],
    count: int,
    name: str,
    color: str = DEFAULT_COLOR,
    max_total_tiles: int = MAX_TILES,
    max_tiles_per_import: int = SPLIT,
    fill_color: str | None = None,
) -> dict:
    result = export_borders(
        chunk_ids, count, name, color, max_total_tiles, max_tiles_per_import, fill_color
    )
    return {
        "first": result.first,
        "second": result.second,
        "first_label": result.first_label,
        "second_label": result.second_label,
        "error": result.error,
        "tile_count": result.tile_count,
        "strings": result.strings,
        "labels": result.labels,
    }


def generate_blocks(
    blocks: list[list[int]],
    count: int,
    name: str,
    color: str = DEFAULT_COLOR,
    max_total_tiles: int = MAX_TILES,
    max_tiles_per_import: int = SPLIT,
    fill_color: str | None = None,
) -> dict:
    result = export_block_borders(
        [(int(block_x), int(block_y)) for block_x, block_y in blocks],
        count,
        name,
        color,
        max_total_tiles,
        max_tiles_per_import,
        fill_color,
    )
    return {
        "first": result.first,
        "second": result.second,
        "first_label": result.first_label,
        "second_label": result.second_label,
        "error": result.error,
        "tile_count": result.tile_count,
        "strings": result.strings,
        "labels": result.labels,
    }
