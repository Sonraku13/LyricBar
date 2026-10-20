"""
Multi-source lyrics fetcher supporting:
- lrc.red
- BiniLyrics
- BetterLyrics
- PaxSenix
- LyricsPlus
- SimpMusic
- Unison
- KuGou
- LRCLIB
- Musixmatch
- Genius
- NetEase / Deezer / Megalobiz
"""
import base64
import logging
import re
import requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
TIMEOUT = 4

def _ms_to_lrc_tag(ms):
    m = int(ms // 60000)
    s = (ms % 60000) / 1000.0
    return f"[{m:02d}:{s:05.2f}]"

def _ttml_to_lrc(ttml_text):
    if not ttml_text or not isinstance(ttml_text, str):
        return None
    p_pattern = re.compile(r'<p\b[^>]*\bbegin=[\"\']([^\"\']+)[\"\'][^>]*>(.*?)</p>', re.DOTALL | re.IGNORECASE)
    tag_pattern = re.compile(r'<[^>]+>')
    lines = []
    for match in p_pattern.finditer(ttml_text):
        begin = match.group(1)
        inner = match.group(2)
        text = tag_pattern.sub('', inner).strip()
        text = re.sub(r"[ \t]+", " ", text).strip()
        if not text:
            continue
        parts = begin.split(':')
        if len(parts) == 3:
            h, m, s = parts
            total_sec = int(h)*3600 + int(m)*60 + float(s)
        elif len(parts) == 2:
            m, s = parts
            total_sec = int(m)*60 + float(s)
        else:
            continue
        m_out = int(total_sec // 60)
        s_out = total_sec % 60
        lines.append(f"[{m_out:02d}:{s_out:05.2f}]{text}")
    return "\n".join(lines) if lines else None


def fetch_lrclib(title, artist, duration=None):
    params = {"artist_name": artist, "track_name": title}
    if duration:
        params["duration"] = int(duration)
    r = requests.get("https://lrclib.net/api/get", params=params, headers=HEADERS, timeout=TIMEOUT)
    if r.status_code == 200:
        data = r.json()
        synced = data.get("syncedLyrics")
        if synced and "[" in synced:
            return synced
    return None

def fetch_lrcred(title, artist):
    # Match via title & artist to get ISRC
    r = requests.get("https://lrc.red/search.json", params={"q": f"{artist} {title}"}, headers=HEADERS, timeout=TIMEOUT)
    if r.status_code == 200:
        data = r.json()
        hits = data.get("hits") or []
        if hits:
            isrc = hits[0].get("isrc")
            if isrc:
                lrc_res = requests.get(f"https://lrc.red/s/{isrc}.lrc", headers=HEADERS, timeout=TIMEOUT)
                if lrc_res.status_code == 200 and "[" in lrc_res.text:
                    return lrc_res.text
                ttml_res = requests.get(f"https://lrc.red/s/{isrc}.ttml", headers=HEADERS, timeout=TIMEOUT)
                if ttml_res.status_code == 200:
                    converted = _ttml_to_lrc(ttml_res.text)
                    if converted:
                        return converted
    return None

def fetch_lyricsplus_and_binilyrics(title, artist):
    mirrors = [
        "https://lyricsplus.binimum.org",
        "https://lyricsplus.prjktla.my.id",
    ]
    for m in mirrors:
        try:
            r = requests.get(f"{m}/v2/lyrics/get", params={"title": title, "artist": artist}, headers=HEADERS, timeout=TIMEOUT)
            if r.status_code == 200:
                data = r.json()
                lyrics_list = data.get("lyrics")
                if lyrics_list and isinstance(lyrics_list, list):
                    lrc_lines = []
                    for item in lyrics_list:
                        ms = item.get("time", 0)
                        txt = item.get("text", "").strip()
                        if txt:
                            lrc_lines.append(f"{_ms_to_lrc_tag(ms)}{txt}")
                    if lrc_lines:
                        return "\n".join(lrc_lines)
        except Exception:
            continue
    return None

def fetch_unison(title, artist):
    r = requests.get("https://unison.boidu.dev/lyrics", params={"song": title, "artist": artist}, headers=HEADERS, timeout=TIMEOUT)
    if r.status_code == 200:
        data = r.json()
        if data.get("success") and isinstance(data.get("data"), dict):
            raw = data["data"].get("lyrics", "")
            fmt = data["data"].get("format", "")
            if fmt == "ttml" or "<tt" in raw:
                return _ttml_to_lrc(raw)
            elif "[" in raw:
                return raw
    return None

def fetch_betterlyrics(title, artist):
    r = requests.get("https://lyrics-api.boidu.dev/getLyrics", params={"s": title, "a": artist}, headers=HEADERS, timeout=TIMEOUT)
    if r.status_code == 200:
        data = r.json()
        ttml = data.get("ttml")
        if ttml:
            return _ttml_to_lrc(ttml)
    return None

def fetch_kugou(title, artist):
    search_url = "http://krcs.kugou.com/search"
    keyword = f"{artist} - {title}" if artist else title
    r = requests.get(search_url, params={"ver": "1", "man": "yes", "client": "mobi", "keyword": keyword, "duration": "0"}, headers=HEADERS, timeout=TIMEOUT)
    if r.status_code == 200:
        candidates = r.json().get("candidates") or []
        if candidates:
            c = candidates[0]
            dl = requests.get("https://lyrics.kugou.com/download", params={"ver": "1", "client": "pc", "id": c["id"], "accesskey": c["accesskey"], "fmt": "lrc", "charset": "utf8"}, headers=HEADERS, timeout=TIMEOUT)
            if dl.status_code == 200:
                raw_b64 = dl.json().get("content")
                if raw_b64:
                    lrc = base64.b64decode(raw_b64).decode("utf-8", errors="ignore")
                    if "[" in lrc:
                        return lrc
    return None

def fetch_paxsenix(title, artist):
    # PaxSenix aggregate query for Apple Music / Spotify endpoints
    try:
        r = requests.get("https://lyrics.paxsenix.org/apple-music/lyrics", params={"title": title, "artist": artist}, headers=HEADERS, timeout=TIMEOUT)
        if r.status_code == 200:
            data = r.json()
            if data.get("lrc") and "[" in data["lrc"]:
                return data["lrc"]
            if data.get("ttml"):
                return _ttml_to_lrc(data["ttml"])
    except Exception:
        pass
    return None

def fetch_simpmusic(title, artist):
    try:
        headers = {
            "User-Agent": "SimpMusic/1.0.0 (Linux; Android 14)",
            "Referer": "https://lyrics.simpmusic.org/",
            "Origin": "https://lyrics.simpmusic.org"
        }
        r = requests.get("https://api-lyrics.simpmusic.org/v1/search", params={"q": f"{artist} {title}"}, headers=headers, timeout=TIMEOUT)
        if r.status_code == 200:
            items = r.json().get("data") or []
            if items:
                v_id = items[0].get("videoId")
                if v_id:
                    dl = requests.get(f"https://api-lyrics.simpmusic.org/v1/{v_id}", headers=headers, timeout=TIMEOUT)
                    if dl.status_code == 200:
                        d = dl.json().get("data")
                        if isinstance(d, list) and d:
                            d = d[0]
                        synced = d.get("syncedLyrics")
                        if synced and "[" in synced:
                            return synced
    except Exception:
        pass
    return None

ALL_CUSTOM_PROVIDERS = [
    ("LRCLIB", fetch_lrclib),
    ("lrc.red", fetch_lrcred),
    ("LyricsPlus", fetch_lyricsplus_and_binilyrics),
    ("Unison", fetch_unison),
    ("BetterLyrics", fetch_betterlyrics),
    ("KuGou", fetch_kugou),
    ("PaxSenix", fetch_paxsenix),
    ("SimpMusic", fetch_simpmusic),
]

def search_multi_source(title, artist, duration=None):
    """
    Tries in sequence:
    1. LRCLIB
    2. lrc.red
    3. LyricsPlus / BiniLyrics
    4. Unison
    5. BetterLyrics
    6. KuGou
    7. PaxSenix
    8. SimpMusic
    """
    for name, fetcher in ALL_CUSTOM_PROVIDERS:
        try:
            if name == "LRCLIB":
                lrc = fetcher(title, artist, duration)
            else:
                lrc = fetcher(title, artist)
            if lrc and "[" in lrc:
                logging.info(f"Lyric found via custom provider: {name}")
                return lrc, name
        except Exception as e:
            logging.debug(f"Provider {name} error: {e}")
            continue
    return None, None
