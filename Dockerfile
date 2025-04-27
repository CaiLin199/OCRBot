# Use Python slim image as base
FROM python:3.10-slim-bullseye

# Prevent interactive prompts
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=UTC

# Set working directory
WORKDIR /app

# Install system dependencies including git
RUN apt-get update && apt-get install -y \
    ffmpeg \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-chi-sim \
    libtesseract-dev \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set environment variables for optimization
ENV PYTHONPATH=/app \
    TESSDATA_PREFIX=/usr/share/tesseract-ocr/4.00/tessdata \
    OMP_NUM_THREADS=4 \
    PYTHONUNBUFFERED=1 \
    PYTESSERACT_CLEANUP=1 \
    OMP_THREAD_LIMIT=4

# Copy requirements first (better caching)
COPY requirements.txt .

# Install Python packages
RUN pip install --no-cache-dir -r requirements.txt \
    && pip cache purge

# Copy the rest of the application
COPY . .

# Run main.py
CMD ["python3", "main.py"]