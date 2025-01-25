FROM python:3.8-slim-buster AS build

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Final stage
FROM python:3.8-slim-buster

WORKDIR /app
COPY --from=build /usr/local/lib/python3.8/site-packages /usr/local/lib/python3.8/site-packages
COPY . .

CMD ["python3", "main.py"]
