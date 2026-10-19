"""Small Python bridge used by the static browser app."""

from export import export_borders, export_block_borders


def format_unlocked_chunks(chunk_ids: list[int]) -> str:
    return " ".join(str(chunk_id) for chunk_id in sorted(set(chunk_ids)))


def generate_chunks(chunk_ids: list[int], count: int, name: str) -> dict:
    result = export_borders(chunk_ids, count, name)
    return {
        "first": result.first,
        "second": result.second,
        "first_label": result.first_label,
        "second_label": result.second_label,
        "error": result.error,
        "tile_count": result.tile_count,
    }


def generate_blocks(blocks: list[list[int]], count: int, name: str) -> dict:
    result = export_block_borders(
        [(int(block_x), int(block_y)) for block_x, block_y in blocks], count, name
    )
    return {
        "first": result.first,
        "second": result.second,
        "first_label": result.first_label,
        "second_label": result.second_label,
        "error": result.error,
        "tile_count": result.tile_count,
    }
