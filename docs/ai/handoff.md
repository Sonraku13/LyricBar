# Handoff — LyricBar

## Updated
2026-10-20

## Branch
`master`

## Source HEAD
`f33064c`

## Current task
Selesai:
1. Dynamic frosted-glass bar (Telegram style) + Material 3 palette extraction dari album artwork SMTC via Pillow (`extract_m3_palette()` di `LyricBar/themes.py`).
2. Fix deadlock/freeze GUI LyricBar: pindah polling SMTC Windows Runtime ke worker background `QThread` (`SystemPollingWorker` di `nowplayingsystem.py`) agar `asyncio.run()` tidak memblokir COM STA/PyQt main thread.
3. Optimasi thumbnail SMTC: cache byte stream per track change dan close stream handle, tidak read berulang tiap interval 25ms.
4. Guard `STTMaintainer`: lewati inisialisasi Vosk model dan PyAudio jika `STT_MODEL_PATH` kosong.
5. Unit tests `test_m3_palette.py` lulus (`python -m unittest tests/test_m3_palette.py`).
6. LyricBar aktif berjalan di background (PID: 12144, `Responding: True`) menampilkan lirik tersinkron dan tema dinamis dari YouTube Music (Brave).

## Working tree
Status Git `LyricBar` (`git status --short`):
- Modified:
  - `LyricBar/backend/sttmaintainer.py` (guard STT / PyAudio)
  - `LyricBar/nowplaying/nowplayingsystem.py` (worker `QThread`, thumbnail cache & handle disposal)
  - `LyricBar/themes.py` (M3 palette & frosted glass styling)
  - `LyricBar/utils/dataclasses.py` (field `thumbnail_bytes` pada `TrackInfo`)
- Untracked:
  - `docs/ai/architecture.md`
  - `docs/ai/handoff.md`
  - `tests/test_m3_palette.py`
  - `lyrics/` (cache file JSON lirik lokal)

## Relevant files
| Path | Alasan |
|---|---|
| `LyricBar/nowplaying/nowplayingsystem.py` | SMTC polling worker `QThread` + media properties & thumbnail extraction |
| `LyricBar/themes.py` | `extract_m3_palette()`, dynamic styling fallback, translucent frosted glass bar |
| `LyricBar/backend/sttmaintainer.py` | Guard STT & PyAudio initialization |
| `LyricBar/utils/dataclasses.py` | `TrackInfo` dataclass dengan `thumbnail_bytes` |
| `tests/test_m3_palette.py` | Unit tests untuk M3 palette generator |
| `settings.yaml` | Konfigurasi appearance, Brave tracking, and providers |

## Decisions
- Polling WinRT SMTC wajib di thread terpisah (`QThread` MTA) dengan komunikasi ke main thread lewat `pyqtSignal`. Memanggil `asyncio.run()` di main thread PyQt menyebabkan deadlock pesan COM Windows.
- Artwork extraction dilakukan sekali saat track berganti (`track_key = (artist, title)`), dengan `DataReader.close()` dan `stream.close()` agar handle WinRT tidak bocor.
- Opacity frosted glass bar diset 80% (`#rrggbbaa`) dengan border highlight kontras tipis dan Material 3 vibrant accent color untuk teks/progress bar.
- Dokumentasi `docs/ai/` ditaruh di dalam folder repo `LyricBar/` sendiri, tidak mencemari root.

## Verification
- Unit test: `python -m unittest tests/test_m3_palette.py` (2 tests, OK).
- Script test 3s PyQt event loop: track live YouTube Music terdeteksi dan lirik ter-render tanpa hang.
- Live background process: `Get-Process` menunjukkan PID 12144 `Responding: True`.

## Next step
1. Evaluasi tampilan visual dynamic palette pada berbagai lagu YouTube Music.
2. Tunggu instruksi user jika ingin git commit untuk perubahan di subproject `LyricBar`.
