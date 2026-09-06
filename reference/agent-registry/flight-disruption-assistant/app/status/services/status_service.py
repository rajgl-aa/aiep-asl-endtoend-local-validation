from app.status.models.models import Status
from app.config import get_app_settings
from app.core.otel_logger import get_logger

logger = get_logger(__name__)


class StatusService:
    """Builds the service status/metadata response."""

    def get_status(self) -> Status:
        logger.info("Getting Status......")
        settings = get_app_settings()
        status = Status(
            message="ok",
            service=settings.app_title,
            version=settings.app_version,
            environment=settings.environment,
        )
        logger.info("Status Retrieved! \u2705")
        return status
