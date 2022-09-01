from collections import defaultdict
from typing import List

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.db import pool
from app.models import Signal
from app.settings import settings


class SignalResponse(BaseModel):
    """
    Indicate the structure of the signals API response.
    """

    url: str
    records: List[Signal]


app = FastAPI(
    title="Status Page",
    description="This service gives back the status of the configured URL.",
    version="0.1.0",
    debug=settings.debug,
    docs_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get(path="/signals", response_model=List[SignalResponse], tags=["Monitoring"])
async def get_signals(limit: int = 60):
    """
    Return the stored monitoring results.

    The returned signals will be sorted by `received` timestamp in a decreasing
    order, limited to `50` records if `limit` not set.
    """

    query = f"""
    SELECT 
        url,
        http_status,
        available,
        received
        FROM signals WHERE url = '{settings.website_url}' ORDER BY received DESC LIMIT {limit};
    """

    signals = defaultdict(list)

    with pool.connection() as conn:
        for result in conn.execute(query):
            signal = Signal(
                url=result[0],
                http_status=result[1],
                available=result[2],
                received=result[3],
            )

            signals[signal.url].append(signal)

    return [
        SignalResponse(url=url, records=list(reversed(records)))
        for url, records in signals.items()
    ]
