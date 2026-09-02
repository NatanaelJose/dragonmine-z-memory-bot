import unittest

from capture import memory_capture_rect


class MemoryCaptureTests(unittest.TestCase):
    def test_uses_central_multi_row_region(self):
        self.assertEqual(
            memory_capture_rect((0, 23, 1920, 1009)),
            (192, 275, 1536, 575),
        )

    def test_keeps_fast_region_through_four_rows(self):
        self.assertEqual(
            memory_capture_rect((0, 23, 1920, 1009), 52),
            (192, 275, 1536, 575),
        )

    def test_expands_for_fifth_row_before_level_101(self):
        self.assertEqual(
            memory_capture_rect((0, 23, 1920, 1009), 53),
            (192, 235, 1536, 676),
        )

    def test_expands_near_full_height_for_six_rows(self):
        self.assertEqual(
            memory_capture_rect((0, 23, 1920, 1009), 75),
            (192, 195, 1536, 776),
        )


if __name__ == "__main__":
    unittest.main()
