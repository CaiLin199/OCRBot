# Use a base image with Python
FROM python:3.8-slim-buster

WORKDIR /app

# Copy requirements.txt first for better caching
COPY requirements.txt ./

# Install minimal required packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt --only-binary :all: \
    && rm -rf ~/.cache/pip \
    && rm -rf /usr/share/doc/* \
    && rm -rf /usr/share/man/*

# Copy the rest of the application
COPY . .

CMD ["python3", "main.py"]