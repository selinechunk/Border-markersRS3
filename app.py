import http.client
import json
import re
import threading
import traceback
import urllib.error
import urllib.parse
import urllib.request

from border import BLOCKS, START_BLOCK
from export import (
    DEFAULT_COLOR,
    DEFAULT_FILL_COLOR,
    MAX_IMPORT_TILES,
    MAX_TILES,
    SPLIT,
    export_block_borders,
    export_borders,
)


MAP_URL = "https://chunkpickerrs3.firebaseio.com/maps/{code}.json?shallow=true"
UNLOCKED_URL = "https://chunkpickerrs3.firebaseio.com/maps/{code}/chunks/unlocked.json"

# The Chunk Picker map covers tiles x 1856-4863 and y 1408-4607, which is this
# many 150-tile blocks once the grid is anchored on BLOCK_ORIGIN.
BLOCK_X_RANGE = range(12, 33)
BLOCK_Y_RANGE = range(9, 31)
ENKLUMPMAN_NAME = "ENKLUMPMAN"
BLOCK_PAIR = re.compile(r"(-?\d+)\s*,\s*(-?\d+)")
DELIMITER_OPTIONS = ("Space", "Comma", "New line", "Tab")
DELIMITERS = {"Space": " ", "Comma": ",", "New line": "\n", "Tab": "\t"}

# Orientation only: a dot per landmark so the empty grid is readable.
LANDMARKS = (
    ("Burthorpe", 2899, 3544),
    ("Taverley", 2894, 3425),
    ("Catherby", 2805, 3433),
    ("Seers' Village", 2707, 3488),
    ("Rellekka", 2668, 3630),
    ("Ardougne", 2662, 3305),
    ("Yanille", 2605, 3093),
    ("Falador", 2965, 3380),
    ("Port Sarim", 3025, 3205),
    ("Brimhaven", 2802, 3178),
    ("Edgeville", 3093, 3493),
    ("Draynor", 3093, 3250),
    ("Varrock", 3212, 3424),
    ("Lumbridge", 3222, 3218),
    ("Al Kharid", 3293, 3174),
    ("Canifis", 3495, 3488),
    ("Burgh de Rott", 3495, 3230),
    ("Port Phasmatys", 3685, 3465),
    ("Daemonheim", 3450, 3700),
    ("Wilderness Volcano", 3360, 3930),
    ("Nardah", 3435, 2915),
    ("Sophanem", 3285, 2785),
    ("Menaphos", 3220, 2740),
    ("Oo'glog", 2530, 2845),
    ("Gnome Stronghold", 2461, 3444),
    ("Piscatoris", 2340, 3650),
    ("Prifddinas", 2240, 3360),
    ("Lletya", 2330, 3170),
)


def block_in_range(block: tuple[int, int]) -> bool:
    block_x, block_y = block
    return block_x in BLOCK_X_RANGE and block_y in BLOCK_Y_RANGE


def format_blocks(blocks: set[tuple[int, int]]) -> str:
    ordered = sorted(blocks, key=lambda block: (-block[1], block[0]))
    return " ".join(f"{block_x},{block_y}" for block_x, block_y in ordered)


def parse_blocks(text: str) -> set[tuple[int, int]]:
    """Read a block list such as "19,23 20,23". Raises ValueError on bad input."""
    found = BLOCK_PAIR.findall(text)
    leftover = BLOCK_PAIR.sub(" ", text)
    if leftover.strip(" \t\r\n,;()"):
        raise ValueError("Blocks look like 19,23 20,23.")
    blocks = {(int(block_x), int(block_y)) for block_x, block_y in found}
    outside = sorted(block for block in blocks if not block_in_range(block))
    if outside:
        block_x, block_y = outside[0]
        raise ValueError(f"Block {block_x},{block_y} is off the map.")
    return blocks | {START_BLOCK}


def block_label(block: tuple[int, int]) -> str:
    west, south, east, north = BLOCKS.bounds(block)
    block_x, block_y = block
    text = f"({block_x}, {block_y})  x {west}-{east}  y {south}-{north}"
    names = [
        name
        for name, tile_x, tile_y in LANDMARKS
        if west <= tile_x <= east and south <= tile_y <= north
    ]
    return f"{text}  · {', '.join(names)}" if names else text


class MapNotFound(Exception):
    pass


class NoUnlockedChunks(Exception):
    pass


class MapLoadError(Exception):
    pass


def input_error(code: str, count_text: str, require_code: bool = True) -> str | None:
    if require_code and not code.strip():
        return "Enter a map code."
    text = count_text.strip()
    if not text.isdecimal() or not 2 <= int(text) <= 64:
        return "Enter a marker count from 2 through 64."
    return None


def _read_json(url: str):
    request = urllib.request.Request(url, headers={"User-Agent": "border-markers"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8")
    except (urllib.error.URLError, TimeoutError, UnicodeDecodeError, http.client.HTTPException) as error:
        raise MapLoadError from error
    try:
        return json.loads(body)
    except json.JSONDecodeError as error:
        raise MapLoadError from error


def fetch_unlocked_ids(code: str) -> list[int]:
    quoted = urllib.parse.quote(code, safe="")
    try:
        shallow = _read_json(MAP_URL.format(code=quoted))
        if shallow is None:
            raise MapNotFound
        unlocked = _read_json(UNLOCKED_URL.format(code=quoted))
    except OSError as error:
        raise MapLoadError from error
    if not isinstance(unlocked, dict):
        raise NoUnlockedChunks
    ids = [int(key) for key in unlocked if str(key).isdecimal()]
    if not ids:
        raise NoUnlockedChunks
    return sorted(ids)


def format_unlocked_chunks(chunk_ids: list[int], delimiter: str = " ") -> str:
    return delimiter.join(str(chunk_id) for chunk_id in sorted(set(chunk_ids)))


def main() -> None:
    import tkinter as tk
    from tkinter import colorchooser

    root = tk.Tk()
    root.title("Border markers")

    code_var = tk.StringVar()
    count_var = tk.StringVar(value="4")
    status_var = tk.StringVar()
    enklumpman_var = tk.BooleanVar(value=False)
    code_label_var = tk.StringVar(value="Map code")
    count_label_var = tk.StringVar(value="Markers per 64 tiles")
    color_var = tk.StringVar(value=DEFAULT_COLOR)
    fill_color_var = tk.StringVar(value=DEFAULT_FILL_COLOR)
    delimiter_var = tk.StringVar(value="Space")
    max_total_var = tk.StringVar(value=str(MAX_TILES))
    max_per_import_var = tk.StringVar(value=str(SPLIT))

    form = tk.Frame(root, padx=12, pady=12)
    form.pack(fill="x")
    enklumpman_check = tk.Checkbutton(
        form, text="Enklumpman mode (150-tile blocks)", variable=enklumpman_var
    )
    enklumpman_check.grid(row=0, column=0, columnspan=2, sticky="w")
    tk.Label(form, textvariable=code_label_var).grid(row=1, column=0, sticky="w", pady=(8, 0))
    tk.Entry(form, textvariable=code_var, width=20).grid(row=1, column=1, padx=(8, 0), pady=(8, 0), sticky="w")
    tk.Label(form, textvariable=count_label_var).grid(row=2, column=0, sticky="w", pady=(8, 0))
    tk.Entry(form, textvariable=count_var, width=20).grid(row=2, column=1, padx=(8, 0), pady=(8, 0), sticky="w")

    tk.Label(form, text="Marker color").grid(row=3, column=0, sticky="w", pady=(8, 0))
    color_controls = tk.Frame(form)
    color_controls.grid(row=3, column=1, padx=(8, 0), pady=(8, 0), sticky="w")
    color_swatch = tk.Label(
        color_controls, textvariable=color_var, background=DEFAULT_COLOR, width=10
    )
    color_swatch.pack(side="left")
    choose_color = tk.Button(color_controls, text="Choose color")
    choose_color.pack(side="left", padx=(6, 0))

    tk.Label(form, text="Fill color").grid(row=4, column=0, sticky="w", pady=(8, 0))
    fill_color_controls = tk.Frame(form)
    fill_color_controls.grid(row=4, column=1, padx=(8, 0), pady=(8, 0), sticky="w")
    fill_color_swatch = tk.Label(
        fill_color_controls,
        textvariable=fill_color_var,
        background=DEFAULT_FILL_COLOR,
        width=10,
    )
    fill_color_swatch.pack(side="left")
    choose_fill_color = tk.Button(fill_color_controls, text="Choose fill")
    choose_fill_color.pack(side="left", padx=(6, 0))

    config_button = tk.Button(form, text="Config")
    config_button.grid(row=5, column=0, sticky="w", pady=(12, 0))
    generate = tk.Button(form, text="Generate")
    generate.grid(row=5, column=1, sticky="e", pady=(12, 0))

    config_panel = tk.Frame(form, padx=8, pady=8)
    config_panel._config_panel = True
    config_panel.grid(row=6, column=0, columnspan=2, sticky="we", pady=(8, 0))
    tk.Label(config_panel, text="Chunk ID delimiter").grid(row=0, column=0, sticky="w")
    tk.OptionMenu(config_panel, delimiter_var, *DELIMITER_OPTIONS).grid(
        row=0, column=1, sticky="w"
    )
    tk.Label(config_panel, text="Maximum total tiles").grid(row=1, column=0, sticky="w")
    tk.Entry(config_panel, textvariable=max_total_var, width=12).grid(
        row=1, column=1, sticky="w"
    )
    tk.Label(config_panel, text="Maximum tiles per import").grid(
        row=2, column=0, sticky="w"
    )
    tk.Entry(config_panel, textvariable=max_per_import_var, width=12).grid(
        row=2, column=1, sticky="w"
    )
    config_panel.grid_remove()
    config_open = {"value": False}

    def toggle_config() -> None:
        config_open["value"] = not config_open["value"]
        if config_open["value"]:
            config_panel.grid()
            config_button.configure(text="Close config")
        else:
            config_panel.grid_remove()
            config_button.configure(text="Config")

    config_button.configure(command=toggle_config)
    tk.Label(form, textvariable=status_var, anchor="w").grid(
        row=7, column=0, columnspan=2, sticky="we", pady=(8, 0)
    )

    first_label_var = tk.StringVar()
    second_label_var = tk.StringVar()

    strings = tk.Frame(root, padx=12)
    strings.pack(fill="both", expand=True)
    tk.Label(strings, textvariable=first_label_var, anchor="w").pack(fill="x")
    first_box = tk.Text(strings, width=40, height=6, wrap="char", state="disabled")
    first_box.pack(fill="both", expand=True)
    copy_first = tk.Button(strings, text="Copy")
    copy_first.pack(anchor="w", pady=(4, 12))
    tk.Label(strings, textvariable=second_label_var, anchor="w").pack(fill="x")
    second_box = tk.Text(strings, width=40, height=6, wrap="char", state="disabled")
    second_box.pack(fill="both", expand=True)
    copy_second = tk.Button(strings, text="Copy")
    copy_second.pack(anchor="w", pady=(4, 12))
    additional_outputs = tk.Frame(strings)
    additional_outputs.pack(fill="x", expand=True)
    extra_output_items = []
    copy_chunks = tk.Button(strings, text="Copy chunk IDs")
    copy_chunks.pack(anchor="w", pady=(4, 12))
    unlocked_chunks = {"ids": []}

    CELL = 24
    LOCKED_FILL = "#2f3136"
    UNLOCKED_FILL = "#3aa84a"
    START_FILL = "#e0a32e"
    columns = list(BLOCK_X_RANGE)
    rows = list(BLOCK_Y_RANGE)
    selected: set[tuple[int, int]] = {START_BLOCK}
    blocks_var = tk.StringVar(value=format_blocks(selected))
    hover_var = tk.StringVar(value="Click or drag to mark the blocks you have.")

    grid_frame = tk.Frame(root, padx=12)
    canvas = tk.Canvas(
        grid_frame,
        width=CELL * len(columns),
        height=CELL * len(rows),
        background="#1c1e22",
        highlightthickness=0,
        cursor="hand2",
    )
    canvas.pack()
    tk.Label(grid_frame, textvariable=hover_var, anchor="w").pack(fill="x", pady=(6, 0))
    list_row = tk.Frame(grid_frame)
    list_row.pack(fill="x", pady=(6, 0))
    tk.Label(list_row, text="Blocks").pack(side="left")
    tk.Entry(list_row, textvariable=blocks_var).pack(side="left", padx=(8, 0), fill="x", expand=True)
    apply_blocks = tk.Button(list_row, text="Apply")
    apply_blocks.pack(side="left", padx=(8, 0))
    clear_blocks = tk.Button(list_row, text="Clear")
    clear_blocks.pack(side="left", padx=(4, 0))

    def cell_corner(block: tuple[int, int]) -> tuple[int, int]:
        block_x, block_y = block
        return (block_x - columns[0]) * CELL, (rows[-1] - block_y) * CELL

    rect_of = {}
    for block_x in columns:
        for block_y in rows:
            left, top = cell_corner((block_x, block_y))
            rect_of[(block_x, block_y)] = canvas.create_rectangle(
                left, top, left + CELL, top + CELL, outline="#50545c", width=1
            )
    for landmark, tile_x, tile_y in LANDMARKS:
        block = BLOCKS.cell_at(tile_x, tile_y)
        if not block_in_range(block):
            continue
        west, south, _east, _north = BLOCKS.bounds(block)
        left, top = cell_corner(block)
        dot_x = left + (tile_x - west) * CELL / BLOCKS.size
        dot_y = top + CELL - (tile_y - south) * CELL / BLOCKS.size
        canvas.create_oval(
            dot_x - 1.5, dot_y - 1.5, dot_x + 1.5, dot_y + 1.5, fill="#9ecbff", outline=""
        )

    def paint_cell(block: tuple[int, int]) -> None:
        if block == START_BLOCK:
            fill = START_FILL
        elif block in selected:
            fill = UNLOCKED_FILL
        else:
            fill = LOCKED_FILL
        canvas.itemconfigure(rect_of[block], fill=fill)

    def repaint() -> None:
        for block in rect_of:
            paint_cell(block)
        blocks_var.set(format_blocks(selected))

    painting = {"on": True, "active": False}

    def block_at_event(event) -> tuple[int, int] | None:
        column = int(canvas.canvasx(event.x)) // CELL
        row = int(canvas.canvasy(event.y)) // CELL
        if not (0 <= column < len(columns) and 0 <= row < len(rows)):
            return None
        return columns[column], rows[-1] - row

    def apply_paint(block: tuple[int, int] | None) -> None:
        if block is None or block == START_BLOCK:
            return
        if painting["on"] == (block in selected):
            return
        if painting["on"]:
            selected.add(block)
        else:
            selected.discard(block)
        paint_cell(block)
        blocks_var.set(format_blocks(selected))
        hover_var.set(block_label(block))

    def on_press(event) -> None:
        block = block_at_event(event)
        if block is None:
            return
        if block == START_BLOCK:
            painting["active"] = False
            hover_var.set("The start block is always unlocked.")
            return
        painting["on"] = block not in selected
        painting["active"] = True
        apply_paint(block)

    def on_drag(event) -> None:
        if painting["active"]:
            apply_paint(block_at_event(event))

    def on_release(_event) -> None:
        painting["active"] = False

    def on_motion(event) -> None:
        block = block_at_event(event)
        if block is not None:
            hover_var.set(block_label(block))

    canvas.bind("<Button-1>", on_press)
    canvas.bind("<B1-Motion>", on_drag)
    canvas.bind("<ButtonRelease-1>", on_release)
    canvas.bind("<Motion>", on_motion)

    def on_apply_blocks() -> None:
        try:
            parsed = parse_blocks(blocks_var.get())
        except ValueError as error:
            status_var.set(str(error))
            return
        selected.clear()
        selected.update(parsed)
        repaint()
        status_var.set(f"{len(selected)} blocks marked.")

    def on_clear_blocks() -> None:
        selected.clear()
        selected.add(START_BLOCK)
        repaint()
        status_var.set("Cleared back to the start block.")

    apply_blocks.configure(command=on_apply_blocks)
    clear_blocks.configure(command=on_clear_blocks)
    repaint()

    def on_mode_change() -> None:
        if enklumpman_var.get():
            code_label_var.set("Marker name")
            count_label_var.set("Markers per block edge")
            copy_chunks.configure(state="disabled")
            grid_frame.pack(fill="x", pady=(0, 12), before=strings)
        else:
            code_label_var.set("Map code")
            count_label_var.set("Markers per 64 tiles")
            copy_chunks.configure(state="normal")
            grid_frame.pack_forget()

    enklumpman_check.configure(command=on_mode_change)

    def on_choose_color(variable, swatch, title: str) -> None:
        _rgb, selected = colorchooser.askcolor(color=variable.get(), title=title)
        if selected:
            variable.set(selected.lower())
            swatch.configure(background=selected)

    choose_color.configure(
        command=lambda: on_choose_color(color_var, color_swatch, "Marker color")
    )
    choose_fill_color.configure(
        command=lambda: on_choose_color(fill_color_var, fill_color_swatch, "Fill color")
    )

    def set_box(box, text: str) -> None:
        box.configure(state="normal")
        box.delete("1.0", "end")
        box.insert("1.0", text)
        box.configure(state="disabled")

    def render_outputs(result) -> None:
        strings = result.strings or [value for value in (result.first, result.second) if value]
        labels = result.labels or [value for value in (result.first_label, result.second_label) if value]
        set_box(first_box, strings[0] if strings else result.error or "")
        first_label_var.set(labels[0] if labels else "")
        set_box(second_box, strings[1] if len(strings) > 1 else "")
        second_label_var.set(labels[1] if len(labels) > 1 else "")

        while len(extra_output_items) < max(0, len(strings) - 2):
            item = tk.Frame(additional_outputs)
            label_var = tk.StringVar()
            tk.Label(item, textvariable=label_var, anchor="w").pack(fill="x")
            box = tk.Text(item, width=40, height=6, wrap="char", state="disabled")
            box.pack(fill="both", expand=True)
            copy_button = tk.Button(item, text="Copy")
            copy_button.configure(command=lambda output=box: on_copy(output))
            copy_button.pack(anchor="w", pady=(4, 12))
            extra_output_items.append((item, label_var, box))

        for index, (item, label_var, box) in enumerate(extra_output_items, start=2):
            if index < len(strings):
                item.pack(fill="x", expand=True)
                label_var.set(labels[index])
                set_box(box, strings[index])
            else:
                item.pack_forget()

    def box_text(box) -> str:
        return box.get("1.0", "end-1c")

    def finish_ok(result, chunk_text: list[int] | None = None) -> None:
        if chunk_text is not None:
            unlocked_chunks["ids"] = chunk_text
        render_outputs(result)
        status_var.set(f"Loaded {result.tile_count} tiles.")
        generate.configure(state="normal")

    def finish_limit(result, chunk_text: list[int] | None = None) -> None:
        if chunk_text is not None:
            unlocked_chunks["ids"] = chunk_text
        render_outputs(result)
        status_var.set(result.error or "")
        generate.configure(state="normal")

    def finish_err(message: str) -> None:
        status_var.set(message)
        generate.configure(state="normal")

    def on_generate() -> None:
        code = code_var.get()
        count_text = count_var.get()
        block_mode = enklumpman_var.get()
        error = input_error(code, count_text, require_code=not block_mode)
        if error:
            status_var.set(error)
            return
        settings = []
        for variable, label in (
            (max_total_var, "maximum total tiles"),
            (max_per_import_var, "maximum tiles per import"),
        ):
            text = variable.get().strip()
            if not text.isdecimal() or int(text) < 1:
                status_var.set(f"Enter a positive whole number for {label}.")
                return
            settings.append(int(text))
        max_total_tiles, max_tiles_per_import = settings
        if max_tiles_per_import > MAX_IMPORT_TILES:
            status_var.set(
                f"Maximum tiles per import cannot exceed {MAX_IMPORT_TILES}."
            )
            return
        color = color_var.get()
        fill_color = fill_color_var.get()
        if block_mode:
            name = code.strip().upper() or ENKLUMPMAN_NAME
            result = export_block_borders(
                sorted(selected),
                int(count_text.strip()),
                name,
                color,
                max_total_tiles,
                max_tiles_per_import,
                fill_color,
            )
            if result.error:
                finish_limit(result)
            else:
                finish_ok(result)
            return
        generate.configure(state="disabled")
        trimmed = code.strip()

        def work() -> None:
            try:
                ids = fetch_unlocked_ids(trimmed.lower())
                chunk_text = ids
                result = export_borders(
                    ids,
                    int(count_text.strip()),
                    trimmed.upper(),
                    color,
                    max_total_tiles,
                    max_tiles_per_import,
                    fill_color,
                )
            except MapNotFound:
                root.after(0, lambda: finish_err("No map found for that code."))
                return
            except NoUnlockedChunks:
                root.after(0, lambda: finish_err("That map has no unlocked chunks."))
                return
            except MapLoadError:
                root.after(0, lambda: finish_err("Could not load the map."))
                return
            except Exception:
                traceback.print_exc()
                root.after(0, lambda: finish_err("Could not load the map."))
                return
            if result.error:
                root.after(0, lambda: finish_limit(result, chunk_text))
                return
            root.after(0, lambda: finish_ok(result, chunk_text))

        threading.Thread(target=work, daemon=True).start()

    def on_copy(box) -> None:
        text = box_text(box)
        if text == "":
            status_var.set("Nothing to copy.")
            return
        root.clipboard_clear()
        root.clipboard_append(text)
        status_var.set("Copied.")

    def on_copy_chunks() -> None:
        if enklumpman_var.get():
            status_var.set("Chunk list is not available in Enklumpman mode.")
            return
        text = format_unlocked_chunks(
            unlocked_chunks["ids"], DELIMITERS[delimiter_var.get()]
        )
        if text == "":
            status_var.set("Nothing to copy.")
            return
        root.clipboard_clear()
        root.clipboard_append(text)
        status_var.set("Copied chunk IDs.")

    generate.configure(command=on_generate)
    copy_first.configure(command=lambda: on_copy(first_box))
    copy_second.configure(command=lambda: on_copy(second_box))
    copy_chunks.configure(command=on_copy_chunks)
    root.mainloop()


if __name__ == "__main__":
    main()
