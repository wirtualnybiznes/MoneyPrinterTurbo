from typing import Any, List, Optional

from pydantic import BaseModel, Field

from app.models.schema import BaseResponse


class AutopilotChannel(BaseModel):
    """A fully automated 'faceless' content channel.

    The autopilot scheduler periodically picks a fresh topic for the
    channel's niche, generates a video through the regular task pipeline
    and (optionally) cross-posts it via the Upload-Post integration.
    """

    id: str = ""
    name: str
    # Niche the LLM uses to invent fresh topics, e.g. "stoic philosophy
    # motivation" or "mind-blowing space facts".
    niche: str
    language: str = ""
    enabled: bool = True
    # How often the channel produces content.
    interval_hours: float = Field(default=24.0, ge=0.25, le=720.0)
    videos_per_run: int = Field(default=1, ge=1, le=5)
    # Optional overrides merged into VideoParams (voice_name, video_aspect,
    # bgm_type, subtitle settings, ...). Keys must match VideoParams fields.
    video_params: dict = Field(default_factory=dict)

    # Runtime bookkeeping (managed by the scheduler).
    next_run_at: float = 0.0
    last_run_at: float = 0.0
    last_task_ids: List[str] = Field(default_factory=list)
    recent_topics: List[str] = Field(default_factory=list)
    total_videos: int = 0


class ChannelCreateRequest(BaseModel):
    name: str = Field(..., max_length=200)
    niche: str = Field(..., max_length=500)
    language: str = ""
    enabled: bool = True
    interval_hours: float = Field(default=24.0, ge=0.25, le=720.0)
    videos_per_run: int = Field(default=1, ge=1, le=5)
    video_params: dict = Field(default_factory=dict)


class ChannelUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, max_length=200)
    niche: Optional[str] = Field(default=None, max_length=500)
    language: Optional[str] = None
    enabled: Optional[bool] = None
    interval_hours: Optional[float] = Field(default=None, ge=0.25, le=720.0)
    videos_per_run: Optional[int] = Field(default=None, ge=1, le=5)
    video_params: Optional[dict] = None


class ChannelResponse(BaseResponse):
    class ChannelData(BaseModel):
        channel: AutopilotChannel

    data: Optional[Any] = None


class ChannelListResponse(BaseResponse):
    data: Optional[Any] = None


class AutopilotStatusResponse(BaseResponse):
    data: Optional[Any] = None
