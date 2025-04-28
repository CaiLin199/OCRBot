# Use a base image with Python
FROM python:3.8-slim-buster

ENV PYTHONUNBUFFERED=1

WORKDIR /app

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

# Copy requirements.txt to the container
COPY requirements.txt requirements.txt

# Install the Python dependencies
RUN pip3 install -r requirements.txt

# Copy repo contents
COPY . .

CMD ["python3", "main.py"]
