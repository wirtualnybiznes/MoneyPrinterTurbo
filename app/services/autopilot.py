"""Autopilot scheduler: hands-off content channels.

Turns MoneyPrinterTurbo into a passive content machine. Each
:class:`~app.models.autopilot.AutopilotChannel` describes a niche and a
cadence; a background thread wakes up periodically, asks the configured
LLM for a fresh topic in that niche, and submits a regular video task to
the existing task manager. With ``upload_post_auto_upload`` enabled the
finished videos are cross-posted to TikTok/Instagram automatically, so a
running instance keeps feeding channels without any human in the loop.

Channels are persisted as JSON under ``storage/autopilot`` so schedules
survive restarts.
"""

import json
import os
import threading
import time
from typing import Callable, Dict, List, Optional

from loguru import logger

from app.models.autopilot import AutopilotChannel
from app.models.schema import VideoParams
from app.services import llm
from app.services import state as sm
from app.utils import utils

# How many past topics we keep per channel to steer the LLM away from
# repeating itself.
_RECENT_TOPICS_LIMIT = 20
_TICK_SECONDS = 30


def generate_topic(niche: str, language: str = "", recent_topics: Optional[List[str]] = None) -> str:
    """Ask the LLM for one fresh, scroll-stopping video subject for a niche."""
    avoid = ""
    if recent_topics:
        topics = "\n".join(f"- {t}" for t in recent_topics)
        avoid = f"\nDo NOT reuse or closely paraphrase any of these already-covered topics:\n{topics}\n"
    language_hint = f"The topic must be written in {language}." if language else ""
    prompt = f"""# Role: Viral Short-Video Topic Generator

Generate exactly ONE concrete, curiosity-driven topic for a short faceless video in the niche: "{niche}".

## Constraints:
1. Return ONLY the topic itself: a single line of plain text, no quotes, no numbering, no explanations.
2. The topic must be specific enough to script a 30-60 second video (not just the niche name).
3. It should create curiosity or deliver a clear promise to the viewer.
{language_hint}{avoid}"""
    response = llm._generate_response(prompt=prompt)
    if response and not response.startswith("Error: "):
        topic = response.strip().strip('"').splitlines()[0].strip()
        if topic:
            return topic
    logger.warning(f"autopilot topic generation failed, falling back to niche: {niche}")
    return niche


class AutopilotScheduler:
    """Background scheduler that keeps autopilot channels producing videos.

    ``submit_task`` is injected by the API layer so the scheduler reuses the
    same concurrency-limited task manager as manual requests.
    """

    def __init__(self, submit_task: Callable[..., None]):
        self._submit_task = submit_task
        self._channels: Dict[str, AutopilotChannel] = {}
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._storage_file = os.path.join(
            utils.storage_dir("autopilot", create=True), "channels.json"
        )
        self._load()

    # ------------------------------------------------------------- storage

    def _load(self):
        if not os.path.isfile(self._storage_file):
            return
        try:
            with open(self._storage_file, "r", encoding="utf-8") as f:
                items = json.load(f)
            self._channels = {
                item["id"]: AutopilotChannel(**item) for item in items
            }
            logger.info(f"autopilot loaded {len(self._channels)} channel(s)")
        except Exception as e:
            logger.error(f"autopilot failed to load channels: {str(e)}")

    def _save(self):
        try:
            items = [c.model_dump() for c in self._channels.values()]
            with open(self._storage_file, "w", encoding="utf-8") as f:
                json.dump(items, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"autopilot failed to save channels: {str(e)}")

    # ------------------------------------------------------------ channels

    def list_channels(self) -> List[AutopilotChannel]:
        with self._lock:
            return list(self._channels.values())

    def get_channel(self, channel_id: str) -> Optional[AutopilotChannel]:
        with self._lock:
            return self._channels.get(channel_id)

    def add_channel(self, channel: AutopilotChannel) -> AutopilotChannel:
        with self._lock:
            channel.id = channel.id or utils.get_uuid()
            if channel.enabled and channel.next_run_at <= 0:
                # First run happens on the next tick so a new channel
                # produces its first video right away.
                channel.next_run_at = time.time()
            self._channels[channel.id] = channel
            self._save()
        logger.success(f"autopilot channel added: {channel.name} ({channel.id})")
        return channel

    def update_channel(self, channel_id: str, fields: dict) -> Optional[AutopilotChannel]:
        with self._lock:
            channel = self._channels.get(channel_id)
            if not channel:
                return None
            was_enabled = channel.enabled
            for key, value in fields.items():
                if value is not None and hasattr(channel, key):
                    setattr(channel, key, value)
            if channel.enabled and not was_enabled:
                channel.next_run_at = time.time()
            self._save()
            return channel

    def delete_channel(self, channel_id: str) -> bool:
        with self._lock:
            if channel_id not in self._channels:
                return False
            del self._channels[channel_id]
            self._save()
            return True

    # ----------------------------------------------------------- execution

    def run_channel_now(self, channel_id: str) -> Optional[List[str]]:
        channel = self.get_channel(channel_id)
        if not channel:
            return None
        return self._produce(channel)

    def _produce(self, channel: AutopilotChannel) -> List[str]:
        topic = generate_topic(channel.niche, channel.language, channel.recent_topics)
        logger.info(f"autopilot channel '{channel.name}' producing: {topic}")

        params_dict = dict(channel.video_params or {})
        params_dict["video_subject"] = topic
        if channel.language:
            params_dict.setdefault("video_language", channel.language)
        params_dict["video_count"] = min(channel.videos_per_run, 5)
        try:
            params = VideoParams(**params_dict)
        except Exception as e:
            logger.error(
                f"autopilot channel '{channel.name}' has invalid video_params: {str(e)}"
            )
            return []

        task_id = utils.get_uuid()
        sm.state.update_task(task_id)
        try:
            self._submit_task(task_id=task_id, params=params)
        except Exception as e:
            sm.state.delete_task(task_id)
            logger.error(
                f"autopilot channel '{channel.name}' failed to enqueue task: {str(e)}"
            )
            return []

        with self._lock:
            now = time.time()
            channel.last_run_at = now
            channel.next_run_at = now + channel.interval_hours * 3600
            channel.last_task_ids = (channel.last_task_ids + [task_id])[-10:]
            channel.recent_topics = (channel.recent_topics + [topic])[-_RECENT_TOPICS_LIMIT:]
            channel.total_videos += params.video_count
            self._save()
        return [task_id]

    # ----------------------------------------------------------- scheduler

    @property
    def running(self) -> bool:
        return self._running

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._loop, name="autopilot-scheduler", daemon=True
        )
        self._thread.start()
        logger.success("autopilot scheduler started")

    def stop(self):
        self._running = False
        logger.info("autopilot scheduler stopped")

    def _loop(self):
        while self._running:
            try:
                now = time.time()
                due = [
                    c
                    for c in self.list_channels()
                    if c.enabled and 0 < c.next_run_at <= now
                ]
                for channel in due:
                    self._produce(channel)
            except Exception as e:
                logger.error(f"autopilot scheduler tick failed: {str(e)}")
            time.sleep(_TICK_SECONDS)
