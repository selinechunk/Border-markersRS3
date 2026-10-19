import sys
import unittest
import unittest.mock

import app
import faketk
from border import BLOCKS, START_BLOCK, block_border_loops, format_block_borders, marker_positions
from export import export_block_borders

CELL = 24


class BlockGeometryTests(unittest.TestCase):
    def test_start_block_matches_the_marked_square(self):
        self.assertEqual(BLOCKS.bounds(START_BLOCK), (2857, 3457, 3006, 3606))

    def test_block_lookup_from_a_tile(self):
        self.assertEqual(BLOCKS.cell_at(2886, 3532), START_BLOCK)
        self.assertEqual(BLOCKS.cell_at(2857, 3457), START_BLOCK)
        self.assertEqual(BLOCKS.cell_at(2856, 3457), (18, 23))
        self.assertEqual(BLOCKS.cell_at(2857, 3456), (19, 22))

    def test_marker_positions_span_the_block_edge(self):
        self.assertEqual(marker_positions(2, 150), [0, 149])
        self.assertEqual(marker_positions(4, 150), [0, 50, 99, 149])
        self.assertEqual(marker_positions(4), [0, 21, 42, 63])


class BlockBorderTests(unittest.TestCase):
    def test_single_block_corners(self):
        self.assertEqual(
            format_block_borders([START_BLOCK], 2),
            "\n".join([
                "(44, 56)41 - 22",
                "(46, 56)62 - 22",
                "(46, 54)62 - 1",
                "(44, 54)41 - 1",
            ]),
        )

    def test_single_block_has_four_markers_an_edge(self):
        loops = block_border_loops([START_BLOCK], 4)
        self.assertEqual(len(loops), 1)
        self.assertEqual(len(loops[0]), 12)

    def test_shared_edge_is_omitted_and_seam_is_kept(self):
        # One 300 by 150 outline. The blocks meet at tiles x 3006 and x 3007, and a
        # straight crossing keeps both seam ends, as in chunk mode.
        self.assertEqual(
            format_block_borders([START_BLOCK, (20, 23)], 2),
            "\n".join([
                "(44, 56)41 - 22",
                "(46, 56)62 - 22",
                "(46, 56)63 - 22",
                "(49, 56)20 - 22",
                "(49, 54)20 - 1",
                "(46, 54)63 - 1",
                "(46, 54)62 - 1",
                "(44, 54)41 - 1",
            ]),
        )

    def test_corner_touch_is_two_loops(self):
        loops = block_border_loops([START_BLOCK, (20, 24)], 2)
        self.assertEqual(len(loops), 2)

    def test_enclosed_block_gets_its_own_loop(self):
        ring = [
            (block_x, block_y)
            for block_x in range(18, 21)
            for block_y in range(22, 25)
            if (block_x, block_y) != (19, 23)
        ]
        loops = block_border_loops(ring, 2)
        self.assertEqual(len(loops), 2)
        self.assertEqual(len(loops[1]), 4)


class BlockExportTests(unittest.TestCase):
    def test_single_block_exports_one_string(self):
        result = export_block_borders([START_BLOCK], 4, "ENKLUMPMAN")
        self.assertIsNone(result.error)
        self.assertEqual(result.tile_count, 12)
        self.assertEqual(result.first_label, "Tiles 1–12")
        self.assertEqual(result.second, "")
        self.assertTrue(result.first.startswith("TM2"))

    def test_too_many_markers_suggests_a_lower_count(self):
        result = export_block_borders([START_BLOCK], 64, "E")
        self.assertIsNotNone(result.error)
        self.assertIn("Try a marker count of", result.error)


class Window:
    """Builds the real window against the recording fake, then exposes its parts."""

    def __init__(self):
        del faketk.instances[:]
        saved = sys.modules.get("tkinter")
        sys.modules["tkinter"] = faketk
        try:
            app.main()
        finally:
            if saved is None:
                del sys.modules["tkinter"]
            else:
                sys.modules["tkinter"] = saved
        self.root = faketk.instances[-1]
        entries = self.root.of_type(faketk.Entry)
        labels = self.root.of_type(faketk.Label)
        self.code = entries[0].options["textvariable"]
        self.count = entries[1].options["textvariable"]
        self.blocks = entries[2].options["textvariable"]
        self.code_label = labels[0].options["textvariable"]
        self.count_label = labels[1].options["textvariable"]
        self.status = labels[2].options["textvariable"]
        self.hover = labels[5].options["textvariable"]
        self.boxes = self.root.of_type(faketk.Text)
        self.canvas = self.root.of_type(faketk.Canvas)[0]
        self.check = self.root.of_type(faketk.Checkbutton)[0]
        self.grid_frame = self.canvas.master

    def centre_of(self, block):
        block_x, block_y = block
        return (block_x - 12) * CELL + CELL // 2, (30 - block_y) * CELL + CELL // 2

    def click(self, block):
        self.canvas.click(*self.centre_of(block))

    def fill_of(self, block):
        key = self.canvas.items
        left, top = (block[0] - 12) * CELL, (30 - block[1]) * CELL
        for item in key.values():
            if item["kind"] == "rectangle" and item["coords"][:2] == (left, top):
                return item.get("fill")
        raise KeyError(block)

    def selected(self):
        return app.parse_blocks(self.blocks.get())


class WindowTests(unittest.TestCase):
    def test_grid_is_hidden_until_the_mode_is_on(self):
        window = Window()
        self.assertFalse(window.grid_frame.visible)
        self.assertEqual(window.code_label.get(), "Map code")
        self.assertEqual(window.count_label.get(), "Markers per 64 tiles")
        self.assertEqual(window.blocks.get(), "19,23")

    def test_toggling_shows_the_grid_and_relabels_the_boxes(self):
        window = Window()
        window.check.toggle()
        self.assertTrue(window.grid_frame.visible)
        self.assertEqual(window.code_label.get(), "Marker name")
        self.assertEqual(window.count_label.get(), "Markers per block edge")
        window.check.toggle()
        self.assertFalse(window.grid_frame.visible)

    def test_start_block_is_coloured_and_cannot_be_cleared(self):
        window = Window()
        self.assertEqual(window.fill_of(START_BLOCK), "#e0a32e")
        self.assertEqual(window.fill_of((20, 23)), "#2f3136")
        window.click(START_BLOCK)
        self.assertEqual(window.selected(), {START_BLOCK})
        self.assertEqual(window.fill_of(START_BLOCK), "#e0a32e")
        self.assertEqual(window.hover.get(), "The start block is always unlocked.")

    def test_clicking_toggles_a_block(self):
        window = Window()
        window.click((20, 23))
        self.assertEqual(window.selected(), {START_BLOCK, (20, 23)})
        self.assertEqual(window.fill_of((20, 23)), "#3aa84a")
        window.click((20, 23))
        self.assertEqual(window.selected(), {START_BLOCK})
        self.assertEqual(window.fill_of((20, 23)), "#2f3136")

    def test_dragging_paints_a_run_of_blocks(self):
        window = Window()
        window.canvas.binds["<Button-1>"](faketk.Event(*window.centre_of((20, 23))))
        window.canvas.drag(*window.centre_of((21, 23)))
        window.canvas.drag(*window.centre_of((22, 23)))
        window.canvas.binds["<ButtonRelease-1>"](faketk.Event(0, 0))
        self.assertEqual(
            window.selected(), {START_BLOCK, (20, 23), (21, 23), (22, 23)}
        )

    def test_hover_names_the_block_and_its_tiles(self):
        window = Window()
        window.canvas.hover(*window.centre_of(START_BLOCK))
        self.assertEqual(
            window.hover.get(), "(19, 23)  x 2857-3006  y 3457-3606  · Burthorpe"
        )

    def test_apply_and_clear_the_block_list(self):
        window = Window()
        window.blocks.set("20,23 19,24")
        window.root.button("Apply").invoke()
        self.assertEqual(window.selected(), {START_BLOCK, (20, 23), (19, 24)})
        self.assertEqual(window.fill_of((19, 24)), "#3aa84a")
        self.assertEqual(window.status.get(), "3 blocks marked.")
        window.root.button("Clear").invoke()
        self.assertEqual(window.selected(), {START_BLOCK})
        self.assertEqual(window.fill_of((19, 24)), "#2f3136")

    def test_a_bad_block_list_is_reported_and_changes_nothing(self):
        window = Window()
        window.click((20, 23))
        window.blocks.set("nonsense")
        window.root.button("Apply").invoke()
        self.assertEqual(window.status.get(), "Blocks look like 19,23 20,23.")
        window.blocks.set("99,99")
        window.root.button("Apply").invoke()
        self.assertEqual(window.status.get(), "Block 99,99 is off the map.")

    def test_generate_builds_markers_from_the_grid(self):
        window = Window()
        window.check.toggle()
        window.click((20, 23))
        window.root.button("Generate").invoke()
        self.assertEqual(window.status.get(), "Loaded 20 tiles.")
        self.assertTrue(window.boxes[0].content.startswith("TM2"))
        self.assertEqual(window.boxes[1].content, "")

    def test_generate_needs_no_map_code_but_uses_it_as_a_name(self):
        window = Window()
        window.check.toggle()
        window.root.button("Generate").invoke()
        default_name = window.boxes[0].content
        window.code.set(" mine ")
        window.root.button("Generate").invoke()
        self.assertNotEqual(window.boxes[0].content, default_name)
        self.assertEqual(window.status.get(), "Loaded 12 tiles.")

    def test_generate_still_validates_the_marker_count(self):
        window = Window()
        window.check.toggle()
        window.count.set("1")
        window.root.button("Generate").invoke()
        self.assertEqual(window.status.get(), "Enter a marker count from 2 through 64.")

    def test_an_oversized_selection_is_refused(self):
        window = Window()
        window.check.toggle()
        window.blocks.set(" ".join(f"19,{row}" for row in range(9, 31)))
        window.root.button("Apply").invoke()
        window.count.set("64")
        window.root.button("Generate").invoke()
        self.assertIn("tiles", window.status.get())
        self.assertTrue(
            window.status.get().startswith("Too many tiles")
            or window.status.get() == "That map is too big, sorry.",
            window.status.get(),
        )

    def test_chunk_mode_still_requires_a_map_code(self):
        window = Window()
        window.root.button("Generate").invoke()
        self.assertEqual(window.status.get(), "Enter a map code.")

    def test_copy_chunks_copies_all_unlocked_coordinates(self):
        window = Window()

        class ImmediateThread:
            def __init__(self, target, daemon):
                self.target = target

            def start(self):
                self.target()

        with unittest.mock.patch("app.fetch_unlocked_ids", return_value=[12850, 12594]):
            with unittest.mock.patch("app.threading.Thread", ImmediateThread):
                window.code.set("BQE")
                window.root.button("Generate").invoke()

        window.root.button("Copy chunks").invoke()
        self.assertEqual(window.root.clipboard, "49,50 50,50")
        self.assertEqual(window.status.get(), "Copied unlocked chunks.")


if __name__ == "__main__":
    unittest.main()
