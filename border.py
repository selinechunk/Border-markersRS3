import math
from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass


STARTING_INDEX = 7495
STEP = 256
CHUNK_SIZE = 64
BLOCK_SIZE = 150
BLOCK_ORIGIN = 7
BLOCK_ORIGIN_X = BLOCK_ORIGIN - 1
START_BLOCK = (19, 23)
HEADINGS = {"E": (1, 0), "S": (0, -1), "W": (-1, 0), "N": (0, 1)}
RIGHT_TURN = {"E": "S", "S": "W", "W": "N", "N": "E"}
LEFT_TURN = {"E": "N", "N": "W", "W": "S", "S": "E"}
OPPOSITE = {"E": "W", "W": "E", "N": "S", "S": "N"}

# The Chunk Picker draws these regions beside the mainland instead of where they sit
# in game. Each entry is the picker's south-west chunk, its north-east chunk, and the
# shift from there to the real chunks.
RELOCATED = (
    ((58, 22), (71, 36), (-31, 151)),  # Arc Islands
    ((57, 63), (66, 71), (23, -31)),  # Anachronia
    ((63, 48), (69, 56), (-11, -28)),  # Havenhythe
    ((29, 47), (31, 50), (-9, 39)),  # Lost Grove
)


@dataclass(frozen=True)
class Lattice:
    """A square grid of cells, measured in game tiles."""

    size: int
    origin_x: int
    origin_y: int

    def low_corner(self, cell: tuple[int, int]) -> tuple[int, int]:
        cell_x, cell_y = cell
        return (
            self.origin_x + self.size * cell_x,
            self.origin_y + self.size * cell_y,
        )

    def bounds(self, cell: tuple[int, int]) -> tuple[int, int, int, int]:
        west, south = self.low_corner(cell)
        return west, south, west + self.size - 1, south + self.size - 1

    def cell_at(self, tile_x: int, tile_y: int) -> tuple[int, int]:
        return (
            (tile_x - self.origin_x) // self.size,
            (tile_y - self.origin_y) // self.size,
        )


CHUNKS = Lattice(CHUNK_SIZE, 0, 0)
BLOCKS = Lattice(BLOCK_SIZE, BLOCK_ORIGIN_X, BLOCK_ORIGIN)


def chunk_id_to_grid(chunk_id: int) -> tuple[int, int]:
    picker_x = abs(math.ceil((chunk_id - STARTING_INDEX) / STEP))
    delta = chunk_id - STARTING_INDEX
    if chunk_id <= STARTING_INDEX:
        picker_y = STARTING_INDEX - chunk_id
    elif delta % STEP == 0:
        picker_y = 0
    else:
        picker_y = STEP - (delta % STEP)
    grid_x, grid_y = picker_x + 29, 71 - picker_y
    for (west, south), (east, north), (shift_x, shift_y) in RELOCATED:
        if west <= grid_x <= east and south <= grid_y <= north:
            return grid_x + shift_x, grid_y + shift_y
    return grid_x, grid_y


def marker_positions(count: int, size: int = CHUNK_SIZE) -> list[int]:
    span = size - 1
    return [math.floor(i * span / (count - 1) + 0.5) for i in range(count)]


def tile_to_point(tile: tuple[int, int]) -> tuple[int, int, int, int]:
    tile_x, tile_y = tile
    grid_x, local_x = divmod(tile_x, CHUNK_SIZE)
    grid_y, local_y = divmod(tile_y, CHUNK_SIZE)
    return grid_x, grid_y, local_x, local_y


def format_point(grid_x: int, grid_y: int, local_x: int, local_y: int) -> str:
    return f"({grid_x}, {grid_y}){local_x} - {local_y}"


def cell_on_right(vertex_x: int, vertex_y: int, heading: str) -> tuple[int, int]:
    if heading == "E":
        return vertex_x, vertex_y - 1
    if heading == "S":
        return vertex_x - 1, vertex_y - 1
    if heading == "W":
        return vertex_x - 1, vertex_y
    return vertex_x, vertex_y


def cell_on_left(vertex_x: int, vertex_y: int, heading: str) -> tuple[int, int]:
    if heading == "E":
        return vertex_x, vertex_y
    if heading == "S":
        return vertex_x, vertex_y - 1
    if heading == "W":
        return vertex_x - 1, vertex_y - 1
    return vertex_x - 1, vertex_y


def choose_heading(vertex_x: int, vertex_y: int, arrival: str, interior: set[tuple[int, int]]) -> str:
    for heading in (RIGHT_TURN[arrival], arrival, LEFT_TURN[arrival], OPPOSITE[arrival]):
        if cell_on_right(vertex_x, vertex_y, heading) in interior and cell_on_left(vertex_x, vertex_y, heading) not in interior:
            return heading
    raise RuntimeError(f"border walk stuck at {(vertex_x, vertex_y)} heading {arrival}")


def northernmost_cell(interior: set[tuple[int, int]]) -> tuple[int, int]:
    candidates = [(x, y) for x, y in interior if (x, y + 1) not in interior]
    return min(candidates, key=lambda cell: (-cell[1], cell[0]))


def edge_tiles(
    lattice: Lattice, cell: tuple[int, int], heading: str, count: int
) -> list[tuple[int, int]]:
    west, south = lattice.low_corner(cell)
    far = lattice.size - 1
    positions = marker_positions(count, lattice.size)
    if heading == "E":
        return [(west + offset, south + far) for offset in positions]
    if heading == "S":
        return [(west + far, south + offset) for offset in reversed(positions)]
    if heading == "W":
        return [(west + offset, south) for offset in reversed(positions)]
    return [(west, south + offset) for offset in positions]


def trace_cycle(
    interior: set[tuple[int, int]], count: int, lattice: Lattice = CHUNKS
) -> list[tuple[int, int, int, int]]:
    grid_x, grid_y = northernmost_cell(interior)
    start_x, start_y, start_heading = grid_x, grid_y + 1, "E"
    vertex_x, vertex_y, heading = start_x, start_y, start_heading
    tiles: list[tuple[int, int]] = []
    for _ in range(len(interior) * 8):
        cell = cell_on_right(vertex_x, vertex_y, heading)
        for tile in edge_tiles(lattice, cell, heading, count):
            if tiles and (tile == tiles[-1] or tile == tiles[0]):
                continue
            tiles.append(tile)
        step_x, step_y = HEADINGS[heading]
        vertex_x += step_x
        vertex_y += step_y
        if (vertex_x, vertex_y) == (start_x, start_y):
            next_heading = choose_heading(vertex_x, vertex_y, heading, interior)
            if next_heading == start_heading:
                return [tile_to_point(tile) for tile in tiles]
            heading = next_heading
        else:
            heading = choose_heading(vertex_x, vertex_y, heading, interior)
    raise RuntimeError("border walk did not close")


def connected_components(cells: set[tuple[int, int]]) -> list[set[tuple[int, int]]]:
    remaining = set(cells)
    groups = []
    while remaining:
        start = remaining.pop()
        group = {start}
        queue = deque([start])
        while queue:
            x, y = queue.popleft()
            for neighbor in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    group.add(neighbor)
                    queue.append(neighbor)
        groups.append(group)
    return groups


def start_key(group: set[tuple[int, int]]) -> tuple[int, int]:
    grid_x, grid_y = northernmost_cell(group)
    return (-grid_y, grid_x)


def cell_border_loops(
    cells: set[tuple[int, int]], count: int, lattice: Lattice
) -> list[list[tuple[int, int, int, int]]]:
    areas = sorted(connected_components(cells), key=start_key)
    return [trace_cycle(area, count, lattice) for area in areas]


def border_loops(chunk_ids: Iterable[int], count: int) -> list[list[tuple[int, int, int, int]]]:
    cells = {chunk_id_to_grid(chunk_id) for chunk_id in chunk_ids}
    return cell_border_loops(cells, count, CHUNKS)


def block_border_loops(
    blocks: Iterable[tuple[int, int]], count: int
) -> list[list[tuple[int, int, int, int]]]:
    cells = {(int(block_x), int(block_y)) for block_x, block_y in blocks}
    return cell_border_loops(cells, count, BLOCKS)


def format_loops(loops: list[list[tuple[int, int, int, int]]]) -> str:
    texts = ["\n".join(format_point(*point) for point in loop) for loop in loops]
    return "\n\n".join(texts)


def format_borders(chunk_ids: Iterable[int], count: int) -> str:
    return format_loops(border_loops(chunk_ids, count))


def format_block_borders(blocks: Iterable[tuple[int, int]], count: int) -> str:
    return format_loops(block_border_loops(blocks, count))
