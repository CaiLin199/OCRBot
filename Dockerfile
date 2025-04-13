# Use minimal base image
FROM python:3.11-slim-bullseye

# Set working directory
WORKDIR /app

# Install dependencies in one layer, clean up thoroughly
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/* /var/cache/apt/* /tmp/*

# Copy requirements first for caching
COPY requirements.txt .

# Install Python dependencies, avoid cache
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Set environment variables for efficiency
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Run bot
CMD ["python", "main.py"]