import unittest
import unittest.mock

import app

from border import border_loops, chunk_id_to_grid, format_borders, marker_positions


def ids_for(grids):
    return [(grid_x - 29) * 256 - (71 - grid_y) + 7495 for grid_x, grid_y in grids]


class GridTests(unittest.TestCase):
    def test_origin_ids(self):
        self.assertEqual(chunk_id_to_grid(7494), (29, 70))
        self.assertEqual(chunk_id_to_grid(7495), (29, 71))
        self.assertEqual(chunk_id_to_grid(7750), (30, 70))
        self.assertEqual(chunk_id_to_grid(7751), (30, 71))

    def test_bqe_example_ids(self):
        self.assertEqual(chunk_id_to_grid(13624), (53, 56))
        self.assertEqual(chunk_id_to_grid(13625), (53, 57))
        self.assertEqual(chunk_id_to_grid(13626), (53, 58))
        self.assertEqual(chunk_id_to_grid(13882), (54, 58))

    def test_marker_positions(self):
        self.assertEqual(marker_positions(4), [0, 21, 42, 63])
        self.assertEqual(marker_positions(5), [0, 16, 32, 47, 63])
        self.assertEqual(marker_positions(2), [0, 63])


class OuterBorderTests(unittest.TestCase):
    def test_single_grid(self):
        self.assertEqual(
            format_borders([12850], 4),
            "\n".join([
                "(50, 50)0 - 63",
                "(50, 50)21 - 63",
                "(50, 50)42 - 63",
                "(50, 50)63 - 63",
                "(50, 50)63 - 42",
                "(50, 50)63 - 21",
                "(50, 50)63 - 0",
                "(50, 50)42 - 0",
                "(50, 50)21 - 0",
                "(50, 50)0 - 0",
                "(50, 50)0 - 21",
                "(50, 50)0 - 42",
            ]),
        )

    def test_shared_edge_is_omitted_and_seam_is_kept(self):
        text = format_borders([12594, 12850], 4)
        self.assertEqual(
            text,
            "\n".join([
                "(49, 50)0 - 63",
                "(49, 50)21 - 63",
                "(49, 50)42 - 63",
                "(49, 50)63 - 63",
                "(50, 50)0 - 63",
                "(50, 50)21 - 63",
                "(50, 50)42 - 63",
                "(50, 50)63 - 63",
                "(50, 50)63 - 42",
                "(50, 50)63 - 21",
                "(50, 50)63 - 0",
                "(50, 50)42 - 0",
                "(50, 50)21 - 0",
                "(50, 50)0 - 0",
                "(49, 50)63 - 0",
                "(49, 50)42 - 0",
                "(49, 50)21 - 0",
                "(49, 50)0 - 0",
                "(49, 50)0 - 21",
                "(49, 50)0 - 42",
            ]),
        )
        self.assertNotIn("(49, 50)63 - 42", text)
        self.assertNotIn("(50, 50)0 - 42", text)

    def test_five_markers_on_one_grid(self):
        lines = format_borders([12850], 5).splitlines()
        self.assertEqual(lines[0], "(50, 50)0 - 63")
        self.assertEqual(lines[1], "(50, 50)16 - 63")
        self.assertEqual(lines[2], "(50, 50)32 - 63")
        self.assertEqual(lines[3], "(50, 50)47 - 63")
        self.assertEqual(lines[4], "(50, 50)63 - 63")
        self.assertEqual(len(lines), 16)

    def test_corner_touch_is_two_areas(self):
        loops = format_borders([12850, 13107], 4).split("\n\n")
        self.assertEqual(len(loops), 2)
        self.assertTrue(loops[0].startswith("(51, 51)0 - 63\n"))
        self.assertTrue(loops[1].startswith("(50, 50)0 - 63\n"))

    def test_border_loops_match_formatted_text(self):
        loops = border_loops([12850], 4)
        text = format_borders([12850], 4)
        self.assertEqual(
            ["\n".join(f"({gx}, {gy}){lx} - {ly}" for gx, gy, lx, ly in loop) for loop in loops],
            text.split("\n\n"),
        )
        self.assertEqual(loops[0][0], (50, 50, 0, 63))


class HoleTests(unittest.TestCase):
    def test_bqe_outer_loops_and_hole(self):
        chunk_ids = [11833, 11834, 11835, 12089, 12091, 12345, 12346, 12347, 13624, 13625, 13626, 13882]
        loops = format_borders(chunk_ids, 4).split("\n\n")
        self.assertEqual(len(loops), 3)
        self.assertTrue(loops[0].startswith("(46, 59)0 - 63\n"))
        self.assertEqual(loops[1], "\n".join([
            "(47, 58)0 - 63",
            "(47, 58)21 - 63",
            "(47, 58)42 - 63",
            "(47, 58)63 - 63",
            "(47, 58)63 - 42",
            "(47, 58)63 - 21",
            "(47, 58)63 - 0",
            "(47, 58)42 - 0",
            "(47, 58)21 - 0",
            "(47, 58)0 - 0",
            "(47, 58)0 - 21",
            "(47, 58)0 - 42",
        ]))
        self.assertTrue(loops[2].startswith("(53, 58)0 - 63\n"))
        self.assertNotIn("(47, 58)", loops[0])
        self.assertNotIn("(46, 58)63 - 42", loops[0])
        self.assertNotIn("(47, 59)21 - 0", loops[0])

    def test_hole_of_two_locked_grids_omits_their_shared_edge(self):
        chunk_ids = [10292, 10548, 10804, 11060, 10291, 11059, 10290, 10546, 10802, 11058]
        loops = format_borders(chunk_ids, 4).split("\n\n")
        self.assertEqual(len(loops), 2)
        self.assertEqual(loops[1], "\n".join([
            "(41, 51)0 - 63",
            "(41, 51)21 - 63",
            "(41, 51)42 - 63",
            "(41, 51)63 - 63",
            "(42, 51)0 - 63",
            "(42, 51)21 - 63",
            "(42, 51)42 - 63",
            "(42, 51)63 - 63",
            "(42, 51)63 - 42",
            "(42, 51)63 - 21",
            "(42, 51)63 - 0",
            "(42, 51)42 - 0",
            "(42, 51)21 - 0",
            "(42, 51)0 - 0",
            "(41, 51)63 - 0",
            "(41, 51)42 - 0",
            "(41, 51)21 - 0",
            "(41, 51)0 - 0",
            "(41, 51)0 - 21",
            "(41, 51)0 - 42",
        ]))
        self.assertNotIn("(41, 51)63 - 42", loops[1])
        self.assertNotIn("(42, 51)0 - 42", loops[1])


class GlobalHoleTests(unittest.TestCase):
    def test_locked_grid_enclosed_by_two_diagonal_areas(self):
        grids = [(30, 67), (30, 68), (31, 67), (32, 67), (32, 68), (31, 69)]
        loops = format_borders(ids_for(grids), 4).split("\n\n")
        self.assertEqual(len(loops), 3)
        hole_loops = [loop for loop in loops if loop.startswith("(31, 68)0 - 63\n")]
        self.assertEqual(len(hole_loops), 1)
        for line in hole_loops[0].splitlines():
            self.assertTrue(line.startswith("(31, 68)"), line)
        self.assertEqual(len(hole_loops[0].splitlines()), 12)

    # Grid x below 29 has no chunk id, so the ring is shifted 30 columns east.
    def test_unlocked_cell_inside_ring_is_not_part_of_hole(self):
        grids = [(x, y) for x in range(40, 45) for y in range(10, 15) if x in (40, 44) or y in (10, 14)]
        grids.append((42, 12))
        loops = format_borders(ids_for(grids), 4).split("\n\n")
        self.assertEqual(len(loops), 3)
        self.assertTrue(loops[0].startswith("(40, 14)0 - 63\n"))
        self.assertTrue(loops[1].startswith("(41, 13)0 - 63\n"))
        center = "\n".join([
            "(42, 12)0 - 63",
            "(42, 12)21 - 63",
            "(42, 12)42 - 63",
            "(42, 12)63 - 63",
            "(42, 12)63 - 42",
            "(42, 12)63 - 21",
            "(42, 12)63 - 0",
            "(42, 12)42 - 0",
            "(42, 12)21 - 0",
            "(42, 12)0 - 0",
            "(42, 12)0 - 21",
            "(42, 12)0 - 42",
        ])
        self.assertEqual(loops[2], center)
        self.assertNotIn("(42, 12)", loops[1])


class AppHelperTests(unittest.TestCase):
    def test_input_errors(self):
        self.assertEqual(app.input_error("  ", "4"), "Enter a map code.")
        self.assertEqual(app.input_error("BQE", "1"), "Enter a marker count from 2 through 64.")
        self.assertEqual(app.input_error("BQE", "65"), "Enter a marker count from 2 through 64.")
        self.assertEqual(app.input_error("BQE", "4.5"), "Enter a marker count from 2 through 64.")
        self.assertEqual(app.input_error("BQE", "\u00b2"), "Enter a marker count from 2 through 64.")
        self.assertIsNone(app.input_error(" BQE ", " 4 "))

    def test_missing_map(self):
        with unittest.mock.patch("app._read_json", return_value=None):
            with self.assertRaises(app.MapNotFound):
                app.fetch_unlocked_ids("missing")

    def test_no_unlocked_chunks(self):
        with unittest.mock.patch("app._read_json", side_effect=[{"chunks": True}, None]):
            with self.assertRaises(app.NoUnlockedChunks):
                app.fetch_unlocked_ids("bqe")

    def test_non_numeric_keys_are_ignored(self):
        with unittest.mock.patch("app._read_json", side_effect=[{"chunks": True}, {"note": "x"}]):
            with self.assertRaises(app.NoUnlockedChunks):
                app.fetch_unlocked_ids("bqe")

    def test_non_decimal_keys_are_ignored(self):
        payload = {"13624": "13624", "\u00b2": "x"}
        with unittest.mock.patch("app._read_json", side_effect=[{"chunks": True}, payload]):
            self.assertEqual(app.fetch_unlocked_ids("bqe"), [13624])

    def test_unlocked_ids(self):
        payload = {"13624": "13624", "note": "x", "13882": "13882"}
        with unittest.mock.patch("app._read_json", side_effect=[{"chunks": True}, payload]):
            self.assertEqual(app.fetch_unlocked_ids("bqe"), [13624, 13882])

    def test_network_failure(self):
        with unittest.mock.patch("app._read_json", side_effect=OSError("offline")):
            with self.assertRaises(app.MapLoadError):
                app.fetch_unlocked_ids("bqe")


if __name__ == "__main__":
    unittest.main()
