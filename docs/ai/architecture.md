# LyricBar — Architecture

## Ringkasan
Aplikasi desktop Windows (PyQt5) untuk menampilkan lirik lagu tersinkron di taskbar, terintegrasi dengan browser Brave (YouTube Music) melalui Windows System Media Transport Controls (SMTC) API (WinRT).

## Stack
- Python 3.12
- GUI: PyQt5, QFramelessWindow, pywinstyles (Aero effect)
- Media Info: WinRT (`winsdk` Windows Media Control & Storage Streams)
- Lyrics Provider: `syncedlyrics` (Lrclib, NetEase, Musixmatch, Deezer, Megalobiz)
- Dynamic Styling: Pillow (Material 3 palette extraction dari album artwork)

## Arsitektur & Threading
1. **SMTC Polling (`LyricBar/nowplaying/nowplayingsystem.py`)**:
   - `SystemPollingWorker(QThread)`: Polling background thread (MTA) untuk query metadata & timeline SMTC via `asyncio.run()`. Mencegah deadlock COM STA di PyQt main thread.
   - Komunikasi ke UI thread menggunakan `pyqtSignal(object)`.
   - Thumbnail extraction: `DataReader` membaca stream byte dari cover album Brave SMTC, di-cache per `(artist, title)`, dan stream di-close.
2. **Dynamic Theming (`LyricBar/themes.py`)**:
   - `extract_m3_palette()`: Resampling artwork ke 48x48 LANCZOS, ekstrak accent vibran Material 3 dan warna frosted glass translucent (80% opacity `#rrggbbaa`).
   - `get_style()`: Fallback otomatis ke dynamic palette jika track tidak punya tema artis statis.
3. **Lyrics Engine (`LyricBar/backend/`)**:
   - `LyricsMaintainer`: Mengelola cache file lirik di folder `lyrics/` dan fetch lirik melalui `syncedlyrics`.
   - `STTMaintainer`: Fallback Speech-To-Text (Vosk/PyAudio), diguard jika `STT_MODEL_PATH` kosong.
4. **UI (`LyricBar/ui/ui.py`)**:
   - `LyricsDisplay(QWidget)`: Window frameless, translucent, stays on top di atas taskbar Windows.
   - `LyricLabel`: Render teks lirik dan progress bar berbasis persentase lagu.

## Command
- Run: `python main.py`
- Test: `python -m unittest discover tests` atau `python -m unittest tests/test_m3_palette.py`
