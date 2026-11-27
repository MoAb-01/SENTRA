FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Copy shared protocol package and core gateway
COPY packages/protocol-py /app/packages/protocol-py
COPY core /app/core

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir /app/packages/protocol-py /app/core

EXPOSE 8000

CMD ["uvicorn", "sentra_core.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--ws-per-message-deflate", "false"]
