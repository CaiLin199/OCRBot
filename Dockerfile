
FROM python:3.10-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install minimal required packages in a single layer
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libglib2.0-0 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir \
    pyrogram \
    tgcrypto \
    opencv-python-headless \
    numpy \
    easyocr \
    torch --index-url https://download.pytorch.org/whl/cpu \
    && python -c "import easyocr; easyocr.Reader(['ch_sim'])" \
    && rm -rf ~/.cache/pip

# Copy the rest of the application
COPY . .

# Create necessary directories
RUN mkdir -p /app/downloads /app/temp

# Set permissions
RUN chmod -R 755 /app

# Command to run the bot
CMD ["python3", "main.py"]