FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy all your code into the image
COPY . /app

# Default command (overridden by docker-compose)
CMD ["python", "AliceServer.py"]