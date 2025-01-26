FROM python:3.8-slim-buster AS build

# Install system dependencies, including FFmpeg and Git
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Final stage
FROM python:3.8-slim-buster

# Copy FFmpeg binaries from the build stage
COPY --from=build /usr/bin/ffmpeg /usr/bin/ffmpeg
COPY --from=build /usr/bin/ffprobe /usr/bin/ffprobe

# Copy Python dependencies from the build stage
COPY --from=build /usr/local/lib/python3.8/site-packages /usr/local/lib/python3.8/site-packages

WORKDIR /app
COPY . .

# Set the default command to run the bot
CMD ["python3", "main.py"]
