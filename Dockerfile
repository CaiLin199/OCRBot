# Use Python slim image
FROM python:3.10-slim-bullseye

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    TESSDATA_PREFIX=/usr/share/tesseract-ocr/4.00/tessdata \
    PYTHONDONTWRITEBYTECODE=1

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libgl1-mesa-glx \
    libmagic1 \
    git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for better caching)
COPY requirements.txt .

# Install Python packages with specific configurations for EasyOCR
RUN pip install --no-cache-dir -r requirements.txt \
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