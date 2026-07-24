FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app

# Install system dependencies (useful for building python extensions if needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy and install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Run the web service on container startup.
# Cloud Run automatically sets the PORT environment variable.
CMD exec uvicorn main:app --host 0.0.0.0 --port $PORT
