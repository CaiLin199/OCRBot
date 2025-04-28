FROM python:3.10-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install minimal required packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir -r requirements.txt \
    --only-binary :all: \
    && rm -rf ~/.cache/pip \
    && rm -rf /usr/share/doc/* \
    && rm -rf /usr/share/man/*

# Copy repo contents
COPY . .

CMD ["python3", "main.py"]