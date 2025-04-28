# Use a base image with Python
FROM python:3.8-slim-buster

ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir \
    pyrogram \
    tgcrypto \
    opencv-python-headless \
    numpy \
    easyocr \
    aiohttp \
    --only-binary :all: \
    && rm -rf ~/.cache/pip \
    && rm -rf /usr/share/doc/* \
    && rm -rf /usr/share/man/*

# Copy entire repo since it's small
COPY . .

CMD ["python3", "main.py"]