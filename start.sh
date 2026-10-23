#!/bin/bash
set -e
echo "==> Starting Redis..."
redis-server --daemonize yes --port 6379 --save ""
echo "==> Waiting for Redis..."
sleep 2
redis-cli ping

echo "==> Running migrations..."
python manage.py migrate --noinput

echo "==> Starting Celery worker..."
celery -A backend worker --loglevel=info --pool=solo --concurrency=1 &

echo "==> Starting Gunicorn on port ${PORT :- 7860}..."
exec gunicorn backend.wsgi.application \
    --bind 0.0.0.0:${PORT :- 7860} \
    --workers 1 \
    --threads 4 \
    --timeout 180 \
    --access-logfile - \
    --error-logfile -