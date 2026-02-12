# Calv-a-lot - Copy-Trading Follower pour Cash-a-lot
FROM python:3.11-slim

# Install curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Créer le dossier data pour SQLite
RUN mkdir -p /app/data

# Run as non-root user (UID 1000 pour matcher l'utilisateur hôte sur le volume monté)
RUN groupadd -g 1000 appgroup && useradd -u 1000 -g appgroup -d /app appuser \
    && chown -R appuser:appgroup /app
USER appuser

EXPOSE 8080

HEALTHCHECK --interval=120s --timeout=5s --retries=3 --start-period=30s \
    CMD curl -f http://localhost:8080/health || exit 1

CMD ["gunicorn", "--config", "gunicorn.conf.py", "app:create_app()"]
