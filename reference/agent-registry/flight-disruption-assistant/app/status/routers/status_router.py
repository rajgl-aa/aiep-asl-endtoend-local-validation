from typing import Annotated

from fastapi import APIRouter, Depends

from app.status.models.models import Status
from app.status.services.status_service import StatusService

router = APIRouter()


def get_status_service() -> StatusService:
    return StatusService()


@router.get("/status")
async def status(
    service: Annotated[StatusService, Depends(get_status_service)],
) -> Status:
    return service.get_status()
