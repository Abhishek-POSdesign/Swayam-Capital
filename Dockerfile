# Multi-stage Dockerfile for Swayam Capital (Cloud Run)
# Stage 1: Build the Vite frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /app/web
COPY web/package*.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

# Stage 2: Python runtime + FastAPI backend serving static frontend
FROM python:3.11-slim
WORKDIR /app

# System dependencies for scientific packages (py_vollib, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt pyproject.toml README.md ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy source and install package in editable/local mode
COPY src/ ./src/
RUN pip install --no-cache-dir -e .

# Reference data the app reads at runtime: the NSE holiday calendar (expiry and
# next-trading-day maths) and the NIFTY 50 constituent list (market breadth).
# `data/` is otherwise a local cache and is not copied.
COPY data/nse_holidays_2026.json data/nifty50_constituents.json ./data/

# The baseline schema, needed by the nightly backup job, which refuses to write
# a schema-less backup. 118 KB for the whole folder; the image does not notice.
COPY migrations/ ./migrations/

# Copy built frontend assets from Stage 1
COPY --from=frontend-builder /app/web/dist ./web/dist

# Cloud Run PORT configuration
ENV PORT=8080
ENV PYTHONUNBUFFERED=1
EXPOSE 8080

# Production ASGI server with Gunicorn + Uvicorn workers
CMD exec gunicorn -k uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:${PORT} \
    --workers 2 --timeout 60 --graceful-timeout 30 \
    swayam.api.main:app
