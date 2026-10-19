# LyricBar (Fork) 🎵

> Windows 11 Taskbar Lyrics with Dynamic Frosted-Glass UI (Telegram-style) and Material 3 palette extraction from album artwork. Tailored for YouTube Music on Brave Browser and Spotify.

Forked from [silora/LyricBar](https://github.com/silora/LyricBar).

---

## ✨ Features Added in This Fork

1. **Brave Browser & YouTube Music SMTC Support**:
   - Native integration with Windows System Media Transport Controls (WinRT SMTC).
   - Case-insensitive target app matching (`brave.exe` / `Brave`).
   - Clean title parser removing `(Official Video)`, `[Official Audio]`, and extraneous metadata.

2. **Material 3 Dynamic Palette & Frosted Glass**:
   - Automatic extraction of vibrant Material 3 accent colors from album covers via Pillow.
   - Telegram-style frosted glass translucent background (`80%` opacity) with crisp outline highlights.
   - Zero-polling overhead: thumbnail parsed once per track change, stream handles cleanly disposed.

3. **Rock-Solid Windows COM STA Threading**:
   - Dedicated `SystemPollingWorker(QThread)` in MTA mode for WinRT async calls.
   - Eliminates UI thread deadlocks and app freezing when interacting with Windows Media APIs.

4. **Modern `syncedlyrics` Compatibility**:
   - Unwraps `Lyrics` objects (`synced` / `unsynced` attributes) from current `syncedlyrics` library versions without crash.

5. **Safe STT Fallback**:
   - Guarded speech-to-text initialization; prevents Vosk / PyAudio hangs when models are unconfigured.

---

## 🚀 Quick Start

### 1. Requirements
- Windows 10 / 11
- Python 3.10+
- Brave Browser (playing YouTube Music) or Spotify

### 2. Installation
```powershell
git clone https://github.com/Sonraku13/LyricBar.git
cd LyricBar
pip install -r requirements.txt
```

### 3. Configuration (`settings.yaml`)
Ensure your `settings.yaml` tracks your browser or player:
```yaml
Tracking App: 'Brave' # or 'Spotify'
Taskbar Height: 48
Lyric Offset: 350
Default Theme: 'Default - white'
```

### 4. Run
```powershell
python main.py
```

---

## 🧪 Testing

Run test suite:
```powershell
python -m unittest discover tests
```

---

## 📜 License
GPL-3.0 License — see original repository [silora/LyricBar](https://github.com/silora/LyricBar).
