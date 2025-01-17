FROM python:3.8-slim-buster

# Install FFmpeg
RUN apt-get update && apt-get install -y ffmpeg && apt-get clean

WORKDIR /app

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy all project files
COPY . .

# Set the default command to run the bot
CMD ["python3", "main.py"]
