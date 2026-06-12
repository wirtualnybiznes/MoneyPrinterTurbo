from fastapi import Header, Path, Request
from loguru import logger

from app.config import config
from app.controllers import base
from app.controllers.v1.base import new_router
from app.controllers.v1.video import task_manager
from app.models.autopilot import (
    AutopilotChannel,
    AutopilotStatusResponse,
    ChannelCreateRequest,
    ChannelListResponse,
    ChannelResponse,
    ChannelUpdateRequest,
)
from app.models.exception import HttpException
from app.services import billing
from app.services import task as tm
from app.services.autopilot import AutopilotScheduler
from app.utils import utils

router = new_router()


def _submit_video_task(task_id: str, params):
    task_manager.add_task(tm.start, task_id=task_id, params=params, stop_at="video")


scheduler = AutopilotScheduler(submit_task=_submit_video_task)

if config.app.get("autopilot_enabled", False):
    scheduler.start()


@router.post(
    "/autopilot/channels",
    response_model=ChannelResponse,
    summary="Create an autopilot channel (scheduled hands-off video production)",
)
def create_channel(
    request: Request,
    body: ChannelCreateRequest,
    x_license_key: str = Header(default="", alias="X-License-Key"),
):
    request_id = base.get_task_id(request)
    try:
        quota = billing.channel_quota(x_license_key)
    except PermissionError as e:
        raise HttpException(
            task_id=request_id, status_code=402, message=f"{request_id}: {str(e)}"
        )
    if quota and len(scheduler.list_channels()) >= quota:
        raise HttpException(
            task_id=request_id,
            status_code=402,
            message=f"{request_id}: plan limit reached ({quota} channels) — upgrade your plan",
        )
    channel = scheduler.add_channel(AutopilotChannel(**body.model_dump()))
    if not scheduler.running and config.app.get("autopilot_enabled", False):
        scheduler.start()
    return utils.get_response(200, {"channel": channel.model_dump()})


@router.get(
    "/autopilot/channels",
    response_model=ChannelListResponse,
    summary="List all autopilot channels",
)
def list_channels(request: Request):
    channels = [c.model_dump() for c in scheduler.list_channels()]
    return utils.get_response(200, {"channels": channels, "total": len(channels)})


@router.get(
    "/autopilot/channels/{channel_id}",
    response_model=ChannelResponse,
    summary="Get an autopilot channel",
)
def get_channel(request: Request, channel_id: str = Path(..., description="Channel ID")):
    channel = scheduler.get_channel(channel_id)
    if not channel:
        request_id = base.get_task_id(request)
        raise HttpException(
            task_id=channel_id,
            status_code=404,
            message=f"{request_id}: channel not found",
        )
    return utils.get_response(200, {"channel": channel.model_dump()})


@router.put(
    "/autopilot/channels/{channel_id}",
    response_model=ChannelResponse,
    summary="Update an autopilot channel",
)
def update_channel(
    request: Request,
    body: ChannelUpdateRequest,
    channel_id: str = Path(..., description="Channel ID"),
):
    channel = scheduler.update_channel(channel_id, body.model_dump(exclude_none=True))
    if not channel:
        request_id = base.get_task_id(request)
        raise HttpException(
            task_id=channel_id,
            status_code=404,
            message=f"{request_id}: channel not found",
        )
    return utils.get_response(200, {"channel": channel.model_dump()})


@router.delete(
    "/autopilot/channels/{channel_id}",
    response_model=ChannelResponse,
    summary="Delete an autopilot channel",
)
def delete_channel(request: Request, channel_id: str = Path(..., description="Channel ID")):
    if not scheduler.delete_channel(channel_id):
        request_id = base.get_task_id(request)
        raise HttpException(
            task_id=channel_id,
            status_code=404,
            message=f"{request_id}: channel not found",
        )
    logger.success(f"autopilot channel deleted: {channel_id}")
    return utils.get_response(200)


@router.post(
    "/autopilot/channels/{channel_id}/run",
    response_model=ChannelResponse,
    summary="Trigger an autopilot channel immediately",
)
def run_channel(request: Request, channel_id: str = Path(..., description="Channel ID")):
    task_ids = scheduler.run_channel_now(channel_id)
    if task_ids is None:
        request_id = base.get_task_id(request)
        raise HttpException(
            task_id=channel_id,
            status_code=404,
            message=f"{request_id}: channel not found",
        )
    return utils.get_response(200, {"task_ids": task_ids})


@router.get(
    "/autopilot/status",
    response_model=AutopilotStatusResponse,
    summary="Get autopilot scheduler status",
)
def autopilot_status(request: Request):
    channels = scheduler.list_channels()
    return utils.get_response(
        200,
        {
            "running": scheduler.running,
            "channels": len(channels),
            "enabled_channels": sum(1 for c in channels if c.enabled),
            "total_videos": sum(c.total_videos for c in channels),
        },
    )


@router.post(
    "/autopilot/start",
    response_model=AutopilotStatusResponse,
    summary="Start the autopilot scheduler",
)
def autopilot_start(request: Request):
    scheduler.start()
    return utils.get_response(200, {"running": scheduler.running})


@router.post(
    "/autopilot/stop",
    response_model=AutopilotStatusResponse,
    summary="Stop the autopilot scheduler",
)
def autopilot_stop(request: Request):
    scheduler.stop()
    return utils.get_response(200, {"running": scheduler.running})
