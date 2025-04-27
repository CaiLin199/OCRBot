# Use a base image with Python
FROM python:3.8-slim-buster

# Install git and aria2
RUN apt-get update && apt-get install -y git aria2

# Set the working directory to /app
WORKDIR /app

# Copy requirements.txt to the container
COPY requirements.txt requirements.txt

# Install the Python dependencies
RUN pip3 install -r requirements.txt

# Copy the rest of the application code
COPY . .

# Make aria2.bash executable
#RUN chmod +x aria2.bash

# Start aria2.bash (aria2c) and the bot
CMD python3 main.py