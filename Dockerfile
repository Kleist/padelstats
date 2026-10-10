FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 POETRY_VIRTUALENVS_CREATE=false
WORKDIR /srv

RUN pip install "poetry>=2.0,<3.0"
COPY pyproject.toml poetry.lock ./
RUN poetry install --no-root --only main

COPY alembic.ini ./
COPY migrations ./migrations
COPY app ./app

ARG GIT_SHA=dev
ENV GIT_SHA=$GIT_SHA

EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers", "--forwarded-allow-ips", "*"]
