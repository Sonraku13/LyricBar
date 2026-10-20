from datetime import datetime, timedelta
import json
import logging
import subprocess
import asyncio
from winsdk.windows.media.control import (
    GlobalSystemMediaTransportControlsSessionManager as MediaManager,
)

from .nowplaying import NowPlaying
from ..globalvariables import TRACKING_APP
from ..utils.dataclasses import PlayingInfo, PlayingStatusTrigger, TrackInfo



class NowPlayingSystem(NowPlaying):
    def __init__(self, sync_interval=50, update_callback=None, offset=0, tracking_app=TRACKING_APP):
        super().__init__(sync_interval, update_callback)
        self.manager = asyncio.run(self.get_media_manager())
        self.tracking_app = tracking_app
        self.app_id = None
        self.session = None
        self.is_initialized = False
        self.offset = offset

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

    def sync(self):
        logging.debug("TRY SYNC WITH SYSTEM")
        if not self.sync_mutex.tryLock(0):
            logging.debug("SYNCING SKIPPED")
            return
        info = asyncio.run(self.get_now_playing_info())
        
        if not self.is_initialized and (info is None or not info.is_playing):
            logging.info("WAITING FOR SPOTIFY")
            self.is_initialized = True
            self.playing_info = None
            if self.update_callback is not None:
                self.update_callback(PlayingStatusTrigger.PAUSE)
            self.sync_mutex.unlock()
            return
        if info is None and self.playing_info is not None:
            logging.info("SPOTIFY DOWN")
            self.is_initialized = True
            self.playing_info = None
            if self.update_callback is not None:
                self.update_callback(PlayingStatusTrigger.PAUSE)
            self.sync_mutex.unlock()
            return
        if info is None:
            self.sync_mutex.unlock()
            return
        if not info.is_playing and (self.playing_info is not None and self.playing_info.is_playing):
            logging.info("PAUSING")
            self.playing_info.is_playing = False
            if self.update_callback is not None:
                self.update_callback(PlayingStatusTrigger.PAUSE)
            self.sync_mutex.unlock()
            return
        if info.is_playing and (self.playing_info is None or self.track_check(self.playing_info, info)):
            logging.info("NEW TRACK: ", info.current_track)
            if self.playing_info is not None:
                self.playing_info.update(info)
            else:
                self.playing_info = info
            if self.update_callback is not None and (self.playing_info.current_track_artist != "" or self.playing_info.current_track_title != ""):
                self.update_callback(PlayingStatusTrigger.NEW_TRACK)
            self.sync_mutex.unlock()
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
        self.sync_mutex.unlock()

    async def get_media_manager(self):
        return await MediaManager.request_async()

    async def get_app_id(self):
        logging.debug("GETTING APP ID")
        try:
            sessions = self.manager.get_sessions()
        except Exception as e:
            logging.debug(f"Error getting sessions: {e}")
            return None

        candidate_ids = [s.source_app_user_model_id for s in sessions if s and s.source_app_user_model_id]
        
        # 1. Direct match on active media session App ID
        target_lower = self.tracking_app.lower()
        for app_id in candidate_ids:
            if target_lower in app_id.lower():
                return app_id

        # 2. Check PowerShell Get-StartApps if direct match not found
        try:
            amuids = subprocess.check_output(
                ["powershell.exe", "Get-StartApps | ConvertTo-Json"],
                shell=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            amuids = json.loads(amuids.decode("utf-8", errors="ignore").replace("\r\n", "\n"))
            if isinstance(amuids, dict):
                amuids = [amuids]
            rets = []
            for app in amuids:
                app_name = app.get("Name", "")
                app_target = app.get("AppID", "").split("\\")[-1]
                if target_lower in app_target.lower() or target_lower in app_name.lower():
                    # check if this app is currently an active session
                    for sess_id in candidate_ids:
                        if app_target.lower() in sess_id.lower():
                            rets.append(sess_id)
            if rets:
                return min(rets, key=len)
        except Exception as e:
            logging.debug(f"Failed to query Get-StartApps: {e}")

        # 3. Fallback: if tracking_app is empty or 'any', or exactly one session is active
        if target_lower in ["any", "*", "all", ""] and candidate_ids:
            return candidate_ids[0]

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
            # If session stale/closed, reset app_id to search again
            if self.session is None:
                self.app_id = None
                return None
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
            return PlayingInfo(
                current_track=TrackInfo(
                    artist=info_dict["artist"] if "artist" in info_dict else None,
                    id=info_dict["track_id"] if "track_id" in info_dict else None,
                    title=info_dict["title"] if "title" in info_dict else None,
                    length=(
                        (info_dict["max_seek_time"] / timedelta(milliseconds=1))
                        if "max_seek_time" in info_dict
                        else None
                    ),
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