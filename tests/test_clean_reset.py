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

    def test_strip_enhanced_lrc_tags(self):
        from LyricBar.backend.lyricmanager import Lyrics
        enhanced_raw = "[02:54.80]<02:54.80>'Cause <02:55.22>you <02:55.64>know <02:56.06>that <02:56.51>I can't <02:57.18>do <02:57.47>this <02:57.95>on <02:58.38>my <02:58.96>own <03:12.14>"
        lyrics = Lyrics.from_lrc(enhanced_raw)
        self.assertEqual(len(lyrics.lines), 1)
        self.assertEqual(lyrics.lines[0].text, "'Cause you know that I can't do this on my own")

if __name__ == "__main__":
    unittest.main()
