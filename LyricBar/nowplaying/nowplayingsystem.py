import asyncio
from datetime import datetime, timedelta
import json
import logging
import re
import subprocess
import time

from PyQt5.QtCore import QThread, pyqtSignal
from winsdk.windows.media.control import (
    GlobalSystemMediaTransportControlsSessionManager as MediaManager,
)
from winsdk.windows.storage.streams import DataReader

from .nowplaying import NowPlaying
from ..globalvariables import TRACKING_APP
from ..utils.dataclasses import PlayingInfo, PlayingStatusTrigger, TrackInfo



def _clean_track_title(title: str, artist: str = None) -> str:
    """Clean track title to remove YouTube noise and extract artist if embedded."""
    if not title:
        return None
    title = title.strip()
    # Remove common YouTube noise
    title = re.sub(r'\s*\(.*?\)\s*$', '', title, flags=re.IGNORECASE)
    title = re.sub(r'\s*\(Official.*?\)\s*$', '', title, flags=re.IGNORECASE)
    title = re.sub(r'\s*\(Audio.*?\)\s*$', '', title, flags=re.IGNORECASE)
    title = re.sub(r'\s*\(Video.*?\)\s*$', '', title, flags=re.IGNORECASE)
    title = re.sub(r'\s*\[.*?\]\s*$', '', title, flags=re.IGNORECASE)
    title = title.strip()
    return title if title else None


class SystemPollingWorker(QThread):
    info_signal = pyqtSignal(object)

    def __init__(self, system):
        super().__init__()
        self.system = system
        self.running = True

    def run(self):
        while self.running:
            try:
                info = asyncio.run(self.system.get_now_playing_info())
                self.info_signal.emit(info)
            except Exception as e:
                logging.debug(f"Worker polling error: {e}")
            time.sleep(self.system.sync_interval / 1000.0)

    def stop(self):
        self.running = False
        self.wait()


class NowPlayingSystem(NowPlaying):
    def __init__(self, sync_interval=50, update_callback=None, offset=0, tracking_app=TRACKING_APP):
        super().__init__(sync_interval, update_callback)
        self.manager = asyncio.run(self.get_media_manager())
        self.tracking_app = tracking_app
        self.app_id = None
        self.session = None
        self.is_initialized = False
        self.offset = offset
        self._last_track_key = None
        self._last_thumb_bytes = None
        self.worker = SystemPollingWorker(self)
        self.worker.info_signal.connect(self.process_info)

    def start_loop(self):
        self.started = True
        self.worker.start()

    def update_check(self, old_playing_info, new_playing_info):
        if old_playing_info is None:
            return True
        if new_playing_info.is_playing != old_playing_info.is_playing:
            return True
        if new_playing_info.current_track != old_playing_info.current_track:
            return True
        if new_playing_info.last_updated_time != old_playing_info.last_updated_time: 
            # logging.info("Time Gap: %.9f"%(new_playing_info.last_updated_time - old_playing_info.last_updated_time))
            return True
        return False
    
    def track_check(self, old_playing_info, new_playing_info):
        if old_playing_info is None or new_playing_info is None:
            return True
        if old_playing_info.current_track == new_playing_info.current_track:
            if old_playing_info.current_track_id is not None:
                new_playing_info.current_track_id = old_playing_info.current_track_id
            return False
        return True

    def process_info(self, info):
        if not self.sync_mutex.tryLock(0):
            return
        try:
            if not self.is_initialized and (info is None or not info.is_playing):
                logging.info("WAITING FOR SPOTIFY")
                self.is_initialized = True
                self.playing_info = None
                if self.update_callback is not None:
                    self.update_callback(PlayingStatusTrigger.PAUSE)
                return
            if info is None and self.playing_info is not None:
                logging.info("SPOTIFY DOWN")
                self.is_initialized = True
                self.playing_info = None
                if self.update_callback is not None:
                    self.update_callback(PlayingStatusTrigger.PAUSE)
                return
            if info is None:
                return
            if not info.is_playing and (self.playing_info is not None and self.playing_info.is_playing):
                logging.info("PAUSING")
                self.playing_info.is_playing = False
                if self.update_callback is not None:
                    self.update_callback(PlayingStatusTrigger.PAUSE)
                return
            if info.is_playing and (self.playing_info is None or self.track_check(self.playing_info, info)):
                logging.info(f"NEW TRACK: {info.current_track}")
                if self.playing_info is not None:
                    self.playing_info.update(info)
                else:
                    self.playing_info = info
                if self.update_callback is not None and (self.playing_info.current_track_artist != "" or self.playing_info.current_track_title != ""):
                    self.update_callback(PlayingStatusTrigger.NEW_TRACK)
                return
            if info.is_playing and not self.playing_info.is_playing:
                logging.info("RESUMING")
                if self.playing_info is not None:
                    self.playing_info.update(info)
                else:
                    self.playing_info = info
                if self.update_callback is not None:
                    self.update_callback(PlayingStatusTrigger.RESUME)
            if info.is_playing and self.playing_info and self.update_check(self.playing_info, info):
                logging.info("SYNCING")
                if self.playing_info is not None:
                    self.playing_info.update(info)
                else:
                    self.playing_info = info
        finally:
            self.sync_mutex.unlock()

    def sync(self):
        logging.debug("TRY SYNC WITH SYSTEM")
        info = asyncio.run(self.get_now_playing_info())
        self.process_info(info)

    async def get_media_manager(self):
        return await MediaManager.request_async()

    async def get_app_id(self):
        logging.debug("GETTING APP ID")
        sessions = self.manager.get_sessions()
        sessions = [session.source_app_user_model_id for session in sessions]
        if not sessions:
            return None

        tracking_lower = self.tracking_app.lower()

        # Try exact match first (case-insensitive)
        exact_match = next((sid for sid in sessions if sid.lower() == tracking_lower), None)
        if exact_match:
            return exact_match

        # Try partial match (e.g. 'brave' in 'brave.exe' or 'Brave')
        partial_match = next((sid for sid in sessions if tracking_lower in sid.lower() or sid.lower() in tracking_lower), None)
        if partial_match:
            return partial_match

        return None

    async def get_now_playing_info(self):
        if self.app_id is None:
            logging.debug("SPOTIFY DOWN")
            self.app_id = await self.get_app_id()
        # logging.info("GETTING NOW PLAYING INFO")
        if self.session is None:  
            sessions = self.manager.get_sessions()
            self.session = next(
                filter(lambda s: s.source_app_user_model_id == self.app_id, sessions),
                None,
            )
        if self.session is not None:
            info_dict = dict()
            try:
                info = await self.session.try_get_media_properties_async()
            except Exception as e:
                logging.debug(e)
                self.session = None
                return None
            if info is not None:
                info_dict.update(
                    {
                        song_attr: info.__getattribute__(song_attr)
                        for song_attr in dir(info)
                        if not song_attr.startswith("_")
                    }
                )
            info = self.session.get_timeline_properties()
            if info is not None:
                info_dict.update(
                    {
                        song_attr: info.__getattribute__(song_attr)
                        for song_attr in dir(info)
                        if not song_attr.startswith("_")
                    }
                )
            info = self.session.get_playback_info()
            if info is not None:
                info_dict.update(
                    {
                        song_attr: info.__getattribute__(song_attr)
                        for song_attr in dir(info)
                        if not song_attr.startswith("_")
                    }
                )
            # logging.info(info_dict)
            # if self.playing_info and self.playing_info.current_begin_time is not None:
            #     logging.info("Progress: ", datetime.now() - datetime.fromtimestamp(self.playing_info.current_begin_time))
            if "playback_status" not in info_dict:
                return None
            track_title = _clean_track_title(info_dict.get("title"))
            track_artist = info_dict.get("artist")
            if track_artist:
                track_artist = track_artist.strip()

            thumb_bytes = None
            track_key = (track_artist, track_title)
            if track_key == self._last_track_key and self._last_thumb_bytes is not None:
                thumb_bytes = self._last_thumb_bytes
            elif "thumbnail" in info_dict and info_dict["thumbnail"] is not None:
                try:
                    thumb_stream = await info_dict["thumbnail"].open_read_async()
                    size = thumb_stream.size
                    if size > 0:
                        reader = DataReader(thumb_stream)
                        await reader.load_async(size)
                        buf = bytearray(size)
                        reader.read_bytes(buf)
                        thumb_bytes = bytes(buf)
                        reader.close()
                    thumb_stream.close()
                except Exception as e:
                    logging.debug(f"Failed to read SMTC thumbnail: {e}")
                self._last_track_key = track_key
                self._last_thumb_bytes = thumb_bytes

            return PlayingInfo(
                current_track=TrackInfo(
                    artist=track_artist,
                    id=info_dict["track_id"] if "track_id" in info_dict else None,
                    title=track_title,
                    length=(
                        (info_dict["max_seek_time"] / timedelta(milliseconds=1))
                        if "max_seek_time" in info_dict
                        else None
                    ),
                    thumbnail_bytes=thumb_bytes,
                ),
                # current_begin_time=(
                #     (datetime.timestamp(info_dict["last_updated_time"]) - info_dict["position"]/ timedelta(milliseconds=1) + self.offset)
                #     if "position" in info_dict
                #     else None
                # ),
                current_begin_time=(
                    ((info_dict["last_updated_time"] - info_dict["position"]).timestamp()*1000 + self.offset) if ("position" in info_dict and "last_updated_time" in info_dict) else None
                ),
                is_playing=(info_dict["playback_status"] == 4),
                last_updated_time=datetime.timestamp(info_dict["last_updated_time"]) if "last_updated_time" in info_dict else None,
            )
        return None
    
if __name__ == "__main__":
    from PyQt5.QtWidgets import QApplication
    import sys
    
    def callback(trigger):
        if trigger == PlayingStatusTrigger.PAUSE:
            logging.info("PAUSE")
        elif trigger == PlayingStatusTrigger.RESUME:
            logging.info("RESUME")
        elif trigger == PlayingStatusTrigger.NEW_TRACK:
            logging.info("NEW TRACK")
    
    app = QApplication(sys.argv)
    np = NowPlayingSystem(update_callback=callback, offset=100)
    np.start_loop()
    breakpoint()
    sys.exit(app.exec_())