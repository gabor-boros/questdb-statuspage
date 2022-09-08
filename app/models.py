from datetime import datetime

from pydantic import BaseModel, Field


class Signal(BaseModel):
    """
    Signal model stands for the results of monitoring requests
    """

    url: str = Field(..., description="The monitored URL")
    http_status: int = Field(..., description="HTTP status code returned by upstream")
    available: bool = Field(..., description="Represents the service availability")
    received: datetime = Field(..., description="Timestamp when the signal received")
