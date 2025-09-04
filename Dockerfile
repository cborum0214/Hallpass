# syntax=docker/dockerfile:1
FROM python:3.11-slim

# Install runtime deps (add curl for healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
  && rm -rf /var/lib/apt/lists/*

# Create app dir and a non-root user
WORKDIR /app
RUN useradd -m appuser

# Copy dependency file first to leverage cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app files
COPY . .

# Create data dir for SQLite file and make it writable
RUN mkdir -p /data && chown -R appuser:appuser /data && chown -R appuser:appuser /app

# Switch to non-root
USER appuser

# Environment (overridden by docker-compose .env at runtime)
ENV FLASK_ENV=production \
    DB_DIR=/data \
    DB_FILE=attendance.db \
    SESSION_MINUTES=20

# Expose port
EXPOSE 5000

# Healthcheck: ask the index page
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -fsS http://127.0.0.1:5000/ || exit 1

# Gunicorn entrypoint (module:variable = attendance_tracker:app)
CMD gunicorn -b 0.0.0.0:5000 --workers 3 --timeout 120 attendance_tracker:app
