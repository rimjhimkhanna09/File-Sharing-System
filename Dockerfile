FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gcc \
        postgresql-client \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create uploads directory
RUN mkdir -p /app/uploads

# Create gunicorn config
RUN echo "[program:fileshare]" > /etc/supervisor/conf.d/fileshare.conf \
    && echo "command=/usr/local/bin/gunicorn -w 4 -b 0.0.0.0:8000 -k uvicorn.workers.UvicornWorker main:app" >> /etc/supervisor/conf.d/fileshare.conf \
    && echo "directory=/app" >> /etc/supervisor/conf.d/fileshare.conf \
    && echo "autostart=true" >> /etc/supervisor/conf.d/fileshare.conf \
    && echo "autorestart=true" >> /etc/supervisor/conf.d/fileshare.conf \
    && echo "stderr_logfile=/var/log/fileshare.err.log" >> /etc/supervisor/conf.d/fileshare.conf \
    && echo "stdout_logfile=/var/log/fileshare.out.log" >> /etc/supervisor/conf.d/fileshare.conf

# Expose port 8000
EXPOSE 8000

# Run supervisor
CMD ["supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
