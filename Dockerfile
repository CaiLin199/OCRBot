FROM python:3.8-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    libtesseract-dev \
    ffmpeg \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Command to run the bot
CMD ["python", "main.py"]