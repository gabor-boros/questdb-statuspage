FROM python:3.8-slim

ENV PYTHONUNBUFFERED 1
WORKDIR /app

RUN apt-get update && apt-get install -y gcc python3-dev libpq-dev
RUN pip install poetry

COPY poetry.lock /app/poetry.lock
COPY pyproject.toml /app/pyproject.toml

RUN poetry config virtualenvs.create false && poetry install --no-dev

COPY . /app

ENTRYPOINT [ "/app/scripts/entrypoint.sh" ]
