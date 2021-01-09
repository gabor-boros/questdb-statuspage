from datetime import datetime

from pydantic import BaseModel, Schema


class Signal(BaseModel):
    """
    Signal model stands for the results of monitoring requests
    """

    url: str = Schema(..., description="The monitored URL")
    http_status: int = Schema(..., description="HTTP status code returned by upstream")
    available: bool = Schema(..., description="Represents the service availability")
    received: datetime = Schema(..., description="Timestamp when the signal received")
