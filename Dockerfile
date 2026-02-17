FROM python:3.12-slim

# Metadata
LABEL maintainer="critical-minerals-agent"
LABEL description="Critical Minerals Signal Hunter — multi-agent pipeline"

# Prevent Python from buffering stdout/stderr
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create data directory for SQLite
RUN mkdir -p /app/data

# Expose FastAPI port
EXPOSE 8000

# Default: run the FastAPI server
# Override with docker run ... python run_pipeline.py for one-shot pipeline
CMD ["uvicorn", "src.api:app", "--host", "0.0.0.0", "--port", "8000"]
