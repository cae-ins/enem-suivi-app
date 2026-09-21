FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /opt/enem
COPY web/backend/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY enem_core ./enem_core
COPY modules ./modules
COPY web/backend ./web/backend
RUN useradd --create-home --uid 10001 enem
USER enem
ENV PYTHONPATH=/opt/enem

CMD ["sh", "-c", "python -m web.backend.manage migrate && gunicorn web.backend.config.wsgi:application --bind 0.0.0.0:8000 --workers 2 --timeout 300"]
