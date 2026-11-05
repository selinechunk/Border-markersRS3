import base64
import unittest

from border import grid_to_chunk_id
from decode import decode_string
from export import encode_string, export_walk, pack_tile


def decode_body(text):
    body = text[3:]
    return base64.urlsafe_b64decode(body + "=" * ((4 - len(body) % 4) % 4))


def read_leb(buf, i):
    value = 0
    shift = 0
    while True:
        byte = buf[i]
        i += 1
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return value, i
        shift += 7


class EncodeStringTests(unittest.TestCase):
    def test_single_tile_pack_and_header(self):
        text = encode_string("test", [(50, 50, 36, 22)])
        data = decode_body(text)
        self.assertEqual(data[0], 0x21)
        self.assertEqual(data[1], 4)
        self.assertEqual(data[2:6], b"test")
        self.assertEqual(data[6], 1)
        packed, _ = read_leb(data, 7)
        self.assertEqual(packed, 15780148)
        self.assertEqual(pack_tile((50, 50, 36, 22)), 15780148)

    def test_custom_color_is_encoded_as_opaque_rgba(self):
        text = encode_string("purple", [(50, 50, 36, 22)], "#c864ff")
        self.assertEqual(
            decode_string(text).style,
            bytes.fromhex("01c864ffffa050cc8c0c14"),
        )

    def test_outline_and_fill_colors_can_be_selected_independently(self):
        text = encode_string("purple", [(50, 50, 36, 22)], "#c864ff", "#38b84a")
        self.assertEqual(
            decode_string(text).style,
            bytes.fromhex("01c864ffff38b84a8c0c14"),
        )

    def test_export_borders_uses_selected_color(self):
        from export import export_borders

        result = export_borders([12850], 2, "Purple", "#c864ff")
        self.assertIsNone(result.error)
        self.assertEqual(
            decode_string(result.first).style,
            bytes.fromhex("01c864ffffa050cc8c0c14"),
        )

    def test_configurable_import_size_can_create_more_than_two_strings(self):
        result = export_borders(
            [12850], 59, "G", max_total_tiles=232, max_tiles_per_import=50
        )
        self.assertIsNone(result.error)
        self.assertEqual(len(result.strings), 5)
        self.assertEqual(result.labels, [
            "Tiles 1–50",
            "Tiles 51–100",
            "Tiles 101–150",
            "Tiles 151–200",
            "Tiles 201–232",
        ])
        self.assertEqual(decode_string(result.strings[2]).name, "G3")

    def test_one_string_per_border_chunk_preserves_the_full_border(self):
        from export import export_borders

        chunk_ids = [12850, 12594]
        whole = export_borders(chunk_ids, 4, "BQE")
        result = export_borders(chunk_ids, 4, "BQE", one_per_chunk=True)
        decoded = [decode_string(text) for text in result.strings]

        self.assertIsNone(result.error)
        self.assertEqual(
            {tile for marker_string in decoded for tile in marker_string.tiles},
            {tile for text in whole.strings for tile in decode_string(text).tiles},
        )
        self.assertTrue(all(len({tile[:2] for tile in item.tiles}) == 1 for item in decoded))
        self.assertEqual(
            result.labels,
            [
                f"Chunk {grid_to_chunk_id(grid_x, grid_y)}"
                for grid_x, grid_y in sorted(
                    {tile[:2] for item in decoded for tile in item.tiles},
                    key=lambda cell: (cell[1], cell[0]),
                )
            ],
        )
        self.assertEqual(
            {item.name for item in decoded},
            {f"BQE-{grid_to_chunk_id(*cell)}" for cell in {tile[:2] for item in decoded for tile in item.tiles}},
        )

    def test_adding_a_distant_chunk_keeps_existing_import_strings(self):
        from export import export_borders

        original = export_borders([12850], 4, "BQE", one_per_chunk=True)
        expanded = export_borders([12850, 7495], 4, "BQE", one_per_chunk=True)

        self.assertIn(original.first, expanded.strings)
        self.assertEqual(len(expanded.strings), len(original.strings) + 1)

    def test_per_chunk_imports_still_honor_the_import_tile_limit(self):
        from export import export_borders

        result = export_borders([12850], 59, "G", one_per_chunk=True, max_tiles_per_import=50)

        self.assertEqual(len(result.strings), 5)
        self.assertTrue(all(label.startswith("Chunk ") for label in result.labels))
        self.assertEqual(
            [label.rsplit(" ", 1)[-1].rstrip(")") for label in result.labels],
            ["1", "2", "3", "4", "5"],
        )

    def test_multiple_whole_chunks_fit_in_one_import_string(self):
        tiles = [
            (40 + chunk_index, 50, local_x, 0)
            for chunk_index in range(12)
            for local_x in range(10)
        ]
        result = export_walk(
            lambda _count: tiles,
            4,
            "G",
            max_tiles_per_import=127,
            whole_chunks_per_import=True,
        )
        self.assertIsNone(result.error)
        chunk_ids = [
            grid_to_chunk_id(40 + chunk_index, 50)
            for chunk_index in range(12)
        ]
        decoded_strings = [decode_string(text) for text in result.strings]
        self.assertEqual(
            sum(len(item.tiles) for item in decoded_strings), 120
        )
        self.assertGreater(len(result.strings), 1)
        self.assertTrue(all(len(item.name) <= 32 for item in decoded_strings))
        self.assertTrue(
            all(
                len({tile[:2] for tile in item.tiles}) > 1
                for item in decoded_strings
            )
        )
        self.assertEqual(
            {
                chunk_id
                for item in decoded_strings
                for chunk_id in map(
                    lambda grid: grid_to_chunk_id(*grid),
                    {tile[:2] for tile in item.tiles},
                )
            },
            set(chunk_ids),
        )
        for label, item in zip(result.labels, decoded_strings):
            ids = [
                str(grid_to_chunk_id(*grid))
                for grid in sorted(
                    {tile[:2] for tile in item.tiles},
                    key=lambda cell: (cell[1], cell[0]),
                )
            ]
            self.assertEqual(label, f"Chunks {', '.join(ids)}")
            self.assertEqual(item.name, f"G-{'-'.join(ids)}")

    def test_whole_chunk_title_limit_requires_a_shorter_map_name(self):
        result = export_walk(
            lambda _count: [(40, 50, 0, 0)],
            4,
            "X" * 27,
            whole_chunks_per_import=True,
        )

        self.assertEqual(
            result.error,
            "Chunk 10290 cannot fit in the 32-character marker title limit. "
            "Use a shorter map name.",
        )

    def test_whole_chunk_groups_obey_the_import_limit_without_splitting(self):
        tiles = [
            (40 + chunk_index, 50, local_x, 0)
            for chunk_index in range(5)
            for local_x in range(10)
        ]
        result = export_walk(
            lambda _count: tiles,
            4,
            "G",
            max_tiles_per_import=25,
            whole_chunks_per_import=True,
        )
        decoded = [decode_string(text) for text in result.strings]

        self.assertIsNone(result.error)
        self.assertEqual([len(item.tiles) for item in decoded], [20, 20, 10])
        self.assertTrue(all(len(item.tiles) <= 25 for item in decoded))
        self.assertTrue(
            all(
                len({tile[:2] for tile in item.tiles}) == len(item.tiles) // 10
                for item in decoded
            )
        )
        chunk_ids = [grid_to_chunk_id(40 + chunk_index, 50) for chunk_index in range(5)]
        self.assertEqual(
            result.labels,
            [
                f"Chunks {chunk_ids[0]}, {chunk_ids[1]}",
                f"Chunks {chunk_ids[2]}, {chunk_ids[3]}",
                f"Chunks {chunk_ids[4]}",
            ],
        )
        self.assertEqual(
            [item.name for item in decoded],
            [
                f"G-{chunk_ids[0]}-{chunk_ids[1]}",
                f"G-{chunk_ids[2]}-{chunk_ids[3]}",
                f"G-{chunk_ids[4]}",
            ],
        )

    def test_whole_chunk_mode_reports_a_chunk_larger_than_the_import_limit(self):
        tiles = [(40, 50, local_x, 0) for local_x in range(10)]
        result = export_walk(
            lambda _count: tiles,
            4,
            "G",
            max_tiles_per_import=9,
            whole_chunks_per_import=True,
        )

        self.assertEqual(
            result.error,
            "Chunk 10290 has 10 markers, exceeding the per-import limit of 9. "
            "Increase the limit or lower the marker count.",
        )
        self.assertEqual(result.strings, [])

    def test_web_bridge_supports_multiple_whole_chunks_per_import(self):
        from web_core import generate_chunks

        result = generate_chunks(
            [12850, 12594], 4, "BQE", whole_chunks_per_import=True
        )

        self.assertIsNone(result["error"])
        self.assertTrue(all(label.startswith("Chunks ") for label in result["labels"]))
        decoded = [decode_string(text) for text in result["strings"]]
        self.assertTrue(all(len(item.tiles) <= 127 for item in decoded))
        self.assertTrue(
            any(len({tile[:2] for tile in item.tiles}) > 1 for item in decoded)
        )
        for label, item in zip(result["labels"], decoded):
            ids = [
                str(grid_to_chunk_id(grid_x, grid_y))
                for grid_x, grid_y in sorted(
                    {tile[:2] for tile in item.tiles},
                    key=lambda cell: (cell[1], cell[0]),
                )
            ]
            self.assertEqual(label, f"Chunks {', '.join(ids)}")
            self.assertEqual(item.name, f"BQE-{'-'.join(ids)}")

    def test_rollable_chunk_filter_keeps_only_adjacent_chunk_markers(self):
        grids = [(50, 50), (49, 50), (50, 51), (49, 51)]
        chunk_ids = ids_for(grids)
        selected_id = ids_for([(50, 50)])[0]
        complete = export_borders(chunk_ids, 4, "MAP")
        filtered = export_borders(
            chunk_ids, 4, "MAP", rollable_chunk_ids=[selected_id]
        )
        filtered_tiles = {
            tile
            for text in filtered.strings
            for tile in decode_string(text).tiles
        }

        self.assertIsNone(filtered.error)
        self.assertLess(filtered.tile_count, complete.tile_count)
        self.assertTrue(filtered_tiles)
        self.assertEqual(
            {tile[:2] for tile in filtered_tiles}, {(49, 50), (50, 51)}
        )

    def test_rollable_chunk_filter_reports_when_no_border_hits_selected_chunks(self):
        result = export_borders([12850], 4, "MAP", rollable_chunk_ids=[])

        self.assertEqual(
            result.error,
            "No border markers fall within chunks adjacent to selected rollable chunks.",
        )
        self.assertEqual(result.tile_count, 0)
        self.assertEqual(result.strings, [])

    def test_web_bridge_supports_rollable_chunk_filter(self):
        from web_core import generate_chunks

        result = generate_chunks(
            [12850, 12594],
            4,
            "BQE",
            rollable_chunk_ids=[12850],
        )
        decoded = [decode_string(text) for text in result["strings"]]

        self.assertIsNone(result["error"])
        self.assertTrue(decoded)
        self.assertTrue(all({tile[:2] for tile in item.tiles} == {(49, 50)} for item in decoded))

    def test_web_bridge_supports_per_chunk_imports(self):
        from web_core import generate_chunks

        result = generate_chunks([12850, 12594], 4, "BQE", one_per_chunk=True)

        self.assertIsNone(result["error"])
        self.assertGreater(len(result["strings"]), 1)
        self.assertTrue(all(label.startswith("Chunk ") for label in result["labels"]))

    def test_configurable_total_limit_refuses_too_many_tiles(self):
        result = export_borders([12850], 2, "G", max_total_tiles=3)
        self.assertEqual(result.error, "That map is too big, sorry.")
        self.assertEqual(result.tile_count, 4)

    def test_import_limit_cannot_exceed_single_byte_tile_count(self):
        with self.assertRaisesRegex(ValueError, "between 1 and 255"):
            export_borders([12850], 2, "G", max_tiles_per_import=256)

    def test_east2_rebuilds(self):
        self.assertEqual(
            encode_string("east2", [(50, 50, 36, 22), (50, 50, 38, 22)]),
            "TM2IQVlYXN0MgK0ksMHCAFk_2n_UMxUjAwUAAA",
        )

    def test_row_10_12_14_rebuilds(self):
        self.assertEqual(
            encode_string(
                "1022 1222 1422",
                [(50, 50, 10, 22), (50, 50, 12, 22), (50, 50, 14, 22)],
            ),
            "TM2IQ4xMDIyIDEyMjIgMTQyMgOcg8MHGAgBZP9p_1DMVIwMFAAAAA",
        )

    def test_chunk_51_51_13_tiles_rebuilds(self):
        tiles = [
            (51, 51, 63, 0),
            (51, 51, 63, 1),
            (51, 51, 61, 0),
            (51, 51, 61, 1),
            (51, 51, 58, 0),
            (51, 51, 58, 1),
            (51, 51, 56, 0),
            (51, 51, 55, 1),
            (51, 51, 54, 2),
            (51, 51, 54, 7),
            (51, 51, 53, 10),
            (51, 51, 52, 9),
            (51, 51, 59, 10),
        ]
        text = encode_string("51,51", tiles)
        self.assertTrue(text.startswith("TM2IQU1MSw1MQ2r9MMHA"))
        self.assertEqual(
            text,
            "TM2IQU1MSw1MQ2r9MMHAREkBRoIARkBBwEjAWT_af9QzFSMDBQAAAAAAAAAAAAAAAAA",
        )


from export import ExportResult, export_borders


def ids_for(grids):
    return [(grid_x - 29) * 256 - (71 - grid_y) + 7495 for grid_x, grid_y in grids]


BQE_GRIDS = [(47, 51), (48, 49), (48, 50), (48, 51), (49, 50), (50, 50)]


class ExportBordersTests(unittest.TestCase):
    def test_one_grid_count_33_splits_at_127(self):
        result = export_borders([12850], 33, "G")
        self.assertIsNone(result.error)
        self.assertEqual(result.tile_count, 128)
        self.assertEqual(result.first_label, "Tiles 1–127")
        self.assertEqual(result.second_label, "Tiles 128–128")
        self.assertTrue(result.first.startswith("TM2"))
        self.assertTrue(result.second.startswith("TM2"))
        self.assertNotEqual(result.first, result.second)

    def test_one_grid_count_59_is_232_and_splits(self):
        result = export_borders([12850], 59, "G")
        self.assertIsNone(result.error)
        self.assertEqual(result.tile_count, 232)
        self.assertEqual(result.first_label, "Tiles 1–127")
        self.assertEqual(result.second_label, "Tiles 128–232")
        self.assertTrue(result.second.startswith("TM2"))

    def test_one_grid_count_60_passes_new_default_limit(self):
        result = export_borders([12850], 60, "G")
        self.assertIsNone(result.error)
        self.assertEqual(result.tile_count, 236)
        self.assertEqual(result.first_label, "Tiles 1–127")
        self.assertEqual(result.second_label, "Tiles 128–236")

    def test_tall_column_count_2_is_too_big(self):
        ids = ids_for([(50, 10 + row) for row in range(59)])
        result = export_borders(ids, 2, "BIG", max_total_tiles=232)
        self.assertEqual(result.error, "That map is too big, sorry.")
        self.assertGreater(result.tile_count, 232)

    def test_bqe_count_9_is_one_string(self):
        result = export_borders(ids_for(BQE_GRIDS), 9, "BQE")
        self.assertIsNone(result.error)
        self.assertEqual(result.tile_count, 119)
        self.assertEqual(result.first_label, "Tiles 1–119")
        self.assertEqual(result.second_label, "")
        self.assertEqual(result.second, "")
        self.assertTrue(result.first.startswith("TM2"))
