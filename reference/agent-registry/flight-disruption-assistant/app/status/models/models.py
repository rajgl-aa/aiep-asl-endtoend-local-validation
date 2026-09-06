from pydantic import BaseModel


class Status(BaseModel):
    """Service health and metadata returned by GET /api/v1/status."""

    message: str = "ok"
    service: str = "aiep-agent-flight-disruption"
    version: str = "1.0.0"
    environment: str = "local"
    capabilities: list[str] = [
        "flight-disruption",
        "passenger-rebooking",
        "baggage-tracing",
        "customer-notification",
    ]
