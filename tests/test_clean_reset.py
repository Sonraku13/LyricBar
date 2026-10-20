import unittest
from LyricBar.utils.dataclasses import TrackInfo
from LyricBar.themes import get_style, STYLES, load_themes
from LyricBar.backend.lyricmanager import _is_clean_title

class TestCleanReset(unittest.TestCase):
    def setUp(self):
        load_themes()

    def test_default_style_clean_transparent(self):
        track = TrackInfo(title="Test Song", artist="Test Artist", is_music=True)
        style = get_style(track)
        bg = style.get("background-color") or style.get("background", {}).get("color")
        self.assertEqual(bg, (0, 0, 0, 0))

    def test_clean_title_removes_noise(self):
        title_with_noise = "Stay (Official Music Video) [Remastered HD]"
        cleaned = _is_clean_title(title_with_noise)
        self.assertEqual(cleaned, "Stay")

        yt_title = "Numb - Official Video"
        cleaned_yt = _is_clean_title(yt_title)
        self.assertEqual(cleaned_yt, "Numb")

if __name__ == "__main__":
    unittest.main()
