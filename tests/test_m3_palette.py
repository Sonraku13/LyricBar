import unittest
from io import BytesIO
from PIL import Image
from LyricBar.themes import extract_m3_palette

class TestM3FrostedPalette(unittest.TestCase):
    def test_extract_m3_palette_red_image(self):
        img = Image.new("RGB", (64, 64), color=(200, 30, 30))
        buf = BytesIO()
        img.save(buf, format="PNG")
        palette = extract_m3_palette(buf.getvalue())
        self.assertIsNotNone(palette)
        self.assertIn("font-color", palette)
        self.assertIn("progress-color", palette)
        self.assertIn("background-color", palette)
        # Background should have frosted alpha channel (translucent hex #rrggbbaa)
        self.assertEqual(len(palette["background-color"]), 9)
        self.assertEqual(palette["background-color"][-2:].lower(), "cc")

    def test_extract_m3_palette_empty(self):
        self.assertIsNone(extract_m3_palette(None))
        self.assertIsNone(extract_m3_palette(b""))

if __name__ == "__main__":
    unittest.main()
