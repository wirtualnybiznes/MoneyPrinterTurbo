import json

from fastapi import Header, Path, Request
from pydantic import BaseModel, Field

from app.controllers import base
from app.controllers.v1.base import new_router
from app.models.exception import HttpException
from app.models.schema import BaseResponse
from app.services import billing
from app.utils import utils

router = new_router()


class CheckoutRequest(BaseModel):
    plan: str = Field(..., max_length=32)
    email: str = Field(default="", max_length=320)


class BillingResponse(BaseResponse):
    pass


@router.post(
    "/billing/checkout",
    response_model=BillingResponse,
    summary="Create a Stripe Checkout session for a subscription plan",
)
def create_checkout(request: Request, body: CheckoutRequest):
    request_id = base.get_task_id(request)
    if not billing.billing_enabled():
        raise HttpException(
            task_id=request_id,
            status_code=400,
            message=f"{request_id}: billing is not enabled on this server",
        )
    try:
        url = billing.create_checkout_session(body.plan, body.email)
    except ValueError as e:
        raise HttpException(
            task_id=request_id, status_code=400, message=f"{request_id}: {str(e)}"
        )
    return utils.get_response(200, {"checkout_url": url})


@router.post(
    "/billing/webhook",
    response_model=BillingResponse,
    summary="Stripe webhook endpoint (checkout completed, subscription deleted)",
)
async def stripe_webhook(
    request: Request, stripe_signature: str = Header(default="", alias="Stripe-Signature")
):
    request_id = base.get_task_id(request)
    raw_body = await request.body()
    if not billing.verify_webhook_signature(raw_body, stripe_signature):
        raise HttpException(
            task_id=request_id,
            status_code=400,
            message=f"{request_id}: invalid webhook signature",
        )
    event = json.loads(raw_body)
    license_key = billing.handle_webhook_event(event)
    return utils.get_response(200, {"license_key": license_key})


@router.get(
    "/billing/license/{license_key}",
    response_model=BillingResponse,
    summary="Check a license key's plan and status",
)
def get_license(request: Request, license_key: str = Path(...)):
    request_id = base.get_task_id(request)
    record = billing.licenses.get(license_key)
    if not record:
        raise HttpException(
            task_id=request_id,
            status_code=404,
            message=f"{request_id}: license not found",
        )
    return utils.get_response(
        200, {"plan": record["plan"], "status": record["status"]}
    )
