FROM python:3.12-slim

# Runtime hygiene
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install deps first (better layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code
COPY src ./src
COPY spike ./spike
COPY config/.env.example ./config/.env.example

# Runtime dirs (also mounted as volumes in compose for persistence)
RUN mkdir -p data landers src/static/icons

EXPOSE 8000

# Config is injected via environment variables (docker-compose env_file),
# so no config/.env file is baked into the image.
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
