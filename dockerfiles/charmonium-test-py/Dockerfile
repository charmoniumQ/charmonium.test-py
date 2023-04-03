FROM python:3.11-buster

RUN pip install --no-cache-dir poetry

COPY pyproject.toml .
COPY poetry.lock .

RUN poetry install --no-root

COPY charmonium .
