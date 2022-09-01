from datetime import datetime

import requests

from app.celery import celery_app
from app.db import pool
from app.models import Signal
from app.settings import settings


@celery_app.task
def monitor():
    """
    Send request to the monitored URL to check its availability.

    For monitoring the URL we will use HTTP HEAD requests to reduce the round
    trip time of request-response, as we don't need to retrieve the static
    resources served by the website.
    """

    try:
        response = requests.head(settings.website_url)
    except Exception as exc:
        query = f"""
            INSERT INTO signals(received,url,http_status,available)
            VALUES(systimestamp(), '{settings.website_url}', -1, False);
            """

        with pool.connection() as conn:
            conn.execute(query)

        raise exc

    signal = Signal(
        url=settings.website_url,
        http_status=response.status_code,
        received=datetime.now(),
        available=response.status_code >= 200 and response.status_code < 400,
    )

    query = f"""
    INSERT INTO signals(received,url,http_status,available)
    VALUES(systimestamp(), '{signal.url}', {signal.http_status}, {signal.available});
    """

    with pool.connection() as conn:
        conn.execute(query)
