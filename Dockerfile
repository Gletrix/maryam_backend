# Backend Dockerfile for Portfolio WebApp
# Deploy to Railway: Set DATABASE_URL, OWNER_PASSWORD, SECRET_KEY, FRONTEND_ORIGIN, MEDIA_STORAGE

FROM python:3.11-slim

# Install system dependencies including ffmpeg for video processing
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libmagic1 \
    libmagic-dev \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Create media directories
RUN mkdir -p /media/thumbnails

# Copy application code
COPY . .

# Expose port (Railway sets PORT env var)
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Start command - Railway provides PORT env var
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
