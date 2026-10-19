import base64
import unittest

from export import encode_string, pack_tile


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

    def test_one_grid_count_60_suggests_59(self):
        result = export_borders([12850], 60, "G")
        self.assertEqual(result.error, "Too many tiles (236). Try a marker count of 59 or less.")
        self.assertEqual(result.first, "")
        self.assertEqual(result.second, "")
        self.assertEqual(result.first_label, "")
        self.assertEqual(result.second_label, "")
        self.assertEqual(result.tile_count, 236)

    def test_tall_column_count_2_is_too_big(self):
        ids = ids_for([(50, 10 + row) for row in range(59)])
        result = export_borders(ids, 2, "BIG")
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
